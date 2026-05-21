# Testing Strategy — Design Spec

**Date:** 2026-05-14
**Status:** Approved — ready for implementation planning
**Scope:** Backend services (auth, core, notification) + Nginx gateway. Frontend tests are out of scope.

---

## 1. Goal

Move the project from "each service has some tests" to a layered, runnable, measurable test suite that:

1. Verifies **behavioral correctness** — what the system does from the outside, per role and per tenant — not just implementation correctness.
2. Verifies **cross-service flows** end-to-end through the real Nginx gateway and real Docker stack.
3. Verifies **notification side effects** (in-app + email) using structured logs as the evidence surface (no real Mailgun calls in dev).
4. Exposes a **single runner script** outside `app/` with flags for unit, smoke, behavioral, integration, regression, and per-service execution.
5. Maps every test to a spec ID from `project_docs/tests.md` so coverage is measurable.

The existing in-process unit tests under `app/<service>/tests/` are kept as-is and called by the new runner. Nothing currently passing gets broken.

---

## 2. Foundational Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Hybrid execution model** | Keep fast in-process unit tests (SQLite + ASGI). Add a new top-level tier that runs against the real Docker stack. Best of both: fast inner loop, real coverage of gateway/Redis/cross-service. |
| 2 | **`/tests` at repo root, organized by category** | Subdirs `unit/`, `smoke/`, `behavioral/`, `integration/`, `regression/`. Runner flag maps 1:1 to subdir. Per-service filtering is a secondary axis (`--service auth`). |
| 3 | **Email verification via structured log line** | When `USE_MAILGUN=False`, notification worker emits one `event=email_suppressed` JSON line per would-be email. Tests assert against logs (`caplog` in-process, `docker compose logs` for stack tests). No new DB schema, works in dev today, manually greppable. |
| 4 | **Truncate Postgres + FLUSHDB Redis before each test file** | Per-file reset gives a known baseline without per-test setup cost. Escape hatch: `@pytest.mark.no_reset` for tests that intentionally verify cross-test state. |

**Out of scope for this work**
- Production email outbox / SysAdmin email-management feature. Will get its own brainstorm later. The dev-only log line satisfies the test verification need.
- Frontend tests (unit, component, E2E). Separate effort.
- Performance / load testing. C-605 calls for SCORM concurrency stress testing — captured as a future regression test, not implemented in this work.
- Building or rebuilding Docker images. The runner only ensures the stack is up and healthy; image build is left to `docker compose up --build` as a manual step.

---

## 3. Directory Layout

```
tests/                                  # NEW — top-level test tier
├── README.md
├── conftest.py                         # session-scoped: stack health check, DB reset hook
├── pytest.ini                          # markers: unit, behavioral, integration, regression, smoke
├── run_tests.sh                        # the runner script
├── requirements-test.txt               # pytest-html, pytest-cov, pytest-asyncio, httpx, etc.
│
├── _support/                           # shared fixtures + helpers (underscore = not collected)
│   ├── __init__.py
│   ├── stack.py                        # docker stack up/wait-healthy
│   ├── db_reset.py                     # truncate Postgres + FLUSHDB Redis
│   ├── http_client.py                  # AsyncClient pointed at gateway (http://localhost)
│   ├── auth.py                         # mint EXTERNAL_JWT, login flows, role shortcuts
│   ├── factories.py                    # build_tenant, build_user, build_training, etc.
│   ├── email_log.py                    # assert_email_sent / assert_no_email_sent helpers
│   ├── seed.py                         # canonical fixtures (bootstrap SysAdmin, default templates)
│   └── coverage_map.py                 # spec-ID coverage reporter
│
├── smoke/                              # ~30s total — gates everything else
│   ├── test_gateway_routing.py
│   ├── test_auth_login.py
│   ├── test_core_health.py
│   └── test_notification_health.py
│
├── unit/                               # in-process (SQLite + ASGI) — collected from app/<svc>/tests
│   ├── auth_service/
│   ├── core_service/
│   └── notification_service/
│
├── behavioral/                         # per-service role + tenant boundary tests
│   ├── auth/
│   │   ├── test_login_flows.py
│   │   ├── test_magic_link.py
│   │   ├── test_role_boundaries.py
│   │   └── test_tenant_isolation.py
│   ├── core/
│   │   ├── test_training_lifecycle.py
│   │   ├── test_progress_gating.py
│   │   ├── test_quiz_attempts.py
│   │   ├── test_certificates.py
│   │   ├── test_role_boundaries.py
│   │   └── test_tenant_isolation.py
│   ├── notification/
│   │   ├── test_inapp_delivery.py
│   │   ├── test_email_dispatch.py
│   │   └── test_tenant_isolation.py
│   └── gateway/
│       ├── test_route_proxying.py
│       ├── test_token_swap.py
│       └── test_internal_secret.py
│
├── integration/                        # multi-service end-to-end flows through gateway
│   ├── test_invite_to_active_user.py
│   ├── test_assign_to_completion.py
│   ├── test_version_pushback.py
│   ├── test_bulk_import_flow.py
│   └── test_recertification_cycle.py
│
├── regression/                         # explicit invariants from constraints.md
│   ├── test_audit_log_immutable.py
│   ├── test_no_hard_deletes.py
│   ├── test_scorm_suspend_data_null.py
│   ├── test_heartbeat_token_refresh.py
│   └── test_completion_record_immutable.py
│
└── _artifacts/                         # gitignored — runner output (see Section 9)
```

