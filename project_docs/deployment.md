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

### Production only

| Variable | Description |
|---|---|
| `FRONTEND_URL` | Public-facing URL (e.g. `https://yourlms.com`) |
| `ENVIRONMENT` | `prod` or `dev` |
| `REDIS_URL` | External Redis URL if not using the compose redis service |

---

## 3. CI/CD — GitHub Actions

Deployment is triggered automatically on every push to the `main` branch.

### Workflow overview

```
push to main
  └── GitHub Actions
        ├── Run tests (all services)
        ├── Lint frontend
        └── Deploy to production
              ├── SSH into server
              ├── git pull
              ├── docker compose build
              ├── Run Alembic migrations (per service)
              └── docker compose up -d
```

### Workflow file: `.github/workflows/deploy.yml`

```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build and test auth-service
        run: |
          docker compose -f docker-compose.yml build auth-service
          docker compose -f docker-compose.yml run --rm auth-service pytest tests/ -v

      - name: Build and test core-service
        run: |
          docker compose -f docker-compose.yml build core-service
          docker compose -f docker-compose.yml run --rm core-service pytest tests/ -v

      - name: Build and test notification-service
        run: |
          docker compose -f docker-compose.yml build notification-service
          docker compose -f docker-compose.yml run --rm notification-service pytest tests/ -v

      - name: Lint frontend
        run: |
          docker compose -f docker-compose.yml build frontend
          docker compose -f docker-compose.yml run --rm frontend npm run lint

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: test
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/lms

            # Pull latest code
            git pull origin main

            # Build new images
            docker compose -f docker-compose.prod.yml build

            # Run migrations (safe — Alembic only applies unapplied)
            docker compose -f docker-compose.prod.yml run --rm auth-service alembic upgrade head
            docker compose -f docker-compose.prod.yml run --rm core-service alembic upgrade head
            docker compose -f docker-compose.prod.yml run --rm notification-service alembic upgrade head

            # Restart all services
            docker compose -f docker-compose.prod.yml up -d

            # Clean up unused images
            docker image prune -f
```

### GitHub Secrets required

| Secret | Description |
|---|---|
| `PROD_HOST` | Production server IP or hostname |
| `PROD_USER` | SSH username on production server |
| `PROD_SSH_KEY` | Private SSH key for production server |

Production environment variables (Mailgun, JWT secrets, DB credentials) are stored in a `.env` file on the production server at `/opt/lms/.env` — never in GitHub Secrets or the repository.

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

## 7. Manual Deployment Runbook

For emergency manual deployments or first-time server setup:

```bash
# 1. SSH into server
ssh user@your-server

# 2. Clone repo (first time only)
git clone https://github.com/your-org/custom-lms.git /opt/lms
cd /opt/lms

# 3. Create .env file from template (first time only)
cp .env.example .env
# Edit .env with production values

# 4. Create volumes (first time only)
docker volume create lms_videos
docker volume create lms_images
docker volume create lms_scorm
docker volume create postgres_data
docker volume create redis_data

# 5. Build and start
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 6. Run migrations
docker compose -f docker-compose.prod.yml run --rm auth-service alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm core-service alembic upgrade head
docker compose -f docker-compose.prod.yml run --rm notification-service alembic upgrade head

# 7. Run production seed (first time only)
docker compose -f docker-compose.prod.yml run --rm auth-service python seed_data.py --production
docker compose -f docker-compose.prod.yml run --rm core-service python seed_data.py --production

# 8. Verify services are running
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=50
```

---

## 8. Known Issues in Current Docker Compose Files

The following must be fixed before the next deployment:

- [ ] Both files use `./src/` paths — actual code lives in `./app/`
- [ ] `email-worker` service must be removed (merged into `notification-service`)
- [ ] `lms_media` volume needs to be replaced with `lms_videos`, `lms_images`, `lms_scorm`
- [ ] Mailgun env vars must move from `auth-service` to `notification-service` in prod file
- [ ] `SCORM_MAX_UPLOAD_MB` env var missing from all services
- [ ] `FRONTEND_URL` missing from dev compose (needed for Magic Link emails)
- [ ] JWT secret env vars (`JWT_ROOT_SECRET`, `EXTERNAL_JWT_SECRET`, `INTERNAL_JWT_SECRET`) not consistently defined across services
