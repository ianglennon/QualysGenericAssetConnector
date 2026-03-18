from unittest.mock import MagicMock
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.credential_crypto import get_crypto
from app.services.qualys_client import QualysClientError, _post_with_retries, submit_batch


def _make_connector(qualys_retry_limit=None):
    connector = MagicMock()
    connector.qualys_retry_limit = qualys_retry_limit
    return connector


def _make_config():
    crypto = get_crypto()
    config = MagicMock()
    config.api_url = "https://qualys.example.com"
    config.username = "qualys-user"
    config.encrypted_password = crypto.encrypt("secret")
    config.encrypted_token = None
    return config


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
async def test_submit_batch_success():
    requests = []
    responses = [(200, {"result": "ok"}, {})]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    config = _make_config()
    records = [{"name": "asset-1"}, {"name": "asset-2"}]

    async with httpx.AsyncClient(transport=transport) as client:
        result = await submit_batch(records, connector, config, client=client)

    assert result.submitted_count == 2
    assert result.failed_count == 0
    assert result.failures == []


@pytest.mark.asyncio
async def test_submit_batch_partial_success_parses_207():
    requests = []
    responses = [
        (
            207,
            {
                "failedRecords": [
                    {"recordIdentifier": "host-1", "errorMessage": "missing name"},
                    {"recordIdentifier": "host-2", "errorMessage": "bad address"},
                ]
            },
            {},
        )
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector()
    config = _make_config()
    records = [{"name": "asset-1"}, {"name": "asset-2"}]

    async with httpx.AsyncClient(transport=transport) as client:
        result = await submit_batch(records, connector, config, client=client)

    assert result.submitted_count == 2
    assert result.failed_count == 2
    assert [failure.record_identifier for failure in result.failures] == ["host-1", "host-2"]
    assert result.failures[0].error_message == "missing name"


@pytest.mark.asyncio
async def test_default_retry_limit_used_when_unset():
    requests = []
    responses = [
        (500, {"error": "boom"}, {}),
        (500, {"error": "boom"}, {}),
        (500, {"error": "boom"}, {}),
        (200, {"result": "ok"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector(qualys_retry_limit=None)
    config = _make_config()
    records = [{"name": "asset-1"}]

    async with httpx.AsyncClient(transport=transport) as client:
        result = await submit_batch(records, connector, config, client=client)

    assert result.submitted_count == 1
    assert len(requests) == 4


@pytest.mark.asyncio
async def test_retry_limit_respected_when_set():
    requests = []
    responses = [
        (500, {"error": "boom"}, {}),
        (500, {"error": "boom"}, {}),
        (200, {"result": "ok"}, {}),
    ]
    transport = _make_transport(responses, requests)
    connector = _make_connector(qualys_retry_limit=1)
    config = _make_config()
    records = [{"name": "asset-1"}]

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(QualysClientError):
            await submit_batch(records, connector, config, client=client)

    assert len(requests) == 2


# --------------- QualysClientError.response Tests ---------------


def test_qualys_client_error_with_response():
    resp = httpx.Response(403, content=b"forbidden")
    exc = QualysClientError("test", response=resp)
    assert exc.response is resp


def test_qualys_client_error_without_response():
    exc = QualysClientError("test")
    assert exc.response is None


# --------------- _post_with_retries response attachment Tests ---------------


@pytest.mark.asyncio
async def test_post_with_retries_attaches_response_on_4xx():
    def handler(request):
        return httpx.Response(403, content=b'{"error": "forbidden"}', request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(QualysClientError) as exc_info:
            await _post_with_retries(client, "https://qualys.example.com/api", None, {}, retry_limit=1)
        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 403


@pytest.mark.asyncio
async def test_post_with_retries_attaches_response_on_5xx():
    responses = [(500, b"error"), (500, b"error")]
    idx = [0]

    def handler(request):
        i = idx[0]
        idx[0] += 1
        status, body = responses[i] if i < len(responses) else responses[-1]
        return httpx.Response(status, content=body, request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(QualysClientError) as exc_info:
            await _post_with_retries(client, "https://qualys.example.com/api", None, {}, retry_limit=1)
        assert exc_info.value.response is not None
        assert exc_info.value.response.status_code == 500


@pytest.mark.asyncio
async def test_post_with_retries_no_response_on_timeout():
    def handler(request):
        raise httpx.ReadTimeout("timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(QualysClientError) as exc_info:
            await _post_with_retries(client, "https://qualys.example.com/api", None, {}, retry_limit=0)
        assert exc_info.value.response is None
