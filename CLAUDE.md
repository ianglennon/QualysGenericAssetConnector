# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Qualys Generic Asset Connector is a self-hosted integration platform that pulls host asset data from arbitrary third-party REST APIs and ingests it into Qualys CSAM. Operators configure connectors and field mappings via a web UI — no coding required.

## Common Commands

```bash
# Start all services (backend + nginx frontend)
make dev                          # docker compose up --build

# Run backend tests
make test                         # docker compose run --rm backend pytest tests/ -v

# Run a single test file
docker compose run --rm backend pytest tests/test_auth.py -v

# Apply database migrations
make migrate                      # docker compose run --rm backend alembic upgrade head

# Open a shell in the backend container
make shell

# Stop services / destroy volume
make down
make clean                        # destroys database volume
```

**Frontend (standalone):**
```bash
cd frontend
npm run dev         # Vite dev server
npm run build       # TypeScript check + production build
```

## Architecture

### Data Flow
```
Source REST API → Paginated Fetch → Field Mapping & Transformation → Qualys CSAM Batch Submit (100/batch)
```

Runs are triggered manually or via APScheduler cron jobs. All run results are stored in `run_history` with per-record failure tracking in `run_failures`.

### Backend (`backend/`)
FastAPI application with this layered structure:
- **`app/routers/`** — HTTP endpoints, thin handlers that delegate to services
- **`app/services/`** — Business logic: ingestion pipeline, auth, field transformation
- **`app/models/`** — SQLAlchemy ORM models
- **`app/schemas/`** — Pydantic schemas for request/response validation
- **`app/core/`** — Settings (Pydantic BaseSettings), security helpers, error handling
- **`app/db/`** — SQLAlchemy session factory, Alembic migration env
- **`app/scheduler/`** — APScheduler integration (SQLAlchemy job store, overlap guard)

**Database:** SQLite at `/data/qualys.db` (Docker volume `qualys-data`). Alembic manages migrations. `PRAGMA foreign_keys=ON` is enforced.

**Credentials** are Fernet-encrypted at rest. API responses use `has_token`/`has_username` boolean flags instead of returning plaintext secrets.

**API base URL:** `/api/v1`. All endpoints require JWT auth. Two roles: `admin` (full access) and `operator` (trigger runs + view history only).

### Frontend (`frontend/`)
React 19 SPA served via nginx. Calls `/api/v1` (relative URL — nginx proxies to backend).

- **`src/pages/`** — Dashboard, Connectors, RunHistory, Settings
- **`src/components/`** — Reusable UI components (Radix UI + Tailwind CSS)
- **`src/hooks/`** — Custom React hooks
- **`src/providers/`** — QueryProvider (TanStack React Query), ThemeProvider
- **JWT storage:** In-memory (cleared on browser close)

### Deployment
`docker-compose.yml` defines two services:
- **backend** — FastAPI + uvicorn on port 8000
- **nginx** — Serves built React SPA and reverse-proxies `/api/*` to backend

Environment is injected from `.env` (copy from `.env.example`). Required vars: `SECRET_KEY`, `FERNET_KEY`, `DATABASE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`.

## Key Domain Concepts

**Field Mapping types:**
- `direct_copy` — Map source field directly to target Qualys field
- `static_default` — Always use a fixed value
- `conditional` — Use source field if condition matches, else fallback

**Connector auth methods:** Bearer token, Basic auth, API key header

**Run statuses:** `running` → `success` | `partial_success` | `failed`

**Qualys submission:** 100 records per batch; 207 responses indicate partial success and are parsed for per-record failures.

## Error Response Format
```json
{
  "detail": {
    "error_code": "STRING",
    "error_message": "STRING",
    "context": {}
  }
}
```
