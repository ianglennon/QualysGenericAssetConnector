import time
import base64
import httpx
from app.models.connector import Connector
from app.services.credential_crypto import get_crypto

HTTPX_TIMEOUT = 10.0


def _build_headers(connector: Connector) -> dict:
    """Build authentication headers by decrypting credentials from the Connector model.

    Returns an empty dict if no credentials are configured for the current auth_method.
    Never raises — returns whatever can be built.
    """
    if connector.auth_method == "bearer_token" and connector.encrypted_token:
        token = get_crypto().decrypt(connector.encrypted_token)
        return {"Authorization": f"Bearer {token}"}
    elif connector.auth_method == "basic_auth" and (
        connector.encrypted_username or connector.encrypted_password
    ):
        username = (
            get_crypto().decrypt(connector.encrypted_username)
            if connector.encrypted_username
            else ""
        )
        password = (
            get_crypto().decrypt(connector.encrypted_password)
            if connector.encrypted_password
            else ""
        )
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    elif (
        connector.auth_method == "api_key_header"
        and connector.api_key_name
        and connector.encrypted_api_key
    ):
        api_key = get_crypto().decrypt(connector.encrypted_api_key)
        return {connector.api_key_name: api_key}
    return {}


def test_connector_connection(connector: Connector) -> dict:
    """Make a sync GET request to the connector's test endpoint.

    Returns a structured dict with success/failure metadata.
    Never raises — all exceptions are caught and returned as structured errors.
    """
    url = connector.base_url.rstrip("/") + "/" + (connector.test_path or "").lstrip("/")
    headers = _build_headers(connector)
    start = time.monotonic()
    try:
        with httpx.Client(timeout=HTTPX_TIMEOUT) as client:
            response = client.get(url, headers=headers)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if 200 <= response.status_code < 300:
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time_ms": elapsed_ms,
                "content_type": response.headers.get("content-type"),
                "record_count": None,  # Phase 3 will inspect body; Phase 2 skips body inspection
            }
        else:
            error_type = "auth_failure" if response.status_code in (401, 403) else "http_error"
            return {
                "success": False,
                "error_type": error_type,
                "message": f"HTTP {response.status_code}",
                "status_code": response.status_code,
            }
    except httpx.TimeoutException:
        return {"success": False, "error_type": "timeout", "message": "Request timed out", "status_code": None}
    except httpx.NetworkError:
        return {"success": False, "error_type": "network_error", "message": "Network error", "status_code": None}
    except httpx.RequestError as e:
        return {"success": False, "error_type": "network_error", "message": str(e), "status_code": None}
