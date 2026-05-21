# Infrastructure Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all infrastructure so `docker compose up --build` succeeds, all three storage volumes are correct, nginx routes all required paths, and GitHub Actions CI/CD exists.

**Architecture:** docker-compose.yml and docker-compose.prod.yml both use `./src/` paths that do not exist — all service code lives in `./app/`. This plan corrects all 24+ path references, removes the deprecated standalone `email-worker` service, replaces the single `lms_media` volume with three separate volumes (`lms_videos`, `lms_images`, `lms_scorm`), adds missing JWT env vars, and creates `.env.example` and `.github/workflows/deploy.yml`.

**Tech Stack:** Docker Compose, Nginx, GitHub Actions

---

## File Map

| File | Action |
|---|---|
| `docker-compose.yml` | Modify — fix all `./src/` → `./app/`, remove email-worker, fix volumes, add JWT env vars |
| `docker-compose.prod.yml` | Modify — same corrections for production |
| `app/gateway/nginx.conf` | Modify — add `/api/v1/progress`, `/storage/videos/`, `/storage/images/`, `/storage/scorm/` routes |
| `.env.example` | Create — document all required environment variables |
| `.github/workflows/deploy.yml` | Create — CI/CD: test → lint → SSH deploy → migrate → restart |

---

### Task 1: Fix docker-compose.yml — service build contexts

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Open `docker-compose.yml` and replace all `./src/` context paths with `./app/`**

Replace the entire file with the corrected version:

```yaml
services:
  gateway:
    build:
      context: ./app/gateway
    ports:
      - "80:80"
    volumes:
      - lms_videos:/mnt/videos
      - lms_images:/mnt/images
      - lms_scorm:/mnt/scorm
      - ./app/gateway/nginx.conf:/etc/nginx/nginx.conf:ro
    networks:
      - lms-network
    depends_on:
      - frontend
      - auth-service
      - core-service
      - notification-service

  auth-service:
    build:
      context: ./app/auth_service
    environment:
      - DB_URL=postgresql://${POSTGRES_USER:-lms_user}:${POSTGRES_PASSWORD:-lms_pass}@postgres/auth_db
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_KEY=${INTERNAL_API_KEY:-super-secret-internal-key}
      - JWT_ROOT_SECRET=${JWT_ROOT_SECRET:-change-me-root}
      - EXTERNAL_JWT_SECRET=${EXTERNAL_JWT_SECRET:-change-me-external}
      - INTERNAL_JWT_SECRET=${INTERNAL_JWT_SECRET:-change-me-internal}
      - ENVIRONMENT=dev
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./app/auth_service:/app
      - /app/__pycache__
    networks:
      - lms-network
    depends_on:
      - postgres
      - redis

  core-service:
    build:
      context: ./app/core_service
    environment:
      - DB_URL=postgresql://${POSTGRES_USER:-lms_user}:${POSTGRES_PASSWORD:-lms_pass}@postgres/core_db
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_KEY=${INTERNAL_API_KEY:-super-secret-internal-key}
      - EXTERNAL_JWT_SECRET=${EXTERNAL_JWT_SECRET:-change-me-external}
      - INTERNAL_JWT_SECRET=${INTERNAL_JWT_SECRET:-change-me-internal}
      - AUTH_SERVICE_URL=http://auth-service:8000
      - ENVIRONMENT=dev
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8001:8000"
    volumes:
      - lms_videos:/mnt/videos
      - lms_images:/mnt/images
      - lms_scorm:/mnt/scorm
      - ./app/core_service:/app
      - /app/__pycache__
    networks:
      - lms-network
    depends_on:
      - postgres
      - redis

  notification-service:
    build:
      context: ./app/notification_service
    environment:
      - DB_URL=postgresql://${POSTGRES_USER:-lms_user}:${POSTGRES_PASSWORD:-lms_pass}@postgres/notification_db
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_KEY=${INTERNAL_API_KEY:-super-secret-internal-key}
      - EXTERNAL_JWT_SECRET=${EXTERNAL_JWT_SECRET:-change-me-external}
      - INTERNAL_JWT_SECRET=${INTERNAL_JWT_SECRET:-change-me-internal}
      - ENVIRONMENT=${ENVIRONMENT:-dev}
      - MAILGUN_API_KEY=${MAILGUN_API_KEY}
      - MAILGUN_DOMAIN=${MAILGUN_DOMAIN}
      - MAILGUN_BASE_URL=${MAILGUN_BASE_URL:-https://api.mailgun.net}
      - MAILGUN_AUTHORIZED_RECIPIENT=${MAILGUN_AUTHORIZED_RECIPIENT}
      - USE_MAILGUN=${USE_MAILGUN:-False}
      - FROM_EMAIL=${FROM_EMAIL:-noreply@example.com}
      - FRONTEND_URL=${FRONTEND_URL:-http://localhost}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8002:8000"
    volumes:
      - ./app/notification_service:/app
      - /app/__pycache__
    networks:
      - lms-network
    depends_on:
      - postgres
      - redis

  frontend:
    build:
      context: ./app/frontend
      dockerfile: Dockerfile
      target: dev
    ports:
      - "5173:80"
    volumes:
      - ./app/frontend:/app
      - /app/node_modules
    networks:
      - lms-network

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-lms_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-lms_pass}
      POSTGRES_DB: ${POSTGRES_DB:-lms_db}
    ports:
      - "5433:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./app/postgres/init-multiple-databases.sh:/docker-entrypoint-initdb.d/init-multiple-databases.sh
    networks:
      - lms-network

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - lms-network

networks:
  lms-network:
    driver: bridge

volumes:
  lms_videos:
  lms_images:
  lms_scorm:
  postgres_data:
  redis_data:
```