Layout rules:
- `app/<service>/tests/` is **not moved**. Files stay where they are. `tests/unit/<service>/` only contains a `conftest.py` that points pytest collection at `app/<service>/tests/`.
- `_support/` and `_artifacts/` are underscore-prefixed so pytest's default collection ignores them.
- `smoke/` is run implicitly before any non-unit category.

---

## 4. Test Categories

Each category has a single, distinct purpose. The runner script's flags map 1:1 to category subdirs.

| Category | What it tests | Where it runs | Speed target | Failure means |
|---|---|---|---|---|
| **unit** | Single function or endpoint in isolation with valid input. "Does this code do what the signature says?" | In-process (SQLite + ASGI), one service at a time | < 30s per service | Code-level regression |
| **smoke** | Stack is up and basics work: services reachable through gateway, login works, can read a notification, can create a training. No edge cases. | Real Docker stack via gateway | < 30s total | Stack is broken — don't bother running anything else |
| **behavioral** | Role and tenant boundaries enforced. Business rules from `business_rules.md` hold. | Real Docker stack via gateway | < 3 min per service | Security/authorization regression |
| **integration** | Multi-step user flow crossing services. | Real Docker stack via gateway | < 5 min total | Cross-service contract broken |
| **regression** | Specific invariants from `constraints.md` (audit-log immutability, no hard deletes, SCORM `cmi.suspend_data` nulling, completion-record immutability). Each test cites its constraint ID. | Real Docker stack via gateway | < 2 min total | A non-negotiable invariant was violated |

**Distinctions worth re-stating:**
- **Unit ≠ behavioral.** Unit: "creating a training works." Behavioral: "creating a training as an Employee returns 403" and "reading Tenant B's training as Tenant A returns 403."
- **Integration is cross-service.** A behavioral test stays within one service's contract; an integration test follows a user flow across 2+ services.
- **Smoke is a prerequisite, not just a category.** The runner auto-runs `smoke/` before any non-unit category. Failing smoke skips everything else with a clear message.

**Per-service filtering**

`--service auth|core|notification|gateway` is orthogonal to category. `./run_tests.sh --behavioral --service core` runs only `tests/behavioral/core/`.

---

## 5. Stack Tests Harness (`tests/_support/`)

Plumbing that every stack test depends on. Tests should read as one or two clear assertions; setup hides in fixtures.

### `stack.py`
- `ensure_stack_up()` — probes gateway and each service health endpoint. If all healthy, returns immediately. Otherwise runs `docker compose up -d --wait` and polls until healthy or 60s timeout. Called once per session.
- Does **not** tear the stack down. Local dev keeps it running; CI runs in a fresh runner.

