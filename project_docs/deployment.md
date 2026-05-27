# Deployment Guide — Custom LMS

> Covers: storage volumes, environment variables, GitHub Actions CI/CD, database migrations, seed data, and manual runbook.

---

## 1. Storage Volumes

Three separate named Docker volumes — independent backup, independent scaling:

| Volume | Mount path | Contents |
|---|---|---|
| `lms_videos` | `/mnt/videos` | Uploaded video files, partitioned by `{tenant_id}/{training_id}/` |
| `lms_images` | `/mnt/images` | Images uploaded via Rich Text lesson editor, partitioned by `{tenant_id}/` |
| `lms_scorm` | `/mnt/scorm` | SCORM packages, partitioned by `{tenant_id}/{training_id}/v{version_id}/` |

**Path conventions:**
```
/mnt/videos/{tenant_id}/{training_id}/{filename}
/mnt/images/{tenant_id}/{filename}
/mnt/scorm/{tenant_id}/{training_id}/v{version_id}/
```

Nginx serves all three volumes directly using `auth_request` for access validation. Microservices never serve static files (C-203).

---

## 2. Environment Variables

### Required in all environments

| Variable | Service | Description |
|---|---|---|
| `POSTGRES_USER` | postgres | DB username |
| `POSTGRES_PASSWORD` | postgres | DB password |
| `INTERNAL_API_KEY` | auth, core, notification | Internal service-to-service secret |
| `JWT_ROOT_SECRET` | auth | Initial login / tenant selection token secret |
| `EXTERNAL_JWT_SECRET` | auth, gateway | User-facing JWT secret (validated by gateway) |
| `INTERNAL_JWT_SECRET` | gateway, core, notification | Swapped by gateway for internal calls |
| `REDIS_URL` | auth, core, notification | Redis connection string |

### Email (notification-service)

| Variable | Description |
|---|---|
| `MAILGUN_API_KEY` | Mailgun API key |
| `MAILGUN_DOMAIN` | Mailgun sending domain |
| `MAILGUN_BASE_URL` | Mailgun API base URL (default: `https://api.mailgun.net`) |
| `MAILGUN_AUTHORIZED_RECIPIENT` | Dev/sandbox override recipient |
| `USE_MAILGUN` | `True` for real sends, `False` to suppress (dev/test) |

### SCORM

| Variable | Description | Default |
|---|---|---|
| `SCORM_MAX_UPLOAD_MB` | Max SCORM package upload size in MB | `250` |

### Production seed

| Variable | Description |
|---|---|
| `SEED_ADMIN_EMAIL` | Email for the initial SysAdmin account created on first deploy |
| `SEED_ADMIN_PASSWORD` | Password for the initial SysAdmin account |

### Production only

| Variable | Description |
|---|---|
| `FRONTEND_URL` | Public-facing URL (e.g. `https://lms.example.com`) |
| `ENVIRONMENT` | `prod` or `dev` |
| `FRONTEND_DOMAIN` | Public domain for the LMS — Caddy uses this for TLS cert provisioning |
| `LETSENCRYPT_EMAIL` | Email for Let's Encrypt cert expiry notifications |

### GitHub Actions secrets (set in repo Settings → Secrets)

| Secret | Description |
|---|---|
| `PROD_SSH_HOST` | Production server IP or hostname |
| `PROD_SSH_USER` | SSH username on production server |
| `PROD_SSH_KEY` | Private SSH key for production server |

---

## 3. CI/CD — GitHub Actions

Two workflow files handle the full cycle.

### Workflow: CI (`ci.yml`) — runs on every PR targeting `main`

```
PR opened / updated targeting main
  └── .github/workflows/ci.yml
        ├── Auth Service Tests    ─┐
        ├── Core Service Tests     ├── all run in parallel
        ├── Notification Tests     │
        └── Frontend Lint         ─┘
```

Set these as required status checks (Settings → Branches → protection rule for `main`) so the merge button is locked until all pass.

### Workflow: Deploy (`deploy.yml`) — runs on every push to `main`

```
merge dev → main  (push to main)
  └── .github/workflows/deploy.yml
        ├── Auth Service Tests    ─┐
        ├── Core Service Tests     ├── re-run as a safety net
        ├── Notification Tests     │     (guards against direct pushes)
        ├── Frontend Lint         ─┘
        │
        └── deploy  ← only runs if all tests pass
              ├── SSH into ~/app/tenant-lms
              ├── git pull origin main
              ├── alembic upgrade head (per service, before restart)
              ├── docker compose up --build -d
              └── seed_data.py --production (idempotent, no-op if seeded)
```

