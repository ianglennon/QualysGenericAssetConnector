# Getting Started

This guide takes you from nothing to your first login in about five minutes, using the prebuilt images published to GitHub Container Registry. For production hardening (TLS, backups, resource limits), see the [[Deployment Guide]]. To build the images yourself, for example to work on the code, see [Building from Source](#building-from-source) below.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 20.10+ with Docker Compose v2+
- A terminal (bash examples shown throughout)

No source checkout, Git, or Python is needed.

## Download the Compose File

Create a folder for the deployment and download the compose file and example settings into it:

```bash
mkdir qualys-connector && cd qualys-connector
curl -fsSLO https://raw.githubusercontent.com/ianglennon/QualysGenericAssetConnector/master/docker-compose.ghcr.yml
curl -fsSL -o .env https://raw.githubusercontent.com/ianglennon/QualysGenericAssetConnector/master/.env.example
```

`docker-compose.ghcr.yml` runs three containers: PostgreSQL 16, the backend (`ghcr.io/ianglennon/qualys-connector-backend`) and nginx serving the web UI (`ghcr.io/ianglennon/qualys-connector-nginx`). The images are public, so no registry login is required.

## Configure Environment

### Generate Secrets

Run this once to generate `SECRET_KEY`, `FERNET_KEY` and `POSTGRES_PASSWORD`. It uses the backend image itself, so nothing else needs to be installed:

```bash
docker run --rm ghcr.io/ianglennon/qualys-connector-backend python -c "import secrets; from cryptography.fernet import Fernet; print('SECRET_KEY=' + secrets.token_hex(32)); print('FERNET_KEY=' + Fernet.generate_key().decode()); print('POSTGRES_PASSWORD=' + secrets.token_hex(16))"
```

Open `.env` in your editor and replace the three placeholder values with the generated ones:

| Setting | Purpose |
|---|---|
| `SECRET_KEY` | Signs JWT authentication tokens |
| `FERNET_KEY` | Encrypts stored connector credentials at rest |
| `POSTGRES_PASSWORD` | Password for the PostgreSQL database |

You can leave `POSTGRES_USER` at its default (`qualys`).

> **Warning:** Keep `FERNET_KEY` safe and back it up with your database. Credentials stored in the application cannot be decrypted without it, and changing it later makes existing connector credentials unreadable.

> **Note:** The compose file builds `DATABASE_URL` from `POSTGRES_USER` and `POSTGRES_PASSWORD`, so you do not need to edit `DATABASE_URL`. The placeholder in `.env.example` is ignored.

### Set Admin Credentials

Set `ADMIN_EMAIL` to a valid email address and `ADMIN_PASSWORD` to a strong password meeting the following policy:

- 12 or more characters
- At least 2 numeric digits
- At least 1 non-alphanumeric character (e.g., `!@#$%^&*`)

> **Warning:** `ADMIN_EMAIL` and `ADMIN_PASSWORD` are only used on the very first startup when no users exist. Changing these values later has no effect. To reset the admin password, use the [[User Management]] page.

### Optional Settings

| Setting | Default | Purpose |
|---|---|---|
| `HTTP_PORT` | `80` | Host port the web UI listens on |
| `IMAGE_TAG` | `latest` | Image version to run, e.g. `sha-c38ebfa` or a release number |
| `DOCS_ENABLED` | `true` in `.env.example` | Serves the interactive API docs; set to `false` to hide them |

The compose file will not start if `SECRET_KEY`, `FERNET_KEY` or `POSTGRES_PASSWORD` is missing.

## Start the Application

```bash
docker compose -f docker-compose.ghcr.yml up -d
```

On startup, the following happens:

1. PostgreSQL 16 database starts and passes its health check
2. Backend runs database migrations automatically
3. Admin user is seeded from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (first startup only)
4. Procrastinate task worker starts for background job processing
5. nginx starts serving the web UI on port 80 (or `HTTP_PORT`)

Check that everything is up with:

```bash
docker compose -f docker-compose.ghcr.yml ps
```

Once all services are healthy, the application is available at **http://localhost** (add `:HTTP_PORT` if you changed it, or use the server's host name).

## Log In

1. Open **http://localhost** in your browser
2. Enter the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you configured in `.env`
3. Click **Login** to reach the dashboard

## Updating

To move to the latest published images:

```bash
docker compose -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.ghcr.yml up -d
```

Database migrations run automatically when the new backend starts, and your data is kept in the `pgdata` volume. Back up first (see [[Deployment Guide]]).

## Building from Source

For development, or to run changes that have not been published yet, build the images locally instead. This needs [Git](https://git-scm.com/) as well as Docker.

The backend image installs the [QualysAPIConnectionManager](https://github.com/ianglennon/QualysAPIConnectionManager) client library from the repository root, so clone it inside the main repository:

```bash
git clone https://github.com/ianglennon/QualysGenericAssetConnector
cd QualysGenericAssetConnector
git clone https://github.com/ianglennon/QualysAPIConnectionManager
cp .env.example .env
```

Fill in `.env` as described in [Configure Environment](#configure-environment), then build and start:

```bash
docker compose up --build
```

Or use the shorthand:

```bash
make dev
```

This also applies `docker-compose.override.yml`, which is intended for development: the backend reloads automatically on code changes, the `backend/` source folder is mounted into the container, and the API docs are enabled.

## What's Next

- [[Qualys Configuration]] -- Connect to your Qualys subscription
- [[Creating a Connector]] -- Set up your first data source
- [[Scheduling]] -- Automate recurring syncs
- [[Deployment Guide]] -- Harden for production use

Having trouble? See [[Troubleshooting]].
