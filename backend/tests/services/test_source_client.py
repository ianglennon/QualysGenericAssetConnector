from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
import httpx
import pytest

from app.schemas.pagination import (
    CursorPagination,
    LinkHeaderPagination,
    OffsetLimitPagination,
    PageNumberPagination,
)
from app.services.source_client import (
    FetchResult,
    SourceFetchResult,
    fetch_all_pages,
    _parse_retry_after,
    _fetch_with_retries,
    RETRY_AFTER_CAP_SECONDS,
)


def _make_connector(
    base_url="https://api.example.com/items",
    source_retry_limit=None,
):
    connector = MagicMock()
    connector.base_url = base_url
    connector.source_retry_limit = source_retry_limit
    connector.auth_method = "bearer_token"
    connector.encrypted_token = None
    connector.encrypted_username = None
    connector.encrypted_password = None
    connector.api_key_name = None
    connector.encrypted_api_key = None
    connector.pagination_config = None
    return connector


def _make_transport(responses, requests):
    def handler(request):
        requests.append(request)
        status, payload, headers = responses.pop(0)
        return httpx.Response(
            status_code=status,
            json=payload,
            headers=headers,
            request=request,
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_cursor_pagination_fetches_all_pages():
    requests = []
    responses = [
        (200, {"records": [{"id": 1}], "next_cursor": "abc"}, {}),
        (200, {"records": [{"id": 2}], "next_cursor": None}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = CursorPagination(cursor_field="next_cursor", cursor_param="cursor", page_size=2)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], client=client)

    assert result.records_fetched == 2
    assert result.pages_fetched == 2
    assert result.partial is False
    assert requests[0].url.params.get("cursor") is None
    assert requests[0].url.params.get("page_size") == "2"
    assert requests[1].url.params.get("cursor") == "abc"


@pytest.mark.asyncio
async def test_offset_limit_pagination_fetches_all_pages():
    requests = []
    responses = [
        (200, {"records": [{"id": 1}, {"id": 2}]}, {}),
        (200, {"records": [{"id": 3}]}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = OffsetLimitPagination(offset_param="offset", limit_param="limit", page_size=2)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], client=client)

    assert result.records_fetched == 3
    assert result.pages_fetched == 2
    assert result.partial is False
    assert requests[0].url.params.get("offset") == "0"
    assert requests[0].url.params.get("limit") == "2"
    assert requests[1].url.params.get("offset") == "2"


@pytest.mark.asyncio
async def test_link_header_pagination_fetches_all_pages():
    requests = []
    responses = [
        (
            200,
            {"records": [{"id": 1}]},
            {"Link": '<https://api.example.com/items?page=2>; rel="next"'},
        ),
        (200, {"records": [{"id": 2}]}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector(base_url="https://api.example.com/items")
    strategy = LinkHeaderPagination()

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], client=client)

    assert result.records_fetched == 2
    assert result.pages_fetched == 2
    assert result.partial is False
    assert str(requests[0].url) == "https://api.example.com/items"
    assert str(requests[1].url) == "https://api.example.com/items?page=2"


@pytest.mark.asyncio
async def test_page_number_pagination_fetches_all_pages():
    requests = []
    responses = [
        (200, {"records": [{"id": 1}, {"id": 2}]}, {}),
        (200, {"records": [{"id": 3}]}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = PageNumberPagination(page_param="page", page_size_param="page_size", page_size=2)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], client=client)

    assert result.records_fetched == 3
    assert result.pages_fetched == 2
    assert result.partial is False
    assert requests[0].url.params.get("page") == "1"
    assert requests[0].url.params.get("page_size") == "2"
    assert requests[1].url.params.get("page") == "2"


@pytest.mark.asyncio
async def test_retry_success_on_transient_error():
    requests = []
    responses = [
        (500, {"error": "boom"}, {}),
        (200, {"records": [{"id": 1}]}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = PageNumberPagination(page_param="page", page_size_param="page_size", page_size=10)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], retry_limit=1, client=client)

    assert result.records_fetched == 1
    assert result.pages_fetched == 1
    assert result.partial is False
    assert len(requests) == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_marks_partial():
    requests = []
    responses = [
        (200, {"records": [{"id": 1}, {"id": 2}]}, {}),
        (500, {"error": "boom"}, {}),
        (500, {"error": "boom"}, {}),
        (500, {"error": "boom"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = OffsetLimitPagination(offset_param="offset", limit_param="limit", page_size=2)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], retry_limit=2, client=client)

    assert result.records_fetched == 2
    assert result.pages_fetched == 1
    assert result.partial is True


def test_fetch_result_dataclass_exists():
    """FetchResult has response and last_failed_response fields."""
    fr = FetchResult(response=None, last_failed_response=None)
    assert fr.response is None
    assert fr.last_failed_response is None


def test_source_fetch_result_has_capture_fields():
    """SourceFetchResult has http_request and http_response fields defaulting to None."""
    sfr = SourceFetchResult(records=[], records_fetched=0, pages_fetched=0, partial=False)
    assert sfr.http_request is None
    assert sfr.http_response is None


# --- Capture tests (Phase 29) ---


@pytest.mark.asyncio
async def test_capture_on_http_failure_no_strategy():
    """HTTP 500 on single-page (no pagination) captures request and response."""
    requests = []
    responses = [
        (500, {"error": "bad"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", retry_limit=0, client=client)

    assert result.partial is True
    assert result.http_request is not None
    assert result.http_request["method"] == "GET"
    assert "https://api.example.com/items" in result.http_request["url"]
    assert result.http_response is not None
    assert result.http_response["status_code"] == 500


@pytest.mark.asyncio
async def test_capture_on_http_failure_cursor_pagination():
    """Page 2 fails with HTTP 500 during cursor pagination -- captures request/response, preserves page 1 records."""
    requests = []
    responses = [
        (200, {"records": [{"id": 1}], "next_cursor": "abc"}, {}),
        (500, {"error": "fail"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    strategy = CursorPagination(cursor_field="next_cursor", cursor_param="cursor", page_size=2)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", pagination_strategies=[strategy], retry_limit=0, client=client)

    assert result.partial is True
    assert result.records_fetched == 1
    assert result.http_request is not None
    assert result.http_response is not None
    assert result.http_response["status_code"] == 500


@pytest.mark.asyncio
async def test_no_capture_on_connection_error():
    """Connection error (no HTTP exchange) produces no capture data."""
    def error_handler(request):
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(error_handler)
    connector = _make_connector()

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", retry_limit=0, client=client)

    assert result.partial is True
    assert result.http_request is None
    assert result.http_response is None


@pytest.mark.asyncio
async def test_capture_redacts_auth_header():
    """Bearer token Authorization header is redacted in captured request."""
    requests = []
    responses = [
        (500, {"error": "unauthorized"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()

    # Mock _build_headers to return an Authorization header without needing real crypto
    with patch("app.services.source_client._build_headers", return_value={"Authorization": "Bearer secret-token"}):
        async with httpx.AsyncClient(transport=transport) as client:
            result = await fetch_all_pages(connector, url="https://api.example.com/items", retry_limit=0, client=client)

    assert result.partial is True
    assert result.http_request is not None
    # The Authorization header should be redacted
    headers = result.http_request["headers"]
    auth_found = False
    for key in headers:
        if key.lower() == "authorization":
            assert headers[key] == "[REDACTED]"
            auth_found = True
    assert auth_found, "Authorization header not found in captured request"


@pytest.mark.asyncio
async def test_successful_fetch_no_capture():
    """Successful fetch produces no capture data."""
    requests = []
    responses = [
        (200, {"records": [{"id": 1}]}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()

    async with httpx.AsyncClient(transport=transport) as client:
        result = await fetch_all_pages(connector, url="https://api.example.com/items", retry_limit=0, client=client)

    assert result.partial is False
    assert result.records_fetched == 1
    assert result.http_request is None
    assert result.http_response is None


# --- 429 Retry-After tests (Phase 41, Plan 01) ---


class TestParseRetryAfter:
    """Tests for _parse_retry_after header parsing."""

    def test_parse_retry_after_integer(self):
        """Integer Retry-After header '30' returns 30.0."""
        response = httpx.Response(429, headers={"retry-after": "30"}, request=httpx.Request("GET", "https://example.com"))
        result = _parse_retry_after(response)
        assert result == 30.0

    def test_parse_retry_after_http_date(self):
        """HTTP-date Retry-After returns positive float seconds delta."""
        future = datetime.now(timezone.utc) + timedelta(seconds=45)
        http_date = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response = httpx.Response(429, headers={"retry-after": http_date}, request=httpx.Request("GET", "https://example.com"))
        result = _parse_retry_after(response)
        assert result is not None
        # Should be roughly 45 seconds (allow some tolerance for test execution time)
        assert 40.0 <= result <= 50.0

    def test_parse_retry_after_missing(self):
        """Missing Retry-After header returns None."""
        response = httpx.Response(429, headers={}, request=httpx.Request("GET", "https://example.com"))
        result = _parse_retry_after(response)
        assert result is None

    def test_parse_retry_after_invalid(self):
        """Invalid/garbage Retry-After header returns None."""
        response = httpx.Response(429, headers={"retry-after": "not-a-number-or-date"}, request=httpx.Request("GET", "https://example.com"))
        result = _parse_retry_after(response)
        assert result is None

    def test_parse_retry_after_past_date(self):
        """Past HTTP-date returns 0.0 (clamped to non-negative)."""
        past = datetime.now(timezone.utc) - timedelta(seconds=60)
        http_date = past.strftime("%a, %d %b %Y %H:%M:%S GMT")
        response = httpx.Response(429, headers={"retry-after": http_date}, request=httpx.Request("GET", "https://example.com"))
        result = _parse_retry_after(response)
        assert result == 0.0


class TestFetchWithRetries429:
    """Tests for 429 handling in _fetch_with_retries."""

    @pytest.mark.asyncio
    async def test_429_with_retry_after_sleeps_and_retries(self):
        """429 with Retry-After '5' sleeps 5 seconds then retries."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, headers={"retry-after": "5"}, request=request)
            return httpx.Response(200, json={"ok": True}, request=request)

        transport = httpx.MockTransport(handler)
        with patch("app.services.source_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                result = await _fetch_with_retries(client, "https://example.com/api", {}, None, 3)

        assert result.response is not None
        assert result.response.status_code == 200
        # Should have slept with the Retry-After value (5 seconds)
        mock_sleep.assert_any_call(5.0)

    @pytest.mark.asyncio
    async def test_429_with_retry_after_exceeding_cap_returns_immediately(self):
        """429 with Retry-After '120' (>60s cap) returns failure without sleeping."""
        def handler(request):
            return httpx.Response(429, headers={"retry-after": "120"}, request=request)

        transport = httpx.MockTransport(handler)
        with patch("app.services.source_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                result = await _fetch_with_retries(client, "https://example.com/api", {}, None, 3)

        assert result.response is None
        # Should NOT have slept at all (returned immediately)
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_429_without_retry_after_falls_back_to_exponential(self):
        """429 without Retry-After falls back to exponential backoff."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(429, headers={}, request=request)
            return httpx.Response(200, json={"ok": True}, request=request)

        transport = httpx.MockTransport(handler)
        with patch("app.services.source_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            async with httpx.AsyncClient(transport=transport) as client:
                result = await _fetch_with_retries(client, "https://example.com/api", {}, None, 3)

        assert result.response is not None
        assert result.response.status_code == 200
        # Should have used exponential backoff (0.1 * 2^0 = 0.1 for first attempt)
        mock_sleep.assert_called_once_with(0.1)


# --- resolve_pagination_config tests (Phase 54, Plan 01) ---

from app.services.source_client import resolve_pagination_config


class TestResolvePaginationConfig:
    def test_none_returns_none(self):
        assert resolve_pagination_config(None) is None

    def test_empty_dict_returns_none(self):
        assert resolve_pagination_config({}) is None

    def test_empty_list_returns_none(self):
        assert resolve_pagination_config([]) is None

    def test_valid_cursor_dict(self):
        result = resolve_pagination_config({
            "strategy": "cursor",
            "cursor_field": "next",
            "cursor_param": "after",
        })
        assert result is not None
        assert len(result) == 1
        assert result[0].strategy == "cursor"

    def test_valid_offset_list(self):
        result = resolve_pagination_config([{
            "strategy": "offset_limit",
            "limit_param": "limit",
            "offset_param": "offset",
            "page_size": 100,
        }])
        assert result is not None
        assert len(result) == 1
        assert result[0].strategy == "offset_limit"

    def test_invalid_strategy_returns_none(self):
        assert resolve_pagination_config({"strategy": "invalid"}) is None

    def test_wrong_type_returns_none(self):
        assert resolve_pagination_config("not_a_dict") is None
