# Contributing

This guide is for developers contributing to the Qualys Generic Asset Connector.

## Tech Stack

- **Backend:** FastAPI (Python 3.12), PostgreSQL 16, SQLAlchemy ORM, Alembic migrations, Procrastinate task queue
- **Frontend:** React 19, Vite, Tailwind CSS, Radix UI, TanStack React Query, React Flow
- **Infrastructure:** Docker Compose (nginx + backend + PostgreSQL)

## Development Setup

```bash
# Start all services (backend + nginx + database)
make dev

# Run backend tests
make test

# Run a single test file
docker compose run --rm backend pytest tests/test_auth.py -v

# Apply database migrations
make migrate

# Open a shell in the backend container
make shell
```

## Frontend Development

```bash
cd frontend
npm install
npm run dev         # Vite dev server on port 5173
npm run build       # TypeScript check + production build
```

## Project Structure

```text
backend/
  app/
    routers/        # HTTP endpoints (thin handlers)
    services/       # Business logic
    models/         # SQLAlchemy ORM models
    schemas/        # Pydantic request/response validation
    core/           # Settings, security, error handling
    db/             # Database session factory, Alembic migrations
    worker/         # Procrastinate task queue integration
  tests/            # pytest test suite

frontend/
  src/
    pages/          # Page components (Dashboard, Connectors, etc.)
    components/     # Reusable UI components
    hooks/          # Custom React hooks
    providers/      # QueryProvider, ThemeProvider
```

## How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Run tests (`make test`)
5. Commit and push
6. Open a pull request
