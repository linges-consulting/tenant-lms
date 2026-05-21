# Requirements — Custom Multi-Tenant LMS

> **Authoritative source for product requirements.** See also:
> - [`business_rules.md`](business_rules.md) — specific behavioral rules (BR-xxx)
> - [`constraints.md`](constraints.md) — technical constraints (C-xxx)
> - [`roadmap.md`](roadmap.md) — phase status and build order

---

## 1. Project Vision

A **B2B Learning Management System (LMS)** for small businesses to manage internal employee training. Multiple independent businesses (tenants) share a single infrastructure with **absolute data isolation**.

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) + SQLAlchemy + PostgreSQL |
| Frontend | React + Vite + Tailwind CSS + shadcn/ui + TanStack React Query |
| UI Components | shadcn/ui (Radix UI primitives) + lucide-react icons |
| Rich Text | TipTap (lesson authoring + rendering) |
| Video | React Player (local files + YouTube, Dailymotion, Vimeo, etc.) |
| SCORM Runtime | scorm-again (SCORM 1.2 + 2004 bridge) |
| Cache | Redis (sessions, quotas, heartbeat, email job queue) |
| Storage | Local Filesystem — media: `/storage/media/`, SCORM: `/storage/scorm/` |
| Email | Mailgun API (`MAILGUN_API_KEY`, `MAILGUN_DOMAIN` env vars) — handled inside `notification_service` |
| PDF Generation | WeasyPrint — HTML template → single-page landscape PDF |
| Background Jobs | Redis queue consumed by `notification_service` background worker (email, certificates, reminders) |

---

## 2. Multi-Tenancy

| Rule | Detail |
|---|---|
| **Single URL** | `app.yourlms.com` — no subdomains |
| **Multi-Tenant Users** | One email can belong to multiple tenants; tenant selection screen shown post-login |
| **Data Isolation** | Every DB row tied to `tenant_id`; all API queries scoped to the JWT's active `tenant_id` |
| **Dynamic Branding** | After tenant selection, inject tenant's `logo`, `primary_color`, and `secondary_color` as CSS variables |
| **Resource Guard** | Every endpoint verifies the resource's `tenant_id` matches the JWT's `tenant_id` |

---

## 3. User Roles & Permissions

All users are **Employees**. Elevated rights are permission flags on `tenant_memberships` — scoped per tenant. A user may be a Manager in one tenant and a base Employee in another.

| Role | DB Flag | Permissions |
|---|---|---|
| **SysAdmin** | `is_sysadmin` | Manage users across all tenants, manage tenants, manage certificate templates per tenant, view system status, view training reports across all tenants, bulk import users into a specific tenant via CSV. **Cannot** view specific training content. Strictly global — cannot hold tenant memberships. Lands on `/admin`. |
| **Employee (Base)** | _(base)_ | View assigned trainings, complete lessons, earn certificates. |
| **Business Manager** | `is_business_manager` | All Employee access + invite/manage all users within their tenant (including other Managers) + update any user's roles within their tenant + manage groups + assign published trainings to users and/or groups + view full compliance reports for their tenant. Cannot manage their own roles or account. |
| **Training Creator** | `is_training_creator` | All Employee access + create/edit/publish trainings + invite collaborators + view compliance reports scoped to their own trainings and collaborations only. No assignment responsibility — that belongs to Business Managers. Cannot delete (only deactivate). |
| **Manager + Creator** | Both flags | Full combined access: user management, full tenant compliance reports, training creation. |

**SysAdmin rules:**
- Can create new SysAdmins (email must not be associated with any tenant).
- When inviting a user, must select the tenant the user will be associated with, plus their role(s).
- Lands on a neutral system-themed global dashboard.
- Cannot be a tenant member.

**Invitation & role assignment:**
- **Business Managers** invite users to their own tenant only. At invite time they select the user's role(s): Manager, Creator, both, or neither (base Employee).
- **SysAdmins** invite users and must explicitly select the target tenant and role(s).
- Roles can be updated after activation by a Business Manager (within their tenant) or a SysAdmin (any tenant).

---

## 4. Auth Flow & Session Management

### Login & Redirection

1. `POST /auth/login` — validates credentials, returns a temporary session token.
2. Redirection logic:
   - **SysAdmin** → `/admin`
   - **Single-tenant user** → `/dashboard` (tenant auto-selected)
   - **Multi-tenant user** → `/select-tenant`
3. `GET /auth/tenants` — returns the user's associated tenants where status is `Active`. Tenants where the user is `Inactive` or `Pending` are hidden entirely from the selection screen.
4. `POST /auth/select-tenant` — issues a tenant-scoped JWT containing `tenant_id`, `user_id`, and role flags.

### JWT & Token Lifecycle

