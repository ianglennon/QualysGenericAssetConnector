"""Phase 60: API response tests for base-anchored fields.

These stubs define the API contract for Phase 60 schema changes.
They should FAIL until Plan 60-01 Task 1 implements the production code.

Requirements covered:
  - RUN-01: API response includes base-anchored fields in run detail
  - RUN-03: List endpoint returns base_records_submitted
"""
import pytest


def test_run_detail_base_fields(client, db_session):
    """RUN-01: GET /api/v1/runs/{id} response includes base_records_total,
    base_records_enriched, base_records_submitted, base_records_failed,
    base_records_full, base_records_partial, base_records_base_only fields.

    Verify: Create a RunHistory row with base fields populated, fetch via API,
    assert response JSON contains all 7 base_records_* keys.
    """
    from app.schemas.run_history import RunHistoryResponse
    fields = RunHistoryResponse.model_fields
    assert 'base_records_total' in fields, \
        "RunHistoryResponse missing base_records_total (RUN-01)"
    assert 'base_records_submitted' in fields, \
        "RunHistoryResponse missing base_records_submitted (RUN-01)"
    pytest.fail("STUB: Full API integration test not yet implemented -- Plan 60-01 must make this pass")


def test_list_runs_base_submitted(client, db_session):
    """RUN-03: GET /api/v1/runs response items include base_records_submitted
    field for use by frontend list views.

    Verify: Create RunHistory rows, list via API, assert response items
    contain base_records_submitted key.
    """
    from app.schemas.run_history import RunHistoryResponse
    fields = RunHistoryResponse.model_fields
    assert 'base_records_full' in fields, \
        "RunHistoryResponse missing base_records_full (RUN-03)"
    assert 'base_records_base_only' in fields, \
        "RunHistoryResponse missing base_records_base_only (RUN-03)"
    pytest.fail("STUB: Full API integration test not yet implemented -- Plan 60-01 must make this pass")
