"""Fan-out executor: tree traversal, concurrent child fetching, result merging.

Composes template_resolver, source_client, and payload_capture into a recursive
DFS tree traversal that fans out child HTTP requests per parent record.

Key invariants (from CONTEXT.md):
- DFS per root record (D-03): each root's subtree fully traversed before next root
- asyncio.Semaphore per endpoint level (D-05/D-06): concurrency bounded per child endpoint
- No DB writes (D-13): all results accumulated in FanOutResult dataclass
- Fault isolation (D-09): failed child does not stop remaining fan-out
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.services.template_resolver import resolve_path, TemplateResolutionError
from app.services.source_client import fetch_all_pages, resolve_pagination_config
from app.services.transform_engine import apply_mappings
from app.services.event_collector import EventCollector, API_CALL, EXCLUSION_RESULT, STAGE_FETCH, STAGE_EXCLUSION
from app.services.exclusion_filter import apply_exclusion_rules, ExclusionRule
from app.schemas.field_mapping import FieldMappingRule
from pydantic import TypeAdapter

logger = logging.getLogger(__name__)


@dataclass
class LevelStats:
    """Per-endpoint-level counters and capped failure diagnostics."""

    endpoint_id: str
    children_attempted: int = 0
    children_succeeded: int = 0
    children_failed: int = 0
    children_skipped: int = 0
    records_fetched: int = 0
    failure_diagnostics: list[dict] = field(default_factory=list)
    MAX_DIAGNOSTICS: int = 50

    def record_failure(self, diagnostic: dict) -> None:
        self.children_failed += 1
        if len(self.failure_diagnostics) < self.MAX_DIAGNOSTICS:
            self.failure_diagnostics.append(diagnostic)

    def record_skip(self) -> None:
        self.children_skipped += 1


@dataclass
class TraversalRecord:
    """A single record flowing through the pipeline with per-endpoint outputs.

    Per D-11: Each endpoint's field mappings are applied to its own source data.
    Per D-13: ancestor_context carries raw _parent.* fields for template resolution.
    endpoint_outputs carries transformed fields per endpoint (separate data channel).
    """

    raw_record: dict  # Raw base record (for exclusion rules)
    ancestor_context: dict  # Accumulated _parent.* context for template resolution
    endpoint_outputs: dict[str, list[dict]] = field(
        default_factory=dict
    )  # {canvas_endpoint_id: [transformed_fields_dict...]}


@dataclass
class FanOutResult:
    """Accumulated result of a fan-out tree traversal."""

    record_outputs: list[TraversalRecord] = field(default_factory=list)
    base_records_total: int = 0
    base_records_excluded: int = 0
    enrichment_gaps: int = 0
    merged_records: list[dict] = field(default_factory=list)
    level_stats: list[LevelStats] = field(default_factory=list)
    has_failures: bool = False
    has_skipped: bool = False


def _merge_parent_context(child_record: dict, ancestor_context: dict) -> dict:
    """Merge ancestor fields into child record with _parent. prefix accumulation.

    Single-level: parent keys get ``_parent.`` prefix.
    Multi-level: existing ``_parent.`` prefixes on ancestor keys are preserved,
    producing nested ``_parent._parent.`` chains.
    """
    merged = dict(child_record)
    for key, value in ancestor_context.items():
        merged[f"_parent.{key}"] = value
    return merged


def _build_tree(canvas_endpoints: list) -> dict[str | None, list]:
    """Group canvas endpoints by parent_ref_id, sorted by tree_order within each group.

    Returns a dict mapping parent_ref_id -> list of children.
    Root endpoints have parent_ref_id=None.
    """
    children_map: dict[str | None, list] = {}
    for ep in sorted(canvas_endpoints, key=lambda e: e.tree_order):
        children_map.setdefault(ep.parent_ref_id, []).append(ep)
    return children_map


def classify_endpoints(
    canvas_endpoints: list,
    base_canvas_endpoint_id: str,
) -> tuple[set[str], set[str]]:
    """Classify canvas endpoints as upstream or downstream relative to base.

    Upstream: all endpoints on the path from root to base (inclusive).
    Downstream: all children of base and their descendants.

    Walk parent_ref_id chain from base to root for upstream.
    BFS from base's children for downstream.
    """
    children_map = _build_tree(canvas_endpoints)
    ce_by_id = {ce.id: ce for ce in canvas_endpoints}

    # Walk backward from base to root via parent_ref_id
    upstream_ids: set[str] = set()
    current: str | None = base_canvas_endpoint_id
    while current is not None:
        upstream_ids.add(current)
        ce = ce_by_id.get(current)
        current = ce.parent_ref_id if ce else None

    # BFS forward from base's children
    downstream_ids: set[str] = set()
    queue = list(children_map.get(base_canvas_endpoint_id, []))
    for ep in queue:
        downstream_ids.add(ep.id)
        queue.extend(children_map.get(ep.id, []))

    return upstream_ids, downstream_ids


async def _fetch_with_one_retry(
    connector,
    url: str,
    client,
    ep,
    collector: EventCollector | None = None,
    depth: int = 0,
) -> "SourceFetchResult | None":
    """Fetch endpoint data with one retry for transient errors.

    Per D-02/D-06: wraps the entire fetch_all_pages call.
    Returns SourceFetchResult on success, None on failure after retry.
    """
    from app.services.source_client import SourceFetchResult

    for attempt in range(2):
        try:
            result = await fetch_all_pages(
                connector,
                url=url,
                client=client,
                data_root=ep.data_root,
                pagination_strategies=resolve_pagination_config(ep.pagination_config),
                capture_on_success=(
                    collector is not None and collector.fault_diagnosis
                ),
            )
            if not result.partial:
                return result
            # partial = internal retries exhausted; this counts as attempt
            if attempt == 0:
                logger.debug("Retry fetch (partial) for %s", url)
                continue
            return result  # still partial after retry
        except Exception as exc:
            if attempt == 0:
                logger.debug("Retry fetch (exception) for %s: %s", url, exc)
                continue
            raise  # re-raise on second attempt
    return None  # unreachable but satisfies type checker


def _get_or_create_stats(result: FanOutResult, endpoint_id: str) -> LevelStats:
    """Look up or create a LevelStats entry in a FanOutResult."""
    for stats in result.level_stats:
        if stats.endpoint_id == endpoint_id:
            return stats
    stats = LevelStats(endpoint_id=endpoint_id)
    result.level_stats.append(stats)
    return stats


def _parent_identifier(record: dict) -> str:
    """Extract a short identifier from a parent record for diagnostics."""
    for key in ("id", "uuid", "name", "hostname", "serial", "ip"):
        if key in record:
            val = str(record[key])
            return val[:80] if len(val) > 80 else val
    if record:
        key = next(iter(record))
        val = str(record[key])[:40]
        return f"{key}={val}"
    return "(empty record)"


async def execute_tree(
    canvas_endpoints: list,
    root_records: list[dict],
    connector,
    client,
    collector: EventCollector | None = None,
    base_canvas_endpoint_id: str | None = None,
    mappings_by_ce: dict[str, list] | None = None,
) -> FanOutResult:
    """Traverse canvas endpoint tree, fan out child requests, merge results.

    DFS per root record (D-03). No DB writes (D-13). Returns flat merged records.

    When base_canvas_endpoint_id is provided, uses base-aware traversal:
    - Upstream endpoints (root to base) are critical path — failure aborts canvas
    - Base exclusion cascades to skip all downstream requests (D-08)
    - Downstream failures are non-fatal enrichment gaps (DEG-01)
    - Per-endpoint field mappings produce endpoint_outputs (D-11)

    When base_canvas_endpoint_id is None, falls back to legacy leaf-centric traversal.

    Args:
        canvas_endpoints: All CanvasEndpoint records for this canvas.
        root_records: Records fetched from the root endpoint.
        connector: Connector instance with base_url, auth credentials.
        client: Shared httpx.AsyncClient for all HTTP requests.
        collector: Optional EventCollector for structured diagnostic logging.
        base_canvas_endpoint_id: If set, enables base-aware traversal.
        mappings_by_ce: Dict of {canvas_endpoint_id: [FieldMappingRule...]} for per-endpoint mapping.

    Returns:
        FanOutResult with per-record traversal outputs and backward-compat merged_records.
    """
    if base_canvas_endpoint_id is not None:
        return await _execute_tree_base_aware(
            canvas_endpoints, root_records, connector, client,
            collector, base_canvas_endpoint_id, mappings_by_ce or {},
        )

    # Legacy path: leaf-centric traversal (backward compat)
    children_map = _build_tree(canvas_endpoints)
    result = FanOutResult()

    # Find root canvas endpoints (parent_ref_id is None)
    root_endpoints = children_map.get(None, [])

    # DFS per root record (D-03, D-04)
    for root_record in root_records:
        if not root_endpoints:
            # No canvas endpoints at all -- root records are the leaf output
            result.merged_records.append(dict(root_record))
            continue

        for root_ep in root_endpoints:
            # Check if root endpoint has children
            child_endpoints = children_map.get(root_ep.id, [])
            if not child_endpoints:
                # Root has no children -- root records are leaf output
                result.merged_records.append(dict(root_record))
            else:
                # Fan out to children of this root endpoint
                await _fan_out_level(
                    parent_records=[root_record],
                    parent_context={},
                    child_endpoints=child_endpoints,
                    children_map=children_map,
                    connector=connector,
                    client=client,
                    result=result,
                    depth=1,
                    collector=collector,
                )

    return result


async def _execute_tree_base_aware(
    canvas_endpoints: list,
    root_records: list[dict],
    connector,
    client,
    collector: EventCollector | None,
    base_canvas_endpoint_id: str,
    mappings_by_ce: dict[str, list],
) -> FanOutResult:
    """Base-aware tree traversal with upstream/downstream split.

    Upstream endpoints (root to base) are critical path — failure aborts canvas (D-05).
    Base exclusion cascades to skip all downstream HTTP requests (D-08).
    Downstream failures are non-fatal enrichment gaps (DEG-01).
    Per-endpoint field mappings produce endpoint_outputs during traversal (D-11).
    """
    children_map = _build_tree(canvas_endpoints)
    ce_by_id = {ce.id: ce for ce in canvas_endpoints}
    upstream_ids, downstream_ids = classify_endpoints(canvas_endpoints, base_canvas_endpoint_id)
    result = FanOutResult()

    # Build upstream path: walk parent_ref_id from base to root, reverse to root-to-base order
    upstream_path: list[str] = []
    current: str | None = base_canvas_endpoint_id
    while current is not None:
        upstream_path.append(current)
        ce = ce_by_id.get(current)
        current = ce.parent_ref_id if ce else None
    upstream_path.reverse()  # Now root-first

    base_ep = ce_by_id[base_canvas_endpoint_id]

    # --- Single-endpoint canvas (root = base, no children) ---
    if len(upstream_path) == 1 and not downstream_ids:
        base_records = root_records
        result.base_records_total = len(base_records)

        # Apply base exclusion rules on raw data (D-10)
        if hasattr(base_ep, "exclusion_rules") and base_ep.exclusion_rules:
            rule_adapter = TypeAdapter(list[ExclusionRule])
            rules = rule_adapter.validate_python(base_ep.exclusion_rules)
            base_records, excluded = apply_exclusion_rules(base_records, rules)
            result.base_records_excluded = excluded

        # Apply base mappings and build TraversalRecords
        base_rules = mappings_by_ce.get(base_canvas_endpoint_id, [])
        for rec in base_records:
            tr = TraversalRecord(raw_record=rec, ancestor_context={})
            tr.endpoint_outputs[base_canvas_endpoint_id] = [apply_mappings(rec, base_rules)]
            result.record_outputs.append(tr)
            # Backward compat
            result.merged_records.append(dict(rec))

        return result

    # --- Multi-endpoint canvas ---
    # Store per-upstream-endpoint transformed outputs (shared across all root records)
    # Root endpoint: root_records are the source data (already fetched)
    root_ce_id = upstream_path[0]
    root_rules = mappings_by_ce.get(root_ce_id, [])
    root_outputs = [apply_mappings(rec, root_rules) for rec in root_records]

    # Traverse upstream: fetch intermediate endpoints between root and base
    # root_records -> intermediate1 -> intermediate2 -> ... -> base
    current_records = root_records
    current_context: dict = {}  # accumulated _parent.* context
    upstream_outputs: dict[str, list[dict]] = {root_ce_id: root_outputs}

    for i in range(1, len(upstream_path)):
        ce_id = upstream_path[i]
        ce = ce_by_id[ce_id]

        # Fan out from current_records to this upstream endpoint
        fetched_records: list[dict] = []
        accumulated_contexts: list[dict] = []

        for parent_rec in current_records:
            ancestor = _merge_parent_context(parent_rec, current_context)

            # Resolve template and build URL
            try:
                resolved_path = resolve_path(
                    ce.path,
                    ancestor,
                    ce.variable_extractions or {},
                )
            except TemplateResolutionError as exc:
                logger.debug("Upstream template resolution failed for %s: %s", ce_id, exc)
                continue

            url = connector.base_url.rstrip("/") + "/" + resolved_path.lstrip("/")

            # Upstream fetch with one retry — failure aborts canvas (D-05)
            fetch_result = await _fetch_with_one_retry(
                connector, url, client, ce, collector,
            )
            if fetch_result is None or fetch_result.partial:
                raise Exception(
                    f"Upstream endpoint {ce_id} fetch failed for {url}"
                )

            for child_rec in fetch_result.records:
                merged = _merge_parent_context(child_rec, ancestor)
                fetched_records.append(child_rec)
                accumulated_contexts.append(ancestor)

        # Apply this endpoint's mappings
        ce_rules = mappings_by_ce.get(ce_id, [])
        upstream_outputs[ce_id] = [apply_mappings(rec, ce_rules) for rec in fetched_records]

        # Update current records and context for next level
        if accumulated_contexts:
            current_context = accumulated_contexts[0]  # all share same parent context at this level
        current_records = fetched_records

    # current_records are now the base records
    base_records = current_records
    result.base_records_total = len(base_records)

    # Apply base exclusion rules on RAW base records (D-10, before mappings)
    if hasattr(base_ep, "exclusion_rules") and base_ep.exclusion_rules:
        rule_adapter = TypeAdapter(list[ExclusionRule])
        rules = rule_adapter.validate_python(base_ep.exclusion_rules)
        base_records, excluded = apply_exclusion_rules(base_records, rules)
        result.base_records_excluded = excluded

    # Apply base field mappings to non-excluded records
    base_rules = mappings_by_ce.get(base_canvas_endpoint_id, [])
    base_mapped = [apply_mappings(rec, base_rules) for rec in base_records]

    # For each non-excluded base record, traverse downstream
    for idx, base_rec in enumerate(base_records):
        # Build ancestor context for this base record
        ancestor_ctx = _merge_parent_context(base_rec, current_context)

        # Collect endpoint outputs for this traversal record
        ep_outputs: dict[str, list[dict]] = {}

        # Include upstream endpoint outputs
        for up_ce_id in upstream_path[:-1]:  # all upstream except base
            if up_ce_id in upstream_outputs:
                ep_outputs[up_ce_id] = upstream_outputs[up_ce_id]

        # Include base outputs
        ep_outputs[base_canvas_endpoint_id] = [base_mapped[idx]]

        # Traverse downstream endpoints
        await _traverse_downstream(
            base_rec=base_rec,
            ancestor_context=ancestor_ctx,
            base_ce_id=base_canvas_endpoint_id,
            children_map=children_map,
            ce_by_id=ce_by_id,
            downstream_ids=downstream_ids,
            connector=connector,
            client=client,
            collector=collector,
            mappings_by_ce=mappings_by_ce,
            ep_outputs=ep_outputs,
            result=result,
        )

        tr = TraversalRecord(
            raw_record=base_rec,
            ancestor_context=ancestor_ctx,
            endpoint_outputs=ep_outputs,
        )
        result.record_outputs.append(tr)

        # Backward compat: flat merged record
        result.merged_records.append(_merge_parent_context(base_rec, current_context))

    # Set has_failures if any enrichment gaps occurred (D-04)
    if result.enrichment_gaps > 0:
        result.has_failures = True

    return result


async def _traverse_downstream(
    base_rec: dict,
    ancestor_context: dict,
    base_ce_id: str,
    children_map: dict,
    ce_by_id: dict,
    downstream_ids: set[str],
    connector,
    client,
    collector: EventCollector | None,
    mappings_by_ce: dict[str, list],
    ep_outputs: dict[str, list[dict]],
    result: FanOutResult,
) -> None:
    """Traverse downstream endpoints for a single base record.

    Downstream failures are non-fatal — enrichment gaps logged but base record preserved.
    Empty responses (0 records, 2xx) are normal operation (D-01, D-03).
    """
    # BFS from base children
    queue: list[tuple[str, dict]] = []  # (ce_id, parent_context)
    for child_ce in children_map.get(base_ce_id, []):
        if child_ce.id in downstream_ids:
            queue.append((child_ce.id, ancestor_context))

    for ds_ce_id, parent_ctx in queue:
        ds_ce = ce_by_id[ds_ce_id]

        # Resolve template
        try:
            resolved_path = resolve_path(
                ds_ce.path,
                parent_ctx,
                ds_ce.variable_extractions or {},
            )
        except TemplateResolutionError as exc:
            logger.debug("Downstream template skip for %s: %s", ds_ce_id, exc)
            continue

        url = connector.base_url.rstrip("/") + "/" + resolved_path.lstrip("/")

        # Fetch with one retry (D-02) — failure is non-fatal
        try:
            fetch_result = await _fetch_with_one_retry(
                connector, url, client, ds_ce, collector,
            )
        except Exception as exc:
            # Both attempts failed — enrichment gap
            result.enrichment_gaps += 1
            logger.debug("Downstream enrichment gap for %s: %s", ds_ce_id, exc)
            if collector:
                collector.add_detail(
                    API_CALL, STAGE_FETCH,
                    f"Enrichment gap: {ds_ce.path} failed after retry",
                    {"url": url, "error": str(exc), "endpoint_id": ds_ce_id},
                )
            continue

        if fetch_result is None or fetch_result.partial:
            # Partial after retry — enrichment gap
            result.enrichment_gaps += 1
            logger.debug("Downstream enrichment gap (partial) for %s", ds_ce_id)
            if collector:
                collector.add_detail(
                    API_CALL, STAGE_FETCH,
                    f"Enrichment gap: {ds_ce.path} partial after retry",
                    {"url": url, "endpoint_id": ds_ce_id},
                )
            continue

        # 0 records from 2xx is normal — no gap, no retry (D-01, D-03)
        if not fetch_result.records:
            continue

        # Apply downstream mappings
        ds_rules = mappings_by_ce.get(ds_ce_id, [])
        ds_mapped = [apply_mappings(rec, ds_rules) for rec in fetch_result.records]
        ep_outputs[ds_ce_id] = ds_mapped

        # Queue children of this downstream endpoint
        for grandchild_ce in children_map.get(ds_ce_id, []):
            if grandchild_ce.id in downstream_ids:
                # Build context for deeper downstream
                if fetch_result.records:
                    deeper_ctx = _merge_parent_context(fetch_result.records[0], parent_ctx)
                    queue.append((grandchild_ce.id, deeper_ctx))


async def _fan_out_level(
    parent_records: list[dict],
    parent_context: dict,
    child_endpoints: list,
    children_map: dict,
    connector,
    client,
    result: FanOutResult,
    depth: int = 1,
    collector: EventCollector | None = None,
) -> None:
    """Fan out to child endpoints for each parent record, bounded by semaphore.

    For each child endpoint, creates an asyncio.Semaphore from its max_concurrency
    setting (D-05/D-06), then processes all parent records concurrently within
    that bound.
    """
    for child_ep in child_endpoints:
        semaphore = asyncio.Semaphore(child_ep.max_concurrency)
        stats = _get_or_create_stats(result, child_ep.id)
        child_path = child_ep.path
        should_capture = collector is not None and collector.fault_diagnosis

        async def _process_one_parent(
            parent_record: dict,
            sem=semaphore,
            ep_path=child_path,
            ep=child_ep,
            st=stats,
            coll=collector,
            do_capture=should_capture,
        ) -> list[dict]:
            """Process a single parent record against a child endpoint."""
            async with sem:
                # Build ancestor context: current parent fields + inherited ancestors
                current_ancestor = _merge_parent_context(parent_record, parent_context)
                st.children_attempted += 1

                # Resolve template variables — resolve_path auto-resolves
                # ancestor variables via _parent.* keys in the merged record
                try:
                    resolved_path = resolve_path(
                        ep_path,
                        current_ancestor,
                        ep.variable_extractions or {},
                    )
                except TemplateResolutionError as exc:
                    st.record_skip()
                    result.has_skipped = True
                    logger.debug("Skipping child %s: %s", ep.id, exc)
                    return []

                # Build full URL
                url = connector.base_url.rstrip("/") + "/" + resolved_path.lstrip("/")

                # Fetch child records
                try:
                    fetch_result = await fetch_all_pages(
                        connector, url=url, client=client,
                        data_root=ep.data_root,
                        pagination_strategies=resolve_pagination_config(ep.pagination_config),
                        capture_on_success=do_capture,
                    )
                except Exception as exc:
                    st.record_failure({
                        "endpoint_name": ep.path,
                        "tree_level": depth,
                        "parent_record": _parent_identifier(parent_record),
                        "url": url,
                        "error": str(exc),
                    })
                    result.has_failures = True
                    logger.debug("Child fetch failed %s: %s", url, exc)
                    if coll:
                        coll.add_detail(API_CALL, STAGE_FETCH,
                            f"GET {url} -> FAILED (child L{depth})",
                            {"url": url, "error": str(exc),
                             "endpoint_path": ep_path, "depth": depth,
                             "parent": _parent_identifier(parent_record)})
                    return []

                # Check for partial fetch (HTTP error after retries)
                if fetch_result.partial:
                    st.record_failure({
                        "endpoint_name": ep.path,
                        "tree_level": depth,
                        "parent_record": _parent_identifier(parent_record),
                        "url": url,
                        "http_request": fetch_result.http_request,
                        "http_response": fetch_result.http_response,
                    })
                    result.has_failures = True
                    if coll:
                        coll.add_detail(API_CALL, STAGE_FETCH,
                            f"GET {url} -> PARTIAL (child L{depth})",
                            {"url": url, "endpoint_path": ep_path, "depth": depth,
                             "parent": _parent_identifier(parent_record),
                             "http_request": fetch_result.http_request,
                             "http_response": fetch_result.http_response})
                    return []

                st.children_succeeded += 1
                st.records_fetched += len(fetch_result.records)

                if coll:
                    coll.add_detail(API_CALL, STAGE_FETCH,
                        f"GET {url} -> {len(fetch_result.records)} records (child L{depth})",
                        {"url": url, "records": len(fetch_result.records),
                         "endpoint_path": ep_path, "depth": depth,
                         "parent": _parent_identifier(parent_record),
                         "http_request": fetch_result.http_request,
                         "http_response": fetch_result.http_response})

                # Apply exclusion rules if configured on this endpoint
                records_to_pass = fetch_result.records
                if hasattr(ep, "exclusion_rules") and ep.exclusion_rules:
                    rule_adapter = TypeAdapter(list[ExclusionRule])
                    rules = rule_adapter.validate_python(ep.exclusion_rules)
                    records_to_pass, excluded_count = apply_exclusion_rules(
                        fetch_result.records, rules
                    )
                    if excluded_count > 0:
                        st.records_fetched -= excluded_count
                        if coll:
                            coll.add_detail(EXCLUSION_RESULT, STAGE_EXCLUSION,
                                f"Child L{depth} exclusion: {excluded_count} records excluded from {ep_path}",
                                {"excluded_count": excluded_count,
                                 "remaining": len(records_to_pass),
                                 "endpoint_path": ep_path, "depth": depth,
                                 "parent": _parent_identifier(parent_record)})

                # Check if this child endpoint is a leaf or has further children
                grandchild_endpoints = children_map.get(ep.id, [])
                if not grandchild_endpoints:
                    # Leaf -- merge parent context into each child record
                    merged = []
                    for child_rec in records_to_pass:
                        merged.append(_merge_parent_context(child_rec, current_ancestor))
                    return merged
                else:
                    # Intermediate -- recurse deeper
                    await _fan_out_level(
                        parent_records=records_to_pass,
                        parent_context=current_ancestor,
                        child_endpoints=grandchild_endpoints,
                        children_map=children_map,
                        connector=connector,
                        client=client,
                        result=result,
                        depth=depth + 1,
                        collector=coll,
                    )
                    return []  # results added by recursive call

        # Run all parent records concurrently with semaphore (D-05)
        tasks = [_process_one_parent(rec) for rec in parent_records]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect leaf merged records, handle any unexpected exceptions
        exceptions_caught = 0
        records_collected = 0
        for res in gather_results:
            if isinstance(res, Exception):
                exceptions_caught += 1
                stats.children_failed += 1
                result.has_failures = True
                logger.error("Unexpected fan-out error: %s", res)
            elif isinstance(res, list):
                records_collected += len(res)
                result.merged_records.extend(res)

        if collector and collector.fault_diagnosis:
            collector.add_detail(API_CALL, STAGE_FETCH,
                f"Fan-out L{depth} {child_ep.path}: {stats.children_succeeded}/{stats.children_attempted} succeeded, "
                f"{records_collected} leaf records collected, {exceptions_caught} exceptions",
                {"depth": depth, "endpoint_path": child_ep.path,
                 "attempted": stats.children_attempted,
                 "succeeded": stats.children_succeeded,
                 "failed": stats.children_failed,
                 "skipped": stats.children_skipped,
                 "records_collected": records_collected,
                 "exceptions": exceptions_caught,
                 "total_merged_so_far": len(result.merged_records)})
