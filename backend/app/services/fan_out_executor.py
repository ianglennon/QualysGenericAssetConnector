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
from app.services.source_client import fetch_all_pages

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
class FanOutResult:
    """Accumulated result of a fan-out tree traversal."""

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
) -> FanOutResult:
    """Traverse canvas endpoint tree, fan out child requests, merge results.

    DFS per root record (D-03). No DB writes (D-13). Returns flat merged records.

    Args:
        canvas_endpoints: All CanvasEndpoint records for this canvas, each with
            a .path attribute (eagerly loaded from ConnectorEndpoint or attached).
        root_records: Records fetched from the root endpoint.
        connector: Connector instance with base_url, auth credentials.
        client: Shared httpx.AsyncClient for all HTTP requests.

    Returns:
        FanOutResult with flat merged_records list and per-level stats.
    """
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
                )

    return result


async def _fan_out_level(
    parent_records: list[dict],
    parent_context: dict,
    child_endpoints: list,
    children_map: dict,
    connector,
    client,
    result: FanOutResult,
    depth: int = 1,
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

        async def _process_one_parent(
            parent_record: dict,
            sem=semaphore,
            ep_path=child_path,
            ep=child_ep,
            st=stats,
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
                        parent_record,
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
                    return []

                st.children_succeeded += 1
                st.records_fetched += len(fetch_result.records)

                # Check if this child endpoint is a leaf or has further children
                grandchild_endpoints = children_map.get(ep.id, [])
                if not grandchild_endpoints:
                    # Leaf -- merge parent context into each child record
                    merged = []
                    for child_rec in fetch_result.records:
                        merged.append(_merge_parent_context(child_rec, current_ancestor))
                    return merged
                else:
                    # Intermediate -- recurse deeper
                    await _fan_out_level(
                        parent_records=fetch_result.records,
                        parent_context=current_ancestor,
                        child_endpoints=grandchild_endpoints,
                        children_map=children_map,
                        connector=connector,
                        client=client,
                        result=result,
                        depth=depth + 1,
                    )
                    return []  # results added by recursive call

        # Run all parent records concurrently with semaphore (D-05)
        tasks = [_process_one_parent(rec) for rec in parent_records]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect leaf merged records, handle any unexpected exceptions
        for res in gather_results:
            if isinstance(res, Exception):
                stats.children_failed += 1
                result.has_failures = True
                logger.error("Unexpected fan-out error: %s", res)
            elif isinstance(res, list):
                result.merged_records.extend(res)
