import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from qualys_client import QualysClient
from qualys_client.exceptions import (
    QualysUnauthorizedError,
    QualysForbiddenError,
    QualysTokenFetchError,
    QualysTokenRefreshError,
    QualysRetryError,
    QualysHTTPError,
    QualysConnectionError,
    QualysClientError as PkgClientError,
)
from qualys_client.exceptions import QualysJSONError
from qualys_client.platform import detect_platform, derive_urls

from app.models.connector import Connector
from app.models.qualys_config import QualysConfig
from app.services.credential_crypto import get_crypto
from app.services.qualys_formatter import format_qualys_payload

logger = logging.getLogger(__name__)

IMPORT_PATH = "/rest/2.0/am/connector/asset/data/sync"


@dataclass
class QualysFailure:
    record_identifier: str
    error_message: str


@dataclass
class QualysSubmitResult:
    submitted_count: int
    failed_count: int
    failures: list[QualysFailure]


class QualysAdapterError(Exception):
    def __init__(
        self,
        message: str,
        error_type: str = "qualys_error",
        status_code: int | None = None,
        error_context: dict | None = None,
        response: None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.error_context = error_context or {}
        self.response = response


def _create_client(config: QualysConfig) -> QualysClient:
    crypto = get_crypto()
    password = crypto.decrypt(config.encrypted_password)
    return QualysClient(username=config.username, password=password)


def _gateway_url(config: QualysConfig) -> str:
    platform = detect_platform(config.username)
    _, gateway_url = derive_urls(platform)
    return gateway_url.rstrip("/") + IMPORT_PATH


def _extract_error_context(exc: Exception) -> dict:
    context: dict = {}
    if hasattr(exc, "request_info") and exc.request_info:
        context["http_request"] = {
            "method": exc.request_info.get("method"),
            "url": exc.request_info.get("url"),
            "headers": exc.request_info.get("headers", {}),
            "body": exc.request_info.get("body_preview"),
        }
    if hasattr(exc, "response_info") and exc.response_info:
        context["http_response"] = {
            "status_code": exc.response_info.get("status_code"),
            "headers": exc.response_info.get("headers", {}),
            "body": exc.response_info.get("body"),
        }
    return context


def _decrypt_secret(config: QualysConfig) -> str:
    crypto = get_crypto()
    if config.encrypted_password:
        return crypto.decrypt(config.encrypted_password)
    raise QualysAdapterError(
        "Qualys credentials are not configured",
        error_type="qualys_missing_credentials",
    )


def _parse_failure_items(payload: Any) -> list[QualysFailure]:
    """Parse failures from Qualys CSAM response.

    Qualys CSAM may return failures in various formats:
    - assetsError object with array of failed assets
    - Standard error arrays
    """
    if not isinstance(payload, dict):
        return []

    failure_lists = []

    # Check for assetsError (CSAM-specific)
    if "assetsError" in payload and isinstance(payload["assetsError"], dict):
        assets_error = payload["assetsError"]
        for key in ("failed", "errors", "rejected"):
            if isinstance(assets_error.get(key), list):
                failure_lists = assets_error[key]
                break

    # Fall back to standard error arrays
    if not failure_lists:
        for key in ("failedRecords", "failures", "errors", "rejected", "failed"):
            if isinstance(payload.get(key), list):
                failure_lists = payload[key]
                break

    if not failure_lists and isinstance(payload.get("data"), dict):
        nested = payload["data"]
        for key in ("failedRecords", "failures", "errors", "rejected", "failed"):
            if isinstance(nested.get(key), list):
                failure_lists = nested[key]
                break

    failures: list[QualysFailure] = []
    for item in failure_lists:
        if isinstance(item, dict):
            record_identifier = (
                item.get("sourceNativeKey")  # Qualys CSAM uses this
                or item.get("recordIdentifier")
                or item.get("record_id")
                or item.get("recordId")
                or item.get("id")
                or item.get("identifier")
                or item.get("hostName")  # Fallback to hostName
                or ""
            )
            error_message = (
                item.get("errorMessage")
                or item.get("error")
                or item.get("message")
                or item.get("reason")
                or "Unknown error"
            )
        else:
            record_identifier = str(item)
            error_message = "Unknown error"

        failures.append(
            QualysFailure(
                record_identifier=str(record_identifier),
                error_message=str(error_message),
            )
        )

    return failures


async def submit_batch(
    records: list[dict],
    connector: Connector,
    config: QualysConfig,
) -> QualysSubmitResult:
    if not records:
        return QualysSubmitResult(submitted_count=0, failed_count=0, failures=[])

    payload = format_qualys_payload(
        records=records,
        connector_name=connector.name,
        connector_uuid=config.connector_uuid,
    )
    url = _gateway_url(config)
    client = _create_client(config)

    try:
        response = await asyncio.to_thread(client.post, url, body=payload)

        if response.status_code == 207:
            try:
                body = response.json()
            except QualysJSONError:
                body = {}
            failures = _parse_failure_items(body)
            logger.debug(
                "Qualys batch partial success: submitted=%d failed=%d",
                len(records), len(failures),
            )
            return QualysSubmitResult(
                submitted_count=len(records),
                failed_count=len(failures),
                failures=failures,
            )

        logger.debug("Qualys batch success: submitted=%d", len(records))
        return QualysSubmitResult(
            submitted_count=len(records),
            failed_count=0,
            failures=[],
        )

    except QualysUnauthorizedError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_auth_failed",
            status_code=401,
            error_context=_extract_error_context(exc),
        ) from exc
    except QualysForbiddenError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_forbidden",
            status_code=403,
            error_context=_extract_error_context(exc),
        ) from exc
    except QualysTokenFetchError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_token_error",
            error_context={},
        ) from exc
    except QualysTokenRefreshError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_token_refresh_error",
            error_context={},
        ) from exc
    except QualysRetryError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_retry_exhausted",
            error_context={"attempts": exc.attempts},
        ) from exc
    except QualysHTTPError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_http_error",
            status_code=exc.status_code,
            error_context=_extract_error_context(exc),
        ) from exc
    except QualysConnectionError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_network_error",
            error_context={},
        ) from exc
    except PkgClientError as exc:
        raise QualysAdapterError(
            str(exc),
            error_type="qualys_error",
            error_context={},
        ) from exc
    finally:
        client.close()
