"""CanvasEndpoint CRUD router with tree validation and canvas-aware field discovery.

Routes mounted at /api/v1/connectors/{connector_id}/canvases/{canvas_id}/endpoints.
Provides cycle detection (D-11), orphan detection (D-12), and canvas-aware field
discovery that walks the endpoint tree and returns merged parent+child fields.
"""

import uuid as _uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import require_role
from app.core.errors import make_error
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.schemas.canvas_endpoint import (
    CanvasEndpointCreate,
    CanvasEndpointUpdate,
    CanvasEndpointResponse,
)
from app.schemas.field_mapping import DiscoverResponse
from app.schemas.run_history import DryRunResponse
from app.services import source_client as _source_client
from app.services.template_resolver import resolve_path, TemplateResolutionError
from app.services.fan_out_executor import execute_tree, _build_tree, _merge_parent_context
from app.services.ingestion_service import _build_mapping_rules
from app.services.transform_engine import apply_mappings
from app.services.source_client import fetch_all_pages
from app.services.field_discovery import merge_fields_across_records
from app.services.connector_service import HTTPX_TIMEOUT, _build_headers
from app.services.exclusion_filter import apply_exclusion_rules
from app.schemas.exclusion_rule import ExclusionRule
from pydantic import TypeAdapter

router = APIRouter(tags=["canvas-endpoints"])

BASE = "/connectors/{connector_id}/canvases/{canvas_id}/endpoints"
BASE_CANVAS = "/connectors/{connector_id}/canvases/{canvas_id}"
DRY_RUN_CAP = 50

DISCOVERY_SAMPLE_SIZE = 3  # D-11: 3 parent records sampled for discovery


def detect_cycle(
    canvas_endpoints: list[CanvasEndpoint],
    new_ref_id: str,
    new_parent_id: str,
) -> bool:
    """Walk up parent chain from new_ref_id using the proposed parent change.

    If we revisit a node, a cycle exists. Returns True if cycle detected.
    """
    parent_map = {ce.id: ce.parent_ref_id for ce in canvas_endpoints}
    parent_map[new_ref_id] = new_parent_id
    visited: set[str] = set()
    current: str | None = new_ref_id
    while current is not None:
        if current in visited:
            return True
        visited.add(current)
        current = parent_map.get(current)
    return False


def find_orphans(canvas_endpoints: list[CanvasEndpoint]) -> list[str]:
    """Find canvas-endpoint IDs that are disconnected from any tree root.

    A root is a canvas-endpoint with parent_ref_id=None.
    An orphan is a node not reachable from any root via parent chain traversal.
    """
    if not canvas_endpoints:
        return []

    # Build child map: parent_id -> list of child ids
    child_map: dict[str | None, list[str]] = {}
    all_ids: set[str] = set()
    for ce in canvas_endpoints:
        all_ids.add(ce.id)
        child_map.setdefault(ce.parent_ref_id, []).append(ce.id)

    # BFS from all roots (parent_ref_id=None)
    reachable: set[str] = set()
    roots = child_map.get(None, [])
    queue = list(roots)
    while queue:
        node = queue.pop(0)
        if node in reachable:
            continue
        reachable.add(node)
        for child in child_map.get(node, []):
            queue.append(child)

    return sorted(all_ids - reachable)


def _get_canvas_or_404(
    db: Session, connector_id: str, canvas_id: str
) -> Canvas:
    """Fetch canvas scoped to connector, raise 404 if not found."""
    canvas = (
        db.query(Canvas)
        .filter_by(id=canvas_id, connector_id=connector_id)
        .first()
    )
    if not canvas:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_NOT_FOUND",
                "Canvas not found",
                {"canvas_id": canvas_id},
            ),
        )
    return canvas


