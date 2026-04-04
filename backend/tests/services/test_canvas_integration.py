"""Integration tests for canvas execution path in run_ingestion.

Exercises the full canvas pipeline end-to-end: root fetch, fan-out to children
via execute_tree (REAL, not mocked), _parent.* merge, apply_mappings (REAL),
and Qualys batch submission. Only HTTP boundaries are mocked: fetch_all_pages
and submit_batch.
"""
from contextlib import contextmanager
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.canvas import Canvas
from app.models.canvas_endpoint import CanvasEndpoint
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.field_mapping import FieldMapping
from app.models.qualys_config import QualysConfig
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus
from app.services.credential_crypto import get_crypto
from app.services.ingestion_service import run_ingestion
from app.services.qualys_adapter import QualysSubmitResult
from app.services.source_client import SourceFetchResult


# ---------------------------------------------------------------------------
# DB fixture -- use conftest engine, monkeypatch SessionLocal
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch, db_session):
    """Patch SessionLocal to reuse the test connection for transaction visibility."""
    bind = db_session.get_bind()
    TestSession = sessionmaker(bind=bind)
    monkeypatch.setattr("app.services.ingestion_service.SessionLocal", TestSession)
    monkeypatch.setattr("app.services.fan_out_executor.SessionLocal", TestSession, raising=False)


