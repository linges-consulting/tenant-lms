# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

A **B2B multi-tenant LMS** for small-business employee training. Each tenant is data-isolated.

### Documentation — always read before starting any feature work

All authoritative documentation lives in **`project_docs/`**:

| File | Purpose |
|---|---|
| [`project_docs/requirements.md`](project_docs/requirements.md) | Full product requirements — roles, auth, training structure, notifications, onboarding |
| [`project_docs/business_rules.md`](project_docs/business_rules.md) | Behavioral rules with stable IDs (BR-xxx) — invitation lifecycle, versioning, deletion policy |
| [`project_docs/constraints.md`](project_docs/constraints.md) | Technical constraints with stable IDs (C-xxx) — security, storage, testing, frontend rules |
| [`project_docs/roadmap.md`](project_docs/roadmap.md) | Phase status and build order — what's done, in progress, and planned |
| [`project_docs/tests.md`](project_docs/tests.md) | Full backend test specification — all test cases, edge cases, and isolation tests by service |
| [`project_docs/deployment.md`](project_docs/deployment.md) | Deployment guide — GitHub Actions CI/CD, volumes, migrations, seed data, env vars, runbook |

> **Note:** `app/agent.md` is an older reference file and may be outdated. `project_docs/` is the source of truth.
>
> **Note:** `docker-compose.yml` references `./src/` paths but the actual service code lives in `./app/`. If you update docker-compose, use `./app/` as the context root.

---

## Running the Stack

```bash
# Start all services (gateway, auth, core, notification, frontend, postgres, redis)
# Note: email_worker is merged into notification_service — no separate email-worker service
docker compose up --build

# Start a single service (e.g. auth-service)
docker compose up auth-service

# View logs for a service
docker compose logs -f auth-service
```

| Service | Host port | Docker internal port |
|---|---|---|
| Gateway (Nginx) | 80 | 80 |
| Auth Service | 8000 | 8000 |
| Core Service | 8001 | 8000 |
| Notification Service | 8002 | 8000 |
| Frontend (Vite dev) | 5173 | 80 |
| PostgreSQL | 5433 | 5432 |
| Redis | 6379 | 6379 |

---

## Frontend Commands

All commands run from `app/frontend/`.

```bash
cd app/frontend
npm run dev       # Vite dev server (hot reload)
npm run build     # tsc + vite build
npm run lint      # ESLint — must pass before any frontend task is complete
npm run preview   # Preview production build
```

**Zero-error policy:** run `npm run lint` after every frontend change and fix all warnings before considering the task done.

---

## Backend — Running Tests

Tests live inside each service directory at `<service>/tests/`. Run them inside Docker or with a local venv pointed at the service's `requirements.txt`.

```bash
# Inside the running container
docker compose exec auth-service pytest tests/

# Or locally (from app/auth_service/)
pytest tests/

# Run a specific test file
pytest tests/api/auth/test_login.py

# Coverage
pytest tests/ --cov=app --cov-report=html:tests/artifacts/coverage
```

Every service (`auth_service`, `core_service`, `notification_service`) has its own `tests/` directory. No test files should appear outside those directories.

---

## Frontend — Running Tests

Vitest + Testing Library + jsdom. All commands run from `app/frontend/`.

```bash
cd app/frontend

npm test               # one-shot run (use this in CI)
npm run test:watch     # interactive watch mode

# Run a single file
npx vitest run src/pages/__tests__/TrainingViewer.test.tsx

# Filter by test name
npx vitest run -t "module-level completion"
```

Test files live next to the code they cover:

```
src/
  components/__tests__/  # component-level tests (e.g. RichTextEditor)
  pages/__tests__/       # page-level tests (e.g. TrainingViewer, ManagerTrainings)
  test/
    setup.ts             # jest-dom matchers, jsdom polyfills (ResizeObserver, matchMedia, createObjectURL)
    utils.tsx            # renderWithProviders() — wraps in MemoryRouter; export-all from @testing-library/react
```