@router.get(BASE + "/validate")
def validate_canvas_tree(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Validate the endpoint tree for a canvas.

    Returns whether the tree is valid (exactly 1 root, no orphans).
    """
    _get_canvas_or_404(db, connector_id, canvas_id)
    refs = (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .all()
    )
    roots = [ce for ce in refs if ce.parent_ref_id is None]
    orphans = find_orphans(refs)
    return {
        "valid": len(roots) == 1 and len(orphans) == 0,
        "orphaned_refs": orphans,
        "root_count": len(roots),
    }


@router.get(BASE + "/{ref_id}/fields/discover", response_model=DiscoverResponse)
async def discover_canvas_endpoint_fields(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Discover fields for a canvas endpoint, including merged _parent.* fields.

    Per D-08/D-09/D-10: Walks up the canvas tree to find ancestors,
    fetches root records, traverses down sampling DISCOVERY_SAMPLE_SIZE
    parent records per level, merges child records with _parent.* prefix,
    and returns the unified field list.
    """
    import logging
    _log = logging.getLogger("canvas_discovery")
    canvas = _get_canvas_or_404(db, connector_id, canvas_id)

    # Load connector
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {}),
        )

    # Load target canvas-endpoint
    target_ce = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not target_ce:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )

    # Load ALL canvas-endpoints for this canvas
    all_ces = db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).all()
    ce_map = {ce.id: ce for ce in all_ces}

    # Load connector endpoints for path and variable_extractions
    endpoint_ids = list({ce.endpoint_id for ce in all_ces})
    conn_endpoints = db.query(ConnectorEndpoint).filter(ConnectorEndpoint.id.in_(endpoint_ids)).all()
    ep_map = {ep.id: ep for ep in conn_endpoints}

    # Walk UP from target to find ancestor chain (ordered root -> ... -> target)
    chain: list[CanvasEndpoint] = []
    current = target_ce
    while current is not None:
        chain.append(current)
        if current.parent_ref_id is None:
            break
        current = ce_map.get(current.parent_ref_id)
    chain.reverse()  # Now ordered: root -> ... -> target

    _log.debug("DISCOVERY chain: %d levels", len(chain))
    for i, ce in enumerate(chain):
        ep = ep_map.get(ce.endpoint_id)
        _log.debug("  Level %d: ce_id=%s ep_path=%s var_extractions=%s data_root=%s parent_ref=%s",
                  i, ce.id, ep.path if ep else "N/A", ce.variable_extractions, ep.data_root if ep else "N/A", ce.parent_ref_id)

    if not chain:
        return DiscoverResponse(fields=[], record_count=0)

    # If target is the root (no parent), use flat discovery
    root_ce = chain[0]
    root_ep = ep_map.get(root_ce.endpoint_id)
    if not root_ep:
        raise HTTPException(
            status_code=404,
            detail=make_error("ENDPOINT_NOT_FOUND", "Root connector endpoint not found", {}),
        )

    headers = _build_headers(connector)
    root_url = connector.base_url.rstrip("/") + "/" + root_ep.path.lstrip("/")

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        # Fetch root records
        root_fetch = await _source_client._fetch_with_retries(
            client, root_url, headers, None, retry_limit=1,
        )
        if root_fetch.response is None:
            raise HTTPException(
                status_code=502,
                detail=make_error("SOURCE_UNREACHABLE", "Root endpoint did not respond", {}),
            )

        root_payload = root_fetch.response.json()
        _log.debug("ROOT fetch status=%s payload_type=%s payload_keys=%s",
                  root_fetch.response.status_code, type(root_payload).__name__,
                  list(root_payload.keys()) if isinstance(root_payload, dict) else "N/A")
        root_records = _source_client._extract_records_with_root(root_payload, root_ep.data_root)
        _log.debug("ROOT extracted %d records (data_root=%s)", len(root_records), root_ep.data_root)
        if not root_records and isinstance(root_payload, dict):
            root_records = [root_payload]

        if not root_records:
            _log.debug("ROOT: no records, returning empty")
            return DiscoverResponse(fields=[], record_count=0)

        # If target IS the root, return flat discovery
        if len(chain) == 1:
            raw_fields = merge_fields_across_records(root_records)
            fields = [{"path": f["path"], "type": f["type"], "sample_value": f["sample_value"]} for f in raw_fields]
            return DiscoverResponse(fields=fields, record_count=len(root_records))

        # Traverse DOWN through chain, sampling DISCOVERY_SAMPLE_SIZE records per level
        # Start with root records as parent records
        sampled_parents = root_records[:DISCOVERY_SAMPLE_SIZE]  # D-11
        parent_context: dict = {}
        all_merged_child_records: list[dict] = []

        for level_idx in range(1, len(chain)):
            current_ce = chain[level_idx]
            current_ep = ep_map.get(current_ce.endpoint_id)
            if not current_ep:
                break

            child_records_this_level: list[dict] = []

            _log.debug("LEVEL %d: processing %d parent samples", level_idx, len(sampled_parents))

            for pi, parent_record in enumerate(sampled_parents):
                _log.debug("  PARENT %d/%d keys=%s", pi, len(sampled_parents), list(parent_record.keys())[:10])
                # Build ancestor context for merging
                current_ancestor = _merge_parent_context(parent_record, parent_context)

                # Resolve child URL template — resolve_path auto-resolves
                # ancestor variables via _parent.* keys in the merged record
                try:
                    resolved = resolve_path(
                        current_ep.path,
                        parent_record,
                        current_ce.variable_extractions or {},
                    )
                    _log.debug("  RESOLVED path=%s", resolved)
                except TemplateResolutionError as te:
                    _log.debug("  TEMPLATE ERROR: %s", te)
                    continue  # Skip this parent sample, try others

                child_url = connector.base_url.rstrip("/") + "/" + resolved.lstrip("/")

                # Fetch child records
                try:
                    child_fetch = await _source_client._fetch_with_retries(
                        client, child_url, headers, None, retry_limit=1,
                    )
                except Exception as exc:
                    _log.debug("  FETCH EXCEPTION: %s", exc)
                    continue  # Skip this parent sample

                if child_fetch.response is None:
                    _log.debug("  FETCH returned None (source unreachable)")
                    continue

                _log.debug("  FETCH status=%s", child_fetch.response.status_code)
                child_payload = child_fetch.response.json()
                _log.debug("  CHILD payload_type=%s keys=%s",
                          type(child_payload).__name__,
                          list(child_payload.keys()) if isinstance(child_payload, dict) else "N/A")
                child_recs = _source_client._extract_records_with_root(child_payload, current_ep.data_root)
                _log.debug("  CHILD extracted %d records (data_root=%s)", len(child_recs), current_ep.data_root)
                if not child_recs and isinstance(child_payload, dict):
                    child_recs = [child_payload]
                    _log.debug("  CHILD fallback: using payload as single record")

                # Merge with _parent.* prefix (D-09)
                for child_rec in child_recs:
                    merged = _merge_parent_context(child_rec, current_ancestor)
                    child_records_this_level.append(merged)

            _log.debug("LEVEL %d: collected %d child records", level_idx, len(child_records_this_level))
            if not child_records_this_level:
                # All parent samples failed at this level
                _log.debug("LEVEL %d: ALL parent samples failed, returning empty", level_idx)
                return DiscoverResponse(fields=[], record_count=0)

            # If this is the target level, collect for field discovery
            if level_idx == len(chain) - 1:
                all_merged_child_records = child_records_this_level
            else:
                # Intermediate level: these become the next level's parents
                sampled_parents = child_records_this_level[:DISCOVERY_SAMPLE_SIZE]
                # Update parent_context for next level
                parent_context = _merge_parent_context(sampled_parents[0], parent_context) if sampled_parents else {}

    # Run merge_fields_across_records on all collected merged child records
    if not all_merged_child_records:
        return DiscoverResponse(fields=[], record_count=0)

    raw_fields = merge_fields_across_records(all_merged_child_records)
    fields = [{"path": f["path"], "type": f["type"], "sample_value": f["sample_value"]} for f in raw_fields]
    return DiscoverResponse(fields=fields, record_count=len(all_merged_child_records))