- `POST /auth/refresh` — exchanges a valid or near-expiry JWT for a fresh one. Handled automatically via a 401 interceptor in the API client.
- Invite links (Magic Links) expire after **48 hours** and are single-use.

### Heartbeat (Infinite Session During Training)

Prevents session expiry while a learner is actively watching content.

| Step | Detail |
|---|---|
| **Frontend** | `setInterval` fires `POST /progress/heartbeat` every 5 minutes while Training Viewer is open |
| **Payload** | `{ enrollment_id }` |
| **Backend** | Validate JWT → write `last_heartbeat_at` to `user_sessions` → if JWT expires within 10 min, return `new_token` header |
| **Redis** | Heartbeat state and session quotas tracked in Redis |

---

## 5. Training Structure & Content

### Hierarchy

A training can contain standalone chapters, modules with chapters, or a mix of both. No structure selection is required at creation — training creation only needs a title and category (description is optional).

**Standalone chapters** (no modules):
```
Training
  └── Chapter
        └── Lesson  (Video | Rich Text | PDF | Quiz | SCORM)
```

**Modules with chapters**:
```
Training
  └── Module
        └── Chapter
              └── Lesson  (Video | Rich Text | PDF | Quiz | SCORM)
```

- Mixing is allowed — a training can have both module-grouped chapters and standalone chapters.
- The `structure_type` DB column is retained for data history but is no longer enforced; creators can add modules or standalone chapters to any training at any time.
- **Sequential gating** is enforced at every level:
  - Lesson N is locked until Lesson N−1 is complete.
  - Chapter N is locked until every lesson in Chapter N−1 is complete.
  - Module N is locked until every chapter in Module N−1 is complete (modular structure only).
- Gating is **server-enforced**. The frontend lock is UX only — the API re-validates before accepting progress updates.

### Lesson Types

| Type | MVP Behaviour |
|---|---|
| **Video** | Two source types: **uploaded file** (stored on local filesystem) or **external URL** (YouTube, Dailymotion, Vimeo, etc.). Rendered via React Player for uniform playback and progress tracking across both types. Completion gated by the `onEnded` event — cannot be skipped. Tracks: resume position (learner can pick up where they left off), and watched percentage milestones (25%, 50%, 75%, 100%) for reporting. |
| **Rich Text** | Markdown-rendered content. Marked complete when learner clicks **Mark Complete** or **Next**. |
| **PDF / Document** | Upload a PDF file. Viewed in-browser via a PDF viewer. Marked complete when learner clicks **Mark Complete** or **Next**. Stored in `lms_images` volume under `{tenant_id}/documents/`. |
| **Quiz** | Supports 5 question types: Multiple Choice (single answer), Multiple Select (multi-answer), True/False, Matching (two-column), Ordering/Sequencing. Attempts configurable per quiz, default **10**. On lockout, Business Manager must reset. |
| **SCORM** | Supports SCORM 1.2 and SCORM 2004. Uploaded as a zip, unzipped to a dedicated local storage directory, manifest auto-parsed for entry point. Completion determined by the package's own reported status — not overridden by the LMS. Exempt from attempt limits; learners may re-launch unlimited times. _(Phase 8)_ |

### Quiz Behaviour

- Passing score is configurable per quiz.
- Max attempts configurable per quiz; default is 10.
- If quiz content changes in a new training version, employees must retake it even if previously passed (BR-404).
- On lockout (all attempts exhausted), only a Business Manager can reset.

---

## 6. Publishing & Versioning

| Rule | Detail |
|---|---|
| **Draft state** | All edits are invisible to learners until the creator hits **Publish** |
| **Owner-only publish** | Only the original creator (owner) can publish, archive, or deactivate a training |
| **Collaborative drafts** | Owners may grant other Training Creators edit access to drafts; collaborators cannot publish or archive |
| **Version increment** | Each publish increments `training.current_version` and writes a snapshot to `training_histories` |
| **Progress pushback** | If a re-published update affects a lesson at or before an employee's current position, their progress resets to that lesson |
| **SCORM reset** | Any pushback must null `cmi.suspend_data` to prevent runtime crashes on resume |
| **Completion records** | Must store `training_version_id` at the moment of completion — immutable once written |
| **Deactivation** | Trainings with active assignments cannot be deleted — use Hard Archive instead (immediately terminates learner access while preserving history) |

### Re-certification

Trainings can optionally require periodic re-certification. Configured per training at creation time (can be updated before publishing):

| Field | Description |
|---|---|
| `requires_recertification` | Boolean — whether the training expires after completion |
| `recertification_period_days` | Number of days after completion before re-certification is required |

When a certification expires:
- The learner is automatically re-enrolled (new `attempt_id`, full reset to first lesson of latest version).
- The learner receives an Email + In-App notification that re-certification is required.
- The Manager receives an In-App notification.
- Due-date reminders (14d, 7d, 1d) apply to re-certification deadlines the same as initial assignments.