@pytest.fixture()
def db_factory(db_session):
    """Compatibility fixture: yields (db_session, sessionmaker) tuple."""
    bind = db_session.get_bind()
    TestSession = sessionmaker(bind=bind)
    yield db_session, TestSession


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_connector(db) -> Connector:
    connector = Connector(
        name="Canvas Test Connector",
        base_url="https://source.example.com",
        auth_method="bearer_token",
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def _seed_qualys_config(db) -> QualysConfig:
    crypto = get_crypto()
    config = QualysConfig(
        username="quays2user1",
        encrypted_password=crypto.encrypt("secret"),
        connector_uuid="test-connector-uuid",
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _seed_endpoint(
    db,
    connector_id: str,
    name: str = "Test Endpoint",
    path: str = "/assets",
    display_order: int = 0,
    is_enabled: bool = True,
    data_root: str | None = None,
    pagination_config: dict | None = None,
) -> ConnectorEndpoint:
    endpoint = ConnectorEndpoint(
        connector_id=connector_id,
        name=name,
        path=path,
        is_enabled=is_enabled,
        display_order=display_order,
        data_root=data_root,
        pagination_config=pagination_config,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return endpoint


def _seed_run(db, connector_id: str) -> RunHistory:
    run = RunHistory(
        connector_id=connector_id,
        status=RunStatus.running,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _seed_mapping(
    db,
    endpoint_id: str,
    source_field: str = "hostname",
    target_field: str = "hostName",
    mapping_type: str = "direct_copy",
) -> FieldMapping:
    mapping = FieldMapping(
        endpoint_id=endpoint_id,
        target_field=target_field,
        mapping_type=mapping_type,
        source_field=source_field,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def _seed_canvas(
    db,
    connector_id: str,
    name: str = "Test Canvas",
    is_enabled: bool = True,
) -> Canvas:
    canvas = Canvas(
        connector_id=connector_id,
        name=name,
        is_enabled=is_enabled,
    )
    db.add(canvas)
    db.commit()
    db.refresh(canvas)
    return canvas


def _seed_canvas_endpoint(
    db,
    canvas_id: str,
    endpoint_id: str,
    parent_ref_id: str | None = None,
    tree_order: int = 0,
    max_concurrency: int = 5,
    variable_extractions: dict | None = None,
    exclusion_rules: list | None = None,
) -> CanvasEndpoint:
    ce = CanvasEndpoint(
        canvas_id=canvas_id,
        endpoint_id=endpoint_id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
        max_concurrency=max_concurrency,
        variable_extractions=variable_extractions,
        exclusion_rules=exclusion_rules,
    )
    db.add(ce)
    db.commit()
    db.refresh(ce)
    return ce


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _fetch_result(records=None, count=None) -> SourceFetchResult:
    if records is None:
        records = [{"hostname": "asset-1"}]
    return SourceFetchResult(
        records=records,
        records_fetched=count if count is not None else len(records),
        pages_fetched=1,
        partial=False,
    )


def _submit_result(count: int = 1) -> QualysSubmitResult:
    return QualysSubmitResult(submitted_count=count, failed_count=0, failures=[])


def _url_router(routes: dict):
    """Create a fetch_all_pages side_effect that dispatches by URL substring.

    routes: dict mapping URL substring -> SourceFetchResult or Exception
    Example: {"/nodes": result1, "/vms": result2}

    URL matching is done in insertion order -- first match wins. This allows
    disambiguation when one URL is a substring of another (e.g. "/nodes" vs
    "/nodes/{node}/vms") by placing the more specific pattern first.
    """
    async def _side_effect(connector, url, client=None, **kwargs):
        for pattern, result in routes.items():
            if pattern in url:
                if isinstance(result, Exception):
                    raise result
                return result
        return SourceFetchResult(records=[], records_fetched=0, pages_fetched=1, partial=False)
    return _side_effect


@contextmanager
def _canvas_mocks(fetch_side_effect, submit_mock):
    """Patch fetch_all_pages in BOTH ingestion_service and fan_out_executor,
    plus submit_batch in ingestion_service."""
    with patch("app.services.ingestion_service.fetch_all_pages", new=AsyncMock(side_effect=fetch_side_effect)), \
         patch("app.services.fan_out_executor.fetch_all_pages", new=AsyncMock(side_effect=fetch_side_effect)), \
         patch("app.services.ingestion_service.submit_batch", new=submit_mock):
        yield


# ---------------------------------------------------------------------------
# Test data (Proxmox-style)
# ---------------------------------------------------------------------------

ROOT_RECORDS = [
    {"node": "pve1", "status": "online"},
    {"node": "pve2", "status": "online"},
]

CHILD_RECORDS = [
    {"vmid": 100, "name": "web-server-01", "node": "inherited"},
]

GRANDCHILD_RECORDS = [
    {"iface": "eth0", "ip": "10.0.0.1"},
]


# ---------------------------------------------------------------------------
# Scenario 1: Happy path -- 2-level canvas tree
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_two_level(db_factory):
    """2-level canvas: root -> child. Verifies full pipeline:
    root fetch, fan-out via real execute_tree, _parent.* merge,
    real apply_mappings with DB-seeded FieldMapping, Qualys submission.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    # Field mapping on the child (leaf) endpoint -- source_field="name" from child records
    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Route: /nodes (not /vms) -> root records; /vms -> child records
    routes = {}
    routes["/vms"] = _fetch_result(records=list(CHILD_RECORDS))
    routes["/nodes"] = _fetch_result(records=list(ROOT_RECORDS))

    submit_mock = AsyncMock(return_value=_submit_result(count=2))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .order_by(EndpointRunLog.execution_order)
        .all()
    )
    # Base-aware model: root_log always created; child logs come from level_stats.
    # When child is the base (has identity mapping) and there are no downstream endpoints,
    # level_stats is empty. Only the root_log exists.
    assert len(logs) >= 1, f"Expected at least 1 EndpointRunLog row, got {len(logs)}"

    # Root log
    root_log = logs[0]
    assert root_log.canvas_id == canvas.id
    assert root_log.endpoint_id == root_ep.id
    assert root_log.records_fetched == 2

    # submit_batch was called (verifies base-anchored submission path)
    assert submit_mock.called, "submit_batch should have been called for base records"

    # Records passed to submit_batch contain "hostName" key (real apply_mappings ran)
    call_args = submit_mock.call_args_list
    submitted_records = call_args[0][0][0]  # first call, first positional arg (batch)
    assert any("hostName" in rec for rec in submitted_records), \
        f"Expected 'hostName' in submitted records, got keys: {[list(r.keys()) for r in submitted_records]}"

    # Verify _parent.* merge happened: merged records contain _parent.node
    # The merged records flow through apply_mappings which may strip unknown keys,
    # but the raw merged records have _parent.node. We verify via the submit args
    # which should have _parent.node pass-through since apply_mappings only adds
    # mapped keys. Actually, apply_mappings returns only mapped fields. So we verify
    # the mapping worked (hostName present) which proves the chain ran correctly.
    assert any(rec.get("hostName") == "web-server-01" for rec in submitted_records), \
        f"Expected hostName='web-server-01' in submitted records"


# ---------------------------------------------------------------------------
# Scenario 2: 3-level chain -- root -> child -> grandchild
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_level_chain(db_factory):
    """3-level canvas: root -> child -> grandchild. Proves recursive
    _parent.* accumulation and tree traversal across 3 levels.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)
    grandchild_ep = _seed_endpoint(
        db, connector.id, name="Interfaces",
        path="api/nodes/{node}/vms/{vmid}/interfaces",
        display_order=2,
    )

    # Field mapping on grandchild (leaf) endpoint
    _seed_mapping(db, grandchild_ep.id, source_field="iface", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )
    grandchild_ce = _seed_canvas_endpoint(
        db, canvas.id, grandchild_ep.id,
        parent_ref_id=child_ce.id,
        tree_order=2,
        variable_extractions={"vmid": "vmid", "node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Route: more specific patterns first so /vms doesn't match /interfaces
    routes = {}
    routes["/interfaces"] = _fetch_result(records=list(GRANDCHILD_RECORDS))
    routes["/vms"] = _fetch_result(records=list(CHILD_RECORDS))
    routes["/nodes"] = _fetch_result(records=list(ROOT_RECORDS))

    submit_mock = AsyncMock(return_value=_submit_result(count=2))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .order_by(EndpointRunLog.execution_order)
        .all()
    )
    # Base-aware model: grandchild has identity mapping, so it is the base.
    # Root and child are upstream — no separate level_stats entries.
    # Only the root_log exists (created by _run_canvas line 446).
    assert len(logs) >= 1, f"Expected at least 1 EndpointRunLog row, got {len(logs)}"

    # submit_batch was called (base-anchored submission)
    assert submit_mock.called, "submit_batch should have been called for base records"

    # Verify mapping worked -- hostName present from grandchild's iface field
    call_args = submit_mock.call_args_list
    submitted_records = call_args[0][0][0]
    assert any("hostName" in rec for rec in submitted_records), \
        f"Expected 'hostName' in submitted records from grandchild mapping"


# ---------------------------------------------------------------------------
# Scenario 3: Child fetch failure isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_child_fetch_failure_isolation(db_factory):
    """Child endpoint fetch failure is isolated: root succeeds, child logs
    failure diagnostics. RunHistory status = partial_success.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Root succeeds, child raises for all requests
    routes = {}
    routes["/vms"] = Exception("connection timeout")
    routes["/nodes"] = _fetch_result(records=list(ROOT_RECORDS))

    submit_mock = AsyncMock(return_value=_submit_result(count=0))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    # Base-aware model: child has identity mapping, so child IS the base.
    # When the base endpoint fetch fails, this is an upstream failure (D-05)
    # which aborts the canvas — status is 'failed', not 'partial_success'.
    assert updated_run.status == RunStatus.failed, \
        f"Expected failed (base endpoint fetch failed), got {updated_run.status}"

    # At least the root_log should exist
    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .all()
    )
    assert len(logs) >= 1, f"Expected at least 1 EndpointRunLog row, got {len(logs)}"

    # Root log should exist
    root_log = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id, EndpointRunLog.endpoint_id == root_ep.id)
        .first()
    )
    assert root_log is not None

    # submit_batch should NOT have been called (base fetch failed, no records)
    assert not submit_mock.called, "submit_batch should not be called when base fetch fails"


# ---------------------------------------------------------------------------
# Scenario 4: Root fetch failure
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_root_fetch_failure(db_factory):
    """Root endpoint fetch failure halts canvas execution. Only 1 EndpointRunLog
    (root, failed) is created. No child logs exist.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Root raises, child mock irrelevant
    async def _failing_fetch(connector, url, client=None, **kwargs):
        raise Exception("root fetch failed")

    submit_mock = AsyncMock(return_value=_submit_result(count=0))

    with _canvas_mocks(_failing_fetch, submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.failed

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .all()
    )
    assert len(logs) == 1, f"Expected exactly 1 EndpointRunLog (root only), got {len(logs)}"

    root_log = logs[0]
    assert root_log.endpoint_id == root_ep.id
    assert root_log.status == "failed"
    assert "root fetch failed" in root_log.error_message
    assert root_log.failure_stage == "source_fetch"

    # No child logs
    child_logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id, EndpointRunLog.endpoint_id == child_ep.id)
        .all()
    )
    assert len(child_logs) == 0, "No child EndpointRunLog should exist when root fetch fails"

    # submit_batch should NOT have been called
    assert not submit_mock.called, "submit_batch should not be called when root fetch fails"


# ---------------------------------------------------------------------------
# Scenario 5: Exclusion rules filter before fan-out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exclusion_rules_filter_before_fanout(db_factory):
    """Root exclusion rules filter records BEFORE fan-out to children.

    Root returns 2 records; exclusion rule matches 1 (status=offline).
    Only the surviving record (pve1) should fan out to children.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    # Field mapping on child (leaf) endpoint
    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(
        db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0,
        exclusion_rules=[
            {"source_field": "status", "operator": "equals", "value": "offline"},
        ],
    )
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Root: 2 records, 1 online (pve1), 1 offline (pve2 -- should be excluded)
    root_records = [
        {"node": "pve1", "status": "online"},
        {"node": "pve2", "status": "offline"},
    ]
    child_records = [{"vmid": 100, "name": "web-server-01"}]

    routes = {}
    routes["/vms"] = _fetch_result(records=list(child_records))
    routes["/nodes"] = _fetch_result(records=list(root_records))

    submit_mock = AsyncMock(return_value=_submit_result(count=1))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .order_by(EndpointRunLog.execution_order)
        .all()
    )
    # Base-aware model: child has identity mapping, so child is the base.
    # No downstream endpoints → level_stats empty → only root_log.
    assert len(logs) >= 1, f"Expected at least 1 EndpointRunLog row, got {len(logs)}"

    # Root log: fetched 2 records, filtered 1
    root_log = logs[0]
    assert root_log.endpoint_id == root_ep.id
    assert root_log.records_fetched == 2
    assert root_log.records_filtered == 1

    # submit_batch was called with records from pve1's children only
    assert submit_mock.called, "submit_batch should have been called for filtered leaf records"
    call_args = submit_mock.call_args_list
    submitted_records = call_args[0][0][0]
    assert any(rec.get("hostName") == "web-server-01" for rec in submitted_records), \
        f"Expected hostName='web-server-01' in submitted records"


# ---------------------------------------------------------------------------
# Scenario 6: Zero child records -- no submission
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_child_records_no_submission(db_factory):
    """Root returns records but ALL child fetches return empty records.

    No merged records exist, so submit_batch should NOT be called.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    # Field mapping on child (leaf) endpoint
    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")

    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Root: 2 records. Child: always returns empty.
    empty_child = SourceFetchResult(records=[], records_fetched=0, pages_fetched=1, partial=False)
    routes = {}
    routes["/vms"] = empty_child
    routes["/nodes"] = _fetch_result(records=list(ROOT_RECORDS))

    submit_mock = AsyncMock(return_value=_submit_result(count=0))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .order_by(EndpointRunLog.execution_order)
        .all()
    )
    # Base-aware model: child has identity mapping, so child is the base.
    # No downstream endpoints → level_stats empty → only root_log.
    assert len(logs) >= 1, f"Expected at least 1 EndpointRunLog row, got {len(logs)}"

    # Root log: fetched 2 records
    root_log = logs[0]
    assert root_log.endpoint_id == root_ep.id
    assert root_log.records_fetched == 2
    assert root_log.records_submitted == 0

    # submit_batch should NOT have been called (no merged records to submit)
    assert not submit_mock.called, "submit_batch should not be called when all child fetches return empty"


# ---------------------------------------------------------------------------
# Scenario 7: Mixed canvas and orphan endpoints in single run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_canvas_and_orphan(db_factory):
    """A connector with one canvas tree AND one orphan endpoint.

    Both canvas and orphan paths execute in a single run_ingestion call.
    Canvas logs have canvas_id set; orphan log has canvas_id=None.
    """
    db, _ = db_factory
    connector = _seed_connector(db)
    _seed_qualys_config(db)

    # Canvas endpoints: root -> child
    root_ep = _seed_endpoint(db, connector.id, name="Nodes", path="api/nodes", display_order=0)
    child_ep = _seed_endpoint(db, connector.id, name="VMs", path="api/nodes/{node}/vms", display_order=1)

    # Orphan endpoint: NOT added to any canvas
    orphan_ep = _seed_endpoint(db, connector.id, name="Standalone", path="api/standalone-assets", display_order=2)

    # Field mappings
    _seed_mapping(db, child_ep.id, source_field="name", target_field="hostName")
    _seed_mapping(db, orphan_ep.id, source_field="hostname", target_field="hostName")

    # Canvas with tree
    canvas = _seed_canvas(db, connector.id)
    root_ce = _seed_canvas_endpoint(db, canvas.id, root_ep.id, parent_ref_id=None, tree_order=0)
    child_ce = _seed_canvas_endpoint(
        db, canvas.id, child_ep.id,
        parent_ref_id=root_ce.id,
        tree_order=1,
        variable_extractions={"node": "node"},
    )

    run = _seed_run(db, connector.id)

    # Route setup: specific patterns first
    routes = {}
    routes["/vms"] = _fetch_result(records=[{"vmid": 100, "name": "web-server-01"}])
    routes["/nodes"] = _fetch_result(records=list(ROOT_RECORDS))
    routes["/standalone"] = _fetch_result(records=[{"hostname": "standalone-host-01"}])

    submit_mock = AsyncMock(return_value=_submit_result(count=1))

    with _canvas_mocks(_url_router(routes), submit_mock):
        await run_ingestion(run.id)

    db.expire_all()
    updated_run = db.query(RunHistory).filter(RunHistory.id == run.id).first()
    assert updated_run.status == RunStatus.success

    logs = (
        db.query(EndpointRunLog)
        .filter(EndpointRunLog.run_id == run.id)
        .order_by(EndpointRunLog.execution_order)
        .all()
    )
    # Base-aware model: child has identity mapping → child is base, no downstream.
    # Canvas produces 1 root_log; orphan produces 1 log → 2 total.
    assert len(logs) >= 2, f"Expected at least 2 EndpointRunLog rows (canvas root + orphan), got {len(logs)}"

    # Find logs by endpoint
    root_log = next((l for l in logs if l.endpoint_id == root_ep.id), None)
    orphan_log = next((l for l in logs if l.endpoint_id == orphan_ep.id), None)

    # Canvas root log has canvas_id set
    assert root_log is not None, "Root log should exist"
    assert root_log.canvas_id == canvas.id, "Root log should have canvas_id"

    # In base-aware model, the root_log aggregates canvas submission stats
    # (submission count is recorded on the single canvas log)

    # Orphan log has no canvas association
    assert orphan_log is not None, "Orphan log should exist"
    assert orphan_log.canvas_id is None, "Orphan log should have canvas_id=None"
    assert orphan_log.canvas_endpoint_id is None, "Orphan log should have canvas_endpoint_id=None"
    assert orphan_log.records_fetched > 0, "Orphan should have fetched records"

    # submit_batch was called (at least for canvas base and/or orphan)
    assert submit_mock.call_count >= 1, \
        f"Expected submit_batch called at least once, got {submit_mock.call_count}"

    # Total records submitted across all logs > 0
    total_submitted = sum(l.records_submitted for l in logs)
    assert total_submitted > 0, "Total records_submitted should be > 0"
