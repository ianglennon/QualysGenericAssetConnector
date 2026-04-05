# Creating a Connector

> **Workflow:** **Connector** > [[Endpoints and Field Discovery|Endpoints]] > [[Canvases and Endpoint Chaining|Canvas]] > [[Field Mapping|Mapping]] > [[Scheduling|Schedule]]

A connector represents a connection to a third-party REST API. This page walks through creating a connector and configuring authentication.

## Creating a New Connector

1. Navigate to **Connectors** in the sidebar.
2. Click **Create Connector**.
3. Enter a **Name** for the connector (e.g., "ServiceNow CMDB" or "Proxmox Cluster").
4. Enter the **Base URL** -- the root URL of the source API (e.g., `https://instance.service-now.com/api/now`). All endpoint paths you add later are appended to this URL.
5. Select an **Authentication Method**. See the next section for details on each method.
6. Optionally configure **SSL Verification** and **retry limits** (see Optional Settings below).
7. Click **Save**.

## Authentication Methods

Every connector requires an authentication method. Choose the one that matches how the source API expects credentials.

### Bearer Token

Enter the token value in the credentials field. The system sends it as an `Authorization: Bearer <token>` header on every request.

Use this when the source API provides a static API token or OAuth2 bearer token.

### Basic Authentication

Enter a **username** and **password**. The system encodes them and sends an `Authorization: Basic <base64>` header on every request.

Use this when the source API requires HTTP Basic authentication.

### API Key Header

Enter a custom **header name** (e.g., `X-API-Key`) and the **key value**. The system sends the key as `<header-name>: <key-value>` on every request.

Use this when the source API expects credentials in a custom header rather than the standard `Authorization` header.

> **Note:** All credentials are Fernet-encrypted at rest and never returned in API responses. The UI shows boolean indicators (e.g., "token configured") instead of plaintext values.

## Optional Settings

| Setting | Default | Description |
|---------|---------|-------------|
| Test Path | (none) | Relative URL path used by the Test Connection button |
| SSL Verification | Enabled | Disable for self-signed certificates |
| Source Retry Limit | (system default) | Max retries when fetching from the source API |
| Qualys Retry Limit | (system default) | Max retries when submitting to Qualys |

## Testing the Connection

1. Set a **Test Path** on the connector -- a lightweight endpoint on the source API (e.g., `/api/health` or `/api/v1/servers?limit=1`).
2. Click **Test Connection**.
3. The system makes a GET request to `{base_url}/{test_path}` using the configured authentication. The result shows the HTTP status code and response time.

A successful test confirms network connectivity and valid credentials. It does not validate endpoint paths or field mappings.

## What's Next

With your connector created, the next step is to add endpoints that define which API resources to fetch.

[[Endpoints and Field Discovery]]