- [ ] **Step 2: Verify no `./src/` references remain**

```bash
grep -r "\./src/" docker-compose.yml
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "fix: correct all service paths and volumes in docker-compose.yml"
```

---

### Task 2: Fix docker-compose.prod.yml

**Files:**
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Read the current prod file**

```bash
cat docker-compose.prod.yml
```

- [ ] **Step 2: Apply the same corrections as Task 1 — `./src/` → `./app/`, remove email-worker, fix volumes, add JWT env vars**

The prod file should use the same service definitions as dev but with:
- No `--reload` flag on uvicorn commands
- No `ports` exposure for internal services (gateway only exposes 80)
- `target: prod` on frontend build
- `ENVIRONMENT=prod`
- Same three volumes: `lms_videos`, `lms_images`, `lms_scorm`
- Same JWT env vars: `JWT_ROOT_SECRET`, `EXTERNAL_JWT_SECRET`, `INTERNAL_JWT_SECRET`
- `USE_MAILGUN=True` for prod

Example auth-service in prod:
```yaml
  auth-service:
    build:
      context: ./app/auth_service
    environment:
      - DB_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/auth_db
      - REDIS_URL=redis://redis:6379/0
      - INTERNAL_API_KEY=${INTERNAL_API_KEY}
      - JWT_ROOT_SECRET=${JWT_ROOT_SECRET}
      - EXTERNAL_JWT_SECRET=${EXTERNAL_JWT_SECRET}
      - INTERNAL_JWT_SECRET=${INTERNAL_JWT_SECRET}
      - ENVIRONMENT=prod
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    volumes:
      - lms_videos:/mnt/videos
      - lms_images:/mnt/images
      - lms_scorm:/mnt/scorm
    networks:
      - lms-network
    depends_on:
      - postgres
      - redis
```

Apply the same pattern for core-service, notification-service.

- [ ] **Step 3: Verify**

```bash
grep -r "\./src/" docker-compose.prod.yml
grep "email.worker" docker-compose.prod.yml
grep "lms_media" docker-compose.prod.yml
```

Expected: all return no output.