### Training Categories & Tags

Every training has:
- **Category** — a single category selected from a predefined or tenant-managed list (e.g. Health & Safety, HR Policy, Technical, Compliance).
- **Tags** — zero or more free-form tags for filtering and search.

Both are used by Managers when filtering the training library for assignment, and by all users when searching their training list.

### Reassignment

Managers may trigger a **Reassign** for failed or overdue trainings. This increments the `attempt_id` and performs a full reset to the first lesson of the latest version.

---

## 7. User Onboarding

1. **SysAdmin** creates a new Tenant and the initial Business Manager via the Admin UI.
2. **Business Manager** (or SysAdmin) invites a user by email via the Manager/Admin UI.
3. System checks whether the email already has an active global account:

| User state | Email sent | What happens |
|---|---|---|
| **New user** (no account) | Magic Link — "Set your password to get started" (48-hour token) | User clicks link → sets password → account created → linked to tenant → status `Active` |
| **Existing active user** | Notification — "You've been added to [Tenant]" | User logs in normally → new tenant appears in selector → status `Active` immediately |
| **Re-invited inactive user (same tenant)** | Notification — "Your access to [Tenant] has been restored" | User logs in normally → tenant reactivated → status `Active` |
| **Pending elsewhere, no global account yet** | Magic Link (same as new user flow) | Each tenant invite is independent; activating one link does not affect other pending invites |

4. Manager receives an **In-App** notification confirming when a user becomes `Active`.

### Password Reset

Self-service only — available to all users from the login screen via a "Forgot password?" link. Sends a secure reset link via Mailgun. Admins cannot manually set or view passwords.

### User Statuses (per tenant)

| Status | Meaning |
|---|---|
| `Pending` | Invited but has not completed registration (new users only) |
| `Active` | Fully registered and permitted access |
| `Inactive` | Access explicitly revoked for that tenant |

---

## 8. Notification System

Two-tier system: **Actionable** (Email + In-App) and **Informational** (In-App only).

- **Bell icon** in the header shows a dropdown of recent unread notifications.
- **Dedicated Notifications page** shows full notification history — all read and unread, with timestamps.

### For Employees (Learners)

| Trigger | Channel |
|---|---|
| Account Invitation | Email (Magic Link) |
| New Training Assigned | Email + In-App |
| Due Date Reminder (14 days) | Email |
| Due Date Reminder (7 days) | Email |
| Due Date Reminder (1 day) | Email |
| Overdue (Completion Lock inactive) | Email (daily) |
| Training Completed | In-App |
| Re-certification Required | Email + In-App |
| Re-certification Due (14 days) | Email |
| Re-certification Due (7 days) | Email |
| Re-certification Due (1 day) | Email |

### For Business Managers

| Trigger | Channel |
|---|---|
| Quiz Lockout | Email + In-App |
| Employee Activation | In-App |
| Progress Pushback (version re-publish) | In-App |
| Re-certification triggered for employee | In-App |

### Email Reminders (Automated)

The system sends 3-step Mailgun reminders for assigned trainings with a due date:
- 14 days before due date
- 7 days before due date
- 1 day before due date

### Overdue Policy

- If **Completion Lock** is active on an assignment and the due date passes, the training becomes inaccessible to the employee.
- If Completion Lock is inactive, daily overdue reminders are sent instead.

### Admin Invitations

SysAdmins can invite new SysAdmins via `POST /users/invite-sysadmin`. Sends an email with onboarding instructions and a temporary access token.

---

## 9. Compliance & Certificates

| Rule | Detail |
|---|---|
| **Soft Deletes** | All tables include `deleted_at`. No hard deletes on user, training, enrollment, or audit data |
| **Immutable Audit Ledger** | `audit_logs` — INSERT only. Captures every enrollment, completion, quiz attempt, progress reset |
| **Certificates** | PDF generated automatically on 100% training completion, using the certificate template selected on the training |
| **7-Year Retention** | No data purged until 7-year mark; Phase 7 tooling enforces archive/purge |

### Certificate Templates

- **Created and managed by SysAdmins only.** Templates are global objects assigned to tenants.
- **Multiple templates** can be assigned to a tenant — tenants maintain a library of available templates.
- **Default template** — when a new tenant is created, a system default template is automatically assigned to it.
- **Tenant-aware variables** — templates support dynamic placeholders for tenant-specific fields: `{{tenant_name}}`, `{{tenant_logo}}`, `{{tenant_primary_color}}`, `{{learner_name}}`, `{{training_title}}`, `{{completion_date}}`.
- **Training-level selection** — each training must have a certificate template selected from its tenant's assigned templates. Used at PDF generation time on 100% completion.
| **Identity Immutability** | Email is non-modifiable. First/last name can only be changed by a SysAdmin with a mandatory audit note |
| **Password Recovery** | Strictly self-service via Mailgun email flow. Admins cannot set or view passwords |