Conventions:
- Use `import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils'` — don't import RTL directly.
- Mock API modules with `vi.mock('../../api/<resource>')`; capture API fn refs at module scope so tests can read `.mock.calls`.
- Mock the auth context (`vi.mock('../../contexts/auth-context')`) and stub heavy components (`RichTextEditor`, `TrainingAuditTimeline`, `react-player`, `sonner`) per suite.
- Call `vi.clearAllMocks()` in each suite's `beforeEach` — otherwise call counts leak between tests.
- Verify navigation via a `<Routes>` wrapper with a marker component on the destination, not `window.location` (MemoryRouter doesn't update it).

---

## Database Migrations (Alembic)

Each backend service manages its own Alembic migrations.

```bash
# Generate a migration (run from inside the service directory)
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

---

## Architecture

### Service Routing (via Nginx Gateway on port 80)

| URL prefix | Routed to |
|---|---|
| `/api/v1/auth`, `/api/v1/users`, `/api/v1/tenants`, `/api/v1/groups`, `/api/v1/assignments`, `/api/v1/onboarding` | `auth-service:8000` |
| `/api/v1/trainings`, `/api/v1/certificates`, `/api/v1/progress`, `/api/v1/user-report` | `core-service:8000` |
| `/api/v1/notifications` | `notification-service:8000` |
| `/storage/media/` | Served directly from shared volume (Nginx `auth_request` gated) |
| `/storage/scorm/` | Served directly from shared volume (Nginx `auth_request` gated) |
| `/` | `frontend:80` |

### Service Layout

Each FastAPI service follows the same structure:
```
<service>/app/
  api/v1/endpoints/   # Route handlers
  api/v1/api.py       # APIRouter assembly
  core/               # Business logic / config / security
  db/                 # SQLAlchemy session setup
  models/             # ORM models
  schemas/            # Pydantic schemas
  utils/
```

`auth_service` is the exception — its `main.py` lives at the root of `app/auth_service/` alongside `models.py`.

### Frontend Structure

```
app/frontend/src/
  api/            # One file per resource (client.ts handles auth + tenant headers)
  components/     # Feature components + layout/
  components/ui/  # shadcn/ui primitives — never edit directly, wrap instead
  contexts/       # auth-context, notification-context, theme-context
  layouts/        # AppLayout, DynamicLayout (role-aware shell)
  pages/          # One file per route (Admin*, Manager*, Learner*, Auth*)
  lib/            # utils.ts (cn()), auth-storage.ts
  hooks/          # Custom hooks
  queries/        # TanStack React Query hooks — one file per resource
```

**Key frontend libraries:**
- **TanStack React Query** — all server state, caching, loading/error handling
- **TipTap** — rich text lesson authoring and rendering
- **React Player** — video lessons (local files + YouTube, Dailymotion, Vimeo, etc.)
- **scorm-again** — SCORM 1.2 + 2004 runtime bridge (Phase 8)
- **shadcn/ui + lucide-react** — UI components and icons

### Multi-Tenancy

- Every DB query **must** filter by `tenant_id` from the JWT. No exceptions.
- JWT carries `tenant_id`, `user_id`, and per-tenant role flags.
- After tenant selection the frontend sets CSS variables for branding:
  ```ts
  document.documentElement.style.setProperty("--primary", tenant.primary_color)
  ```
- All API modules check that the resource's `tenant_id` matches the JWT `tenant_id`.

### Email & Notifications

The `notification_service` handles both in-app notifications (HTTP API) and email delivery (background Redis queue consumer). There is no separate `email_worker` service. Set `USE_MAILGUN=False` in `.env` for local development to suppress actual sends.

---

## Non-Negotiable Rules

These apply to every file, endpoint, and migration:

1. **Tenant scoping** — every DB query filters by `tenant_id` from the JWT. No exceptions.
2. **No hard deletes** — use `deleted_at` on users, trainings, enrollments.
3. **Audit log is append-only** — never `UPDATE` or `DELETE` `audit_logs`.
4. **Heartbeat must refresh JWT** — include `new_token` header when remaining lifetime ≤ 10 min. Heartbeat is training-viewer only.
5. **Lesson gating is server-enforced** — Lesson N locked until N-1 complete; Chapter N locked until all lessons in Chapter N-1 complete. Frontend lock is UX only; API re-validates.
6. **Progress resets must be audited** — log in `audit_logs` with `event_type = "progress_reset"` and `version_id`.
7. **Magic Link tokens** — single-use, expire in 48 h, new users only. Existing active users are auto-linked without a Magic Link.
8. **No cloud storage in MVP** — three separate volumes: `lms_videos` (`/mnt/videos/`), `lms_images` (`/mnt/images/`), `lms_scorm` (`/mnt/scorm/`). Nginx serves all three, never microservices.
9. **Draft/publish separation** — changes invisible to learners until `is_published = true`. Only the training owner can publish or unpublish.
10. **Completion records are immutable** — never alter once written with a `training_version_id`.
11. **Users cannot change their own name or email** — locked in UI, enforced in API. SysAdmins can change names with a mandatory audit note.
12. **SysAdmins are global-only** — cannot hold tenant memberships. Cannot view specific training content.
13. **Training assignment is Manager-only** — Training Creators build content; Business Managers assign it to users/groups.
14. **SCORM is exempt from attempt limits** — learners may re-launch unlimited times.
15. **Training structure is flexible** — any training can contain standalone chapters, modules with chapters, or a mix of both. The `structure_type` DB column is retained for data history but is no longer enforced. Creators can add modules or chapters to any training regardless of `structure_type`.
16. **Frontend zero-error policy** — `npm run lint` must pass before completing any frontend task.

---

## UI / Component Rules

- Use `cn()` from `lib/utils.ts` for class merging — never concatenate strings.
- Icons: **lucide-react** only.
- Never edit `components/ui/` — wrap shadcn primitives instead.
- Every component needs a typed props interface — no `any`.
- CSS variable classes only (`bg-primary`, `text-foreground`) — never hard-code hex values.

### Sidebar & Navigation
- Single sidebar, role-filtered sections: **Learning** (all), **Management** (Managers + SysAdmins), **Studio** (Training Creators).
- Desktop: persistent sidebar with collapse toggle in header (icon-only mode when collapsed). Avatar + name pinned sticky at sidebar bottom.
- Mobile: sidebar hidden, hamburger opens Sheet drawer, avatar shown in header.

### Backend Library Quick Reference
- **PDF**: WeasyPrint (HTML → single-page landscape PDF)
- **Email**: Mailgun API (`MAILGUN_API_KEY`, `MAILGUN_DOMAIN` env vars; `USE_MAILGUN=False` to suppress locally)
- **Background jobs**: Redis queue consumed by `notification_service` worker
