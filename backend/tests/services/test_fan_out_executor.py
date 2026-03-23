import asyncio
import pytest
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.fan_out_executor import (
    FanOutResult,
    LevelStats,
    _merge_parent_context,
    _build_tree,
    execute_tree,
)
from app.services.template_resolver import TemplateResolutionError


@dataclass
class SourceFetchResult:
    """Local mirror of source_client.SourceFetchResult for testing without ORM imports."""
    records: list[Any]
    records_fetched: int
    pages_fetched: int
    partial: bool
    http_request: dict | None = None
    http_response: dict | None = None


# --- Fixtures ---


def _make_canvas_ep(
    id="ep-1",
    parent_ref_id=None,
    tree_order=0,
    endpoint_id="conn-ep-1",
    variable_extractions=None,
    max_concurrency=5,
    path="/default",
):
    return SimpleNamespace(
        id=id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
        endpoint_id=endpoint_id,
        variable_extractions=variable_extractions,
        max_concurrency=max_concurrency,
        path=path,
    )


def _make_connector(base_url="https://api.example.com", auth_method="bearer_token", api_key_name=None, source_retry_limit=3):
    return SimpleNamespace(
        base_url=base_url,
        auth_method=auth_method,
        api_key_name=api_key_name,
        source_retry_limit=source_retry_limit,
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


# --- execute_tree async tests ---


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_fan_out_one_child_per_parent(mock_fetch):
    """Given 3 root records and 1 child endpoint, execute_tree calls fetch_all_pages
    3 times (once per root) and returns 3 merged records."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/nodes/{name}/vms",
        variable_extractions={"name": "node"},
    )
    connector = _make_connector()
    client = AsyncMock()

    root_records = [
        {"node": "pve1"},
        {"node": "pve2"},
        {"node": "pve3"},
    ]

    async def fake_fetch(conn, url, client=None, **kwargs):
        # Return one child record per call
        return SourceFetchResult(
            records=[{"vmid": 100, "source_url": url}],
            records_fetched=1,
            pages_fetched=1,
            partial=False,
        )
    mock_fetch.side_effect = fake_fetch

    result = await execute_tree([root_ep, child_ep], root_records, connector, client)

    assert mock_fetch.call_count == 3
    assert len(result.merged_records) == 3
    # Each merged record should have parent context
    for rec in result.merged_records:
        assert "_parent.node" in rec


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_fan_out_resolves_template_variables(mock_fetch):
    """Child endpoint path /nodes/{name}/vms with variable_extractions={"name": "node"}
    and parent record {"node": "pve1"} resolves to connector.base_url + /nodes/pve1/vms."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/nodes/{name}/vms",
        variable_extractions={"name": "node"},
    )
    connector = _make_connector(base_url="https://api.example.com")
    client = AsyncMock()

    captured_urls = []

    async def fake_fetch(conn, url, client=None, **kwargs):
        captured_urls.append(url)
        return SourceFetchResult(records=[{"vmid": 100}], records_fetched=1, pages_fetched=1, partial=False)
    mock_fetch.side_effect = fake_fetch

    await execute_tree([root_ep, child_ep], [{"node": "pve1"}], connector, client)

    assert len(captured_urls) == 1
    assert captured_urls[0] == "https://api.example.com/nodes/pve1/vms"


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_semaphore_limits_concurrency(mock_fetch):
    """With max_concurrency=2 and 5 parent records, at most 2 fetch_all_pages
    calls run concurrently."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/items",
        variable_extractions={},
        max_concurrency=2,
    )
    connector = _make_connector()
    client = AsyncMock()

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def tracking_fetch(conn, url, client=None, **kwargs):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.01)  # simulate work
        async with lock:
            active -= 1
        return SourceFetchResult(records=[{"data": "ok"}], records_fetched=1, pages_fetched=1, partial=False)
    mock_fetch.side_effect = tracking_fetch

    root_records = [{"id": i} for i in range(5)]
    result = await execute_tree([root_ep, child_ep], root_records, connector, client)

    assert max_active <= 2
    assert max_active > 0  # ensure concurrency was actually tested
    assert len(result.merged_records) == 5


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_failure_isolation(mock_fetch):
    """If 1 of 3 child fetches raises Exception, the other 2 still complete
    and appear in merged_records; has_failures=True."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/items",
        variable_extractions={},
    )
    connector = _make_connector()
    client = AsyncMock()

    call_count = 0

    async def failing_fetch(conn, url, client=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise Exception("Connection timeout")
        return SourceFetchResult(records=[{"data": f"rec-{call_count}"}], records_fetched=1, pages_fetched=1, partial=False)
    mock_fetch.side_effect = failing_fetch

    root_records = [{"id": 1}, {"id": 2}, {"id": 3}]
    result = await execute_tree([root_ep, child_ep], root_records, connector, client)

    assert result.has_failures is True
    assert len(result.merged_records) == 2  # 2 out of 3 succeeded


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_partial_fetch_failure(mock_fetch):
    """If fetch_all_pages returns SourceFetchResult(partial=True), that child
    is recorded as failed with diagnostic capture."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/items",
        variable_extractions={},
    )
    connector = _make_connector()
    client = AsyncMock()

    async def partial_fetch(conn, url, client=None, **kwargs):
        return SourceFetchResult(
            records=[],
            records_fetched=0,
            pages_fetched=0,
            partial=True,
            http_request={"method": "GET", "url": url},
            http_response={"status_code": 500},
        )
    mock_fetch.side_effect = partial_fetch

    result = await execute_tree([root_ep, child_ep], [{"id": 1}], connector, client)

    assert result.has_failures is True
    assert len(result.merged_records) == 0
    # Should have stats for child endpoint
    assert len(result.level_stats) >= 1
    child_stats = [s for s in result.level_stats if s.endpoint_id == "child-1"]
    assert len(child_stats) == 1
    assert child_stats[0].children_failed == 1


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_template_resolution_skip(mock_fetch):
    """If resolve_path raises TemplateResolutionError, child is skipped
    (children_skipped incremented), has_skipped=True, other children still processed."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/nodes/{name}/vms",
        variable_extractions={"name": "node"},
    )
    connector = _make_connector()
    client = AsyncMock()

    async def fake_fetch(conn, url, client=None, **kwargs):
        return SourceFetchResult(records=[{"vmid": 100}], records_fetched=1, pages_fetched=1, partial=False)
    mock_fetch.side_effect = fake_fetch

    # First record has "node" key, second doesn't -> should skip second
    root_records = [
        {"node": "pve1"},
        {"missing_key": "no_node_field"},
    ]

    result = await execute_tree([root_ep, child_ep], root_records, connector, client)

    assert result.has_skipped is True
    assert len(result.merged_records) == 1  # only first parent produced results
    child_stats = [s for s in result.level_stats if s.endpoint_id == "child-1"]
    assert len(child_stats) == 1
    assert child_stats[0].children_skipped == 1


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_leaf_vs_intermediate(mock_fetch):
    """Root -> Child -> Grandchild chain: only grandchild records appear in
    merged_records (child is intermediate, not a leaf)."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/items",
        variable_extractions={},
    )
    grandchild_ep = _make_canvas_ep(
        id="grandchild-1", parent_ref_id="child-1", tree_order=2,
        path="/details",
        variable_extractions={},
    )
    connector = _make_connector()
    client = AsyncMock()

    call_count = 0

    async def fake_fetch(conn, url, client=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if "/items" in url:
            return SourceFetchResult(records=[{"child_data": "intermediate"}], records_fetched=1, pages_fetched=1, partial=False)
        elif "/details" in url:
            return SourceFetchResult(records=[{"leaf_data": "final"}], records_fetched=1, pages_fetched=1, partial=False)
        return SourceFetchResult(records=[], records_fetched=0, pages_fetched=0, partial=False)
    mock_fetch.side_effect = fake_fetch

    result = await execute_tree(
        [root_ep, child_ep, grandchild_ep],
        [{"root_field": "value"}],
        connector, client,
    )

    # Only grandchild (leaf) records should be in merged_records
    assert len(result.merged_records) == 1
    assert "leaf_data" in result.merged_records[0]
    # Should have parent context from child
    assert "_parent.child_data" in result.merged_records[0]
    # Should have grandparent context from root
    assert "_parent._parent.root_field" in result.merged_records[0]


@pytest.mark.asyncio
@patch("app.services.fan_out_executor.fetch_all_pages")
async def test_dfs_per_root(mock_fetch):
    """With 2 roots and 1 child endpoint, each root's children are fully traversed
    before moving to next root (DFS order verified via merged_records order)."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    child_ep = _make_canvas_ep(
        id="child-1", parent_ref_id="root-1", tree_order=1,
        path="/items",
        variable_extractions={},
        max_concurrency=1,  # Force sequential to verify order
    )
    connector = _make_connector()
    client = AsyncMock()

    async def ordered_fetch(conn, url, client=None, **kwargs):
        # Return 2 records per parent to verify grouping
        return SourceFetchResult(
            records=[{"batch": "a"}, {"batch": "b"}],
            records_fetched=2, pages_fetched=1, partial=False,
        )
    mock_fetch.side_effect = ordered_fetch

    root_records = [{"root_id": "first"}, {"root_id": "second"}]
    result = await execute_tree([root_ep, child_ep], root_records, connector, client)

    assert len(result.merged_records) == 4
    # First 2 records should have parent context from root "first"
    assert result.merged_records[0]["_parent.root_id"] == "first"
    assert result.merged_records[1]["_parent.root_id"] == "first"
    # Last 2 records should have parent context from root "second"
    assert result.merged_records[2]["_parent.root_id"] == "second"
    assert result.merged_records[3]["_parent.root_id"] == "second"


@pytest.mark.asyncio
async def test_no_children_root_is_leaf():
    """If root endpoint has no children in the tree, root records appear
    directly in merged_records."""
    root_ep = _make_canvas_ep(id="root-1", parent_ref_id=None, tree_order=0, path="/nodes")
    connector = _make_connector()
    client = AsyncMock()

    root_records = [{"node": "pve1"}, {"node": "pve2"}]
    result = await execute_tree([root_ep], root_records, connector, client)

    assert len(result.merged_records) == 2
    assert result.merged_records[0] == {"node": "pve1"}
    assert result.merged_records[1] == {"node": "pve2"}
    assert result.has_failures is False
    assert result.has_skipped is False
