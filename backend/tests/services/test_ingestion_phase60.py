"""Phase 60: Base-anchored stats and enrichment status tests.

Requirements covered:
  - DEG-02: RunHistory has base_records_total/enriched/submitted/failed columns
  - DEG-03: RunHistory has enrichment counters (full/partial/base_only) that sum
             to base_records_total
  - RUN-02: EndpointRunLog.endpoint_role accepts 'base', 'downstream', 'upstream' values
  - Gap 6: FanOutResult enrichment classification in _execute_tree_base_aware
  - Gap 7: submitted_total uses root_log.records_submitted, not sum of non-root logs
  - Gap 8: LevelStats http_request/http_response fields exist
  - Gap 9: _get_or_create_stats creates LevelStats per downstream endpoint
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app.db.base import Base

# Import all models so their tables are registered with Base.metadata
import app.models.connector  # noqa: F401
import app.models.connector_endpoint  # noqa: F401
import app.models.run_history  # noqa: F401
import app.models.canvas  # noqa: F401
import app.models.canvas_endpoint  # noqa: F401
import app.models.field_mapping  # noqa: F401
import app.models.user  # noqa: F401


@pytest.fixture(autouse=True)
def _patch_session(monkeypatch, engine):
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr("app.services.ingestion_service.SessionLocal", TestSession)


# ---------------------------------------------------------------------------
# DEG-02: RunHistory base-anchored columns exist and accept values (Gap 1)
# ---------------------------------------------------------------------------

def test_base_anchored_stats_columns_exist_and_persist(db_session):
    """DEG-02: RunHistory has base_records_total/enriched/submitted/failed columns.

    Verify: Create a RunHistory row with all four base-anchored stat columns
    populated and confirm they round-trip through the DB correctly.
    """
    from app.models.run_history import RunHistory, RunStatus
    from app.models.connector import Connector

    connector = Connector(name="Test", base_url="https://api.example.com", auth_method="bearer_token")
    db_session.add(connector)
    db_session.commit()
    db_session.refresh(connector)

    run = RunHistory(
        connector_id=connector.id,
        status=RunStatus.success,
        started_at=datetime.utcnow(),
        records_fetched=10,
        records_submitted=8,
        records_failed=2,
        base_records_total=10,
        base_records_enriched=7,
        base_records_submitted=8,
        base_records_failed=2,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    assert run.base_records_total == 10, "base_records_total not persisted correctly"
    assert run.base_records_enriched == 7, "base_records_enriched not persisted correctly"
    assert run.base_records_submitted == 8, "base_records_submitted not persisted correctly"
    assert run.base_records_failed == 2, "base_records_failed not persisted correctly"


# ---------------------------------------------------------------------------
# DEG-03: Enrichment counters exist, persist, and sum to total (Gap 2)
# ---------------------------------------------------------------------------

def test_enrichment_counters_sum_to_total(db_session):
    """DEG-03: base_records_full + base_records_partial + base_records_base_only
    should sum to base_records_total when all are populated.

    Verify: Persist a RunHistory with all three enrichment counters set and
    confirm they are retrievable and sum correctly.
    """
    from app.models.run_history import RunHistory, RunStatus
    from app.models.connector import Connector

    connector = Connector(name="Enrich Test", base_url="https://api.example.com", auth_method="bearer_token")
    db_session.add(connector)
    db_session.commit()
    db_session.refresh(connector)

    total = 12
    full = 5
    partial = 4
    base_only = 3

    run = RunHistory(
        connector_id=connector.id,
        status=RunStatus.partial_success,
        started_at=datetime.utcnow(),
        records_fetched=total,
        records_submitted=total,
        records_failed=0,
        base_records_total=total,
        base_records_full=full,
        base_records_partial=partial,
        base_records_base_only=base_only,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    assert run.base_records_full == full
    assert run.base_records_partial == partial
    assert run.base_records_base_only == base_only

    computed_sum = run.base_records_full + run.base_records_partial + run.base_records_base_only
    assert computed_sum == total, (
        f"Enrichment counters do not sum to total: {full}+{partial}+{base_only}={computed_sum}, expected {total}"
    )


# ---------------------------------------------------------------------------
# RUN-02: EndpointRunLog.endpoint_role column accepts valid values (Gap 3)
# ---------------------------------------------------------------------------

def test_endpoint_role_column_accepts_valid_values(db_session):
    """RUN-02: EndpointRunLog.endpoint_role accepts 'base', 'downstream', 'upstream'.

    Verify: Create EndpointRunLog rows with each role and confirm they persist
    and are retrievable.
    """
    from app.models.run_history import RunHistory, RunStatus, EndpointRunLog
    from app.models.connector import Connector
    from app.models.connector_endpoint import ConnectorEndpoint

    connector = Connector(name="Role Test", base_url="https://api.example.com", auth_method="bearer_token")
    db_session.add(connector)
    db_session.commit()
    db_session.refresh(connector)

    ep_base = ConnectorEndpoint(connector_id=connector.id, name="base-ep", path="/base", is_enabled=True, display_order=0)
    ep_down = ConnectorEndpoint(connector_id=connector.id, name="down-ep", path="/down", is_enabled=True, display_order=1)
    db_session.add_all([ep_base, ep_down])
    db_session.commit()
    db_session.refresh(ep_base)
    db_session.refresh(ep_down)

    run = RunHistory(
        connector_id=connector.id,
        status=RunStatus.success,
        started_at=datetime.utcnow(),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    log_base = EndpointRunLog(
        run_id=run.id,
        endpoint_id=ep_base.id,
        execution_order=0,
        status="success",
        endpoint_role="base",
    )
    log_down = EndpointRunLog(
        run_id=run.id,
        endpoint_id=ep_down.id,
        execution_order=1,
        status="success",
        endpoint_role="downstream",
    )
    db_session.add_all([log_base, log_down])
    db_session.commit()
    db_session.refresh(log_base)
    db_session.refresh(log_down)

    assert log_base.endpoint_role == "base", f"Expected 'base' but got '{log_base.endpoint_role}'"
    assert log_down.endpoint_role == "downstream", f"Expected 'downstream' but got '{log_down.endpoint_role}'"


# ---------------------------------------------------------------------------
# Gap 6: FanOutResult enrichment classification in _execute_tree_base_aware
# ---------------------------------------------------------------------------

def _make_canvas_ep(id, parent_ref_id=None, tree_order=0, path="/default",
                    exclusion_rules=None, variable_extractions=None,
                    data_root=None, pagination_config=None, max_concurrency=5):
    return SimpleNamespace(
        id=id,
        parent_ref_id=parent_ref_id,
        tree_order=tree_order,
        path=path,
        exclusion_rules=exclusion_rules,
        variable_extractions=variable_extractions,
        data_root=data_root,
        pagination_config=pagination_config,
        max_concurrency=max_concurrency,
    )


def _make_connector(base_url="https://api.example.com"):
    return SimpleNamespace(
        base_url=base_url,
        auth_method="bearer_token",
        api_key_name=None,
        source_retry_limit=3,
    )


def test_single_endpoint_canvas_classifies_all_as_enrichment_full():
    """Gap 6 (single-endpoint): When a canvas has only one endpoint (root == base,
    no downstream), all records must be classified as enrichment_full.

    This tests the fast-path in _execute_tree_base_aware where
    len(upstream_path) == 1 and not downstream_ids.
    """
    from app.services.fan_out_executor import execute_tree

    base_ep = _make_canvas_ep(id="ep-base", path="/assets")
    canvas_endpoints = [base_ep]
    root_records = [{"id": "a1"}, {"id": "a2"}, {"id": "a3"}]
    connector = _make_connector()

    from unittest.mock import AsyncMock, patch
    mock_client = AsyncMock()

    result = asyncio.get_event_loop().run_until_complete(
        execute_tree(
            canvas_endpoints=canvas_endpoints,
            root_records=root_records,
            connector=connector,
            client=mock_client,
            base_canvas_endpoint_id="ep-base",
            mappings_by_ce={},
        )
    )

    assert result.enrichment_full == 3, (
        f"Single-endpoint canvas: expected enrichment_full=3 but got {result.enrichment_full}"
    )
    assert result.enrichment_partial == 0, (
        f"Single-endpoint canvas: expected enrichment_partial=0 but got {result.enrichment_partial}"
    )
    assert result.enrichment_base_only == 0, (
        f"Single-endpoint canvas: expected enrichment_base_only=0 but got {result.enrichment_base_only}"
    )
    assert result.base_records_total == 3


def test_multi_endpoint_canvas_classifies_enrichment_correctly():
    """Gap 6 (multi-endpoint): For a canvas with base + downstream endpoint,
    records that get downstream data are classified as full; those with empty
    downstream response are base_only.

    This tests the per-base-record classification loop in _execute_tree_base_aware.
    """
    from app.services.fan_out_executor import execute_tree
    from unittest.mock import AsyncMock, patch
    from app.services.source_client import SourceFetchResult

    base_ep = _make_canvas_ep(id="ep-base", path="/assets", tree_order=0)
    down_ep = _make_canvas_ep(id="ep-down", parent_ref_id="ep-base",
                              path="/assets/details", tree_order=1)
    canvas_endpoints = [base_ep, down_ep]
    root_records = [{"id": "a1"}, {"id": "a2"}]
    connector = _make_connector()

    mock_client = AsyncMock()

    def make_fetch_result(records):
        return SourceFetchResult(
            records=records,
            records_fetched=len(records),
            pages_fetched=1,
            partial=False,
            http_request={"method": "GET", "url": "/test"},
            http_response={"status_code": 200},
        )

    # a1 gets downstream data (full), a2 gets empty response (base_only)
    fetch_results = iter([
        make_fetch_result([{"detail": "info-for-a1"}]),  # downstream for a1 -> data
        make_fetch_result([]),                            # downstream for a2 -> empty
    ])

    async def mock_fetch_all_pages(*args, **kwargs):
        return next(fetch_results)

    async def _run():
        with patch("app.services.fan_out_executor.fetch_all_pages", side_effect=mock_fetch_all_pages), \
             patch("app.services.fan_out_executor.resolve_pagination_config", return_value=[]):
            return await execute_tree(
                canvas_endpoints=canvas_endpoints,
                root_records=root_records,
                connector=connector,
                client=mock_client,
                base_canvas_endpoint_id="ep-base",
                mappings_by_ce={},
            )

    result = asyncio.run(_run())

    total_classified = result.enrichment_full + result.enrichment_partial + result.enrichment_base_only
    assert total_classified == 2, (
        f"Total classified should be 2, got full={result.enrichment_full} "
        f"partial={result.enrichment_partial} base_only={result.enrichment_base_only}"
    )
    # a1 has downstream data => full
    assert result.enrichment_full >= 1, (
        f"Expected at least 1 full-enrichment record, got {result.enrichment_full}"
    )


# ---------------------------------------------------------------------------
# Gap 7: submitted_total uses root_log.records_submitted
# ---------------------------------------------------------------------------

def test_ingestion_service_uses_root_log_for_submitted_total(db_session):
    """Gap 7: In _run_canvas, submitted_total must equal root_log.records_submitted.

    The bug was that submitted_total was the sum of non-root logs (all zero).
    After the fix, root_log.records_submitted holds the actual submission count.

    Verify: Grep for the fixed pattern in ingestion_service source.
    """
    import inspect
    from app.services import ingestion_service

    source = inspect.getsource(ingestion_service)

    # The fix: use root_log.records_submitted directly
    assert "submitted_total = root_log.records_submitted" in source, (
        "ingestion_service.py does not use root_log.records_submitted for submitted_total "
        "(Gap 7: bug fix required)"
    )

    # The old buggy pattern must NOT be present
    assert "sum(\n        log.records_submitted for log in logs if log != root_log\n    )" not in source, (
        "ingestion_service.py still sums non-root logs for submitted_total (old bug pattern)"
    )


# ---------------------------------------------------------------------------
# Gap 8: LevelStats has http_request/http_response fields
# ---------------------------------------------------------------------------

def test_level_stats_has_http_detail_fields():
    """Gap 8: LevelStats dataclass must have http_request and http_response fields.

    _traverse_downstream populates them from the first SourceFetchResult.
    """
    from app.services.fan_out_executor import LevelStats

    stats = LevelStats(endpoint_id="ep-test")

    assert hasattr(stats, "http_request"), "LevelStats missing http_request field"
    assert hasattr(stats, "http_response"), "LevelStats missing http_response field"
    assert stats.http_request is None, "LevelStats.http_request should default to None"
    assert stats.http_response is None, "LevelStats.http_response should default to None"

    # Should accept dict values
    stats.http_request = {"method": "GET", "url": "/test"}
    stats.http_response = {"status_code": 200, "body": "{}"}
    assert stats.http_request["method"] == "GET"
    assert stats.http_response["status_code"] == 200


# ---------------------------------------------------------------------------
# Gap 9: _get_or_create_stats creates LevelStats per downstream endpoint
# ---------------------------------------------------------------------------

def test_get_or_create_stats_creates_and_reuses_level_stats():
    """Gap 9: _get_or_create_stats must create a LevelStats per unique endpoint_id,
    and return the existing instance on subsequent calls for the same endpoint_id.
    """
    from app.services.fan_out_executor import FanOutResult, LevelStats, _get_or_create_stats

    result = FanOutResult()

    # First call: creates new LevelStats
    stats_a = _get_or_create_stats(result, "ep-1")
    assert isinstance(stats_a, LevelStats), "Expected LevelStats instance"
    assert stats_a.endpoint_id == "ep-1"
    assert len(result.level_stats) == 1

    # Second call with same ID: returns existing
    stats_a_again = _get_or_create_stats(result, "ep-1")
    assert stats_a_again is stats_a, "Expected same LevelStats instance to be returned"
    assert len(result.level_stats) == 1  # still 1

    # Different ID: creates new entry
    stats_b = _get_or_create_stats(result, "ep-2")
    assert stats_b is not stats_a
    assert stats_b.endpoint_id == "ep-2"
    assert len(result.level_stats) == 2

    # Mutations on stats_a are visible through the result
    stats_a.children_attempted += 5
    assert result.level_stats[0].children_attempted == 5
