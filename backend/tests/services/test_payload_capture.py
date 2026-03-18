"""Tests for payload_capture utility module."""

import uuid
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.connector import Connector
from app.models.connector_endpoint import ConnectorEndpoint
from app.models.run_history import EndpointRunLog, RunHistory, RunStatus
from app.services.payload_capture import (
    BODY_TRUNCATE_BYTES,
    PAYLOAD_RETENTION_DAYS,
    capture_request,
    capture_response,
    cleanup_old_payloads,
    redact_headers,
)


# --------------- Header Redaction Tests ---------------


def test_redact_headers_bearer_token():
    headers = {"Authorization": "Bearer secret123", "Content-Type": "application/json"}
    result = redact_headers(headers, auth_type="bearer_token")
    assert result["Authorization"] == "[REDACTED]"
    assert result["Content-Type"] == "application/json"


def test_redact_headers_basic_auth():
    headers = {"Authorization": "Basic abc123", "Accept": "*/*"}
    result = redact_headers(headers, auth_type="basic_auth")
    assert result["Authorization"] == "[REDACTED]"
    assert result["Accept"] == "*/*"


def test_redact_headers_api_key_header():
    headers = {"X-API-Key": "secret", "Host": "example.com"}
    result = redact_headers(headers, auth_type="api_key_header", api_key_name="X-API-Key")
    assert result["X-API-Key"] == "[REDACTED]"
    assert result["Host"] == "example.com"


def test_redact_headers_api_key_case_insensitive():
    headers = {"X-Api-Key": "secret"}
    result = redact_headers(headers, auth_type="api_key_header", api_key_name="x-api-key")
    assert result["X-Api-Key"] == "[REDACTED]"


def test_redact_headers_qualys_mode():
    headers = {"Authorization": "Basic xyz", "Host": "qualys.com"}
    result = redact_headers(headers, auth_type="qualys")
    assert result["Authorization"] == "[REDACTED]"
    assert result["Host"] == "qualys.com"


def test_redact_headers_no_auth_header_present():
    headers = {"Content-Type": "application/json"}
    result = redact_headers(headers, auth_type="bearer_token")
    assert result == {"Content-Type": "application/json"}


def test_redact_headers_preserves_other_headers():
    headers = {
        "Authorization": "Bearer secret",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "X-Custom": "keep-me",
    }
    result = redact_headers(headers, auth_type="bearer_token")
    assert result["Authorization"] == "[REDACTED]"
    assert result["Content-Type"] == "application/json"
    assert result["Accept"] == "*/*"
    assert result["X-Custom"] == "keep-me"


# --------------- Capture Request Tests ---------------


def test_capture_request_get():
    request = httpx.Request(
        "GET",
        "https://api.example.com/data",
        headers={"Authorization": "Bearer secret"},
    )
    result = capture_request(request, auth_type="bearer_token")
    assert result["method"] == "GET"
    assert result["url"] == "https://api.example.com/data"
    assert result["headers"]["authorization"] == "[REDACTED]"
    assert result["body"] is None


def test_capture_request_post_with_body():
    body = b'{"key": "value"}'
    request = httpx.Request(
        "POST",
        "https://api.example.com/data",
        headers={"Content-Type": "application/json"},
        content=body,
    )
    result = capture_request(request, auth_type="bearer_token")
    assert result["method"] == "POST"
    assert result["body"] == '{"key": "value"}'


def test_capture_request_large_body_truncated():
    body = b"x" * (BODY_TRUNCATE_BYTES + 1000)
    request = httpx.Request(
        "POST",
        "https://api.example.com/data",
        content=body,
    )
    result = capture_request(request, auth_type="bearer_token")
    assert len(result["body"]) == BODY_TRUNCATE_BYTES


# --------------- Capture Response Tests ---------------


def test_capture_response_basic():
    response = httpx.Response(
        200,
        content=b'{"key": "value"}',
        headers={"Content-Type": "application/json"},
    )
    result = capture_response(response)
    assert result["status_code"] == 200
    assert result["body"] == '{"key": "value"}'
    assert "content-type" in result["headers"]


def test_capture_response_large_body_truncated():
    body = b"y" * (BODY_TRUNCATE_BYTES + 500)
    response = httpx.Response(200, content=body)
    result = capture_response(response)
    assert len(result["body"]) == BODY_TRUNCATE_BYTES


