# Technical Constraints — Custom LMS

> Implementation-level rules. Rule IDs (C-xxx) are stable — reference them in code comments, PRs, and tests.

---

## 1. Gateway & Internal Security

**C-101 — No Direct Access**
All microservices (Auth, Core, Notification) must reject traffic not originating from the Gateway's internal IP or carrying a valid `INTERNAL_JWT_SECRET`.

**C-102 — Path Obfuscation**
The Gateway maps internal service routes (e.g., `core-service:8000/api/v1`) to clean public paths (e.g., `/api/training`).

**C-103 — Real-Time Revocation**
The API Gateway verifies tenant status via Redis on every request to ensure immediate lockout for deactivated organizations.

**C-104 — Scope Enforcement**
All internal service endpoints must validate the `scope` claim within `INTERNAL_JWT_SECRET` (e.g., a service cannot send notifications unless it holds `system:notify`).

**C-105 — Secret Hierarchy**
Every service uses the correct secret for its context:

| Secret | Context |
|---|---|
| `JWT_ROOT_SECRET` | Initial login / tenant selection |
| `EXTERNAL_JWT_SECRET` | Validated by the Gateway |
| `INTERNAL_JWT_SECRET` | User-initiated service calls (swapped by Gateway; must include `system_scope`) |
| `INTERNAL_SERVICE_SECRET` | Machine-to-machine trust (e.g., Notification ↔ Core) |

---

## 2. SCORM & Media Handling

**C-201 — Heartbeat Upserts**
The Core Service handles high-frequency SCORM heartbeats using non-blocking **upsert** logic to prevent database bottlenecks.

**C-202 — Storage Isolation**
Three separate Docker volumes with dedicated mount points:

| Volume | Mount | Contents |
|---|---|---|
| `lms_videos` | `/mnt/videos` | Uploaded video files — `{tenant_id}/{training_id}/{filename}` |
| `lms_images` | `/mnt/images` | Rich Text lesson images — `{tenant_id}/{filename}` |
| `lms_scorm` | `/mnt/scorm` | SCORM packages — `{tenant_id}/{training_id}/v{version_id}/` |

All assets are partitioned by `tenant_id` within their volume.

**C-203 — Stateless Serving**
Microservices must NOT serve static files. Nginx serves media and SCORM content from the shared volume using `auth_request` for access validation.

**C-204 — SCORM State Integrity**
Any progress pushback event must explicitly `NULL` the `cmi.suspend_data` bookmark to prevent runtime crashes in the SCORM player.

**C-205 — SCORM Version Support**
The SCORM runtime bridge must support both SCORM 1.2 (`LMSInitialize`, `LMSSetValue`, `LMSCommit`, `LMSFinish`) and SCORM 2004 (`Initialize`, `SetValue`, `Commit`, `Terminate`) API namespaces, implemented using the **scorm-again** library.

**C-206 — SCORM Upload Limit**
Maximum SCORM package upload size is **250MB** by default. Configurable via the `SCORM_MAX_UPLOAD_MB` environment variable. Enforced at the Gateway before the file reaches the Core Service.

**C-207 — SCORM Completion Trust**
The LMS accepts the completion and success status as reported by the SCORM package (`cmi.core.lesson_status` for 1.2; `cmi.completion_status` / `cmi.success_status` for 2004). No score threshold override.

**C-208 — SCORM Attempt Policy**
SCORM lessons are exempt from the quiz attempt limit system. Learners may re-launch a SCORM package unlimited times regardless of prior completion status.

---

## 3. Training & Progress Logic

**C-301 — Shadow Versioning**
Progress is tracked via composite key: `(user_id, training_id, attempt_id)`. All assignments point to a stable `training_id`, but progress records include `version_id`.

**C-302 — Sequential Enforcement**
The backend validates that all prerequisite lessons are marked `Complete` before accepting progress updates for subsequent lessons.

**C-303 — Archival Integrity**
Hard check: if `assignment_count > 0`, a `DELETE` request must be rejected in favor of `HARD_ARCHIVE`.

---

## 4. Operations & Environment

**C-401 — Async Performance**
Backend services use asynchronous drivers (e.g., `asyncpg` for PostgreSQL) to handle high-concurrency SCORM heartbeats.

**C-402 — Centralized Logs**
All services output structured JSON logs to `stdout`.

**C-403 — Reseed Protection**
Seed scripts must check `ENVIRONMENT != "prod"` before running mock data. Production seed (`--production` flag) checks for existing data before inserting and exits cleanly if already seeded. Mock seed (`--mock` flag) is never called from the CI/CD pipeline.

**C-404 — CI/CD Pipeline**
All pushes to `main` trigger a GitHub Actions workflow that runs all backend test suites and lints the frontend. On success, deploys to production via SSH. Alembic migrations run before services restart. No deployment proceeds if any test fails.

