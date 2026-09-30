# Qualys Generic Asset Connector

A self-hosted integration platform that pulls host asset data from third-party REST APIs into Qualys CSAM.
No coding required.

<!-- TODO: Replace with actual screenshot of dashboard or mapping canvas -->
![Dashboard](docs/images/screenshot.png)

## Features

- No-code connector setup for any REST API with Bearer, Basic, or API key authentication
- Visual field mapping canvas to drag-and-drop source fields to Qualys CSAM targets
- Multi-endpoint chaining with parent-child data flows across hierarchical APIs
- Automatic field discovery detects available fields, types, and sample values
- Interval-based scheduling with configurable frequency and overlap protection
- Run history with per-endpoint status, failure tracking, and HTTP payload inspection
- Role-based access control (RBAC) with custom roles, 30 granular permissions, and permission matrix
- Exclusion rules to filter unwanted records before submission
- PostgreSQL 16 database with Procrastinate task queue
- Docker Compose deployment with three containers (nginx, backend, database)

## Quick Start

Prerequisites: [Docker](https://docs.docker.com/get-docker/) with Docker Compose v2. No source checkout or build is needed; the prebuilt images are pulled from GitHub Container Registry.

**1. Download the compose file and example settings**

```bash
mkdir qualys-connector && cd qualys-connector
curl -fsSLO https://raw.githubusercontent.com/ianglennon/QualysGenericAssetConnector/master/docker-compose.ghcr.yml
curl -fsSL -o .env https://raw.githubusercontent.com/ianglennon/QualysGenericAssetConnector/master/.env.example
```

**2. Generate secrets**

```bash
docker run --rm ghcr.io/ianglennon/qualys-connector-backend python -c "import secrets; from cryptography.fernet import Fernet; print('SECRET_KEY=' + secrets.token_hex(32)); print('FERNET_KEY=' + Fernet.generate_key().decode()); print('POSTGRES_PASSWORD=' + secrets.token_hex(16))"
```

**3. Edit `.env`**

- Replace `SECRET_KEY`, `FERNET_KEY` and `POSTGRES_PASSWORD` with the values from step 2.
- Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` for the first admin account. The password needs 12+ characters, at least 2 digits and 1 symbol. These are only used on first startup.
- Optional: `HTTP_PORT` if port 80 is taken, `IMAGE_TAG` to pin a version, `DOCS_ENABLED=false` to hide the API docs.

Keep `FERNET_KEY` safe: it encrypts the stored connector credentials, and they cannot be decrypted without it.

**4. Start it**

```bash
docker compose -f docker-compose.ghcr.yml up -d
```

Open http://localhost (or the host name and `HTTP_PORT` you chose) and log in with the admin credentials from `.env`.

**Updating** to the latest images:

```bash
docker compose -f docker-compose.ghcr.yml pull && docker compose -f docker-compose.ghcr.yml up -d
```

### Building from source

For development, clone this repo and put [QualysAPIConnectionManager](https://github.com/ianglennon/QualysAPIConnectionManager) in its root (the backend image installs it from there), then build:

```bash
git clone https://github.com/ianglennon/QualysGenericAssetConnector.git
cd QualysGenericAssetConnector
git clone https://github.com/ianglennon/QualysAPIConnectionManager.git
cp .env.example .env   # then fill it in as above
docker compose up --build
```

This also applies `docker-compose.override.yml` (auto-reload, source mounted into the backend, API docs on).

## Documentation

Full documentation is available in the [GitHub Wiki](../../wiki).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

MIT -- see [LICENSE](LICENSE).