@router.post(BASE_CANVAS + "/dry-run", response_model=DryRunResponse)
async def dry_run_canvas(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Execute canvas chain without Qualys submission. Returns mapped records capped at 50.

    Per D-10: Reuses execute_tree() and apply_mappings(). Does NOT create RunHistory.
    Does NOT require Qualys configuration.
    """
    canvas = _get_canvas_or_404(db, connector_id, canvas_id)
    connector = db.query(Connector).filter_by(id=connector_id).first()
    if not connector:
        raise HTTPException(
            status_code=404,
            detail=make_error("CONNECTOR_NOT_FOUND", "Connector not found", {}),
        )

    # Load canvas endpoints
    canvas_endpoints = db.query(CanvasEndpoint).filter_by(canvas_id=canvas_id).all()
    if not canvas_endpoints:
        return DryRunResponse(records=[], total_records=0, capped=False)

    # Load connector endpoints for path resolution
    endpoint_ids = [ce.endpoint_id for ce in canvas_endpoints]
    conn_eps = db.query(ConnectorEndpoint).filter(ConnectorEndpoint.id.in_(endpoint_ids)).all()
    ep_map = {ep.id: ep for ep in conn_eps}
    for ce in canvas_endpoints:
        ep = ep_map.get(ce.endpoint_id)
        ce.path = ep.path if ep else ""

    # Find root
    roots = [ce for ce in canvas_endpoints if ce.parent_ref_id is None]
    root_ep = ep_map.get(roots[0].endpoint_id) if roots else None
    if not root_ep:
        return DryRunResponse(records=[], total_records=0, capped=False)

    root_url = connector.base_url.rstrip("/") + "/" + root_ep.path.lstrip("/")

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        source_result = await fetch_all_pages(connector, url=root_url, client=client)

        # D-03/D-12: Filter root records before fan-out
        rule_adapter = TypeAdapter(list[ExclusionRule])
        root_ce = roots[0]
        root_rules_raw = root_ce.exclusion_rules or []
        total_filtered = 0
        if root_rules_raw:
            root_rules = rule_adapter.validate_python(root_rules_raw)
            filtered_root_records, root_filt = apply_exclusion_rules(
                source_result.records, root_rules
            )
            total_filtered += root_filt
        else:
            filtered_root_records = source_result.records

        fan_out_result = await execute_tree(canvas_endpoints, filtered_root_records, connector, client)

    # Determine leaf endpoints (those with no children)
    children_map = _build_tree(canvas_endpoints)
    leaf_ids = {ce.id for ce in canvas_endpoints if ce.id not in children_map}

    # Collect mappings from all leaf endpoints
    all_mapping_rules = []
    for leaf_ce_id in leaf_ids:
        leaf_ce = {ce.id: ce for ce in canvas_endpoints}.get(leaf_ce_id)
        if not leaf_ce:
            continue
        leaf_ep = ep_map.get(leaf_ce.endpoint_id)
        if not leaf_ep:
            continue
        mappings = (
            db.query(FieldMapping)
            .filter(FieldMapping.endpoint_id == leaf_ep.id)
            .order_by(FieldMapping.created_at.asc())
            .all()
        )
        all_mapping_rules.extend(_build_mapping_rules(mappings))

    # D-10/D-12: Apply leaf exclusion rules to merged records
    records_to_map = fan_out_result.merged_records
    for leaf_ce_id in leaf_ids:
        leaf_ce = {ce.id: ce for ce in canvas_endpoints}.get(leaf_ce_id)
        if not leaf_ce:
            continue
        leaf_rules_raw = leaf_ce.exclusion_rules or []
        if leaf_rules_raw:
            leaf_rules = rule_adapter.validate_python(leaf_rules_raw)
            records_to_map, leaf_filt = apply_exclusion_rules(records_to_map, leaf_rules)
            total_filtered += leaf_filt

    total = len(records_to_map)
    capped_records = records_to_map[:DRY_RUN_CAP]

    if not all_mapping_rules:
        return DryRunResponse(records=[], total_records=total, capped=total > DRY_RUN_CAP, records_filtered=total_filtered)

    transformed = [apply_mappings(rec, all_mapping_rules) for rec in capped_records]
    return DryRunResponse(records=transformed, total_records=total, capped=total > DRY_RUN_CAP, records_filtered=total_filtered)



@router.get(BASE, response_model=list[CanvasEndpointResponse])
def list_canvas_endpoints(
    connector_id: str,
    canvas_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """List all canvas-endpoint references for a canvas, ordered by tree_order."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    return (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .order_by(CanvasEndpoint.tree_order.asc())
        .all()
    )


