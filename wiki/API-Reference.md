# API Reference

All endpoints are under `/api/v1`. Requests require a valid JWT access token in the `Authorization: Bearer <token>` header (except login and health check).

## Error Responses

All errors follow a consistent JSON format produced by the `make_error()` function:

```json
{
  "error": {
    "code": "CONNECTOR_NOT_FOUND",
    "message": "Connector not found",
    "details": {"connector_id": "abc-123"}
  }
}
```

The `code` field is a machine-readable string. The `message` field is human-readable. The `details` object provides additional context specific to the error.

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| AUTH_INVALID_CREDENTIALS | 401 | Invalid email or password |
| AUTH_INVALID_TOKEN | 401 | Invalid or expired token |
| AUTH_TOKEN_EXPIRED | 401 | Refresh token expired |
| AUTH_UNAUTHORIZED | 401 | Missing or invalid authorization header |
| AUTH_FORBIDDEN | 403 | Insufficient permissions for this action |
| AUTH_PASSWORD_POLICY | 422 | Password does not meet complexity requirements |
| CONNECTOR_NOT_FOUND | 404 | Connector does not exist |
| CONNECTOR_RUN_IN_PROGRESS | 409 | A sync is already running for this connector |
| ENDPOINT_NOT_FOUND | 404 | Endpoint does not exist |
| ENDPOINT_IN_USE | 409 | Cannot delete endpoint -- it is referenced by a canvas |
| CANVAS_NOT_FOUND | 404 | Canvas does not exist |
| CANVAS_DISABLED | 400 | Canvas is disabled and cannot be synced |
| NO_ENABLED_ENDPOINTS | 400 | No enabled endpoints to sync |
| INVALID_ENDPOINT_MAPPINGS | 400 | Endpoints missing required identity field mappings |
| SOURCE_UNREACHABLE | 502 | Source API did not respond |
| QUALYS_NOT_CONFIGURED | 404 | Qualys credentials not configured |
| ROLE_NOT_FOUND | 404 | Role does not exist |
| ROLE_NAME_EXISTS | 409 | A role with this name already exists |
| ROLE_SYSTEM_PROTECTED | 403 | Cannot modify built-in system role |
| ROLE_HAS_USERS | 409 | Cannot delete role -- users are assigned to it |
| PERMISSION_INVALID | 422 | Invalid permission string |
| USER_NOT_FOUND | 404 | User does not exist |
| RUN_NOT_FOUND | 404 | Run does not exist |
| NO_SCHEDULE | 400 | Connector has no schedule configured |
| ROUTE_DEPRECATED | 410 | Endpoint has been removed |
| VALIDATION_ERROR | 422 | Request body failed validation |

For diagnosis of specific error codes, see [[Troubleshooting]].

