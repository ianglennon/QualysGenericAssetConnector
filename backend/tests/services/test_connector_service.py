import base64
from unittest.mock import MagicMock, patch
import httpx
import pytest
from app.services.connector_service import _build_headers, test_connector_connection


def _make_connector(
    auth_method="bearer_token",
    encrypted_token=None,
    encrypted_username=None,
    encrypted_password=None,
    api_key_name=None,
    encrypted_api_key=None,
    base_url="https://api.example.com",
    test_path="health",
):
    """Create a mock Connector for testing."""
    connector = MagicMock()
    connector.auth_method = auth_method
    connector.encrypted_token = encrypted_token
    connector.encrypted_username = encrypted_username
    connector.encrypted_password = encrypted_password
    connector.api_key_name = api_key_name
    connector.encrypted_api_key = encrypted_api_key
    connector.base_url = base_url
    connector.test_path = test_path
    return connector


# ── _build_headers tests ──────────────────────────────────────────────────────

def test_build_headers_bearer_token():
    connector = _make_connector(auth_method="bearer_token", encrypted_token="ciphertext")
    with patch("app.services.connector_service.get_crypto") as mock_get_crypto:
        mock_get_crypto.return_value.decrypt.return_value = "mytoken"
        headers = _build_headers(connector)
    assert headers == {"Authorization": "Bearer mytoken"}


def test_build_headers_basic_auth():
    connector = _make_connector(
        auth_method="basic_auth",
        encrypted_username="enc_user",
        encrypted_password="enc_pass",
    )
    with patch("app.services.connector_service.get_crypto") as mock_get_crypto:
        mock_get_crypto.return_value.decrypt.side_effect = lambda x: {
            "enc_user": "testuser",
            "enc_pass": "testpass",
        }[x]
        headers = _build_headers(connector)
    expected_encoded = base64.b64encode(b"testuser:testpass").decode()
    assert headers == {"Authorization": f"Basic {expected_encoded}"}


def test_build_headers_api_key():
    connector = _make_connector(
        auth_method="api_key_header",
        api_key_name="X-API-Key",
        encrypted_api_key="enc_key",
    )
    with patch("app.services.connector_service.get_crypto") as mock_get_crypto:
        mock_get_crypto.return_value.decrypt.return_value = "thekey"
        headers = _build_headers(connector)
    assert headers == {"X-API-Key": "thekey"}


def test_build_headers_no_credentials():
    """bearer_token auth_method with no encrypted_token → empty dict."""
    connector = _make_connector(auth_method="bearer_token", encrypted_token=None)
    headers = _build_headers(connector)
    assert headers == {}


# ── test_connector_connection tests ──────────────────────────────────────────

def test_test_connection_success():
    connector = _make_connector(
        auth_method="bearer_token",
        encrypted_token="enc_token",
        base_url="https://api.example.com",
        test_path="health",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}

    with patch("app.services.connector_service.get_crypto") as mock_crypto, \
         patch("app.services.connector_service.httpx.Client") as mock_client_cls:
        mock_crypto.return_value.decrypt.return_value = "token123"
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = False

        result = test_connector_connection(connector)

    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["response_time_ms"] >= 0
    assert result["content_type"] == "application/json"
    assert result["record_count"] is None


def test_test_connection_auth_failure():
    """401 response → error_type 'auth_failure'."""
    connector = _make_connector(auth_method="bearer_token", encrypted_token=None)
    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("app.services.connector_service.httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = False

        result = test_connector_connection(connector)

    assert result["success"] is False
    assert result["error_type"] == "auth_failure"
    assert result["status_code"] == 401


def test_test_connection_403_auth_failure():
    """403 response → error_type 'auth_failure'."""
    connector = _make_connector(auth_method="bearer_token", encrypted_token=None)
    mock_response = MagicMock()
    mock_response.status_code = 403

    with patch("app.services.connector_service.httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = False

        result = test_connector_connection(connector)

    assert result["success"] is False
    assert result["error_type"] == "auth_failure"


def test_test_connection_timeout():
    """TimeoutException → error_type 'timeout'."""
    connector = _make_connector(auth_method="bearer_token", encrypted_token=None)

    with patch("app.services.connector_service.httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = httpx.TimeoutException("timed out")
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = False

        result = test_connector_connection(connector)

    assert result["success"] is False
    assert result["error_type"] == "timeout"
    assert result["status_code"] is None


def test_test_connection_network_error():
    """NetworkError → error_type 'network_error'."""
    connector = _make_connector(auth_method="bearer_token", encrypted_token=None)

    with patch("app.services.connector_service.httpx.Client") as mock_client_cls:
        mock_client_instance = MagicMock()
        mock_client_instance.get.side_effect = httpx.NetworkError("connection refused")
        mock_client_cls.return_value.__enter__.return_value = mock_client_instance
        mock_client_cls.return_value.__exit__.return_value = False

        result = test_connector_connection(connector)

    assert result["success"] is False
    assert result["error_type"] == "network_error"
    assert result["status_code"] is None
