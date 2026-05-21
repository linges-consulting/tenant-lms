# Roadmap & Phase Status — Custom Multi-Tenant LMS

> Tracks what has been built, what is in progress, and what is planned.
> Update this file when a phase completes or scope changes.

---

## Current Phase Status

| Phase | Focus | Status |
|---|---|---|
| **1 — Identity & Auth** | Multi-tenant auth, JWT refresh, Admin UI, Global Users, Tenant Registration | **COMPLETE** |
| **2 — Theme & Appearance** | Theme persistence (`light/dark/system`), avatar shapes, Settings UI | **COMPLETE** |
| **3 — Settings & Profile UI** | Avatar selection (predefined shapes), name-edit restricted to SysAdmins, theme radio selector | **COMPLETE** |
| **4 — Admin Management** | Add Admin dialog, SysAdmin invite endpoint | **COMPLETE** |
| **5 — Group Management** | CRUD for groups, member assignment, bulk selection + bulk-delete | **IN PROGRESS** |
| **6 — Training Engine** | Training Creator UI, sequential gating, versioning, certificates, heartbeat | **IN PROGRESS** |
| **7 — User Onboarding** | Magic Links, invitation flow, self-service activation, seed data | **IN PROGRESS** |
| **8 — SCORM** | Local unzipping, manifest parsing, SCORM-to-API bridge, `cmi.suspend_data` reset | PLANNED |
| **9 — Reporting & Retention** | Compliance dashboards, audit log exports, manager reports, 7-year archive/purge tooling | PLANNED |

---

## Phase Detail

### Phase 5 — Group Management (In Progress)
- [ ] Group CRUD (create, rename, delete)
- [ ] Member assignment (add/remove employees)
- [ ] Bulk selection and bulk-delete
- [ ] Assign training to a group (bulk enrollment)

### Phase 6 — Training Engine (In Progress)
- [ ] Training Creator UI (create, edit, publish, deactivate)
- [ ] Training categories and tags (per training, filterable)
- [ ] Module / Chapter / Lesson hierarchy management (flat + modular)
- [ ] Collaborative drafts (owner grants editor access)
- [ ] Sequential lesson gating (server-enforced at lesson + chapter + module level)
- [ ] Lesson types: Video (upload + external URL), Rich Text (TipTap), PDF, Quiz, SCORM
- [ ] Video progress tracking (resume position + 25/50/75/100% milestones)
- [ ] Quiz engine (5 question types, configurable attempts, lockout, Manager reset)
- [ ] Re-certification settings (configurable per training, auto-reassignment on expiry)
- [ ] Training version snapshots on publish
- [ ] Progress pushback on re-publish + SCORM `cmi.suspend_data` null
- [ ] Reassignment by Manager (full reset, new `attempt_id`)
- [ ] Certificate PDF generation on 100% completion (WeasyPrint, tenant-branded)
- [ ] Heartbeat endpoint (`POST /progress/heartbeat`, training viewer only)
- [ ] Hard Archive flow (when assignments exist)
- [ ] Training search + filter (by category, tags, status, due date)

### Phase 7 — User Onboarding (In Progress)
- [ ] Magic Link invitation (Business Manager → employee email) with role selection at invite time
- [ ] 48-hour UUID token generation and email delivery
- [ ] Auto-association for existing global accounts (no Magic Link, notification email only)
- [ ] Re-invitation of inactive users (auto-reactivation)
- [ ] New user password setup via token
- [ ] Manager in-app notification on employee activation
- [ ] Password reset (self-service, Mailgun)
- [ ] SysAdmin invite flow (`POST /users/invite-sysadmin`)
- [ ] Bulk user import via CSV (SysAdmin only, per tenant, result report)

### Phase 8 — SCORM (Planned)
- Unzip uploaded SCORM packages to local storage
- Parse `imsmanifest.xml` for entry point
- SCORM-to-API runtime bridge
- `cmi.suspend_data` nulled on progress pushback

### Phase 9 — Reporting & Retention (Planned)
- Manager compliance dashboard (completion rates, overdue, quiz failures)
- Audit log export (CSV/PDF)
- 7-year retention enforcement tools (archive/purge scripts)
- Automated 3-step email reminders (14d / 7d / 1d before due date)
- Completion Lock (training becomes inaccessible when overdue, if enabled)
- Daily overdue reminders (when Completion Lock is inactive)

---

## Non-Negotiable Rules (Quick Reference)

1. Every DB query filters by `tenant_id` from the JWT — no exceptions.
2. No hard deletes — use `deleted_at`.
3. `audit_logs` is append-only — never UPDATE or DELETE.
4. Heartbeat must return `new_token` when JWT lifetime ≤ 10 min.
5. Chapter/Lesson gating is server-enforced — frontend is UX only.
6. Progress resets must be logged in `audit_logs` with `event_type = "progress_reset"` and `version_id`.
7. Magic Link tokens are single-use, expire in 48 hours, validated and invalidated server-side.
8. No cloud storage in MVP — all video and SCORM files on local filesystem.
9. Draft/publish separation — changes invisible to learners until `is_published = true`.
10. Completion records are immutable — never alter once written with `training_version_id`.
11. Users cannot change their own name or email — enforced in API, locked in UI.
12. SysAdmins are global-only — cannot hold tenant memberships.
13. Frontend zero-error policy — `npm run lint` must pass before any frontend task is complete.