## Authentication

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/login` | Login with email/password, returns access + refresh tokens | Public |
| POST | `/auth/refresh` | Exchange refresh token for new access token | Public |
| GET | `/auth/me` | Get current user info and permissions | Any authenticated user |

### Login

**Request:**
```json
POST /api/v1/auth/login
{
  "email": "admin@example.com",
  "password": "SecurePass1!"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Refresh Token

**Request:**
```json
POST /api/v1/auth/refresh
{
  "refresh_token": "eyJ..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

## Connectors

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/` | List all connectors | connectors:read |
| POST | `/connectors/` | Create a connector | connectors:create |
| GET | `/connectors/{id}` | Get connector by ID | connectors:read |
| PATCH | `/connectors/{id}` | Update connector | connectors:update |
| DELETE | `/connectors/{id}` | Delete connector (cascades) | connectors:delete |
| POST | `/connectors/{id}/test` | Test source API connectivity | connectors:read |

### Create Connector

**Request:**
```json
POST /api/v1/connectors/
{
  "name": "ServiceNow CMDB",
  "base_url": "https://instance.service-now.com/api/now",
  "auth_method": "bearer_token",
  "credentials": {
    "token": "your-api-token"
  },
  "verify_ssl": true
}
```

Auth methods: `bearer_token`, `basic_auth`, `api_key_header`

**Response (201):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "ServiceNow CMDB",
  "base_url": "https://instance.service-now.com/api/now",
  "test_path": null,
  "auth_method": "bearer_token",
  "has_token": true,
  "has_username": false,
  "has_password": false,
  "has_api_key": false,
  "api_key_name": null,
  "source_retry_limit": null,
  "qualys_retry_limit": null,
  "verify_ssl": true,
  "has_valid_endpoints": false,
  "created_at": "2026-04-05T12:00:00",
  "updated_at": "2026-04-05T12:00:00"
}
```

Credentials are never returned in responses. Boolean flags (`has_token`, `has_username`, etc.) indicate which credentials are stored.

## Endpoints

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/{id}/endpoints` | List endpoints | connectors:read |
| POST | `/connectors/{id}/endpoints` | Create endpoint | connectors:create |
| GET | `/connectors/{id}/endpoints/{eid}` | Get endpoint | connectors:read |
| PATCH | `/connectors/{id}/endpoints/{eid}` | Update endpoint | connectors:update |
| DELETE | `/connectors/{id}/endpoints/{eid}` | Delete endpoint | connectors:delete |
| POST | `/connectors/{id}/endpoints/reorder` | Reorder endpoints | connectors:update |
| GET | `/connectors/{id}/endpoints/{eid}/fields/discover` | Discover source fields | connectors:read |

### Create Endpoint
```json
POST /api/v1/connectors/{id}/endpoints
{
  "name": "Hosts",
  "path": "/v2/hosts",
  "data_root": "data.items",
  "is_enabled": true,
  "display_order": 0
}
```

## Canvases

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/{id}/canvases` | List canvases | canvases:read |
| POST | `/connectors/{id}/canvases` | Create canvas | canvases:create |
| GET | `/connectors/{id}/canvases/{cid}` | Get canvas | canvases:read |
| PATCH | `/connectors/{id}/canvases/{cid}` | Update canvas | canvases:update |
| DELETE | `/connectors/{id}/canvases/{cid}` | Delete canvas (cascades) | canvases:delete |

## Canvas Endpoints

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/{id}/canvases/{cid}/endpoints` | List canvas endpoints | canvases:read |
| POST | `/connectors/{id}/canvases/{cid}/endpoints` | Add endpoint to canvas | canvases:create |
| GET | `/connectors/{id}/canvases/{cid}/endpoints/{rid}` | Get canvas endpoint | canvases:read |
| PATCH | `/connectors/{id}/canvases/{cid}/endpoints/{rid}` | Update canvas endpoint | canvases:update |
| DELETE | `/connectors/{id}/canvases/{cid}/endpoints/{rid}` | Remove from canvas | canvases:delete |
| GET | `/connectors/{id}/canvases/{cid}/endpoints/validate` | Validate tree structure | canvases:read |
| GET | `/connectors/{id}/canvases/{cid}/endpoints/{rid}/fields/discover` | Discover fields (with parent context) | canvases:read |
| POST | `/connectors/{id}/canvases/{cid}/dry-run` | Dry run canvas | canvases:read |

### Add Endpoint to Canvas
```json
POST /api/v1/connectors/{id}/canvases/{cid}/endpoints
{
  "endpoint_id": "endpoint-uuid",
  "parent_ref_id": null,
  "variable_extractions": {"host_id": "id"},
  "max_concurrency": 5,
  "exclusion_rules": [],
  "tree_order": 0
}
```

