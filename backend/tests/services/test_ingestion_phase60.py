"""Phase 60: Base-anchored stats and enrichment status tests.

These stubs define the behavioral contract for Phase 60 ingestion changes.
They should FAIL until Plan 60-01 Task 2 implements the production code.

Requirements covered:
  - DEG-02: _run_canvas populates base_records_total/enriched/submitted/failed
  - DEG-03: _run_canvas populates enrichment counters (full/partial/base_only)
  - RUN-02: EndpointRunLog includes endpoint_role field
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.db.base import Base


@pytest.fixture(autouse=True)
def db_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr("app.services.ingestion_service.SessionLocal", TestSession)
    db = TestSession()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_base_anchored_stats(db_session):
    """DEG-02: After _run_canvas completes, RunHistory has base_records_total,
    base_records_enriched, base_records_submitted, base_records_failed populated.

    Verify: Create a connector with a canvas (base + 1 downstream endpoint),
    run ingestion, assert RunHistory row has non-null base_records_total and
    base_records_submitted.
    """
    from app.models.run_history import RunHistory
    # Stub: assert the column exists on the model
    assert hasattr(RunHistory, 'base_records_total'), \
        "RunHistory model missing base_records_total column (DEG-02)"
    assert hasattr(RunHistory, 'base_records_enriched'), \
        "RunHistory model missing base_records_enriched column (DEG-02)"
    assert hasattr(RunHistory, 'base_records_submitted'), \
        "RunHistory model missing base_records_submitted column (DEG-02)"
    assert hasattr(RunHistory, 'base_records_failed'), \
        "RunHistory model missing base_records_failed column (DEG-02)"
    pytest.fail("STUB: Behavioral test not yet implemented -- Plan 60-01 must make this pass")


def test_enrichment_counters(db_session):
    """DEG-03: After _run_canvas completes, RunHistory has enrichment breakdown
    counters: base_records_full, base_records_partial, base_records_base_only.

    Verify: Run ingestion with a canvas that has downstream endpoints,
    some records get all downstream data (full), some get partial, some get none.
    Assert the three counters sum to base_records_total.
    """
    from app.models.run_history import RunHistory
    assert hasattr(RunHistory, 'base_records_full'), \
        "RunHistory model missing base_records_full column (DEG-03)"
    assert hasattr(RunHistory, 'base_records_partial'), \
        "RunHistory model missing base_records_partial column (DEG-03)"
    assert hasattr(RunHistory, 'base_records_base_only'), \
        "RunHistory model missing base_records_base_only column (DEG-03)"
    pytest.fail("STUB: Behavioral test not yet implemented -- Plan 60-01 must make this pass")


def test_endpoint_role_assignment(db_session):
    """RUN-02: EndpointRunLog records include endpoint_role field set to
    'upstream', 'base', or 'downstream' based on classify_endpoints output.

    Verify: After _run_canvas, each EndpointRunLog has a non-null endpoint_role
    matching its position relative to the base endpoint.
    """
    from app.models.run_history import EndpointRunLog
    assert hasattr(EndpointRunLog, 'endpoint_role'), \
        "EndpointRunLog model missing endpoint_role column (RUN-02)"
    pytest.fail("STUB: Behavioral test not yet implemented -- Plan 60-01 must make this pass")
