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

Prerequisites: [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

```bash
git clone https://github.com/ianglennon/QualysGenericAssetConnector.git
cd QualysGenericAssetConnector
cp .env.example .env
# Edit .env with your SECRET_KEY, FERNET_KEY, and admin credentials
docker compose up -d
```

Open http://localhost in your browser and log in with the admin credentials from `.env`.

## Documentation

Full documentation is available in the [GitHub Wiki](../../wiki).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

GPL v3 -- see [LICENSE.md](LICENSE.md).
