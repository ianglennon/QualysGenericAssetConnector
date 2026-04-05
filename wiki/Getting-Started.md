# Getting Started

This guide walks you from a fresh clone to your first login in about five minutes. For production hardening (TLS, backups, resource limits), see the [[Deployment Guide]].

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 20.10+ with Docker Compose v2+
- [Git](https://git-scm.com/)
- A terminal (bash examples shown throughout)

## Clone the Repository

```bash
git clone <repository-url>
cd QualysGenericAssetConnector
```

## Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` in your editor and set the following values.

### Generate SECRET_KEY

Used to sign JWT authentication tokens.

```bash
openssl rand -hex 32
```

Paste the output as the `SECRET_KEY` value.

### Generate FERNET_KEY

Used to encrypt stored credentials at rest.

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output as the `FERNET_KEY` value.

### Generate POSTGRES_PASSWORD

The password for the PostgreSQL database.

```bash
openssl rand -hex 16
```

Paste the output as the `POSTGRES_PASSWORD` value. You can leave `POSTGRES_USER` at its default (`qualys`).

> **Note:** `docker-compose.yml` automatically constructs `DATABASE_URL` from `POSTGRES_USER` and `POSTGRES_PASSWORD`, so you do not need to edit `DATABASE_URL` manually. The placeholder value in `.env.example` is overridden at runtime by Docker Compose.

### Set Admin Credentials

Set `ADMIN_EMAIL` to a valid email address and `ADMIN_PASSWORD` to a strong password meeting the following policy:

- 12 or more characters
- At least 2 numeric digits
- At least 1 non-alphanumeric character (e.g., `!@#$%^&*`)

> **Warning:** `ADMIN_EMAIL` and `ADMIN_PASSWORD` are only used on the very first startup when no users exist. Changing these values later has no effect. To reset the admin password, use the [[User Management]] page.

## Start the Application

```bash
docker compose up --build
```

Or use the shorthand:

```bash
make dev
```

On startup, the following happens:

1. PostgreSQL 16 database starts and passes its health check
2. Backend runs database migrations automatically
3. Admin user is seeded from `ADMIN_EMAIL` and `ADMIN_PASSWORD` (first startup only)
4. Procrastinate task worker starts for background job processing
5. nginx starts serving the web UI on port 80

Once all services are healthy, the application is available at **http://localhost**.

## Log In

1. Open **http://localhost** in your browser
2. Enter the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you configured in `.env`
3. Click **Login** to reach the dashboard

## What's Next

- [[Qualys Configuration]] -- Connect to your Qualys subscription
- [[Creating a Connector]] -- Set up your first data source
- [[Scheduling]] -- Automate recurring syncs
- [[Deployment Guide]] -- Harden for production use

Having trouble? See [[Troubleshooting]].
