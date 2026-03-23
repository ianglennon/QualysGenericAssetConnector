import pytest
from types import SimpleNamespace
from app.services.fan_out_executor import (
    FanOutResult,
    LevelStats,
    _merge_parent_context,
    _build_tree,
)


# --- Fixtures ---


def _make_canvas_ep(
    id="ep-1",
    parent_ref_id=None,
    tree_order=0,
    endpoint_id="conn-ep-1",
    variable_extractions=None,
    max_concurrency=5,
):
    return SimpleNamespace(
        id=id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
        endpoint_id=endpoint_id,
        variable_extractions=variable_extractions,
        max_concurrency=max_concurrency,
    )


# --- _merge_parent_context tests ---


def test_merge_single_level():
    result = _merge_parent_context(
        {"vmid": 100, "name": "web01"},
        {"node": "pve1", "status": "online"},
    )
    assert result == {
        "vmid": 100,
        "name": "web01",
        "_parent.node": "pve1",
        "_parent.status": "online",
    }


def test_merge_two_levels():
    result = _merge_parent_context(
        {"iface": "eth0"},
        {"vmid": 100, "_parent.node": "pve1"},
    )
    assert result == {
        "iface": "eth0",
        "_parent.vmid": 100,
        "_parent._parent.node": "pve1",
    }


def test_merge_empty_ancestor():
    result = _merge_parent_context({"id": 1}, {})
    assert result == {"id": 1}


# --- _build_tree tests ---


def test_build_tree_groups_by_parent():
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None)
    child_ep = _make_canvas_ep(id="child-1", parent_ref_id="root-1")
    tree = _build_tree([root_ep, child_ep])
    assert None in tree
    assert "root-1" in tree
    assert tree[None] == [root_ep]
    assert tree["root-1"] == [child_ep]


def test_build_tree_sorts_by_tree_order():
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0)
    child_a = _make_canvas_ep(id="child-a", parent_ref_id="root-1", tree_order=2)
    child_b = _make_canvas_ep(id="child-b", parent_ref_id="root-1", tree_order=1)
    tree = _build_tree([root_ep, child_a, child_b])
    assert tree["root-1"] == [child_b, child_a]


# --- LevelStats tests ---


def test_level_stats_record_failure():
    stats = LevelStats(endpoint_id="ep-1")
    stats.record_failure({"error": "timeout"})
    assert stats.children_failed == 1
    assert len(stats.failure_diagnostics) == 1
    assert stats.failure_diagnostics[0] == {"error": "timeout"}


def test_level_stats_diagnostic_cap():
    stats = LevelStats(endpoint_id="ep-1")
    for i in range(51):
        stats.record_failure({"error": f"fail-{i}"})
    assert stats.children_failed == 51
    assert len(stats.failure_diagnostics) == 50


def test_level_stats_record_skip():
    stats = LevelStats(endpoint_id="ep-1")
    stats.record_skip()
    stats.record_skip()
    assert stats.children_skipped == 2


# --- FanOutResult tests ---


def test_fan_out_result_defaults():
    result = FanOutResult()
    assert result.merged_records == []
    assert result.level_stats == []
    assert result.has_failures is False
    assert result.has_skipped is False
