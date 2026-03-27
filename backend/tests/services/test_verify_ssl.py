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
