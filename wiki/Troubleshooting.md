# Troubleshooting

For error code definitions, see [[API Reference]].

## Common Issues

### Cannot log in

**Symptom:** Login fails with "Invalid email or password"

**Possible causes:**
- Wrong email or password
- Admin user was not seeded (check backend logs for seed errors)
- Password does not meet policy (12+ chars, 2+ numbers, 1+ special char)

**Fix:** Check the backend container logs:
```bash
docker compose logs backend | grep -i "seed\|admin\|password"
```

If the admin user was not created, verify `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env` meet the password policy, then run:
```bash
make clean  # WARNING: destroys all data
make dev
```

---

### Admin lockout recovery

**Symptom:** The admin password has been forgotten and no other admin account exists.

**Safer recovery path:** The bootstrap seed only runs when the users table is empty, so changing `ADMIN_PASSWORD` in `.env` alone will not reset an existing admin account. Instead, use the backend shell to reset the password directly:

```bash
make shell
python -c "
from app.db.session import SessionLocal
from app.models.user import User
from app.services.auth_service import hash_password
db = SessionLocal()
admin = db.query(User).filter(User.email == 'your-admin@example.com').first()
admin.hashed_password = hash_password('NewSecurePass12!')
db.commit()
print('Password reset successfully')
"
```

Replace `your-admin@example.com` with the actual admin email from your `.env` file.

**Last resort (destroys all data):**

> **Warning:** `make clean` destroys ALL data including connectors, field mappings, run history, user accounts, and Qualys configuration. Use only as a last resort.

```bash
make clean
make dev
```

This recreates the database and seeds a fresh admin account from the `ADMIN_EMAIL` and `ADMIN_PASSWORD` values in `.env`.

---

### "Source API did not respond" on field discovery

**Symptom:** 502 error when discovering fields

**Possible causes:**
- Source API is unreachable from the Docker container
- DNS resolution failure
- SSL certificate verification failure
- Wrong base URL or endpoint path

**Fix:**
1. Test connectivity from inside the container:
   ```bash
   make shell
   curl -v https://your-api-url/endpoint
   ```
2. If using self-signed certificates, set **Verify SSL** to `false` on the connector
3. Verify the base URL doesn't have a trailing slash conflict with the endpoint path

---

### "INVALID_ENDPOINT_MAPPINGS" when triggering a run

**Symptom:** 400 error when clicking Sync Now

**Cause:** One or more enabled endpoints are missing an identity field mapping. At least one identity field (e.g., `hostName`, `ipAddress`, `sourceNativeKey`) must be mapped.

**Fix:**
1. Check which endpoints are invalid in the error response `invalid_endpoints` array
2. Open the field mapping editor for each invalid endpoint
3. Map at least one identity field

---

### "CONNECTOR_RUN_IN_PROGRESS" when triggering a run

**Symptom:** 409 error when clicking Sync Now

**Cause:** A run is already active for this connector.

**Fix:** Wait for the current run to complete. Check run history for the active run's status. If a run appears stuck in `running` status, it may have crashed -- check backend logs.

---

### No records fetched (0 records)

**Possible causes:**
- The API returned data but the **Data Root** is wrong
- The API returns an empty response
- Authentication is failing silently (some APIs return 200 with empty data on auth failure)

**Fix:**
1. Use **Discover Fields** to verify the endpoint returns data
2. Check the **Data Root** setting -- if the API wraps records in a nested object (e.g., `{"data": {"items": [...]}}`), set Data Root to `data.items`
3. Run a **Test Connection** to verify authentication
4. Check the run detail HTTP request/response capture for the actual API response

---

### Qualys submission failures

**Symptom:** Run completes with `partial_success` and some records failed

**Fix:**
1. Open the run detail page
2. Check the **Failures** section for per-record error messages
3. Common causes:
   - Missing required Qualys fields
   - Invalid data format (e.g., non-UUID in a UUID field)
   - Duplicate records
   - Qualys API rate limiting

---

### Template resolution errors in chained endpoints

**Symptom:** Child endpoint records are empty or missing

**Cause:** Template variables in the child endpoint path (e.g., `{{host_id}}`) cannot be resolved from parent records.

**Fix:**
1. Verify the **Variable Extractions** configuration matches actual parent record field names
2. Use **Discover Fields** on the parent endpoint to see available fields
3. Check that the extraction path uses dot notation for nested fields (e.g., `metadata.id`)