---

## 10. Profile & Appearance

### Profile Page

Every user has a profile page. Any user can view any other user's profile, but content is role-gated:

| Viewer | Visible on profile |
|---|---|
| **Employee** | Name, avatar, department — basic info only |
| **Training Creator** | Basic info + shared trainings they collaborate on |
| **Business Manager** | Basic info + training assignments + progress + completed certificates + group memberships + activity log |
| **SysAdmin** | Everything + all tenant memberships + full activity log + ability to edit name (with mandatory audit note) |
| **Own profile** | Full personal details + settings (theme, avatar, username) + own completed certificates |

### Personal Settings

- **Theme preference** — `light | dark | system` — persisted per user.
- **Avatars** — predefined shape identifiers stored in `user.avatar_url`, with initials fallback.
- **Username** — users may update their username provided it is globally unique. Old profile URLs return 404 after a username change.
- **Manager self-exclusion** — Managers are filtered out of their own employee management views and cannot manage their own account status or roles.

### Navigation & Layout

**Sidebar sections** — shown only when the user holds the relevant role:

| Section | Visible to | Contents |
|---|---|---|
| **Learning** | All users | My Trainings, My Certificates |
| **Management** | Business Managers + SysAdmins | Users, Groups, Assignments, Reports; SysAdmin also sees: Tenants, Certificate Templates, System Status |
| **Studio** | Training Creators | My Trainings (owned), Collaborations |

**Sidebar behaviour:**

| Viewport | Behaviour |
|---|---|
| **Desktop (`≥ md`)** | Persistent left column. Collapse toggle button in header shrinks sidebar to icon-only mode. Avatar + display name pinned to sticky bottom of sidebar with link to Profile & Settings. |
| **Mobile (`< md`)** | Sidebar hidden. Hamburger button in header opens sidebar as a Sheet drawer. Avatar + profile menu shown in header. |

**Header (always visible):**
- Bell icon — notification dropdown with link to full Notifications page
- Sidebar collapse toggle — desktop only
- Hamburger menu — mobile only
- Avatar + profile menu — mobile only

---

## 11. Dashboards

Every user lands on a role-specific dashboard as their home screen. All dashboards show data scoped to the user's active tenant (except SysAdmin which is global).

### SysAdmin Dashboard
- Total tenants (active / inactive)
- Total users across all tenants
- Total trainings across all tenants
- Platform-wide completion rate
- Recent system activity log
- System status (service health)

### Business Manager Dashboard
- Total employees in tenant (active / pending / inactive breakdown)
- Training completion rate across tenant (% of assigned trainings completed)
- Overdue assignments count (with quick link to list)
- Quiz lockouts awaiting reset
- Upcoming due dates (next 7 days)
- Recent employee activity feed

### Training Creator Dashboard
- Total trainings owned
- Total active enrollments across owned trainings
- Average completion rate across owned trainings
- Quiz performance summary (pass rate, common failures)
- Trainings currently in draft vs published
- Recent collaborator activity

### Employee Dashboard
- My assigned trainings summary (not started / in progress / completed)
- Upcoming due dates (next 7 days)
- Recently completed trainings
- Certificates earned
- Continue where I left off (quick-resume card for in-progress training)

---

## 12. Bulk User Import

SysAdmins can upload a CSV file to invite multiple users into a specific tenant at once.

**CSV format:**
```
email,first_name,last_name,is_business_manager,is_training_creator
john@example.com,John,Smith,false,false
jane@example.com,Jane,Doe,true,false
```

**Behaviour:**
- Same invite logic as individual invites: existing active users are auto-linked; new users receive a Magic Link email.
- Per-row validation: invalid email, missing required fields, or duplicate within the file are flagged.
- Import produces a **result report**: rows succeeded, rows failed, reasons for each failure.
- Partial success is allowed — valid rows are processed even if some fail.
- SysAdmin must select the target tenant before uploading.
- Only SysAdmins can perform bulk imports.

---

## 13. Training Search & Filter

All users can search and filter their accessible training list. No self-enrollment — learners only see trainings they have been assigned.

### For Learners (Employee view)
- Search by training title or keyword
- Filter by: category, status (not started / in progress / completed), due date range
- Sort by: due date, title, recently accessed

### For Managers (assignment library)
- Search the tenant's full published training library when assigning
- Filter by: category, tags, creator
- Sort by: title, date published

### For Training Creators (Studio view)
- Search their owned and collaborated trainings
- Filter by: status (draft / published / archived), category, tags
