"""Payload capture utilities: header redaction, body truncation, retention cleanup."""

import logging
from datetime import datetime, timedelta

import httpx

from app.models.run_history import EndpointRunLog
from app.models.run_event import RunEvent

logger = logging.getLogger(__name__)

BODY_TRUNCATE_BYTES = 16_384  # 16KB
PAYLOAD_RETENTION_DAYS = 14


def redact_headers(
    headers: dict[str, str],
    auth_type: str,
    api_key_name: str | None = None,
) -> dict[str, str]:
    """Redact auth header values based on connector config.

    For Qualys mode, pass auth_type="qualys" (always redacts Authorization).
    Source mode: pass auth_type from connector (bearer_token, basic_auth, api_key_header).
    """
    redacted = dict(headers)
    if auth_type in ("bearer_token", "basic_auth", "qualys"):
        for key in list(redacted.keys()):
            if key.lower() == "authorization":
                redacted[key] = "[REDACTED]"
    elif auth_type == "api_key_header" and api_key_name:
        for key in list(redacted.keys()):
            if key.lower() == api_key_name.lower():
                redacted[key] = "[REDACTED]"
    return redacted


def _truncate_body(content: bytes) -> str | None:
    """Truncate bytes to BODY_TRUNCATE_BYTES and decode as UTF-8."""
    if not content:
        return None
    return content[:BODY_TRUNCATE_BYTES].decode("utf-8", errors="replace")


def capture_request(
    request: httpx.Request,
    auth_type: str,
    api_key_name: str | None = None,
    body_override: str | None = None,
) -> dict:
    """Capture an httpx.Request as a JSON-serializable dict with redacted headers.

    When body_override is provided, it replaces the actual request body content.
    This is used for Qualys submissions where the body contains asset records
    that should not be captured -- replaced with record count metadata instead.
    """
    headers = dict(request.headers)
    redacted = redact_headers(headers, auth_type, api_key_name)

    if body_override is not None:
        body = body_override
    else:
        body = _truncate_body(request.content) if request.content else None

    return {
        "method": request.method,
        "url": str(request.url),
        "headers": redacted,
        "body": body,
    }


def capture_response(response: httpx.Response) -> dict:
    """Capture an httpx.Response as a JSON-serializable dict."""
    body = _truncate_body(response.content) if response.content else None

    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body,
    }


def cleanup_old_payloads(db) -> int:
    """NULL out http_request and http_response on old EndpointRunLog rows.

    Returns the number of rows cleaned.
    """
    cutoff = datetime.utcnow() - timedelta(days=PAYLOAD_RETENTION_DAYS)
    rows_updated = (
        db.query(EndpointRunLog)
        .filter(
            EndpointRunLog.created_at < cutoff,
            (EndpointRunLog.http_request.isnot(None))
            | (EndpointRunLog.http_response.isnot(None)),
        )
        .update(
            {"http_request": None, "http_response": None},
            synchronize_session=False,
        )
    )
    db.commit()

    # Also delete old run_events rows beyond retention period
    events_deleted = (
        db.query(RunEvent)
        .filter(RunEvent.timestamp < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Cleaned %d payload rows, %d event rows", rows_updated, events_deleted)

    return rows_updated
