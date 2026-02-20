import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.models.connector import Connector
from app.models.qualys_config import QualysConfig
from app.services.credential_crypto import get_crypto
from app.services.connector_service import HTTPX_TIMEOUT

DEFAULT_RETRY_LIMIT = 3
DEFAULT_BACKOFF_SECONDS = 0.1
IMPORT_PATH = "/qps/rest/2.0/import/thirdpartyasset"


@dataclass
class QualysFailure:
    record_identifier: str
    error_message: str


@dataclass
class QualysSubmitResult:
    submitted_count: int
    failed_count: int
    failures: list[QualysFailure]


class QualysClientError(Exception):
    def __init__(
        self,
        message: str,
        error_type: str = "qualys_error",
        status_code: int | None = None,
        error_context: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code
        self.error_context = error_context or {}


def _qualys_url(api_url: str) -> str:
    return api_url.rstrip("/") + IMPORT_PATH


def _backoff_seconds(attempt: int) -> float:
    return DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1))


def _effective_retry_limit(connector: Connector, retry_limit: int | None) -> int:
    if retry_limit is not None:
        return retry_limit
    if connector.qualys_retry_limit is not None:
        return connector.qualys_retry_limit
    return DEFAULT_RETRY_LIMIT


def _decrypt_secret(config: QualysConfig) -> str:
    crypto = get_crypto()
    if config.encrypted_password:
        return crypto.decrypt(config.encrypted_password)
    if config.encrypted_token:
        return crypto.decrypt(config.encrypted_token)
    raise QualysClientError(
        "Qualys credentials are not configured",
        error_type="qualys_missing_credentials",
    )


def _parse_failure_items(payload: Any) -> list[QualysFailure]:
    if not isinstance(payload, dict):
        return []

    failure_lists = []
    for key in ("failedRecords", "failures", "errors", "rejected"):
        if isinstance(payload.get(key), list):
            failure_lists = payload[key]
            break

    if not failure_lists and isinstance(payload.get("data"), dict):
        nested = payload["data"]
        for key in ("failedRecords", "failures", "errors", "rejected"):
            if isinstance(nested.get(key), list):
                failure_lists = nested[key]
                break

    failures: list[QualysFailure] = []
    for item in failure_lists:
        if isinstance(item, dict):
            record_identifier = (
                item.get("recordIdentifier")
                or item.get("record_id")
                or item.get("recordId")
                or item.get("id")
                or item.get("sourceNativeKey")
                or item.get("identifier")
                or ""
            )
            error_message = (
                item.get("errorMessage")
                or item.get("message")
                or item.get("error")
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


async def _post_with_retries(
    client: httpx.AsyncClient,
    url: str,
    auth: httpx.BasicAuth,
    payload: dict,
    retry_limit: int,
) -> httpx.Response:
    attempts = 0
    while True:
        try:
            response = await client.post(url, json=payload, auth=auth)
        except httpx.TimeoutException as exc:
            attempts += 1
            if attempts > retry_limit:
                raise QualysClientError(
                    "Qualys request timed out",
                    error_type="qualys_timeout",
                    error_context={"attempts": attempts},
                ) from exc
            await asyncio.sleep(_backoff_seconds(attempts))
            continue
        except httpx.RequestError as exc:
            attempts += 1
            if attempts > retry_limit:
                raise QualysClientError(
                    "Qualys request failed",
                    error_type="qualys_network_error",
                    error_context={"error": str(exc)},
                ) from exc
            await asyncio.sleep(_backoff_seconds(attempts))
            continue

        if response.status_code in (200, 207):
            return response

        if 500 <= response.status_code < 600:
            attempts += 1
            if attempts > retry_limit:
                raise QualysClientError(
                    "Qualys server error",
                    error_type="qualys_server_error",
                    status_code=response.status_code,
                    error_context={"response": response.text},
                )
            await asyncio.sleep(_backoff_seconds(attempts))
            continue

        raise QualysClientError(
            "Qualys request failed",
            error_type="qualys_http_error",
            status_code=response.status_code,
            error_context={"response": response.text},
        )


async def submit_batch(
    records: list[dict],
    connector: Connector,
    config: QualysConfig,
    retry_limit: int | None = None,
    client: httpx.AsyncClient | None = None,
) -> QualysSubmitResult:
    if not records:
        return QualysSubmitResult(submitted_count=0, failed_count=0, failures=[])

    secret = _decrypt_secret(config)
    auth = httpx.BasicAuth(config.username, secret)
    effective_retry_limit = _effective_retry_limit(connector, retry_limit)
    url = _qualys_url(config.api_url)

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=HTTPX_TIMEOUT)
        close_client = True

    try:
        response = await _post_with_retries(
            client,
            url,
            auth,
            {"data": records},
            effective_retry_limit,
        )
        if response.status_code == 207:
            payload = response.json() if response.content else {}
            failures = _parse_failure_items(payload)
            return QualysSubmitResult(
                submitted_count=len(records),
                failed_count=len(failures),
                failures=failures,
            )

        return QualysSubmitResult(
            submitted_count=len(records),
            failed_count=0,
            failures=[],
        )
    finally:
        if close_client:
            await client.aclose()
