# Configuration Reference

All configuration for the Qualys Generic Asset Connector is managed through environment variables defined in the `.env` file at the project root. Copy `.env.example` to `.env` and fill in the required values before starting the application. For initial setup steps, see [[Getting Started]]. For production hardening, see [[Deployment Guide]].

## Environment Variables

### SECRET_KEY

**Purpose:** Signs JWT access and refresh tokens (HS256 algorithm).
**Required:** Yes
**Default:** None -- must be set
**Format:** 64-character hex string
**Generate:**
```bash
openssl rand -hex 32
```
**Wrong-value symptom:** All API requests return 401 Unauthorized; existing JWTs become invalid if the key changes.

### FERNET_KEY

**Purpose:** Encrypts connector credentials and Qualys passwords at rest using Fernet symmetric encryption.
**Required:** Yes
**Default:** None -- must be set
**Format:** 44-character URL-safe base64 string
**Generate:**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
**Wrong-value symptom:** Application crashes on startup with an InvalidToken error. If changed after data exists, all encrypted credentials become permanently unrecoverable.

> **Warning:** If you lose your `FERNET_KEY`, all encrypted credentials (connector auth tokens, Qualys passwords) become permanently unrecoverable. Back up your `.env` file securely.

### POSTGRES_USER

**Purpose:** PostgreSQL database username, used by both the `db` service and the backend connection string.
**Required:** No
**Default:** `qualys`
**Format:** Plain string (alphanumeric, no spaces)
**Generate:** N/A -- use the default or choose a username.
**Wrong-value symptom:** Backend fails to connect to the database on startup with an authentication error.

### POSTGRES_PASSWORD

**Purpose:** PostgreSQL database password, used by both the `db` service and the backend connection string.
**Required:** Yes
**Default:** None -- must be set
**Format:** Any string
**Generate:**
```bash
openssl rand -hex 16
```
**Wrong-value symptom:** Backend fails to connect to the database on startup with an authentication error.

### DATABASE_URL

**Purpose:** SQLAlchemy connection string for the backend to reach PostgreSQL.
**Required:** No (when using Docker Compose)
**Default:** None in `.env.example`, but `docker-compose.yml` constructs it automatically as `postgresql://${POSTGRES_USER:-qualys}:${POSTGRES_PASSWORD}@db:5432/qualys`.
**Format:** `postgresql://user:password@host:5432/dbname`
**Generate:** N/A -- automatically constructed by Docker Compose from `POSTGRES_USER` and `POSTGRES_PASSWORD`.
**Wrong-value symptom:** Backend fails to connect to the database. Note: the `DATABASE_URL` value in `.env` is ignored when running via Docker Compose because `docker-compose.yml` overrides it. This variable only matters if you run the backend outside Docker.

### ADMIN_EMAIL

**Purpose:** Email address for the initial admin user, seeded on first startup when no users exist in the database.
**Required:** Yes (for first startup)
**Default:** `""` (empty -- admin seed is skipped if not set)
**Format:** Valid email address
**Generate:** N/A
**Wrong-value symptom:** No admin user is created on first startup; a warning is logged. After the first user exists, this variable is ignored on subsequent startups.

### ADMIN_PASSWORD

**Purpose:** Password for the initial admin user, seeded on first startup when no users exist in the database.
**Required:** Yes (for first startup)
**Default:** `""` (empty -- admin seed is skipped if not set)
**Format:** 12+ characters, at least 2 numeric digits, at least 1 non-alphanumeric character (see [[#Password Policy]])
**Generate:** N/A -- choose a strong password that meets the policy.
**Wrong-value symptom:** If the password does not meet the policy, the admin seed fails with a validation error on startup. After the first user exists, this variable is ignored on subsequent startups.

### DOCS_ENABLED

**Purpose:** Enables Swagger UI at `/docs` and ReDoc at `/redoc` for interactive API documentation.
**Required:** No
**Default:** `false`
**Format:** `true` or `false`
**Generate:** N/A
**Wrong-value symptom:** No visible symptom if misconfigured. If set to `true` in production, API documentation endpoints become publicly accessible.

### ACCESS_TOKEN_EXPIRE_MINUTES

**Purpose:** Lifetime of JWT access tokens in minutes.
**Required:** No
**Default:** `15`
**Format:** Integer (minutes)
**Generate:** N/A
**Wrong-value symptom:** Too low forces users to re-authenticate frequently; too high increases risk if a token is compromised.

### REFRESH_TOKEN_EXPIRE_DAYS

**Purpose:** Lifetime of JWT refresh tokens in days.
**Required:** No
**Default:** `7`
**Format:** Integer (days)
**Generate:** N/A
**Wrong-value symptom:** Too low forces users to log in again frequently; too high means refresh tokens remain valid longer after a user is removed.

## Docker Compose Topology

The application runs as three Docker Compose services. The browser connects to nginx on port 80, which serves the React SPA for static requests and proxies `/api/*` requests to the backend. The backend connects to PostgreSQL for all data storage.

```mermaid
graph LR
    Browser -->|":80"| nginx
    nginx -->|"/api/*"| backend["backend :8080"]
    nginx -->|"static"| SPA["React SPA"]
    backend --> db["PostgreSQL :5432"]

    subgraph Docker Compose
        nginx
        backend
        db
    end
```

### db

- **Image:** `postgres:16-alpine`
- **Internal port:** 5432 (not exposed to host)
- **Healthcheck:** `pg_isready -U qualys -d qualys` every 5 seconds
- **Volume:** `pgdata:/var/lib/postgresql/data`

### backend

- **Image:** Custom (Python 3.12-slim)
- **Internal port:** 8080 (not exposed to host)
- **Depends on:** db (healthy)
- **Healthcheck:** `GET http://localhost:8080/health` every 10 seconds, 30-second start period

### nginx

- **Image:** Custom (nginx:1.27-alpine with compiled React SPA)
- **Exposed port:** 80
- **Depends on:** backend (healthy)
- **Routing:** Serves the React SPA for all paths and proxies `/api/*` to `backend:8080`

## Volumes

| Volume   | Mount Point                    | Purpose                        |
|----------|--------------------------------|--------------------------------|
| `pgdata` | `/var/lib/postgresql/data`     | PostgreSQL data persistence    |

## Password Policy

All user passwords must meet:

- Minimum 12 characters
- At least 2 numeric digits
- At least 1 non-alphanumeric character (e.g., `!@#$%^&*`)

This applies to the admin seed password (`ADMIN_PASSWORD`) and all passwords created through the UI.

## JWT Configuration

| Token Type    | Default Lifetime | Storage                          | Purpose                                              |
|---------------|------------------|----------------------------------|------------------------------------------------------|
| Access Token  | 15 minutes       | Browser memory (cleared on close)| Short-lived token for API access                     |
| Refresh Token | 7 days           | Database (server-side)           | Rotated on each use for obtaining new access tokens  |

Having trouble? See [[Troubleshooting]].
