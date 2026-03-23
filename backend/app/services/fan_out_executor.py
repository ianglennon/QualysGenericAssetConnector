"""Fan-out executor: tree traversal, concurrent child fetching, result merging."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class LevelStats:
    """Per-endpoint-level counters and capped failure diagnostics."""

    endpoint_id: str
    children_attempted: int = 0
    children_succeeded: int = 0
    children_failed: int = 0
    children_skipped: int = 0
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


async def execute_tree(
    canvas_endpoints: list,
    root_records: list[dict],
    connector,
    client,
) -> FanOutResult:
    """Stub -- returns empty result. Will be implemented in GREEN phase."""
    return FanOutResult()