### What lives where

- **GitHub Secrets** — SSH credentials only (see §2 above)
- **`~/app/tenant-lms/.env`** on the server — all runtime secrets (DB passwords, JWT secrets, Mailgun keys, etc.) — never committed to the repository

---

## 4. Database Migrations

Each service manages its own Alembic migrations. Migrations run automatically as part of every deployment before services restart.

```bash
# Manual migration (per service)
docker compose -f docker-compose.prod.yml run --rm auth-service alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm core-service alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm notification-service alembic upgrade head

# Check current migration version
docker compose -f docker-compose.prod.yml run --rm core-service alembic current

# Roll back one migration (emergency only)
docker compose -f docker-compose.prod.yml run --rm core-service alembic downgrade -1
```

**Rules:**
- Always run migrations before restarting services — never after.
- Never edit or delete an applied migration — always create a new one.
- Each migration must be backward-compatible where possible (add columns with defaults, never drop columns immediately).

---

## 5. Seed Data (Production)

Seed data is the minimum needed to make a fresh production instance functional. It runs **once** on first deployment only, guarded by an existence check.

**What seed data creates:**
- Default SysAdmin account (email + hashed password from env vars `SEED_ADMIN_EMAIL`, `SEED_ADMIN_PASSWORD`)
- Default certificate template (the system default auto-assigned to all new tenants per BR-702)

```bash
# Run seed on first deployment only
docker compose -f docker-compose.prod.yml run --rm auth-service python seed_data.py --production
docker compose -f docker-compose.prod.yml run --rm core-service python seed_data.py --production
```

The `--production` flag ensures the script checks for existing data before inserting and exits cleanly if already seeded.

---

## 6. Mock Data (Development Only)

Mock data populates a realistic development environment. It is **never run in production**.

**What mock data creates:**
- 2–3 tenants with different branding (logo, colours)
- Users across all roles per tenant: SysAdmin, Business Manager, Training Creator, Employee
- Sample trainings: flat and modular structures, published and draft states
- Sample enrollments, quiz attempts, notifications, and certificates
- Sample groups with members

```bash
# Run mock data (dev only)
docker compose run --rm auth-service python seed_data.py --mock
docker compose run --rm core-service python seed_data.py --mock
```

**Protection:** Both `seed_data.py` scripts must check `ENVIRONMENT != "prod"` before running mock data. The GitHub Actions deploy workflow never calls mock seed scripts.

---

## 7. First-Time Server Setup

Run this once on the VPS before the first automated deploy. Subsequent deploys are fully automated via GitHub Actions.

**Prerequisites:**
- Docker and `docker compose` installed on the server
- DNS A record for `FRONTEND_DOMAIN` pointing at the server's public IP (Caddy needs this for Let's Encrypt)

```bash
# 1. SSH into server and clone the repo
ssh user@your-server
git clone https://github.com/<owner>/CustomLMS4.git ~/app/tenant-lms
cd ~/app/tenant-lms

# 2. Create .env from the template and fill in all production values
cp .env.example .env
# Required values to set: POSTGRES_USER, POSTGRES_PASSWORD, all JWT secrets,
# FRONTEND_URL, FRONTEND_DOMAIN, LETSENCRYPT_EMAIL,
# MAILGUN_*, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD, ALLOWED_ORIGINS
vim .env

# 3. Build images and start all services
docker compose --env-file .env -f docker-compose.prod.yml up --build -d

# 4. Run migrations
docker compose --env-file .env -f docker-compose.prod.yml run --rm auth-service alembic upgrade head
docker compose --env-file .env -f docker-compose.prod.yml run --rm core-service alembic upgrade head
docker compose --env-file .env -f docker-compose.prod.yml run --rm notification-service alembic upgrade head

# 5. Seed production data (creates initial SysAdmin + default certificate template)
docker compose --env-file .env -f docker-compose.prod.yml run --rm auth-service python seed_data.py --production

# 6. Verify
docker compose -f docker-compose.prod.yml ps
curl -I https://<FRONTEND_DOMAIN>     # should return 200 with valid TLS cert
```

### Rollback

To roll back to a previous commit, check out that commit on the server and rebuild:

```bash
ssh user@your-server
cd ~/app/tenant-lms
git checkout <previous-sha>
docker compose --env-file .env -f docker-compose.prod.yml up --build -d
```

Migration rollback (if the previous version requires an older schema) must be done manually with `alembic downgrade -1` before checking out the older commit.

