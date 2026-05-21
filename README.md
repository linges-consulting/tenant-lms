# Enterprise Learning Platform

A B2B multi-tenant Learning Management System for small-business employee training. Each tenant is data-isolated; learners, trainings, certificates, assignments, and notifications are all scoped to a single organization.

## Stack at a glance

| Layer | Tech |
|---|---|
| Frontend | React 19, Vite, TypeScript, Tailwind, shadcn/ui, TanStack Query, TipTap, react-player, scorm-again |
| Backend | FastAPI (Python 3.11), SQLAlchemy 2 async, Pydantic v2 |
| Data | PostgreSQL 16, Redis (cache + event bus), three Docker volumes for media (`lms_videos`, `lms_images`, `lms_scorm`) |
| Gateway | Nginx — terminates all `/api/v1/*` and `/storage/*` routes |
| PDFs | WeasyPrint (certificates) |
| Email | Mailgun (toggleable via `USE_MAILGUN` for local dev) |

## Services

| Service | Host port | Purpose |
|---|---|---|
| Gateway (Nginx) | 80 | Routes `/api/v1/*`, serves `/storage/*` |
| `auth-service` | 8000 | Identity, tenants, users, groups, assignments, onboarding |
| `core-service` | 8001 | Trainings, modules, chapters, quizzes, progress, certificates |
| `notification-service` | 8002 | In-app notifications + email worker (one process, no separate worker) |
| Frontend (Vite) | 5173 | Dev server |
| PostgreSQL | 5433 | |
| Redis | 6379 | |

## Getting started

```bash
# Bring up the whole stack
docker compose up --build

# Logs for a single service
docker compose logs -f core-service

# Frontend dev server (HMR, runs against the dockerized gateway)
cd app/frontend && npm install && npm run dev
```

## Tests

```bash
# Backend (per service, inside the container)
docker compose exec core-service pytest tests/

# Frontend (Vitest + Testing Library + jsdom)
cd app/frontend && npm test
```

See [`CLAUDE.md`](CLAUDE.md) for the full conventions (how to mock APIs, what to stub, navigation assertions, etc.).

## Repository layout

```
app/
  auth_service/         # FastAPI — users, tenants, groups, onboarding
  core_service/         # FastAPI — trainings, chapters, quizzes, progress
  notification_service/ # FastAPI — in-app + email
  frontend/             # React + Vite
  gateway/              # Nginx config
project_docs/           # Source of truth — requirements, business rules, roadmap, tests
docker-compose.yml
CLAUDE.md               # Working conventions for contributors and AI assistants
```

## Documentation

Authoritative docs live under [`project_docs/`](project_docs/). Always read before starting feature work:

| Doc | Purpose |
|---|---|
| [`requirements.md`](project_docs/requirements.md) | Product requirements — roles, auth, training structure, notifications |
| [`business_rules.md`](project_docs/business_rules.md) | Behavioral rules with stable IDs (BR-xxx) |
| [`constraints.md`](project_docs/constraints.md) | Technical constraints with stable IDs (C-xxx) |
| [`roadmap.md`](project_docs/roadmap.md) | Phase status and build order |
| [`tests.md`](project_docs/tests.md) + [`tests/`](project_docs/tests/) | Backend test spec + per-feature manual/API test cases |
| [`deployment.md`](project_docs/deployment.md) | CI/CD, secrets, runbook |

`CLAUDE.md` at the root captures non-negotiable rules (tenant scoping, no hard deletes, draft/publish separation, JWT heartbeat, etc.), UI conventions, and how to run things locally.

## Non-negotiables (excerpt)

These are enforced in every endpoint and frontend module — see `CLAUDE.md` for the full list:

- Every DB query filters by `tenant_id` from the JWT.
- No hard deletes — `deleted_at` only.
- `audit_logs` is append-only.
- Lesson gating is server-enforced. The frontend lock is UX only; the API re-validates.
- Completion records (`enrollment.training_version_id`) are immutable once written.
- SysAdmins are global only — cannot hold tenant memberships.
- Training assignment is Manager-only; Training Creators build content but don't assign it.
- `npm run lint` must pass before a frontend task is considered complete.