@router.get(BASE + "/{ref_id}", response_model=CanvasEndpointResponse)
def get_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "operator")),
):
    """Retrieve a single canvas-endpoint reference."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )
    return ref


@router.post(
    BASE,
    response_model=CanvasEndpointResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    payload: CanvasEndpointCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Add an endpoint reference to a canvas.

    Validates: canvas exists, endpoint exists for this connector,
    parent_ref_id exists in same canvas, no circular reference.
    """
    canvas = _get_canvas_or_404(db, connector_id, canvas_id)

    # Validate endpoint belongs to this connector
    endpoint = (
        db.query(ConnectorEndpoint)
        .filter_by(id=payload.endpoint_id, connector_id=connector_id)
        .first()
    )
    if not endpoint:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "ENDPOINT_NOT_FOUND",
                "Connector endpoint not found or does not belong to this connector",
                {"endpoint_id": payload.endpoint_id},
            ),
        )

    # Validate parent_ref_id if specified
    if payload.parent_ref_id is not None:
        parent_ref = (
            db.query(CanvasEndpoint)
            .filter_by(id=payload.parent_ref_id, canvas_id=canvas_id)
            .first()
        )
        if not parent_ref:
            raise HTTPException(
                status_code=404,
                detail=make_error(
                    "PARENT_REF_NOT_FOUND",
                    "Parent canvas endpoint reference not found in this canvas",
                    {"parent_ref_id": payload.parent_ref_id},
                ),
            )

    new_id = str(_uuid.uuid4())

    # Check for circular reference if parent is set
    if payload.parent_ref_id is not None:
        existing_refs = (
            db.query(CanvasEndpoint)
            .filter_by(canvas_id=canvas_id)
            .all()
        )
        if detect_cycle(existing_refs, new_id, payload.parent_ref_id):
            raise HTTPException(
                status_code=409,
                detail=make_error(
                    "CIRCULAR_REFERENCE",
                    "Adding this parent reference would create a circular dependency",
                ),
            )

    ref = CanvasEndpoint(
        id=new_id,
        canvas_id=canvas_id,
        endpoint_id=payload.endpoint_id,
        parent_ref_id=payload.parent_ref_id,
        field_role=payload.field_role,
        variable_extractions=payload.variable_extractions,
        max_concurrency=payload.max_concurrency,
        exclusion_rules=payload.exclusion_rules,
        tree_order=payload.tree_order,
    )
    db.add(ref)
    db.commit()
    db.refresh(ref)

    # Check for orphans after creation and include warning if found
    all_refs = (
        db.query(CanvasEndpoint)
        .filter_by(canvas_id=canvas_id)
        .all()
    )
    orphans = find_orphans(all_refs)
    if orphans:
        response_data = CanvasEndpointResponse.model_validate(ref).model_dump()
        response_data["warnings"] = {"orphaned_refs": orphans}
        return response_data

    return ref