def test_capture_response_empty_body():
    response = httpx.Response(204, content=b"")
    result = capture_response(response)
    assert result["body"] is None
    assert result["status_code"] == 204


# --------------- Cleanup Old Payloads Tests ---------------


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_connector(db_session) -> str:
    """Create a minimal Connector and return its id."""
    cid = str(uuid.uuid4())
    db_session.execute(
        Connector.__table__.insert().values(
            id=cid,
            name="test-connector",
            base_url="https://example.com",
            auth_method="bearer_token",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    return cid


def _make_endpoint(db_session, connector_id: str) -> str:
    """Create a minimal ConnectorEndpoint and return its id."""
    eid = str(uuid.uuid4())
    db_session.execute(
        ConnectorEndpoint.__table__.insert().values(
            id=eid,
            connector_id=connector_id,
            name="test-endpoint",
            path="/test",
            is_enabled=1,
            display_order=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    return eid


def _make_run(db_session, connector_id: str) -> str:
    """Create a minimal RunHistory and return its id."""
    rid = str(uuid.uuid4())
    db_session.execute(
        RunHistory.__table__.insert().values(
            id=rid,
            connector_id=connector_id,
            status="running",
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    return rid


def _make_endpoint_run_log(db_session, run_id, endpoint_id, created_at, http_request=None, http_response=None):
    """Create an EndpointRunLog with given payload data.

    When http_request/http_response are None, they are omitted from the INSERT
    so SQLite stores SQL NULL (not the JSON text "null").
    """
    log_id = str(uuid.uuid4())
    values = {
        "id": log_id,
        "run_id": run_id,
        "endpoint_id": endpoint_id,
        "execution_order": 0,
        "records_fetched": 0,
        "records_submitted": 0,
        "records_failed": 0,
        "status": "success",
        "created_at": created_at,
    }
    if http_request is not None:
        values["http_request"] = http_request
    if http_response is not None:
        values["http_response"] = http_response
    db_session.execute(EndpointRunLog.__table__.insert().values(**values))
    db_session.commit()
    return log_id


def test_cleanup_old_payloads_nulls_old_rows(db_session):
    cid = _make_connector(db_session)
    eid = _make_endpoint(db_session, cid)
    rid = _make_run(db_session, cid)
    old_date = datetime.utcnow() - timedelta(days=20)
    log_id = _make_endpoint_run_log(
        db_session, rid, eid, old_date,
        http_request={"method": "GET"}, http_response={"status_code": 200},
    )
    count = cleanup_old_payloads(db_session)
    assert count >= 1
    row = db_session.query(EndpointRunLog).filter(EndpointRunLog.id == log_id).first()
    assert row.http_request is None
    assert row.http_response is None


def test_cleanup_old_payloads_preserves_recent(db_session):
    cid = _make_connector(db_session)
    eid = _make_endpoint(db_session, cid)
    rid = _make_run(db_session, cid)
    recent_date = datetime.utcnow() - timedelta(days=5)
    log_id = _make_endpoint_run_log(
        db_session, rid, eid, recent_date,
        http_request={"method": "GET"}, http_response={"status_code": 200},
    )
    cleanup_old_payloads(db_session)
    row = db_session.query(EndpointRunLog).filter(EndpointRunLog.id == log_id).first()
    assert row.http_request == {"method": "GET"}
    assert row.http_response == {"status_code": 200}


def test_cleanup_old_payloads_skips_already_null(db_session):
    cid = _make_connector(db_session)
    eid = _make_endpoint(db_session, cid)
    rid = _make_run(db_session, cid)
    old_date = datetime.utcnow() - timedelta(days=20)
    _make_endpoint_run_log(db_session, rid, eid, old_date, http_request=None, http_response=None)
    count = cleanup_old_payloads(db_session)
    assert count == 0


def test_cleanup_old_payloads_returns_count(db_session):
    cid = _make_connector(db_session)
    eid = _make_endpoint(db_session, cid)
    rid = _make_run(db_session, cid)
    old_date = datetime.utcnow() - timedelta(days=20)
    _make_endpoint_run_log(
        db_session, rid, eid, old_date,
        http_request={"method": "GET"}, http_response={"status_code": 200},
    )
    _make_endpoint_run_log(
        db_session, rid, eid, old_date,
        http_request={"method": "POST"}, http_response={"status_code": 201},
    )
    count = cleanup_old_payloads(db_session)
    assert count == 2