## Field Mappings

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/{id}/endpoints/{eid}/mappings` | List mappings | connectors:read |
| PUT | `/connectors/{id}/endpoints/{eid}/mappings` | Batch replace mappings | connectors:update |

### Batch Replace Mappings
```json
PUT /api/v1/connectors/{id}/endpoints/{eid}/mappings
{
  "mappings": [
    {
      "mapping_type": "direct_copy",
      "target_field": "hostName",
      "source_field": "hostname",
      "order": 0
    },
    {
      "mapping_type": "static_default",
      "target_field": "isContainer",
      "static_value": "false",
      "order": 1
    },
    {
      "mapping_type": "conditional",
      "target_field": "operatingSystem",
      "conditions": [
        {"source_field": "os_type", "operator": "equals", "target_value": "linux", "value": "Linux"},
        {"source_field": "os_type", "operator": "equals", "target_value": "win", "value": "Windows"}
      ],
      "fallback": "Unknown",
      "order": 2
    }
  ]
}
```

## Runs

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/runs` | List all runs (paginated) | runs:read |
| GET | `/runs/stats` | Dashboard statistics | runs:read |
| GET | `/runs/{id}` | Get run detail with endpoint logs | runs:read |
| GET | `/connectors/{id}/runs` | List runs for connector (paginated) | runs:read |
| POST | `/connectors/{id}/runs` | Trigger manual sync | runs:trigger_sync |

### Trigger Sync

```
POST /api/v1/connectors/{id}/runs
```

Optional query parameter: `?canvas_id=<uuid>` for single-canvas sync.

**Response (202):**
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running"
}
```

The sync runs asynchronously. Poll `GET /runs/{run_id}` for status updates.

## Schedules

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/connectors/{id}/schedule` | Get schedule status | schedules:read |
| PUT | `/connectors/{id}/schedule` | Set/update schedule | schedules:create |
| POST | `/connectors/{id}/schedule/pause` | Pause schedule | schedules:update |
| POST | `/connectors/{id}/schedule/resume` | Resume schedule | schedules:update |
| DELETE | `/connectors/{id}/schedule` | Delete schedule | schedules:delete |

### Set Schedule
```json
PUT /api/v1/connectors/{id}/schedule
{
  "interval": {
    "interval_type": "hours",
    "interval_value": 6
  },
  "execution_timeout": 3600
}
```

Interval types: `minutes`, `hours`, `days`, `weeks`

## Users

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/users/` | List all users | users:read |
| POST | `/users/` | Create a new user | users:create |
| GET | `/users/{id}` | Get user details | users:read |
| PATCH | `/users/{id}` | Update user | users:update |
| POST | `/users/{id}/deactivate` | Deactivate user | users:update |

### Create User

**Request:**
```json
POST /api/v1/users/
{
  "email": "operator@example.com",
  "role_id": "role-uuid"
}
```

**Response (201):**
```json
{
  "id": "user-uuid",
  "email": "operator@example.com",
  "is_active": true,
  "must_change_password": true,
  "temporary_password": "auto-generated-password",
  "role": {
    "id": "role-uuid",
    "name": "Viewer"
  }
}
```

The `temporary_password` is only returned once at creation time. The user must change it on first login.

## Roles

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/roles/` | List all roles with user counts | roles:read |
| POST | `/roles/` | Create a new role | roles:create |
| GET | `/roles/{id}` | Get role with permissions | roles:read |
| PATCH | `/roles/{id}` | Update role name/description | roles:update |
| DELETE | `/roles/{id}` | Delete role | roles:delete |
| POST | `/roles/{id}/permissions` | Add permissions to role | roles:update |
| DELETE | `/roles/{id}/permissions/{permission}` | Remove permission from role | roles:update |

### Create Role

**Request:**
```json
POST /api/v1/roles/
{
  "name": "Viewer",
  "description": "Read-only access to connectors and run history"
}
```

**Response (201):**
```json
{
  "id": "role-uuid",
  "name": "Viewer",
  "description": "Read-only access to connectors and run history",
  "is_system": false,
  "created_at": "2026-04-05T12:00:00",
  "permissions": []
}
```

New roles start with no permissions. Add permissions individually using `POST /roles/{id}/permissions`.

## Qualys Configuration

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/qualys/config` | Get Qualys config | settings:read |
| PUT | `/qualys/config` | Create/update Qualys config | settings:update |
| GET | `/qualys/schema` | Get Qualys CSAM target field schema | connectors:read |

## Health Check

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/health` | Application + database health | None |

The health endpoint is outside the `/api/v1` prefix. It returns `200` when the backend and database are healthy, or `503` during startup.