@router.patch(
    BASE + "/{ref_id}",
    response_model=CanvasEndpointResponse,
)
def update_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    payload: CanvasEndpointUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Update a canvas-endpoint reference. Cycle detection on parent change."""
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )

    updates = payload.model_dump(exclude_unset=True)

    # If parent_ref_id is changing, validate and check cycle
    if "parent_ref_id" in updates and updates["parent_ref_id"] is not None:
        parent_ref = (
            db.query(CanvasEndpoint)
            .filter_by(id=updates["parent_ref_id"], canvas_id=canvas_id)
            .first()
        )
        if not parent_ref:
            raise HTTPException(
                status_code=404,
                detail=make_error(
                    "PARENT_REF_NOT_FOUND",
                    "Parent canvas endpoint reference not found in this canvas",
                    {"parent_ref_id": updates["parent_ref_id"]},
                ),
            )

        existing_refs = (
            db.query(CanvasEndpoint)
            .filter_by(canvas_id=canvas_id)
            .all()
        )
        if detect_cycle(existing_refs, ref_id, updates["parent_ref_id"]):
            raise HTTPException(
                status_code=409,
                detail=make_error(
                    "CIRCULAR_REFERENCE",
                    "Adding this parent reference would create a circular dependency",
                ),
            )

    for field, value in updates.items():
        setattr(ref, field, value)
    db.commit()
    db.refresh(ref)
    return ref


@router.delete(
    BASE + "/{ref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_canvas_endpoint(
    connector_id: str,
    canvas_id: str,
    ref_id: str,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    """Remove an endpoint reference from a canvas.

    Children are orphaned (parent_ref_id SET NULL) by the FK constraint.
    """
    _get_canvas_or_404(db, connector_id, canvas_id)
    ref = (
        db.query(CanvasEndpoint)
        .filter_by(id=ref_id, canvas_id=canvas_id)
        .first()
    )
    if not ref:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "CANVAS_ENDPOINT_NOT_FOUND",
                "Canvas endpoint reference not found",
                {"ref_id": ref_id},
            ),
        )
    db.delete(ref)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
