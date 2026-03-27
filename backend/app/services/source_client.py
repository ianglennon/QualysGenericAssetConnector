import asyncio
import email.utils
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)
from app.models.connector import Connector
from app.services.payload_capture import capture_request, capture_response
from app.schemas.pagination import (
    CursorPagination,
    LinkHeaderPagination,
    OffsetLimitPagination,
    PageNumberPagination,
    PaginationStrategy,
)
from app.services.connector_service import HTTPX_TIMEOUT, _build_headers

DEFAULT_RETRY_LIMIT = 3
DEFAULT_BACKOFF_SECONDS = 0.1
RETRY_AFTER_CAP_SECONDS = 60


@dataclass
class FetchResult:
    """Internal result from _fetch_with_retries."""
    response: httpx.Response | None
    last_failed_response: httpx.Response | None = None


@dataclass
class SourceFetchResult:
    records: list[Any]
    records_fetched: int
    pages_fetched: int
    partial: bool
    http_request: dict | None = None
    http_response: dict | None = None


def _extract_records(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("records", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _extract_records_with_root(payload: Any, data_root: str | None) -> list[Any]:
    """Extract records, using data_root if configured, else fallback to heuristic."""
    if data_root:
        from app.services.path_resolver import resolve_path
        unwrapped = resolve_path(payload, data_root) if isinstance(payload, dict) else None
        if isinstance(unwrapped, list):
            return unwrapped
        # data_root didn't resolve -- fall back to standard extraction
    return _extract_records(payload)


def _parse_next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip()
        match = re.search(r"<([^>]+)>", section)
        if not match:
            continue
        if "rel=" not in section:
            continue
        rel_value = section.split("rel=", 1)[1].strip().strip("\"")
        if rel_value == "next":
            return match.group(1)
    return None


def _backoff_seconds(attempt: int) -> float:
    return DEFAULT_BACKOFF_SECONDS * (2 ** (attempt - 1))


def _parse_retry_after(response: httpx.Response) -> float | None:
    """Parse Retry-After header, return seconds to wait or None."""
    header = response.headers.get("retry-after")
    if not header:
        return None
    # Try integer seconds first
    try:
        seconds = int(header)
        return float(seconds)
    except ValueError:
        pass
    # Try HTTP-date format (RFC 7231)
    try:
        parsed = email.utils.parsedate_to_datetime(header)
        delta = (parsed - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, delta)
    except (ValueError, TypeError):
        return None


async def _fetch_with_retries(
    client: httpx.AsyncClient,
    url: str,
    headers: dict,
    params: dict | None,
    retry_limit: int,
) -> FetchResult:
    attempts = 0
    last_failed_response: httpx.Response | None = None
    while True:
        try:
            logger.debug("Source API request: GET %s params=%s", url, params)
            response = await client.get(url, headers=headers, params=params)
            logger.debug(
                "Source API response: status=%d size=%d",
                response.status_code,
                len(response.content),
            )
            if 200 <= response.status_code < 300:
                return FetchResult(response=response)
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                last_failed_response = exc.response
            attempts += 1
            logger.debug(
                "Source API request failed (attempt %d/%d): %s",
                attempts, retry_limit, exc,
            )
            if attempts > retry_limit:
                return FetchResult(response=None, last_failed_response=last_failed_response)
            # 429 Retry-After handling
            if (isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429):
                retry_seconds = _parse_retry_after(exc.response)
                if retry_seconds is not None:
                    if retry_seconds > RETRY_AFTER_CAP_SECONDS:
                        logger.debug(
                            "Retry-After %ss exceeds cap %ss, exhausting retries",
                            retry_seconds, RETRY_AFTER_CAP_SECONDS,
                        )
                        return FetchResult(response=None, last_failed_response=last_failed_response)
                    logger.debug("429 with Retry-After: sleeping %ss", retry_seconds)
                    await asyncio.sleep(retry_seconds)
                    continue
            await asyncio.sleep(_backoff_seconds(attempts))


def _maybe_capture(
    fetch_result: FetchResult,
    auth_type: str,
    api_key_name: str | None,
) -> tuple[dict | None, dict | None]:
    """Capture request/response from a failed fetch, or return (None, None)."""
    if fetch_result.last_failed_response is not None:
        return (
            capture_request(fetch_result.last_failed_response.request, auth_type, api_key_name),
            capture_response(fetch_result.last_failed_response),
        )
    return None, None


def _resolve_pagination_strategies(
    connector: Connector,
    pagination_strategies: list[PaginationStrategy] | None,
) -> list[PaginationStrategy]:
    if pagination_strategies is not None:
        return pagination_strategies
    return []


async def fetch_all_pages(
    connector: Connector,
    url: str,
    pagination_strategies: list[PaginationStrategy] | None = None,
    retry_limit: int | None = None,
    client: httpx.AsyncClient | None = None,
    data_root: str | None = None,
) -> SourceFetchResult:
    headers = _build_headers(connector)
    effective_retry_limit = (
        retry_limit
        if retry_limit is not None
        else (connector.source_retry_limit if connector.source_retry_limit is not None else DEFAULT_RETRY_LIMIT)
    )
    strategies = _resolve_pagination_strategies(connector, pagination_strategies)
    strategy = strategies[0] if strategies else None

    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=HTTPX_TIMEOUT, verify=connector.verify_ssl)
        close_client = True

    try:
        logger.debug(
            "Starting source fetch: url=%s strategy=%s",
            url,
            type(strategy).__name__ if strategy else "none",
        )
        if strategy is None:
            fetch_result = await _fetch_with_retries(
                client,
                url,
                headers,
                None,
                effective_retry_limit,
            )
            if fetch_result.response is None:
                logger.debug("Source fetch failed: no response after retries")
                req_capture, resp_capture = _maybe_capture(fetch_result, connector.auth_method, connector.api_key_name)
                return SourceFetchResult([], 0, 0, True, req_capture, resp_capture)
            payload = fetch_result.response.json()
            records = _extract_records_with_root(payload, data_root)
            logger.debug("Source fetch complete: %d records in 1 page", len(records))
            return SourceFetchResult(records, len(records), 1, False)

        if isinstance(strategy, CursorPagination):
            return await _fetch_cursor_pages(
                client,
                url,
                headers,
                strategy,
                effective_retry_limit,
                connector.auth_method,
                connector.api_key_name,
                data_root,
            )
        if isinstance(strategy, OffsetLimitPagination):
            return await _fetch_offset_limit_pages(
                client,
                url,
                headers,
                strategy,
                effective_retry_limit,
                connector.auth_method,
                connector.api_key_name,
                data_root,
            )
        if isinstance(strategy, LinkHeaderPagination):
            return await _fetch_link_header_pages(
                client,
                url,
                headers,
                effective_retry_limit,
                connector.auth_method,
                connector.api_key_name,
                data_root,
            )
        if isinstance(strategy, PageNumberPagination):
            return await _fetch_page_number_pages(
                client,
                url,
                headers,
                strategy,
                effective_retry_limit,
                connector.auth_method,
                connector.api_key_name,
                data_root,
            )

        return SourceFetchResult([], 0, 0, False)
    finally:
        if close_client:
            await client.aclose()


async def _fetch_cursor_pages(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    strategy: CursorPagination,
    retry_limit: int,
    auth_type: str,
    api_key_name: str | None,
    data_root: str | None = None,
) -> SourceFetchResult:
    records: list[Any] = []
    pages_fetched = 0
    cursor = None

    while True:
        params: dict[str, Any] = {}
        if cursor is not None:
            params[strategy.cursor_param] = cursor
        if strategy.page_size is not None:
            params["page_size"] = strategy.page_size

        fetch_result = await _fetch_with_retries(
            client, base_url, headers, params, retry_limit
        )
        if fetch_result.response is None:
            req_capture, resp_capture = _maybe_capture(fetch_result, auth_type, api_key_name)
            return SourceFetchResult(records, len(records), pages_fetched, True, req_capture, resp_capture)

        payload = fetch_result.response.json()
        page_records = _extract_records_with_root(payload, data_root)
        records.extend(page_records)
        pages_fetched += 1

        next_cursor = payload.get(strategy.cursor_field) if isinstance(payload, dict) else None
        if not next_cursor:
            return SourceFetchResult(records, len(records), pages_fetched, False)
        cursor = next_cursor


async def _fetch_offset_limit_pages(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    strategy: OffsetLimitPagination,
    retry_limit: int,
    auth_type: str,
    api_key_name: str | None,
    data_root: str | None = None,
) -> SourceFetchResult:
    records: list[Any] = []
    pages_fetched = 0
    offset = 0
    limit = strategy.page_size

    while True:
        params: dict[str, Any] = {strategy.offset_param: offset}
        if limit is not None:
            params[strategy.limit_param] = limit

        fetch_result = await _fetch_with_retries(
            client, base_url, headers, params, retry_limit
        )
        if fetch_result.response is None:
            req_capture, resp_capture = _maybe_capture(fetch_result, auth_type, api_key_name)
            return SourceFetchResult(records, len(records), pages_fetched, True, req_capture, resp_capture)

        payload = fetch_result.response.json()
        page_records = _extract_records_with_root(payload, data_root)
        records.extend(page_records)
        pages_fetched += 1

        if not page_records:
            return SourceFetchResult(records, len(records), pages_fetched, False)
        if limit is not None and len(page_records) < limit:
            return SourceFetchResult(records, len(records), pages_fetched, False)

        offset += len(page_records) if limit is None else limit


async def _fetch_link_header_pages(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    retry_limit: int,
    auth_type: str,
    api_key_name: str | None,
    data_root: str | None = None,
) -> SourceFetchResult:
    records: list[Any] = []
    pages_fetched = 0
    next_url = base_url

    while True:
        fetch_result = await _fetch_with_retries(
            client, next_url, headers, None, retry_limit
        )
        if fetch_result.response is None:
            req_capture, resp_capture = _maybe_capture(fetch_result, auth_type, api_key_name)
            return SourceFetchResult(records, len(records), pages_fetched, True, req_capture, resp_capture)

        payload = fetch_result.response.json()
        page_records = _extract_records_with_root(payload, data_root)
        records.extend(page_records)
        pages_fetched += 1

        next_link = _parse_next_link(fetch_result.response.headers.get("link"))
        if not next_link:
            return SourceFetchResult(records, len(records), pages_fetched, False)
        next_url = urljoin(next_url, next_link)


async def _fetch_page_number_pages(
    client: httpx.AsyncClient,
    base_url: str,
    headers: dict,
    strategy: PageNumberPagination,
    retry_limit: int,
    auth_type: str,
    api_key_name: str | None,
    data_root: str | None = None,
) -> SourceFetchResult:
    records: list[Any] = []
    pages_fetched = 0
    page = 1

    while True:
        params: dict[str, Any] = {strategy.page_param: page}
        if strategy.page_size is not None:
            params[strategy.page_size_param] = strategy.page_size

        fetch_result = await _fetch_with_retries(
            client, base_url, headers, params, retry_limit
        )
        if fetch_result.response is None:
            req_capture, resp_capture = _maybe_capture(fetch_result, auth_type, api_key_name)
            return SourceFetchResult(records, len(records), pages_fetched, True, req_capture, resp_capture)

        payload = fetch_result.response.json()
        page_records = _extract_records_with_root(payload, data_root)
        records.extend(page_records)
        pages_fetched += 1

        if not page_records:
            return SourceFetchResult(records, len(records), pages_fetched, False)
        if strategy.page_size is not None and len(page_records) < strategy.page_size:
            return SourceFetchResult(records, len(records), pages_fetched, False)

        page += 1
