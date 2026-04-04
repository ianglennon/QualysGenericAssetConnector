"""Phase 60: API response tests for base-anchored fields.

Requirements covered:
  - RUN-01: RunHistoryResponse schema includes all 7 base_records_* fields
  - RUN-03: RunHistoryResponse includes base_records_submitted for list views
  - Gap 4: Schema serializes all 7 base_records_* fields correctly
  - Gap 5: base_records_submitted present in schema used by list endpoint
"""
from datetime import datetime

import pytest


# ---------------------------------------------------------------------------
# RUN-01: RunHistoryResponse schema has all 7 base_records_* fields (Gap 4)
# ---------------------------------------------------------------------------

def test_run_detail_schema_contains_all_seven_base_fields():
    """RUN-01: RunHistoryResponse must expose all 7 base_records_* fields.

    Verify: Instantiate RunHistoryResponse with all 7 base fields populated
    and confirm the serialized dict contains each field with the correct value.
    """
    from app.schemas.run_history import RunHistoryResponse

    # All 7 fields must be present in the schema definition
    fields = RunHistoryResponse.model_fields
    expected_fields = [
        "base_records_total",
        "base_records_enriched",
        "base_records_submitted",
        "base_records_failed",
        "base_records_full",
        "base_records_partial",
        "base_records_base_only",
    ]
    for field_name in expected_fields:
        assert field_name in fields, f"RunHistoryResponse missing field: {field_name} (RUN-01)"

    # Instantiate with values and check serialization
    response = RunHistoryResponse(
        id="run-001",
        connector_id="conn-001",
        status="success",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        records_fetched=20,
        records_submitted=18,
        records_failed=2,
        base_records_total=10,
        base_records_enriched=8,
        base_records_submitted=9,
        base_records_failed=1,
        base_records_full=5,
        base_records_partial=3,
        base_records_base_only=2,
        error_type=None,
        error_message=None,
        error_context=None,
    )

    data = response.model_dump()
    assert data["base_records_total"] == 10
    assert data["base_records_enriched"] == 8
    assert data["base_records_submitted"] == 9
    assert data["base_records_failed"] == 1
    assert data["base_records_full"] == 5
    assert data["base_records_partial"] == 3
    assert data["base_records_base_only"] == 2


def test_run_detail_schema_base_fields_default_to_none():
    """RUN-01: All 7 base_records_* fields in RunHistoryResponse default to None
    for backward compatibility with pre-v1.6 runs.
    """
    from app.schemas.run_history import RunHistoryResponse

    response = RunHistoryResponse(
        id="run-legacy",
        connector_id="conn-001",
        status="success",
        started_at=datetime.utcnow(),
        finished_at=None,
        records_fetched=5,
        records_submitted=5,
        records_failed=0,
        error_type=None,
        error_message=None,
        error_context=None,
    )

    data = response.model_dump()
    for field_name in [
        "base_records_total", "base_records_enriched", "base_records_submitted",
        "base_records_failed", "base_records_full", "base_records_partial",
        "base_records_base_only",
    ]:
        assert data[field_name] is None, (
            f"Expected {field_name}=None for legacy run but got {data[field_name]}"
        )


# ---------------------------------------------------------------------------
# RUN-03: base_records_submitted present in schema used by list views (Gap 5)
# ---------------------------------------------------------------------------

def test_list_runs_schema_includes_base_records_submitted(db_session):
    """RUN-03: RunHistoryResponse (used by both list and detail endpoints)
    must include base_records_submitted for frontend list views to display
    the correct primary stat.

    Verify: Create a RunHistory row with base_records_submitted set, round-trip
    it through the schema, and confirm the value is present in the response.
    """
    from app.models.run_history import RunHistory, RunStatus
    from app.models.connector import Connector
    from app.routers.runs import _to_response

    connector = Connector(name="List Test", base_url="https://api.example.com", auth_method="bearer_token")
    db_session.add(connector)
    db_session.commit()
    db_session.refresh(connector)

    run = RunHistory(
        connector_id=connector.id,
        status=RunStatus.success,
        started_at=datetime.utcnow(),
        records_fetched=15,
        records_submitted=12,
        records_failed=3,
        base_records_total=15,
        base_records_submitted=12,
        base_records_full=10,
        base_records_partial=2,
        base_records_base_only=3,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    response = _to_response(run, failures=[])
    data = response.model_dump()

    assert data["base_records_submitted"] == 12, (
        f"Expected base_records_submitted=12 in list view response but got {data['base_records_submitted']}"
    )
    assert data["base_records_full"] == 10
    assert data["base_records_base_only"] == 3


def test_list_runs_schema_maps_base_records_submitted_via_to_response(db_session):
    """RUN-03 (fixture version): Same as above but uses db_session fixture.

    Verifies _to_response maps base_records_submitted from model to response
    (the function called by both list_runs and list_connector_runs endpoints).
    """
    from app.models.run_history import RunHistory, RunStatus
    from app.models.connector import Connector
    from app.routers.runs import _to_response

    connector = Connector(name="List Test 2", base_url="https://api.example.com", auth_method="bearer_token")
    db_session.add(connector)
    db_session.commit()
    db_session.refresh(connector)

    run = RunHistory(
        connector_id=connector.id,
        status=RunStatus.success,
        started_at=datetime.utcnow(),
        records_fetched=6,
        records_submitted=5,
        records_failed=1,
        base_records_total=6,
        base_records_submitted=5,
        base_records_full=3,
        base_records_partial=2,
        base_records_base_only=1,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    response = _to_response(run, failures=[])
    data = response.model_dump()

    assert data["base_records_submitted"] == 5, (
        f"_to_response did not map base_records_submitted: got {data['base_records_submitted']}"
    )
    assert data["base_records_full"] == 3
    assert data["base_records_partial"] == 2
    assert data["base_records_base_only"] == 1