**C-405 — Migration Safety**
Migrations always run before service restart, never after. Must be backward-compatible where possible (add columns with defaults; never immediately drop columns). Never edit or delete an applied migration — always create a new one.

**C-406 — Secret Management**
Production credentials (JWT secrets, DB passwords, Mailgun keys) live in a `.env` file on the production server only — never in the repository or GitHub Secrets. GitHub Secrets hold SSH access credentials for deployment only.

**C-407 — Storage Volumes**
Three separate named Docker volumes: `lms_videos`, `lms_images`, `lms_scorm`. Each is independently backed up. `lms_media` (legacy) must be removed and replaced with these three volumes. See `deployment.md` for full volume specifications.

---

## 5. Frontend & UX

**C-501 — Component Library**
Use **shadcn/ui** and **Tailwind CSS** for all interface elements. Never edit files under `components/ui/` — wrap primitives instead.

**C-502 — Unified Sidebar**
Render a single sidebar with role-filtered navigation sections (`Learning`, `Management`, `Studio`). Sections appear only when the user holds the relevant role. No separate dashboards per role — one shell, filtered content.

**C-502a — Sidebar Responsive Behaviour**
- Desktop (`≥ md`): persistent sidebar with collapse toggle in header. Collapsed state shows icons only (no labels). Avatar + display name pinned sticky at bottom of sidebar.
- Mobile (`< md`): sidebar hidden by default. Hamburger in header opens it as a Sheet drawer. Avatar + profile menu rendered in header instead of sidebar.

**C-503 — Responsive Viewport**
All layouts must be fully responsive and mobile-optimized for training consumption.

**C-512 — Notification Service Architecture**
`email_worker` is merged into `notification_service`. The combined service:
- Serves the in-app notifications API (`GET/POST /api/v1/notifications`)
- Runs a background async worker that consumes email jobs from the Redis queue and sends via Mailgun
- Owns all notification channels (in-app, email, future: push/Slack)

The standalone `email_worker` Docker service is deprecated and removed.

**C-511 — Frontend Data Fetching**
Use **TanStack React Query** for all server state management — API calls, caching, background refetching, and loading/error states. Plain fetch inside query/mutation functions. No Redux or other global state library. Verify implementation during codebase audit.

**C-510 — Video Player**
All video lessons use **React Player** for uniform handling of both uploaded files (local filesystem) and external streaming URLs (YouTube, Dailymotion, Vimeo, etc.). Progress tracking uses `onProgress` callbacks to save resume position and record milestones at 25%, 50%, 75%, and 100% watched. Completion gate uses `onEnded`. Resume position is restored when the learner reopens the lesson. No separate player implementation per source type.

**C-509 — Rich Text Editor**
Rich Text lessons are authored using **TipTap** (headless, React-compatible). Rendered output is stored as HTML and displayed to learners with Tailwind prose styling.

**C-507 — PDF Generation**
Certificate PDFs are generated using **WeasyPrint**. HTML templates with resolved tenant/learner variables are rendered to single-page landscape PDFs. WeasyPrint must be installed as a Python dependency in the Core Service container.

**C-508 — Email Configuration**
All Mailgun credentials must be supplied via environment variables: `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`. No credentials hardcoded in source. Set `USE_MAILGUN=False` locally to suppress sends.

**C-504 — CSS Variable Classes Only**
Use `bg-primary`, `text-foreground`, etc. — never hard-code hex values. This is what makes per-tenant branding work.

**C-505 — Class Merging**
Use `cn()` from `lib/utils.ts` for all Tailwind class composition. Never concatenate class strings manually.

**C-506 — Icons**
Use **lucide-react** exclusively for all icons.

---

## 6. Testing & Quality Assurance

**C-601 — Test-Driven Development**
Every service-level requirement must have a corresponding test suite in the service's `/tests` directory. A task is only "complete" once all tests pass in the containerized environment. See [`tests.md`](tests.md) for the full test specification including edge cases.

**C-602 — Tenant Isolation Audits**
Integration tests must explicitly verify "Tenant Leakage" — e.g., attempting to fetch a Training ID belonging to Tenant B using a JWT scoped for Tenant A.

**C-603 — Version Pushback Simulations**
Automated tests must simulate a content update and verify that affected users are pushed back to the correct lesson and their `cmi.suspend_data` is nulled.

**C-604 — Gateway Mocking**
Backend unit tests must mock the Gateway's token swap to ensure services correctly validate `INTERNAL_JWT_SECRET` and its `system_scope` claims.

**C-605 — Async Concurrency Testing**
The Core service must be stress-tested for concurrent SCORM heartbeats to verify the upsert logic prevents race conditions or database deadlocks.

**C-606 — Mandatory Regression Testing**
After every logic change, the full backend API test suite for the affected service must pass before the task is considered complete.
