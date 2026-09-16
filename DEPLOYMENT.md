# Alquiler — Deployment Guide

Target: a **free-tier DEMO/PITCH deployment**. This guide assumes no paid
infrastructure, no Paystack, and no extra processes. It uses:
overview-friendly free tiers (one web runtime, one managed PostgreSQL, optional
Redis) and keeps the architecture production-shaped so it can be upgraded to
paid tiers later **without rewriting code**.

> The authoritative database migration mechanism is **PostgreSQL dump/restore**
> (`pg_dump`). The JSON tools (`export_data` / `import_data`) are a **secondary
> convenience** for moving demo data and are NOT a substitute for a real dump.

---

## 1. Reference architecture

```
                        ┌──────────────────────────────────┐
  Landlord / Tenant     │  Single "web" process            │
  (React admin web app) │  gunicorn → Django → DRF          │
  ──────────────────▶   │  whitenoise serves static assets  │
      mobile app        │         │                         │
      (Expo) ───────────▶        ▼                          │
                        │  PostgreSQL (managed free tier)   │
                        │  Redis (optional, caching only)   │
                        └──────────────────────────────────┘
```

- **API + static files** in one process (gunicorn + whitenoise). No nginx
  required; add one later only for TLS termination or traffic reasons.
- **PostgreSQL** managed by the provider (free tier). This is the source of
  truth.
- **Redis** is optional for the demo (used only as a cache when
  `REDIS_URL` is set). Leave it empty to run without it.
- **Frontend** is built with Vite into static files and served by any static
  host, or from the same origin as the API.

---

## 2. Environment reference

Copy `backend/.env.example` → `backend/.env` and set real values. Everything is
read from environment variables or `.env` (django-environ). Reference:

| Variable | Required (prod) | Meaning |
|---|---|---|
| `DEBUG` | yes | Must be `False` in production. |
| `DJANGO_SECRET_KEY` | yes | Long random value. The insecure default is **rejected** when `DEBUG=False` (the app refuses to boot). |
| `ALLOWED_HOSTS` | yes | Comma-separated hostnames (e.g. `alquiler-api.example.com`). |
| `DB_ENGINE` | yes | `postgres` for production (default `sqlite` for local dev). |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | yes | PostgreSQL connection. |
| `DB_SSLMODE` | no | Defaults to `require` (insecure connections are rejected). |
| `CORS_ALLOWED_ORIGINS` | yes | Comma-separated origins of the frontend(s) (scheme://host[:port]). |
| `CSRF_TRUSTED_ORIGINS` | yes | Same list as CORS for the Django admin/browsable API. |
| `SITE_URL` | yes | Public origin used in invitation/password-reset email links. |
| `REDIS_URL` | no | Leave empty to run without Redis. |
| `EMAIL_BACKEND` | no | Defaults to console backend in `.env.example` for the demo (see §7). |
| `SECURE_SSL_REDIRECT` | no | `True` by default when `DEBUG=False`. Set `False` only if the host does not forward `X-Forwarded-Proto: https` (avoids redirect loops). |
| `GUNICORN_WORKERS` / `GUNICORN_TIMEOUT` | no | gunicorn tuning (`gunicorn.conf.py`). |

Security headers (HSTS, secure cookies, etc.) are enabled automatically when
`DEBUG=False` (`config/settings.py`).

### Runtime check
- Health (no auth): `GET /health/` or `GET /api/v1/auth/health/`
  → `200 {"status":"healthy","database":"ok"}`.
- Swagger: `GET /api/docs/`.

---

## 3. Deploy the backend (single container — recommended free tier)

Build the image (static assets are collected during the build into a volume):

```bash
cd backend
cp .env.example .env          # fill in production values (see §2)
docker compose build web
docker run -d --name alquiler \
  -p 8000:8000 \
  --env-file .env \
  -v alquiler_static:/app/staticfiles \
  -v alquiler_media:/app/media \
  alquiler
```

Then:

```bash
docker exec alquiler python manage.py migrate
docker exec alquiler python manage.py createsuperuser   # first platform admin
curl http://localhost:8000/health/
```

> On most free tiers you will map web ingress to port 8000, or set
> `GUNICORN_BIND` for the platform's expected port. If the provider injects a
> `PORT` env var, set `GUNICORN_BIND=0.0.0.0:${PORT}` accordingly.

### Full stack (Docker Compose) — local/preview

```bash
cp backend/.env.example backend/.env
docker compose up -d          # web + postgres + redis
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

`docker-compose.yml` overrides the web service to use the bundled `db` and
`redis` containers.

---

## 4. Deploy the frontend (React admin web app)

```bash
cd frontend
cp .env.example .env          # set VITE_API_BASE_URL=https://<api-origin>/api/v1
# or:  VITE_API_BASE_URL=https://<api-origin>/api/v1 npm run build
npm run build
```

`VITE_*` variables are **inlined at build time** — rebuild after any change.
Upload the `dist/` directory to any static host (or serve it from nginx /
Cloudflare Pages / GitHub Pages). Point `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS` at the frontend's origin.

---

## 5. Point the mobile app (Expo) at the deployed API

In `mobile/.env` set the API base URL to the deployed backend, e.g.:

```env
EXPO_PUBLIC_API_BASE_URL=https://alquiler-api.example.com
# schema used by the app: <base>/api/v1
```

Rebuild/restart the app. Notifications and password-reset emails embed links
built from the backend's `SITE_URL`.

---

## 6. Database: backup, restore, and moving hosts

**This is the authoritative mechanism.** `backend/backups/` is gitignored —
dumps must **never** be committed.

### Backup (pg_dump)

```bash
./backend/scripts/pg_backup.sh                 # → backend/backups/alquiler_YYYY-MM-DD.sql
./backend/scripts/pg_backup.sh --verbose       # stream progress
DB_HOST=<host> ./backend/scripts/pg_backup.sh  # override any DB_* setting
```

The script reads `DB_*` from `backend/.env` (or the environment), dumps with
`--no-owner --no-privileges` as **plain SQL** for inspectability and portability,
and aborts if the dump is empty. Suppress a scheduled run:

```bash
PGDUMP='pg_dump -c' ...   # (not needed — see restore below)
```

### Restore (psql)

```bash
# newest dump in backend/backups/
./backend/scripts/pg_restore.sh

# specific dump, on a FRESH database
./backend/scripts/pg_restore.sh /path/alquiler_2026-01-15.sql --createdb

# specific dump, overwriting an EXISTING database (destroys its data)
./backend/scripts/pg_restore.sh --reset /path/alquiler_2026-01-15.sql
```

`--reset` drops and recreates the `public` schema (with confirmation) so both
fresh and existing PostgreSQL targets restore cleanly. `psql` runs with
`ON_ERROR_STOP=1`.

### Moving to a new PostgreSQL host

```
Current Host (PostgreSQL)
   │  ./backend/scripts/pg_backup.sh      → alquiler_YYYY-MM-DD.sql
   ▼
backup file (kept OUTSIDE git)
   │  copy to new host (scp / upload)
   ▼
New Host PostgreSQL
   │  ./backend/scripts/pg_restore.sh --createdb /path/alquiler_YYYY-MM-DD.sql
   ▼
configure DATABASE_URL / DB_* in the new host's .env
   ▼
python manage.py migrate          # no-op if dump is current; harmless otherwise
   ▼
verify data  →  python manage.py shell, or hit /api/v1/... endpoints
```

### JSON export/import (secondary convenience)

For demo data only, never for authoritative backups:

```bash
python manage.py export_data --output backup.json     # plaintext demo copy
python manage.py import_data  backup.json --dry-run   # validate first
python manage.py import_data  backup.json
```

What the JSON tools do:
- preserve relationships (FKs by primary key), stable identifiers, and
  created/updated timestamps (to milliseconds);
- **never** export passwords, auth tokens, device sessions, audit logs, or
  API keys;
- validate the whole archive before writing; import runs in one transaction;
  existing primary keys are skipped (idempotent);
- merge `subscriptions.Plan` rows into the target's seeded plan catalog by
  tier (seeded records win; unknown tiers are created) so the unique `tier`
  constraint is never violated.

Limitations: imported users
get an unusable password and must use the password-reset flow; notification
schedule state is re-derived by the normal management commands. Always verify
the target afterwards.

---

## 7. Email for the demo

The demo uses the **console backend** (`.env.example`: `EMAIL_BACKEND=...console...`)
so invitations and password-reset emails are printed to the application log
instead of being delivered. This avoids every email deliverability paywall on
free tiers. To send real mail, switch to the SMTP backend and set
`EMAIL_HOST_*` / `DEFAULT_FROM_EMAIL` — no code changes.

---

## 8. Upgrade path to paid (no rewrites)

- **Static/TLS**: move gunicorn behind a real proxy/CDN; keep whitenoise or set
  `WHITENOISE_KEEP_ONLY_HASHED_FILES` off and serve `staticfiles/` from the CDN.
- **PostgreSQL**: keep using the same `pg_backup.sh` / `pg_restore.sh` flow to
  move to a larger managed instance.
- **Redis**: already supported (`REDIS_URL`); enables future task/queue work.
- **Email / payments (Paystack)**: the schema already carries gateway fields
  (`Payment.gateway`, `gateway_reference`, `verified`) and SaaS billing is
  isolated in `subscriptions/` — extending costs no data migration.
- **Media**: `FileSystemStorage` is used for the demo; swap to object storage
  by changing `STORAGES['default']` in settings.

---

## 9. Post-deployment checklist

1. `GET /health/` returns `200` with `"database":"ok"`.
2. `DEBUG=False` and a real `DJANGO_SECRET_KEY` (app refuses to boot otherwise).
3. `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`
   set to the real domains.
4. `python manage.py migrate` applied; a platform admin exists via
   `createsuperuser`.
5. Landlord registration works and the invitation / password-reset emails
   print to the log (`console` backend).
6. A `pg_backup.sh` dump was taken and restored on a scratch DB at least once
   (see §6).