### `db_reset.py`
- `reset_databases()` connects directly to Postgres (host port 5433) and Redis (6379). Truncates every table **except**:
  - `alembic_version` (preserves migration state)
  - The default certificate template seed row (so cert tests don't reseed each time)
- Runs `FLUSHDB` on Redis DB 0.
- Wired as a `module`-scoped autouse fixture in `tests/conftest.py` — runs before each test file.
- Escape hatch: `@pytest.mark.no_reset` skips reset for the file.

### `http_client.py`
- `gateway_client()` — `httpx.AsyncClient(base_url="http://localhost")` so every test hits the real Nginx gateway. This is what makes auth/token-swap/route-mapping testable.
- `with_auth(client, token)` — returns a new client with the Authorization header baked in.

### `auth.py`
- `mint_external_jwt(user_id, tenant_id, roles, secret=EXTERNAL_JWT_SECRET, expires_in=3600)` — signs a JWT with the **external** secret so it passes the gateway. Used when tests don't care about exercising login.
- `login_as(email, password)` — full login + tenant-select flow, returns scoped token. Used by integration tests that verify the login flow itself.
- `as_sysadmin()`, `as_manager(tenant_id)`, `as_creator(tenant_id)`, `as_employee(tenant_id)` — convenience wrappers that create the user via factories and return `(user, token)`.

### `factories.py`
- `build_tenant(name=None)` → tenant dict with sensible defaults, created via SysAdmin token.
- `build_user(tenant_id, role, email=None)` → invites + auto-confirms a user, returns user + plaintext password.
- `build_training(tenant_id, creator, *, published=True, structure="flat", lessons=[…])` → creates training with the given lesson set, optionally publishes.
- `build_group(tenant_id, members=[…])` → group with members.
- Factories use real API endpoints (not bypassing business logic), but skip the email confirmation step via an internal seed token.

### `email_log.py`
- `assert_email_sent(template, to=None, contains=None, tenant_id=None, since=None, timeout=3.0) -> dict` — polls `docker compose logs notification-service` for `event=email_suppressed` lines matching the criteria. Returns the parsed log dict. On timeout, raises with the last 20 log lines so you can immediately see what *did* happen.
- `assert_no_email_sent(template=None, to=None, since=None, wait=1.0) -> None` — waits `wait` seconds, then fails if any matching line appears.
- `clear_email_log() -> datetime` — sets a "since" marker; future asserts only see lines after this point. Auto-called by the `reset_databases` fixture.
- In-process variant `assert_email_sent_caplog(caplog, …)` provides the same API for `tests/unit/notification_service/` tests that use pytest's `caplog` fixture.

### `seed.py`
- Defines `DEFAULT_SYSADMIN_EMAIL` / `DEFAULT_SYSADMIN_PASSWORD` — the bootstrap SysAdmin created on a fresh stack so tests have a way in.
- Defines the default certificate template (preserved across DB resets so cert tests don't need to recreate it).

### `coverage_map.py`
- Walks all test files under `tests/` and `app/<svc>/tests/`, parses spec IDs from docstrings, produces `coverage_map.md` and `spec_status.csv` artifacts.
- Compares to the previous run's manifest and reports `Newly missing > 0` as a failure condition.

### Example behavioral test using the harness

```python
# tests/behavioral/core/test_tenant_isolation.py

async def test_manager_cannot_read_other_tenant_training(gateway_client):
    """Covers: T-CO-47, C-602"""
    tenant_a = await build_tenant()
    tenant_b = await build_tenant()
    manager_a, token_a = await as_manager(tenant_a.id)
    _, creator_b_token = await as_creator(tenant_b.id)
    training_b = await build_training(tenant_b.id, creator_b_token, published=True)

    resp = await with_auth(gateway_client, token_a).get(f"/api/v1/trainings/{training_b.id}")

    assert resp.status_code == 403
```

---

## 6. Runner Script (`tests/run_tests.sh`)

Single entry point. Flags compose orthogonally (category × service).

### Invocation examples
```bash
./tests/run_tests.sh                              # default: unit + smoke (fast feedback)
./tests/run_tests.sh --all                        # everything
./tests/run_tests.sh --unit                       # in-process tests only
./tests/run_tests.sh --smoke                      # quick stack health check
./tests/run_tests.sh --behavioral                 # role/tenant boundary tests
./tests/run_tests.sh --integration                # cross-service flows
./tests/run_tests.sh --regression                 # invariant tests
./tests/run_tests.sh --behavioral --service core  # core's behavioral tests only
./tests/run_tests.sh --service auth               # all categories, auth only
./tests/run_tests.sh --ci                         # --all + JUnit XML + no colors + stop on first failure
```

### Flag reference

| Flag | Effect |
|---|---|
| `--unit` | Run `tests/unit/` |
| `--smoke` | Run `tests/smoke/` |
| `--behavioral` | Run `tests/behavioral/` |
| `--integration` | Run `tests/integration/` |
| `--regression` | Run `tests/regression/` |
| `--all` | All of the above |
| `--service <name>` | Filter to `auth`/`core`/`notification`/`gateway` (composes with category flags) |
| `--no-stack` | Skip `ensure_stack_up()` check |
| `--no-reset` | Skip per-file DB reset fixture (faster, but tests must be order-independent) |
| `--no-smoke` | Suppress the implicit smoke prerun |
| `--keep-logs` | After run, dump `docker compose logs` for each service into `tests/_artifacts/logs/` |
| `--show-emails` | After run, print all `event=email_suppressed` lines |
| `-k <expr>` | Passed straight through to pytest for name filtering |
| `--ci` | Implies `--all`, JUnit XML output, no colors, `-x` (stop on first failure) |
| `--coverage` | Adds Python code coverage collection, HTML report at `tests/_artifacts/coverage/` |
| `--coverage-map` | Generate spec-ID coverage map at `tests/_artifacts/coverage_map.md` |
| `-v` / `-vv` | Verbosity, passed to pytest |

### Behavior rules

1. **Smoke runs first.** If any non-unit category is requested, `smoke/` is implicitly prepended unless `--no-smoke`. If smoke fails, the rest is aborted with a clear message.
2. **Stack check is automatic.** Any non-unit category triggers `ensure_stack_up()` unless `--no-stack`.
3. **Default is fast.** Bare `./run_tests.sh` runs only unit + smoke — under a minute.
4. **Exit codes are honest.** Non-zero on any failure. `--ci` adds `-x`.
5. **No magic in the script.** Thin bash wrapper (~150 lines) that builds and runs a pytest command. Real logic lives in `_support/`.

### What it does not do
- Doesn't run `docker compose up --build`. Image build is a manual concern.
- Doesn't run frontend tests. Separate command (`npm run test`).
- Doesn't apply migrations. Service entrypoints already do that on startup.

---

## 7. Email Verification Mechanics

### Change to `notification_service`

In the worker code that processes email jobs, where `USE_MAILGUN=False` currently short-circuits the Mailgun call, add one structured log line right before the short-circuit:

```python
# app/notification_service/app/worker/email_dispatcher.py

if settings.USE_MAILGUN:
    await mailgun_client.send(...)
else:
    logger.info(
        "email_suppressed",
        extra={
            "event": "email_suppressed",
            "to": job.to_email,
            "template": job.template_name,
            "tenant_id": str(job.tenant_id) if job.tenant_id else None,
            "subject": rendered.subject,
            "body_preview": rendered.body_html[:500],
            "variables": job.variables,
            "job_id": str(job.id),
            "queued_at": job.queued_at.isoformat(),
        },
    )
```

Constraints honored:
- Uses the existing JSON-structured logging setup (C-402 — structured JSON to stdout).
- `body_preview` capped at 500 chars to keep log lines manageable. Tests needing full body content set `include_full_body=True` on the assertion helper, extending the cap.
- No secret redaction in dev (per scope decision: production outbox / redaction is out of scope).

### Helper API

```python
async def assert_email_sent(
    template: str,
    to: str | None = None,
    contains: str | list[str] | None = None,
    tenant_id: str | None = None,
    since: datetime | None = None,
    timeout: float = 3.0,
) -> dict: ...

async def assert_no_email_sent(
    template: str | None = None,
    to: str | None = None,
    since: datetime | None = None,
    wait: float = 1.0,
) -> None: ...

def clear_email_log() -> datetime: ...
```

### Polling implementation

`assert_email_sent` runs `docker compose logs notification-service --since=<marker>`, parses each line as JSON, filters for `event=email_suppressed` matching the criteria. Poll loop is 100ms intervals up to `timeout`. The `clear_email_log()` marker is stored in module state on the test process.

### Example test bodies

```python
async def test_magic_link_invite_sends_email(gateway_client):
    """Covers: T-AU-19, T-NO-12"""
    tenant = await build_tenant()
    _, mgr_token = await as_manager(tenant.id)

    resp = await with_auth(gateway_client, mgr_token).post(
        "/api/v1/users/invite",
        json={"email": "new@acme.com", "role": "Employee"},
    )
    assert resp.status_code == 200

    email = await assert_email_sent(
        template="magic_link_invite",
        to="new@acme.com",
        contains=["accept-invite", "48 hours"],
    )
    assert email["tenant_id"] == str(tenant.id)
    assert "invite_url" in email["variables"]


async def test_forgot_password_unknown_email_sends_nothing(gateway_client):
    """Covers: T-AU-32"""
    clear_email_log()
    resp = await gateway_client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ghost@nowhere.com"},
    )
    assert resp.status_code == 200
    await assert_no_email_sent(template="password_reset", to="ghost@nowhere.com")
```

### In-process variant

Tests under `tests/unit/notification_service/` use pytest's `caplog` fixture because the worker runs in-process. `assert_email_sent_caplog(caplog, ...)` provides the same API surface.

---

## 8. Coverage Mapping

Every test ties to a spec ID from `project_docs/tests.md` so coverage is measurable, not subjective.

### Convention

Every test function carries one or more spec IDs on the first line of its docstring:

```python
async def test_employee_cannot_read_other_employees_progress(gateway_client):
    """Covers: T-CO-87, C-602"""
    ...
```

Tests that don't map cleanly either:
- Add a new spec ID to `project_docs/tests.md` (PR note explains what behavior it covers), or
- Use `@pytest.mark.no_spec` with a brief comment for tests covering implementation details rather than spec-level requirements.

### Coverage report

`./run_tests.sh --coverage-map` produces `tests/_artifacts/coverage_map.md`:

```
Total spec IDs:           247
Covered:                  93   (37.7%)
Missing:                  154

Missing by service:
  auth-service:           28
  core-service:           71
  notification-service:   19
  gateway:                15
  cross-cutting:          21

Newly covered (vs last run): 14
Newly missing (vs last run): 0   ← regression check
```

And `tests/_artifacts/spec_status.csv` — one row per spec ID with columns `spec_id`, `service`, `category`, `description`, `covered_by` (test path, blank if uncovered), `last_run_status`.

CI gate: build fails if `Newly missing > 0` — catches "someone deleted a test and didn't notice."

### Gap-fill priority order

| Priority | Category | Why |
|---|---|---|
| 1 | Smoke gaps | Without these, nothing else is trustworthy |
| 2 | Tenant isolation (spec category: `isolation`) | The exact gap that motivated this work; security-critical |
| 3 | Role/auth boundaries (spec category: `auth`) | Same blast radius — wrong role getting through is a breach |
| 4 | Gateway tests (T-GW-01 … T-GW-15) | Currently zero coverage; gateway is the security perimeter |
| 5 | Regression invariants from `constraints.md` | High-cost failures if they regress |
| 6 | Happy-path gaps for endpoints with no test at all | Baseline coverage |
| 7 | Edge cases (spec category: `edge`) | Last because broadest and lowest per-test value |

Priorities 1–5 are non-negotiable for "done." Priorities 6–7 are best-effort.

---

## 9. Test Results & Artifacts

All runner output lands in **`tests/_artifacts/`** — gitignored, overwritten each run.

| File / dir | When | Purpose |
|---|---|---|
| `report.html` | Always | Human-readable HTML summary of every test (pass/fail/skip, duration, error details). Open in a browser. Generated by `pytest-html`. |
| `report.txt` | Always | Plain-text summary. |
| `junit.xml` | Always | JUnit XML for CI consumption. |
| `last_run.json` | Always | Manifest: timestamp, flags used, exit code, totals, duration. |
| `coverage/index.html` | `--coverage` | Per-file Python code coverage from `pytest-cov`. |
| `coverage.xml` | `--coverage` | Coverage XML for Codecov / SonarQube. |
| `coverage_map.md` | `--coverage-map` | Spec-ID coverage map (Section 8). |
| `spec_status.csv` | `--coverage-map` | Per-spec-ID status CSV. |
| `logs/<service>.log` | `--keep-logs` | Captured `docker compose logs` per service. |
| `emails.log` | `--show-emails` | All `event=email_suppressed` lines, pretty-printed. |

### Layout
```
tests/_artifacts/
├── report.html
├── report.txt
├── junit.xml
├── last_run.json
├── coverage/             ← only if --coverage
│   └── index.html
├── coverage.xml
├── coverage_map.md       ← only if --coverage-map
├── spec_status.csv
├── logs/                 ← only if --keep-logs
└── emails.log            ← only if --show-emails
```

### Behavior rules
- Always-on artifacts are cheap (~50ms each).
- Conditional artifacts are flag-gated because they slow runs measurably.
- Directory overwritten, not appended. Copy elsewhere to preserve a previous run.
- Gitignored — `.gitignore` covers the whole directory.

### Test dependencies (`tests/requirements-test.txt`)
- `pytest-html` — HTML report
- `pytest-cov` — coverage
- `pytest-asyncio` — already used by existing service tests
- `httpx` — already used
- `pytest-xdist` — optional, parallel stack-test execution if needed later

---

## 10. Wave Plan

Each wave is independently mergeable and leaves the test tier in a working state.

### Wave 0 — Foundation
- Create `tests/` skeleton (directories, `pytest.ini`, `conftest.py`)
- Build `_support/`: `stack.py`, `db_reset.py`, `http_client.py`, `auth.py`, `factories.py`, `seed.py`
- Build `run_tests.sh` with all flags wired
- Add `email_suppressed` log line to `notification_service` worker
- Build `email_log.py` helper
- Write 2-3 smoke tests
- **Exit:** `./tests/run_tests.sh --smoke` passes against a freshly-started stack

### Wave 1 — Coverage baseline
- Audit every existing test in `app/<service>/tests/` and annotate with spec IDs
- Build `coverage_map.py` and produce first `coverage_map.md`
- Wire `tests/unit/<service>/` collection so existing tests run via the new runner
- **Exit:** `./tests/run_tests.sh --unit --coverage-map` runs all existing tests via the new runner and produces a coverage report

### Wave 2 — Tenant isolation across the board
- Behavioral tests under `tests/behavioral/<svc>/test_tenant_isolation.py`
- Auth: T-AU-12, T-AU-13, T-AU-27, T-AU-29
- Core: T-CO-11, T-CO-22, T-CO-30, T-CO-47, T-CO-52, T-CO-87, T-CO-100, T-CO-111, T-CO-113, T-PD-04, T-CT-06, T-DB-09
- Notification: T-NO-04, T-NO-05
- Audit log: T-AU-LOG-08
- **Exit:** every cross-tenant attempt returns 403/404 and has a test with a spec ID

### Wave 3 — Role/auth boundaries
- `tests/behavioral/<svc>/test_role_boundaries.py` for each service
- One test per wrong-role attempt that should return 403, for every protected endpoint
- Covers `auth` spec category across all services
- **Exit:** every endpoint with role gating has an explicit "wrong role" test

### Wave 4 — Gateway
- `tests/behavioral/gateway/` with route mapping, token swap, internal-secret enforcement, SCORM upload size
- All 15 T-GW-* tests
- **Exit:** all T-GW tests pass; direct-port bypass attempt returns 403

### Wave 5 — Cross-cutting regression invariants
- `tests/regression/` populated with the 5 invariant tests from Section 3:
  - Audit-log immutability (T-AU-LOG-06, T-AU-LOG-07)
  - Version pushback + suspend_data null (T-CO-89, T-CO-91, C-204, C-603)
  - Heartbeat token refresh (T-AU-35 → T-AU-40)
  - Completion record immutability (T-CO-93)
  - No-hard-deletes (T-SD-04)
- **Exit:** every invariant listed has a passing regression test

### Wave 6 — Cross-service integration flows
- `tests/integration/` populated with 5 end-to-end flows
- Each flow goes through the gateway, touches 2+ services, asserts email log lines
- **Exit:** all 5 flows pass; total runtime < 5 min

### Wave 7 — Notification deepening
- `tests/behavioral/notification/test_email_dispatch.py` — one test per email template (right event, right recipient, right variables)
- Covers T-NO-06 → T-NO-18 + T-RC-05
- **Exit:** every email-producing event in the spec has a passing test using `assert_email_sent`

### Wave 8 — Happy-path and edge-case fill-in
- Fill remaining gaps from the coverage map, lowest-priority items last
- Target: 85%+ spec coverage

### Sequencing notes
- Waves 0 and 1 are strictly serial.
- Waves 2-7 can parallelize if multiple contributors work the spec.
- Each wave commits independently with spec IDs in the commit message.
- After each wave, run `./tests/run_tests.sh --all` to confirm no regressions.

### Rough size estimate
- Wave 0: ~12-15 files, ~1 day
- Wave 1: mechanical, ~½ day
- Waves 2, 3: ~3-4 days each (largest behavioral work)
- Wave 4: ~1-2 days
- Waves 5, 6, 7: ~1-2 days each
- Wave 8: open-ended

---

## 11. Open Items (deferred, not blocking)

1. **Production email outbox feature.** Dev-only log line satisfies the test need. The prod feature (SysAdmin UI, redaction, retention) needs its own brainstorming and security review. Tracked as a future spec.
2. **Frontend test suite.** Out of scope for this work. Separate brainstorming will define category, runner, and CI integration for the frontend.
3. **SCORM concurrency stress test (C-605).** Captured as a future regression test. Needs a load-generation tool choice (Locust, k6, hand-rolled asyncio) — separate spec.
4. **CI integration.** GitHub Actions workflow update (running `./tests/run_tests.sh --ci` on push) is a follow-up PR after the runner is proven locally.
