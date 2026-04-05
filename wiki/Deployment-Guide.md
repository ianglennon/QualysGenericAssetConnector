# Deployment Guide

This guide covers production considerations for running the Qualys Generic Asset Connector. For initial setup and first login, see [[Getting Started]].

## What Happens on Startup

When the application starts, the backend performs the following sequence:

1. Alembic database migrations run (`alembic upgrade head`)
2. Database integrity verification checks that all 13 expected tables exist
3. Admin user is seeded if the users table is empty (from `ADMIN_EMAIL` / `ADMIN_PASSWORD`)
4. Procrastinate schema is created (`CREATE SCHEMA IF NOT EXISTS procrastinate`)
5. Procrastinate worker starts for async task processing
6. Application is marked as ready
7. Health endpoint begins returning `{"status": "ok", "db": "ok", "worker": "ok"}`

## Health Check

The backend exposes an unauthenticated health endpoint for monitoring and orchestration.

- **Endpoint:** `GET /health`
- **During startup:** Returns `{"status": "starting"}` with HTTP 503
- **When healthy:** Returns `{"status": "ok", "db": "ok", "worker": "ok"}` with HTTP 200
- **Docker Compose** uses this endpoint for container health checks (10s interval, 30s start period)

Use this endpoint with external monitoring tools or load balancer health probes.

## Production Considerations

### PostgreSQL Backups

Back up the PostgreSQL database using `pg_dump` from the `db` container:

```bash
# Create backup
docker compose exec db pg_dump -U qualys qualys > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose exec -T db psql -U qualys qualys < backup_20260405.sql
```

Automate backups with a cron job or your preferred scheduling tool. Store backups off-host.

> **Warning:** `make clean` permanently destroys the PostgreSQL data volume. All connectors, mappings, run history, and user accounts are lost. Always back up before running this command.

### TLS Termination

The default configuration serves on port 80 (HTTP). For production, add TLS using one of these approaches:

1. **External reverse proxy** -- Place Traefik, Caddy, or a cloud load balancer in front of nginx on port 80. The proxy handles TLS termination and forwards traffic to the container.
2. **Modify nginx directly** -- Edit `nginx/nginx.conf` to add SSL certificate directives and listen on port 443.

Follow your TLS provider's documentation for certificate setup.

### nginx Configuration

The bundled nginx service handles both API proxying and static file serving:

- `/api/` is proxied to `http://backend:8080/api/` with `X-Real-IP` and `X-Forwarded-For` headers
- All other paths serve the React SPA from `/usr/share/nginx/html`
- `index.html` is served with no-cache headers so the browser always loads the latest version
- `try_files $uri $uri/ /index.html` enables client-side routing for the SPA

### Memory Limits

Add resource limits to `docker-compose.yml` to prevent any single service from consuming excessive memory:

```yaml
services:
  db:
    deploy:
      resources:
        limits:
          memory: 256M
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
  nginx:
    deploy:
      resources:
        limits:
          memory: 128M
```

### Disabling API Documentation

Set `DOCS_ENABLED=false` in `.env` to disable Swagger UI (`/docs`) and ReDoc (`/redoc`) in production. This is the default when running via Docker Compose.

## Make Commands

| Command | Description |
|---------|-------------|
| `make dev` | `docker compose up --build` |
| `make test` | `docker compose run --rm backend pytest tests/ -v` |
| `make migrate` | `docker compose run --rm backend alembic upgrade head` |
| `make shell` | `docker compose run --rm backend /bin/bash` |
| `make down` | `docker compose down` |
| `make clean` | `docker compose down -v` (destroys pgdata volume) |

> **Warning:** `make clean` permanently destroys the PostgreSQL data volume. All connectors, mappings, run history, and user accounts are lost.

## Environment Variables

See [[Configuration Reference]] for a complete reference of all environment variables, Docker Compose topology, and service configuration.

Having trouble? See [[Troubleshooting]].
