import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.services.credential_crypto import get_crypto
from app.services.qualys_adapter import (
    QualysAdapterError,
    QualysSubmitResult,
    _decrypt_secret,
    _extract_error_context,
    _gateway_url,
    submit_batch,
)
from qualys_client.exceptions import (
    QualysConnectionError,
    QualysForbiddenError,
    QualysHTTPError,
    QualysRetryError,
    QualysTokenFetchError,
    QualysTokenRefreshError,
    QualysUnauthorizedError,
)


def _make_connector():
    connector = MagicMock()
    connector.name = "test-connector"
    return connector


def _make_config():
    crypto = get_crypto()
    config = MagicMock()
    config.username = "quays2ab1"  # US2 platform (char '2' at index 5)
    config.encrypted_password = crypto.encrypt("secret")
    config.connector_uuid = "test-uuid-1234"
    return config


# --------------- submit_batch success ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
async def test_submit_batch_success(mock_create_client, mock_gateway_url):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.post = MagicMock(return_value=mock_response)
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()
    records = [{"name": "asset-1"}, {"name": "asset-2"}]

    result = await submit_batch(records, connector, config)

    assert result.submitted_count == 2
    assert result.failed_count == 0
    assert result.failures == []
    mock_gateway_url.assert_called_once_with(config)
    mock_client.close.assert_called_once()


# --------------- submit_batch uses asyncio.to_thread ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_submit_batch_uses_to_thread(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_to_thread.return_value = mock_response
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()
    records = [{"name": "asset-1"}]

    result = await submit_batch(records, connector, config)

    assert mock_to_thread.call_count == 1
    assert mock_to_thread.call_args[0][0] is mock_client.post
    assert result.submitted_count == 1


# --------------- submit_batch 207 partial success ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
async def test_submit_batch_partial_success_parses_207(mock_create_client, mock_gateway_url):
    mock_response = MagicMock()
    mock_response.status_code = 207
    mock_response.json.return_value = {
        "failedRecords": [
            {"recordIdentifier": "host-1", "errorMessage": "missing name"},
            {"recordIdentifier": "host-2", "errorMessage": "bad address"},
        ]
    }
    mock_client = MagicMock()
    mock_client.post = MagicMock(return_value=mock_response)
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()
    records = [{"name": "asset-1"}, {"name": "asset-2"}]

    result = await submit_batch(records, connector, config)

    assert result.submitted_count == 2
    assert result.failed_count == 2
    assert result.failures[0].record_identifier == "host-1"
    assert result.failures[0].error_message == "missing name"
    assert result.failures[1].record_identifier == "host-2"
    assert result.failures[1].error_message == "bad address"


# --------------- submit_batch empty records ---------------


@pytest.mark.asyncio
async def test_submit_batch_empty_records():
    connector = _make_connector()
    config = _make_config()

    result = await submit_batch([], connector, config)

    assert result.submitted_count == 0
    assert result.failed_count == 0
    assert result.failures == []


# --------------- Exception mapping tests (SVC-02) ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_unauthorized(mock_to_thread, mock_create_client, mock_gateway_url):
    exc = QualysUnauthorizedError("401 bad creds")
    exc.request_info = {"method": "POST", "url": "https://gw.example.com", "headers": {}}
    exc.response_info = {"status_code": 401, "headers": {}, "body": "unauthorized"}
    mock_to_thread.side_effect = exc
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_auth_failed"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_forbidden(mock_to_thread, mock_create_client, mock_gateway_url):
    exc = QualysForbiddenError("403 denied")
    exc.request_info = {"method": "POST", "url": "https://gw.example.com", "headers": {}}
    exc.response_info = {"status_code": 403, "headers": {}, "body": "forbidden"}
    mock_to_thread.side_effect = exc
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_forbidden"
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_token_fetch(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysTokenFetchError("token failed")
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_token_error"


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_token_refresh(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysTokenRefreshError("refresh failed")
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_token_refresh_error"


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_retry_exhausted(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysRetryError("retries exceeded", attempts=5)
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_retry_exhausted"
    assert exc_info.value.error_context["attempts"] == 5


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_http_error(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysHTTPError(
        "500 error",
        request_info={"method": "POST", "url": "https://gw.example.com/api", "headers": {}, "body_preview": "..."},
        response_info={"status_code": 500, "headers": {}, "body": "server error", "elapsed_ms": 100},
    )
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_http_error"
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_exception_mapping_connection_error(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysConnectionError("network down")
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert exc_info.value.error_type == "qualys_network_error"


# --------------- Diagnostic dict extraction (SVC-04) ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_diagnostic_dicts_from_http_error(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysHTTPError(
        "500 error",
        request_info={"method": "POST", "url": "https://gateway.qg2.apps.qualys.com/api", "headers": {}, "body_preview": "..."},
        response_info={"status_code": 500, "headers": {}, "body": "server error", "elapsed_ms": 100},
    )
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError) as exc_info:
        await submit_batch([{"name": "asset-1"}], connector, config)

    exc = exc_info.value
    assert exc.error_context["http_request"]["method"] == "POST"
    assert "gateway.qg2.apps.qualys.com" in exc.error_context["http_request"]["url"]
    assert exc.error_context["http_response"]["status_code"] == 500
    assert exc.error_context["http_response"]["body"] == "server error"


# --------------- _extract_error_context with no info ---------------


def test_extract_error_context_no_info():
    result = _extract_error_context(Exception("plain"))
    assert result == {}


# --------------- _gateway_url derives correct URL ---------------


def test_gateway_url_derives_from_username():
    config = MagicMock()
    config.username = "quays2ab1"
    result = _gateway_url(config)
    assert result == "https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync"


# --------------- _decrypt_secret raises for missing password ---------------


def test_decrypt_secret_raises_for_missing_password():
    config = MagicMock()
    config.encrypted_password = None

    with pytest.raises(QualysAdapterError) as exc_info:
        _decrypt_secret(config)

    assert exc_info.value.error_type == "qualys_missing_credentials"


# --------------- client.close() called even on exception ---------------


@pytest.mark.asyncio
@patch("app.services.qualys_adapter._gateway_url", return_value="https://gateway.qg2.apps.qualys.com/rest/2.0/am/connector/asset/data/sync")
@patch("app.services.qualys_adapter._create_client")
@patch("asyncio.to_thread", new_callable=AsyncMock)
async def test_client_close_called_on_exception(mock_to_thread, mock_create_client, mock_gateway_url):
    mock_to_thread.side_effect = QualysConnectionError("fail")
    mock_client = MagicMock()
    mock_create_client.return_value = mock_client

    connector = _make_connector()
    config = _make_config()

    with pytest.raises(QualysAdapterError):
        await submit_batch([{"name": "asset-1"}], connector, config)

    assert mock_client.close.called