---

### Database migration errors / PostgreSQL startup errors

**Symptom:** Backend fails to start with Alembic errors, "connection refused", or "database does not exist" messages.

**Possible causes:**
- PostgreSQL container is not ready yet (race condition on first startup)
- `DATABASE_URL` in `.env` is misconfigured or does not match the docker-compose service name
- The PostgreSQL data volume is corrupted
- Alembic migrations are out of sync with the database schema

**Fix:**
1. Check PostgreSQL container status:
   ```bash
   docker compose logs db
   ```
2. Verify `DATABASE_URL` in `.env` uses the docker-compose service name as host (e.g., `postgresql://user:pass@db:5432/qualys`)
3. Ensure the `db` service is healthy before the backend starts -- docker-compose `depends_on` with `condition: service_healthy` handles this automatically
4. If tables are missing, the backend attempts self-healing by re-running Alembic migrations on startup
5. Allow more time on first start -- PostgreSQL initialization can take 10-20 seconds
6. If self-healing fails, restart cleanly:
   ```bash
   docker compose down
   docker compose up
   ```
7. As a last resort, reset the database:
   ```bash
   make clean  # WARNING: destroys all data
   make dev
   ```

---

### Container health check failing

**Symptom:** nginx container doesn't start (depends on healthy backend)

**Fix:**
1. Check backend logs: `docker compose logs backend`
2. The health check calls `GET /health` -- if the backend is stuck in startup (migrations, etc.), it returns 503
3. Allow more time (health check has 30s start period and 5 retries)

---

### Permission Denied (403)

**Symptom:** API calls return 403 Forbidden with error code `AUTH_FORBIDDEN`.

**Possible Causes:**
- Your user account does not have the required permission for this action
- Your role is missing the specific resource permission (e.g., `connectors:create`, `runs:trigger`)

**Fix:**
1. Ask an administrator to check your role's permissions in **Settings > Roles**
2. The administrator can edit your role and enable the missing permission
3. Permission changes take effect on your next API request (no re-login needed)
4. See [[User Management]] for the full list of permissions by resource area

---

### Canvas Validity Errors

**Symptom:** Triggering a sync fails with `CANVAS_DISABLED`, `NO_ENABLED_ENDPOINTS`, or `INVALID_ENDPOINT_MAPPINGS`.

**Possible Causes:**
- `CANVAS_DISABLED` -- The canvas is disabled. Only enabled canvases participate in syncs.
- `NO_ENABLED_ENDPOINTS` -- The canvas has no enabled endpoints. At least one endpoint must be enabled.
- `INVALID_ENDPOINT_MAPPINGS` -- One or more endpoints are missing an identity field mapping (the field that maps to the Qualys asset identifier).

**Fix:**
1. Open the connector and navigate to the failing canvas
2. For `CANVAS_DISABLED`: Enable the canvas using the toggle
3. For `NO_ENABLED_ENDPOINTS`: Ensure at least one endpoint is enabled in the canvas tree
4. For `INVALID_ENDPOINT_MAPPINGS`: Open [[Field Mapping]] for each endpoint and verify an identity field (instanceUuid source) is mapped
5. Re-trigger the sync

---

### Schedule Not Firing

**Symptom:** A connector has a schedule configured but syncs are not running automatically.

**Possible Causes:**
- The schedule is **paused** (disabled)
- A previous run is still in progress (the queue lock prevents overlapping runs)
- The backend worker process is not running or has restarted

**Fix:**
1. Open the connector's Schedule section and check the **Enabled** toggle is on
2. Check [[Run History and Diagnostics]] for a run with status `running` -- if stuck, it may need manual resolution
3. Verify the backend container is healthy: `docker compose ps` should show the backend as "Up"
4. Check backend logs for scheduler errors: `docker compose logs backend | grep -i schedule`
5. If the schedule shows a **next fire time** in the past, disable and re-enable the schedule to reset it

## Viewing Logs

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# nginx only
docker compose logs -f nginx
```

The backend logs every HTTP request with method, path, status, and response time.

## Resetting Everything

To start completely fresh:

```bash
make clean    # Stops containers AND destroys the database volume
make dev      # Rebuilds and starts fresh
```

This deletes all connectors, mappings, run history, users, and Qualys configuration.
