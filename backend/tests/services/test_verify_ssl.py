"""Regression tests: verify_ssl flag is threaded to all source-API httpx clients."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock


def _make_connector(verify_ssl=True, **kwargs):
    """Create a mock Connector with verify_ssl support."""
    connector = MagicMock()
    connector.verify_ssl = verify_ssl
    connector.base_url = kwargs.get("base_url", "https://api.example.com")
    connector.test_path = kwargs.get("test_path", "health")
    connector.auth_method = kwargs.get("auth_method", "bearer_token")
    connector.encrypted_token = kwargs.get("encrypted_token", "enc_token")
    connector.encrypted_username = kwargs.get("encrypted_username", None)
    connector.encrypted_password = kwargs.get("encrypted_password", None)
    connector.api_key_name = kwargs.get("api_key_name", None)
    connector.encrypted_api_key = kwargs.get("encrypted_api_key", None)
    connector.source_retry_limit = kwargs.get("source_retry_limit", None)
    return connector


class TestConnectorServiceVerifySSL:
    """test_connector_connection should pass verify= to httpx.Client."""

    @patch("app.services.connector_service._build_headers", return_value={"Authorization": "Bearer test"})
    @patch("app.services.connector_service.httpx.Client")
    def test_verify_ssl_false_passed_to_client(self, mock_client_cls, _mock_headers):
        mock_connector = _make_connector(verify_ssl=False)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {},
            headers={"content-type": "application/json"},
        )
        mock_client_cls.return_value = mock_client

        from app.services.connector_service import test_connector_connection
        test_connector_connection(mock_connector)

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs.get("verify") is False

    @patch("app.services.connector_service._build_headers", return_value={"Authorization": "Bearer test"})
    @patch("app.services.connector_service.httpx.Client")
    def test_verify_ssl_true_passed_to_client(self, mock_client_cls, _mock_headers):
        mock_connector = _make_connector(verify_ssl=True)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {},
            headers={"content-type": "application/json"},
        )
        mock_client_cls.return_value = mock_client

        from app.services.connector_service import test_connector_connection
        test_connector_connection(mock_connector)

        mock_client_cls.assert_called_once()
        call_kwargs = mock_client_cls.call_args.kwargs
        assert call_kwargs.get("verify") is True


class TestSourceClientVerifySSL:
    """source_client.fetch_all_pages should pass verify= to httpx.AsyncClient when creating its own client."""

    @pytest.mark.asyncio
    @patch("app.services.source_client._build_headers", return_value={"Authorization": "Bearer test"})
    @patch("app.services.source_client.httpx.AsyncClient")
    async def test_verify_ssl_false_threaded(self, mock_async_cls, _mock_headers):
        mock_connector = _make_connector(verify_ssl=False)
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("short-circuit"))
        mock_async_cls.return_value = mock_client

        from app.services.source_client import fetch_all_pages
        try:
            await fetch_all_pages(
                connector=mock_connector,
                url="https://api.example.com/data",
            )
        except Exception:
            pass

        mock_async_cls.assert_called_once()
        call_kwargs = mock_async_cls.call_args.kwargs
        assert call_kwargs.get("verify") is False

    @pytest.mark.asyncio
    @patch("app.services.source_client._build_headers", return_value={"Authorization": "Bearer test"})
    @patch("app.services.source_client.httpx.AsyncClient")
    async def test_verify_ssl_true_threaded(self, mock_async_cls, _mock_headers):
        mock_connector = _make_connector(verify_ssl=True)
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("short-circuit"))
        mock_async_cls.return_value = mock_client

        from app.services.source_client import fetch_all_pages
        try:
            await fetch_all_pages(
                connector=mock_connector,
                url="https://api.example.com/data",
            )
        except Exception:
            pass

        mock_async_cls.assert_called_once()
        call_kwargs = mock_async_cls.call_args.kwargs
        assert call_kwargs.get("verify") is True


class TestQualysClientUnaffected:
    """Qualys API calls must never receive a verify= override — always strict TLS."""

    def test_qualys_adapter_does_not_use_httpx_directly(self):
        """qualys_adapter.py must not create httpx clients — it delegates to the qualys_client package."""
        from pathlib import Path
        adapter_path = Path(__file__).parent.parent.parent / "app" / "services" / "qualys_adapter.py"
        content = adapter_path.read_text()
        # The adapter must not import or instantiate httpx clients directly
        assert "httpx.AsyncClient" not in content, (
            "qualys_adapter.py must not create httpx.AsyncClient — "
            "Qualys calls must go through QualysClient package only"
        )
        assert "httpx.Client(" not in content, (
            "qualys_adapter.py must not create httpx.Client — "
            "Qualys calls must go through QualysClient package only"
        )

    def test_qualys_adapter_does_not_pass_verify_false(self):
        """qualys_adapter.py must not contain verify=False — Qualys TLS must always be strict."""
        from pathlib import Path
        adapter_path = Path(__file__).parent.parent.parent / "app" / "services" / "qualys_adapter.py"
        content = adapter_path.read_text()
        assert "verify=False" not in content, (
            "qualys_adapter.py must not pass verify=False — "
            "Qualys API calls must always use strict TLS verification"
        )


class TestConnectorSchemaVerifySSL:
    """Pydantic schemas must accept verify_ssl in create/update and return it in responses."""

    def test_connector_create_accepts_verify_ssl_false(self):
        """ConnectorCreate schema must accept verify_ssl=False."""
        from app.schemas.connector import ConnectorCreate
        payload = ConnectorCreate(
            name="test",
            base_url="https://api.example.com",
            auth_method="bearer_token",
            verify_ssl=False,
        )
        assert payload.verify_ssl is False

    def test_connector_create_defaults_verify_ssl_to_true(self):
        """ConnectorCreate schema must default verify_ssl to True when omitted."""
        from app.schemas.connector import ConnectorCreate
        payload = ConnectorCreate(
            name="test",
            base_url="https://api.example.com",
            auth_method="bearer_token",
        )
        assert payload.verify_ssl is True

    def test_connector_update_accepts_verify_ssl_false(self):
        """ConnectorUpdate schema must accept verify_ssl=False for patching."""
        from app.schemas.connector import ConnectorUpdate
        payload = ConnectorUpdate(verify_ssl=False)
        assert payload.verify_ssl is False

    def test_connector_update_preserves_none_when_verify_ssl_omitted(self):
        """ConnectorUpdate schema must leave verify_ssl as None when not provided (preserve existing)."""
        from app.schemas.connector import ConnectorUpdate
        payload = ConnectorUpdate(name="renamed")
        assert payload.verify_ssl is None

    def test_connector_response_includes_verify_ssl_field(self):
        """ConnectorResponse schema must include verify_ssl as a required boolean field."""
        from app.schemas.connector import ConnectorResponse
        from datetime import datetime
        now = datetime.utcnow()
        response = ConnectorResponse(
            id="abc",
            name="test",
            base_url="https://api.example.com",
            test_path=None,
            auth_method="bearer_token",
            has_token=True,
            has_username=False,
            has_password=False,
            has_api_key=False,
            api_key_name=None,
            source_retry_limit=None,
            qualys_retry_limit=None,
            verify_ssl=False,
            fault_diagnosis=False,
            has_valid_endpoints=False,
            created_at=now,
            updated_at=now,
        )
        assert response.verify_ssl is False

    def test_connector_response_verify_ssl_true_round_trips(self):
        """ConnectorResponse schema must correctly return verify_ssl=True."""
        from app.schemas.connector import ConnectorResponse
        from datetime import datetime
        now = datetime.utcnow()
        response = ConnectorResponse(
            id="xyz",
            name="another",
            base_url="https://api.example.com",
            test_path=None,
            auth_method="basic_auth",
            has_token=False,
            has_username=True,
            has_password=True,
            has_api_key=False,
            api_key_name=None,
            source_retry_limit=None,
            qualys_retry_limit=None,
            verify_ssl=True,
            fault_diagnosis=False,
            has_valid_endpoints=True,
            created_at=now,
            updated_at=now,
        )
        assert response.verify_ssl is True


class TestGrepVerification:
    """Verify all httpx client creation points include verify= parameter via static analysis."""

    def test_all_source_client_sites_have_verify(self):
        """All httpx client creations in source-facing code should include verify= param."""
        import re
        from pathlib import Path

        root = Path(__file__).parent.parent.parent / "app"
        source_files = [
            root / "services" / "source_client.py",
            root / "services" / "connector_service.py",
            root / "services" / "ingestion_service.py",
            root / "services" / "preview.py",
            root / "routers" / "connectors.py",
            root / "routers" / "canvas_endpoints.py",
        ]

        pattern = re.compile(r"httpx\.(Async)?Client\(")
        verify_pattern = re.compile(r"verify=")

        for filepath in source_files:
            content = filepath.read_text()
            for match in pattern.finditer(content):
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                line = content[line_start:line_end]
                assert verify_pattern.search(line), (
                    f"httpx client in {filepath.name} missing verify= parameter: {line.strip()}"
                )