- [ ] **Step 4: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "fix: correct prod compose paths, volumes, remove email-worker"
```

---

### Task 3: Fix nginx.conf — add missing routes and storage locations

**Files:**
- Modify: `app/gateway/nginx.conf`

- [ ] **Step 1: Add `/api/v1/progress` route to nginx.conf**

Add this block inside the `server {}` block, after the `/api/v1/certificates` block:

```nginx
        location /api/v1/progress {
            proxy_pass $core_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }

        location /api/v1/dashboards {
            proxy_pass $core_service;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
```

- [ ] **Step 2: Replace the old `/media/` block with three new storage blocks**

Remove:
```nginx
        location /media/ {
            alias /mnt/media/;
            autoindex off;
            add_header Cache-Control "public, max-age=31536000";
        }
```

Add:
```nginx
        # Internal auth validation endpoint (called by auth_request)
        location = /internal/validate-media-access {
            internal;
            proxy_pass $auth_service/api/v1/auth/validate-media;
            proxy_pass_request_body off;
            proxy_set_header Content-Length "";
            proxy_set_header X-Original-URI $request_uri;
            proxy_set_header Authorization $http_authorization;
        }

        location /storage/videos/ {
            auth_request /internal/validate-media-access;
            alias /mnt/videos/;
            autoindex off;
            add_header Cache-Control "private, max-age=3600";
        }

        location /storage/images/ {
            auth_request /internal/validate-media-access;
            alias /mnt/images/;
            autoindex off;
            add_header Cache-Control "private, max-age=3600";
        }

        location /storage/scorm/ {
            auth_request /internal/validate-media-access;
            alias /mnt/scorm/;
            autoindex off;
            add_header Cache-Control "private, no-store";
        }
```

- [ ] **Step 3: Increase client_max_body_size for SCORM uploads (250MB)**

Add inside the `http {}` block, before the `server {}` block:

```nginx
    client_max_body_size 260m;
```

- [ ] **Step 4: Add the media validation endpoint to auth_service**

Create `app/auth_service/app/api/v1/endpoints/media.py`:

```python
from fastapi import APIRouter, Header, HTTPException
from app.core.security import decode_token

router = APIRouter()

@router.get("/validate-media")
async def validate_media_access(
    authorization: str | None = Header(default=None),
    x_original_uri: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401)
    token = authorization.removeprefix("Bearer ")
    try:
        decode_token(token)
    except Exception:
        raise HTTPException(status_code=401)
    return {"status": "ok"}
```

Register the router in `app/auth_service/app/api/v1/api.py`:

```python
from app.api.v1.endpoints import auth, users, tenants, groups, assignments, media

# existing includes ...
api_router.include_router(media.router, prefix="/auth", tags=["media"])
```

- [ ] **Step 5: Verify nginx config is valid (inside gateway container)**

```bash
docker compose run --rm gateway nginx -t
```

Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful`

- [ ] **Step 6: Commit**

```bash
git add app/gateway/nginx.conf app/auth_service/app/api/v1/endpoints/media.py app/auth_service/app/api/v1/api.py
git commit -m "fix: add progress/dashboard/storage routes to nginx, auth_request on storage"
```

---

### Task 4: Create .env.example

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Create `.env.example` with all required variables**

```bash
cat > .env.example << 'EOF'
# ── Database ─────────────────────────────────────────────────────────────────
POSTGRES_USER=lms_user
POSTGRES_PASSWORD=change-me-in-prod
POSTGRES_DB=lms_db

# ── JWT Secrets (generate with: openssl rand -hex 32) ─────────────────────
JWT_ROOT_SECRET=change-me
EXTERNAL_JWT_SECRET=change-me
INTERNAL_JWT_SECRET=change-me
INTERNAL_API_KEY=change-me

# ── Mailgun ──────────────────────────────────────────────────────────────────
USE_MAILGUN=False                       # set True in prod
MAILGUN_API_KEY=
MAILGUN_DOMAIN=
MAILGUN_BASE_URL=https://api.mailgun.net
FROM_EMAIL=noreply@yourdomain.com
MAILGUN_AUTHORIZED_RECIPIENT=          # dev redirect address

# ── App ──────────────────────────────────────────────────────────────────────
ENVIRONMENT=dev
FRONTEND_URL=http://localhost

# ── SCORM ────────────────────────────────────────────────────────────────────
SCORM_MAX_UPLOAD_MB=250
EOF
```

- [ ] **Step 2: Add `.env` to `.gitignore` if not already present**

```bash
grep -q "^\.env$" .gitignore 2>/dev/null || echo ".env" >> .gitignore
```

- [ ] **Step 3: Commit**

```bash
git add .env.example .gitignore
git commit -m "chore: add .env.example with all required variables"
```

---

### Task 5: Create GitHub Actions CI/CD workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create the workflow directory and file**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Write `.github/workflows/deploy.yml`**

```yaml
name: Test, Lint, and Deploy

on:
  push:
    branches: [main]

jobs:
  test-auth:
    name: Auth Service Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: lms_user
          POSTGRES_PASSWORD: lms_pass
          POSTGRES_DB: auth_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r app/auth_service/requirements.txt
      - name: Run auth tests
        working-directory: app/auth_service
        env:
          DB_URL: postgresql://lms_user:lms_pass@localhost/auth_db
          EXTERNAL_JWT_SECRET: test-secret
          INTERNAL_JWT_SECRET: test-internal
          ENVIRONMENT: test
        run: pytest tests/ -v --tb=short

  test-core:
    name: Core Service Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: lms_user
          POSTGRES_PASSWORD: lms_pass
          POSTGRES_DB: core_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r app/core_service/requirements.txt
      - name: Run core tests
        working-directory: app/core_service
        env:
          DB_URL: postgresql://lms_user:lms_pass@localhost/core_db
          EXTERNAL_JWT_SECRET: test-secret
          INTERNAL_JWT_SECRET: test-internal
          ENVIRONMENT: test
        run: pytest tests/ -v --tb=short

  test-notification:
    name: Notification Service Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: lms_user
          POSTGRES_PASSWORD: lms_pass
          POSTGRES_DB: notification_db
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r app/notification_service/requirements.txt
      - name: Run notification tests
        working-directory: app/notification_service
        env:
          DB_URL: postgresql://lms_user:lms_pass@localhost/notification_db
          EXTERNAL_JWT_SECRET: test-secret
          INTERNAL_JWT_SECRET: test-internal
          ENVIRONMENT: test
          USE_MAILGUN: "False"
        run: pytest tests/ -v --tb=short

  lint-frontend:
    name: Frontend Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: app/frontend/package-lock.json
      - name: Install dependencies
        working-directory: app/frontend
        run: npm ci
      - name: Lint
        working-directory: app/frontend
        run: npm run lint

  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [test-auth, test-core, test-notification, lint-frontend]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_SSH_HOST }}
          username: ${{ secrets.PROD_SSH_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            set -e
            cd /opt/lms
            git pull origin main

            # Run migrations before restart
            docker compose -f docker-compose.prod.yml run --rm auth-service alembic upgrade head
            docker compose -f docker-compose.prod.yml run --rm core-service alembic upgrade head
            docker compose -f docker-compose.prod.yml run --rm notification-service alembic upgrade head

            # Restart services
            docker compose -f docker-compose.prod.yml up -d --build

            # Seed production data (idempotent)
            docker compose -f docker-compose.prod.yml run --rm auth-service python seed_data.py --production
```

- [ ] **Step 3: Add required GitHub Secrets to the repo**

In GitHub → Settings → Secrets → Actions, add:
- `PROD_SSH_HOST` — production server IP or hostname
- `PROD_SSH_USER` — SSH login username
- `PROD_SSH_KEY` — private SSH key (the server must have the matching public key in `authorized_keys`)

These are the only secrets that go in GitHub. All app credentials (`EXTERNAL_JWT_SECRET`, `MAILGUN_API_KEY`, etc.) live in `/opt/lms/.env` on the production server.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add GitHub Actions test+lint+deploy workflow"
```

---

### Task 6: Smoke test the full stack

- [ ] **Step 1: Build and start all services**

```bash
docker compose up --build -d
```

Expected: all services start without `context not found` or volume errors.

- [ ] **Step 2: Check all services are healthy**

```bash
docker compose ps
```

Expected: `auth-service`, `core-service`, `notification-service`, `frontend`, `gateway`, `postgres`, `redis` all showing `running` or `healthy`. No `email-worker` service.

- [ ] **Step 3: Verify routing**

```bash
curl -s http://localhost/api/v1/auth/health | python3 -m json.tool
curl -s http://localhost/api/v1/trainings/health | python3 -m json.tool
curl -s http://localhost/api/v1/notifications/health | python3 -m json.tool
```

Expected: each returns `{"status": "ok", "service": "..."}`.

- [ ] **Step 4: Verify volumes exist**

```bash
docker volume ls | grep lms
```

Expected output includes `lms_videos`, `lms_images`, `lms_scorm`. No `lms_media`.

- [ ] **Step 5: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: infrastructure smoke-test fixes"
```
