"""Fan-out executor: tree traversal, concurrent child fetching, result merging."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LevelStats:
    endpoint_id: str
    # stub - no methods yet


@dataclass
class FanOutResult:
    pass  # stub


def _merge_parent_context(child_record: dict, ancestor_context: dict) -> dict:
    return {}  # stub


def _build_tree(canvas_endpoints: list) -> dict:
    return {}  # stub
