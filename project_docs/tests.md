# Backend Test Specification — Custom LMS

> Covers: Gateway, Auth Service, Core Service, Notification Service.
> Frontend test spec to be written as a separate pass after the backend audit.
>
> Every endpoint is considered incomplete until it has a corresponding test. See constraints C-601 to C-606 for enforcement rules.
>
> **Test categories used throughout:**
> - `happy` — expected successful path
> - `edge` — boundary conditions and uncommon but valid inputs
> - `auth` — unauthenticated, wrong role, expired token
> - `isolation` — cross-tenant leakage attempts

---

## 1. Gateway

### 1.1 Route Mapping

| ID | Test | Category | Expected |
|---|---|---|---|
| T-GW-01 | Request to `/api/v1/auth/*` is proxied to auth-service | happy | 2xx from auth-service |
| T-GW-02 | Request to `/api/v1/trainings/*` is proxied to core-service | happy | 2xx from core-service |
| T-GW-03 | Request to `/api/v1/notifications/*` is proxied to notification-service | happy | 2xx from notification-service |
| T-GW-04 | Request to `/media/*` is served from volume directly | happy | File returned |
| T-GW-05 | Request to unknown route returns 404 | edge | 404 |

### 1.2 Security & Token Swap

| ID | Test | Category | Expected |
|---|---|---|---|
| T-GW-06 | Request with valid `EXTERNAL_JWT_SECRET` is forwarded with swapped `INTERNAL_JWT_SECRET` | happy | Internal secret present on forwarded request |
| T-GW-07 | Request with no token to protected route is rejected at gateway | auth | 401 |
| T-GW-08 | Request with expired JWT is rejected at gateway | auth | 401 |
| T-GW-09 | Request with tampered JWT signature is rejected | auth | 401 |
| T-GW-10 | Direct request to internal service port (bypassing gateway) is rejected | isolation | 403 |
| T-GW-11 | Request with valid JWT but deactivated tenant is rejected (Redis check) | edge | 403 |
| T-GW-12 | Internal service-to-service call with valid `INTERNAL_SERVICE_SECRET` is accepted | happy | Request forwarded |
| T-GW-13 | Internal service call without `INTERNAL_SERVICE_SECRET` is rejected | auth | 403 |

### 1.3 SCORM Upload Size

| ID | Test | Category | Expected |
|---|---|---|---|
| T-GW-14 | SCORM upload under `SCORM_MAX_UPLOAD_MB` limit is accepted | happy | 2xx |
| T-GW-15 | SCORM upload exceeding `SCORM_MAX_UPLOAD_MB` limit is rejected at gateway | edge | 413 |

---

## 2. Auth Service

### 2.1 Login & Redirection

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-01 | Valid email + password for single-tenant user returns JWT with tenant context | happy | 200, JWT with `tenant_id` |
| T-AU-02 | Valid email + password for multi-tenant user returns temporary token + tenant list | happy | 200, tenant list |
| T-AU-03 | Valid email + password for SysAdmin returns JWT scoped to `/admin` | happy | 200, `is_sysadmin: true` |
| T-AU-04 | Invalid password returns 401 | auth | 401 |
| T-AU-05 | Non-existent email returns 401 (no user enumeration) | auth | 401 |
| T-AU-06 | Inactive user account returns 401 | edge | 401 |
| T-AU-07 | User with all tenants inactive is blocked with clear message | edge | 403, message about no active orgs |
| T-AU-08 | Login with correct email but wrong case returns 401 (or succeeds if case-insensitive — must be consistent) | edge | Consistent result |

### 2.2 Tenant Selection

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-09 | `GET /auth/tenants` returns only `Active` tenant memberships | happy | Only active tenants listed |
| T-AU-10 | `GET /auth/tenants` excludes `Inactive` and `Pending` memberships | edge | Excluded |
| T-AU-11 | `POST /auth/select-tenant` with valid tenant returns scoped JWT + branding | happy | 200, JWT with `tenant_id`, branding payload |
| T-AU-12 | `POST /auth/select-tenant` for tenant user is not `Active` in is rejected | isolation | 403 |
| T-AU-13 | `POST /auth/select-tenant` for tenant that does not belong to user is rejected | isolation | 403 |
| T-AU-14 | SysAdmin cannot call `POST /auth/select-tenant` | auth | 403 |

### 2.3 JWT Refresh

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-15 | `POST /auth/refresh` with valid near-expiry token returns new token | happy | 200, new JWT |
| T-AU-16 | `POST /auth/refresh` with expired token is rejected | auth | 401 |
| T-AU-17 | `POST /auth/refresh` with tampered token is rejected | auth | 401 |
| T-AU-18 | Refreshed token carries same `tenant_id` and roles as original | happy | Claims preserved |

### 2.4 Magic Link / Onboarding

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-19 | Inviting a new email generates a 48-hour token and sends Magic Link email | happy | Token created, email queued |
| T-AU-20 | New user clicking valid Magic Link can set password and activates account | happy | Status → `Active`, account created |
| T-AU-21 | Existing active user invited to new tenant is auto-linked, notification email sent (no password step) | happy | Status → `Active` in new tenant immediately |
| T-AU-22 | Inactive user re-invited to same tenant is reactivated, notification email sent | edge | Status → `Active` |
| T-AU-23 | Clicking expired Magic Link (>48h) returns error | edge | 400/410, token expired message |
| T-AU-24 | Clicking already-used Magic Link is rejected (single-use) | edge | 400, token already used |
| T-AU-25 | Confirming registration with mismatched email is rejected (BR-101) | edge | 400 |
| T-AU-26 | Manager regenerating invite for `Pending` user invalidates previous token | edge | Old token rejected, new token valid |
| T-AU-27 | Inviting an email that is `Pending` in another tenant creates independent invite | isolation | New token created, old tenant unaffected |
| T-AU-28 | Non-manager cannot call invite endpoint | auth | 403 |
| T-AU-29 | Manager cannot invite user to a different tenant | isolation | 403 |
| T-AU-30 | SysAdmin inviting user must specify tenant; invite fails without `tenant_id` | edge | 422 |

### 2.5 Password Reset

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-31 | `POST /auth/forgot-password` with valid email queues reset email | happy | 200, email queued |
| T-AU-32 | `POST /auth/forgot-password` with unknown email returns 200 (no enumeration) | edge | 200, no indication of existence |
| T-AU-33 | Reset link is single-use and expires after 48 hours | edge | Token invalidated after use or expiry |
| T-AU-34 | Admin cannot reset another user's password via API | auth | 403/404 |

### 2.6 Heartbeat

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-35 | `POST /progress/heartbeat` with valid enrollment updates `last_heartbeat_at` | happy | 200 |
| T-AU-36 | Heartbeat with JWT expiring within 10 minutes returns `new_token` header | edge | 200, `new_token` present in response header |
| T-AU-37 | Heartbeat with JWT expiring in >10 minutes does NOT return `new_token` | edge | 200, no `new_token` header |
| T-AU-38 | Heartbeat with expired JWT is rejected | auth | 401 |
| T-AU-39 | Heartbeat with enrollment_id belonging to another tenant is rejected | isolation | 403 |
| T-AU-40 | Heartbeat with enrollment_id not belonging to calling user is rejected | auth | 403 |

### 2.7 SysAdmin Invite

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-41 | SysAdmin can invite a new SysAdmin via `POST /users/invite-sysadmin` | happy | 200, invite email queued |
| T-AU-42 | Inviting an email already associated with a tenant as SysAdmin is rejected (BR-107) | edge | 400 |
| T-AU-43 | Non-SysAdmin cannot call `POST /users/invite-sysadmin` | auth | 403 |
| T-AU-44 | Inviting duplicate SysAdmin email is rejected | edge | 400 |

---

## 3. Core Service

### 3.1 Tenant Management

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-01 | SysAdmin can create a new tenant | happy | 201, tenant created |
| T-CO-02 | New tenant creation auto-assigns default certificate template | happy | Template assigned |
| T-CO-03 | SysAdmin can update tenant branding (logo, colors) | happy | 200, updated |
| T-CO-04 | SysAdmin can deactivate a tenant | happy | 200, tenant deactivated |
| T-CO-05 | Non-SysAdmin cannot create or modify tenants | auth | 403 |
| T-CO-06 | Deactivated tenant's users are blocked at gateway on next request (Redis invalidation) | edge | 403 on next request |

### 3.2 User Management

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-07 | Manager can list all users in their tenant | happy | 200, tenant-scoped list |
| T-CO-08 | Manager list excludes themselves | edge | Self not in list (BR-501) |
| T-CO-09 | Manager can update another user's roles | happy | 200, roles updated |
| T-CO-10 | Manager cannot update their own roles | auth | 403 |
| T-CO-11 | Manager cannot update a user from a different tenant | isolation | 403 |
| T-CO-12 | Manager can deactivate a user (`Inactive`) | happy | 200, status updated |
| T-CO-13 | SysAdmin can update user's first/last name with mandatory audit note | happy | 200, name updated, audit log entry created |
| T-CO-14 | Non-SysAdmin cannot update first/last name | auth | 403 |
| T-CO-15 | User cannot update their own email | auth | 403 |
| T-CO-16 | User can update their username if globally unique | happy | 200 |
| T-CO-17 | Username update fails if already taken globally | edge | 409 |

### 3.3 Groups

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-18 | Manager can create a group in their tenant | happy | 201 |
| T-CO-19 | Manager can add members to a group | happy | 200 |
| T-CO-20 | Manager can remove members from a group | happy | 200 |
| T-CO-21 | Manager can delete a group | happy | 200 (soft delete) |
| T-CO-22 | Manager cannot create or modify groups in another tenant | isolation | 403 |
| T-CO-23 | Non-manager cannot manage groups | auth | 403 |
| T-CO-24 | Bulk-delete groups removes all selected groups | happy | 200, all deleted |
| T-CO-25 | Deleting a group does not delete its members | edge | Members unaffected |

### 3.4 Assignments

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-26 | Manager can assign a published training to a user | happy | 201, enrollment created |
| T-CO-27 | Manager can assign a published training to a group (bulk enrollment) | happy | 201, all group members enrolled |
| T-CO-28 | Manager can assign training to both individual users and groups simultaneously | happy | 201, all enrolled |
| T-CO-29 | Assigning an unpublished training is rejected | edge | 400 |
| T-CO-30 | Assigning training from another tenant is rejected | isolation | 403 |
| T-CO-31 | Non-manager cannot assign trainings | auth | 403 |
| T-CO-32 | Duplicate assignment for same user + training is handled gracefully (no duplicate enrollment) | edge | 200 or 409 with clear message |
| T-CO-33 | Manager can set a due date on an assignment | happy | 200 |
| T-CO-34 | Manager can enable Completion Lock on an assignment | happy | 200 |
| T-CO-35 | Manager can reassign a training (increments `attempt_id`, full reset to first lesson) | happy | 200, progress reset |

### 3.5 Trainings

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-36 | Training Creator can create a training (flat or modular structure) | happy | 201 |
| T-CO-37 | Created training defaults to draft (`is_published = false`) | happy | `is_published: false` |
| T-CO-38 | Training structure type (flat/modular) is fixed at creation and cannot be changed | edge | 400 on structure change attempt |
| T-CO-39 | Owner can publish a draft training | happy | 200, `is_published: true`, version incremented |
| T-CO-40 | Owner can unpublish a training | happy | 200, `is_published: false` |
| T-CO-41 | Collaborator cannot publish a training | auth | 403 |
| T-CO-42 | Non-owner Training Creator cannot publish another owner's training | auth | 403 |
| T-CO-43 | Owner can deactivate a training with zero assignments | happy | 200 |
| T-CO-44 | Owner cannot hard-delete a training with active assignments (must use Hard Archive) | edge | 400 |
| T-CO-45 | Hard Archive immediately removes learner access while preserving history | happy | Enrollees blocked, data intact |
| T-CO-46 | Learner cannot see unpublished or deactivated trainings | auth | Not in response |
| T-CO-47 | Training Creator cannot see trainings from another tenant | isolation | 403 |
| T-CO-48 | Owner can invite a collaborator to a draft training | happy | 201, collaborator linked |
| T-CO-49 | Collaborator can edit a training in draft state | happy | 200 |
| T-CO-50 | Collaborator cannot edit a training that is published | edge | 400 |
| T-CO-51 | Training Creator can view compliance reports for their own trainings only | happy | Scoped report returned |
| T-CO-52 | Training Creator cannot view compliance reports for trainings they don't own or collaborate on | isolation | 403 |

### 3.6 Modules, Chapters & Lessons

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-53 | Owner can add a module to a modular training | happy | 201 |
| T-CO-54 | Adding a module to a flat training is rejected | edge | 400 |
| T-CO-55 | Owner can add a chapter to a module (modular) or directly to training (flat) | happy | 201 |
| T-CO-56 | Owner can add a lesson (Video/Rich Text/Quiz/SCORM) to a chapter | happy | 201 |
| T-CO-57 | Lesson sequence order is respected on retrieval | happy | Ordered by `sequence_order` |
| T-CO-58 | Reordering lessons updates `sequence_order` correctly | happy | 200, order updated |
| T-CO-59 | Video lesson accepts both uploaded file path and external URL | happy | 201 |
| T-CO-60 | Rich Text lesson stores TipTap HTML content | happy | 201, content stored |
| T-CO-61 | SCORM lesson upload over size limit is rejected | edge | 413 |
| T-CO-62 | SCORM zip is extracted and manifest parsed for entry point | happy | Entry point stored |
| T-CO-63 | Invalid SCORM zip (no manifest) is rejected | edge | 400 |

### 3.7 Quiz Engine

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-64 | Quiz lesson can be created with configurable max attempts and passing score | happy | 201 |
| T-CO-65 | Quiz supports all 5 question types (MC, MS, T/F, Matching, Ordering) | happy | Each type created successfully |
| T-CO-66 | Learner submitting correct answers above passing score marks quiz complete | happy | 200, lesson marked complete |
| T-CO-67 | Learner submitting below passing score increments attempt counter | happy | 200, attempt count updated |
| T-CO-68 | Learner exhausting all attempts is locked out | edge | Attempt blocked, lockout status set |
| T-CO-69 | Locked-out learner cannot submit further attempts | auth | 403 |
| T-CO-70 | Manager can reset a locked-out quiz for an employee | happy | 200, attempts reset |
| T-CO-71 | Non-manager cannot reset a quiz lockout | auth | 403 |
| T-CO-72 | Quiz retake required if quiz content changes in new version (BR-404) | edge | Attempt count reset on version change |
| T-CO-73 | Attempt counter is per-enrollment, not per-user globally | isolation | Separate counts per enrollment |

### 3.8 Progress Tracking

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-74 | Learner can only access Lesson 1 of a training on first open | happy | Only first lesson unlocked |
| T-CO-75 | Completing Lesson N unlocks Lesson N+1 | happy | Next lesson unlocked |
| T-CO-76 | Completing all lessons in Chapter N unlocks Chapter N+1 | happy | Next chapter unlocked |
| T-CO-77 | Completing all chapters in Module N unlocks Module N+1 (modular) | happy | Next module unlocked |
| T-CO-78 | Learner cannot mark a locked lesson complete via direct API call (server-enforced) | auth | 403 |
| T-CO-79 | Video lesson marks complete only after `onEnded` (full watch) | happy | 200 on completion event |
| T-CO-80 | Rich Text lesson marks complete on explicit "Mark Complete" / "Next" action | happy | 200 |
| T-CO-81 | Video progress (resume position, milestones) is saved on `onProgress` events | happy | Position and milestones stored |
| T-CO-82 | Learner resumes video from saved position on reopen | happy | Resume position returned |
| T-CO-83 | 25%, 50%, 75%, 100% video milestones are recorded for reporting | happy | Milestones in progress record |
| T-CO-84 | SCORM completion is accepted from package-reported status (not overridden) | happy | 200, completion recorded |
| T-CO-85 | SCORM learner can re-launch unlimited times regardless of prior status | edge | No lockout, re-launch allowed |
| T-CO-86 | Progress is scoped to `(user_id, training_id, attempt_id)` — reassignment creates new attempt | happy | New attempt, fresh progress |
| T-CO-87 | Learner cannot access another user's progress via API | isolation | 403 |

### 3.9 Publishing, Versioning & Progress Pushback

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-88 | Publishing a training increments `current_version` and creates a snapshot in `training_histories` | happy | Version incremented, snapshot stored |
| T-CO-89 | Re-publishing with a changed lesson before an employee's current position triggers progress pushback | happy | Employee progress reset to changed lesson |
| T-CO-90 | Progress pushback notifies the employee's Business Manager (In-App) | happy | Notification created for manager |
| T-CO-91 | Progress pushback nulls `cmi.suspend_data` for SCORM lessons | edge | `cmi.suspend_data` = null |
| T-CO-92 | Re-publishing with changes only after employee's current position does NOT reset progress | edge | Progress unchanged |
| T-CO-93 | Completion record stores `training_version_id` at time of completion and is immutable | happy | `version_id` stored, update rejected |

### 3.10 Certificates

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-94 | Completing 100% of a training triggers certificate PDF generation | happy | PDF created, certificate record stored |
| T-CO-95 | Certificate uses the template selected on the training | happy | Correct template applied |
| T-CO-96 | Certificate template variables are correctly resolved (`tenant_name`, `learner_name`, etc.) | happy | Variables replaced in PDF |
| T-CO-97 | Certificate is single-page landscape orientation | happy | PDF format correct |
| T-CO-98 | Learner can retrieve their own certificates | happy | 200 |
| T-CO-99 | Manager can view certificates of employees in their tenant | happy | 200 |
| T-CO-100 | Employee cannot view another employee's certificates | auth | 403 |
| T-CO-101 | Training Creator cannot view another user's certificates | auth | 403 |
| T-CO-102 | SysAdmin can create a certificate template | happy | 201 |
| T-CO-103 | Non-SysAdmin cannot create certificate templates | auth | 403 |
| T-CO-104 | New tenant automatically receives default certificate template | happy | Template assigned on creation |
| T-CO-105 | Multiple templates can be assigned to a tenant | happy | All templates listed for tenant |

### 3.11 Compliance Reports

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CO-106 | Manager can view completion rates for all trainings in their tenant | happy | 200, scoped report |
| T-CO-107 | Manager can view overdue assignments | happy | 200 |
| T-CO-108 | Manager can view quiz failure counts | happy | 200 |
| T-CO-109 | SysAdmin can view reports across all tenants | happy | 200, cross-tenant report |
| T-CO-110 | Training Creator can view reports for their own trainings only | happy | Scoped to owned/collaborated trainings |
| T-CO-111 | Training Creator cannot view reports for another creator's trainings | isolation | 403 |
| T-CO-112 | Employee cannot access compliance reports | auth | 403 |
| T-CO-113 | Manager cannot view reports from another tenant | isolation | 403 |

---

## 4. Notification Service

### 4.1 In-App Notifications

| ID | Test | Category | Expected |
|---|---|---|---|
| T-NO-01 | `GET /api/v1/notifications` returns notifications for authenticated user | happy | 200, scoped list |
| T-NO-02 | Unread count is accurate | happy | Count matches unread items |
| T-NO-03 | User can mark a notification as read | happy | 200, `is_read: true` |
| T-NO-04 | User cannot read another user's notifications | isolation | 403 |
| T-NO-05 | Notifications are scoped to the active tenant | isolation | Only current-tenant notifications returned |
| T-NO-06 | New training assigned creates in-app + email notification for employee | happy | Both created |
| T-NO-07 | Quiz lockout creates in-app + email notification for manager | happy | Both created |
| T-NO-08 | Employee activation creates in-app notification for manager | happy | Notification created |
| T-NO-09 | Progress pushback creates in-app notification for manager | happy | Notification created |
| T-NO-10 | Training completed creates in-app notification for employee | happy | Notification created |
| T-NO-11 | Re-certification triggered creates Email + In-App for employee and In-App for manager | happy | Both notifications created |

### 4.2 Email Queue

| ID | Test | Category | Expected |
|---|---|---|---|
| T-NO-12 | Magic Link invite email is queued and sent via Mailgun | happy | Job queued, Mailgun called |
| T-NO-13 | Existing user invite sends notification email (no Magic Link) | edge | Correct email template used |
| T-NO-14 | Reactivation email is sent for re-invited inactive user | edge | Correct email template used |
| T-NO-15 | Due-date reminder jobs are queued at correct intervals (14d, 7d, 1d) | happy | Jobs created at correct times |
| T-NO-16 | Re-certification reminder jobs queued at 14d, 7d, 1d before expiry | happy | Jobs created at correct times |
| T-NO-17 | Overdue reminder is sent daily when Completion Lock is inactive | edge | Daily job created |
| T-NO-18 | No email sent when `USE_MAILGUN=False` | edge | Queue consumed but Mailgun not called |
| T-NO-19 | Failed email job is retried and logged | edge | Retry attempted, failure logged |

---

## 5. New Features

### 5.1 Re-certification

| ID | Test | Category | Expected |
|---|---|---|---|
| T-RC-01 | Training with `requires_recertification=true` auto-enrolls learner after `recertification_period_days` | happy | New enrollment created, reset to lesson 1 |
| T-RC-02 | Re-certification creates new `attempt_id`, does not overwrite prior completion record | happy | Old record preserved, new enrollment created |
| T-RC-03 | Training with `requires_recertification=false` does not trigger re-enrollment | edge | No new enrollment |
| T-RC-04 | Changing re-certification settings before publish is allowed | edge | 200 |
| T-RC-05 | Re-certification reminder emails sent at 14d, 7d, 1d before expiry | happy | Jobs queued at correct times |
| T-RC-06 | Employee and Manager both notified when re-certification triggers | happy | Both notifications created |
| T-RC-07 | Re-certification does not trigger for SCORM lessons exempt from attempt tracking | edge | Standard re-cert still applies at training level |

### 5.2 Bulk User Import

| ID | Test | Category | Expected |
|---|---|---|---|
| T-BI-01 | SysAdmin uploads valid CSV and all rows are processed | happy | All users invited/linked, result report returned |
| T-BI-02 | Existing active users in CSV are auto-linked (no Magic Link) | edge | Auto-linked, notification email sent |
| T-BI-03 | New users in CSV receive Magic Link email | happy | Token created, email queued |
| T-BI-04 | Invalid email format in CSV row is rejected with reason in report | edge | Row failed, others proceed |
| T-BI-05 | Duplicate email within same CSV is flagged in report | edge | Duplicate row skipped with reason |
| T-BI-06 | Partial success — valid rows processed even when some rows fail | edge | Valid rows succeed, failures reported |
| T-BI-07 | Non-SysAdmin cannot access bulk import endpoint | auth | 403 |
| T-BI-08 | SysAdmin must specify target tenant; missing `tenant_id` is rejected | edge | 422 |
| T-BI-09 | Import into non-existent tenant is rejected | edge | 404 |
| T-BI-10 | CSV with no valid rows returns error with full failure report | edge | 400, all rows listed as failed |

### 5.3 PDF Lesson

| ID | Test | Category | Expected |
|---|---|---|---|
| T-PD-01 | Training Creator can upload a PDF as a lesson | happy | 201, file stored in `lms_images` volume |
| T-PD-02 | Learner can retrieve PDF lesson URL | happy | 200, signed/gated URL returned |
| T-PD-03 | PDF lesson marked complete on "Mark Complete" / "Next" action | happy | 200, lesson complete |
| T-PD-04 | Learner from another tenant cannot access PDF from different tenant | isolation | 403 |
| T-PD-05 | PDF follows same sequential gating rules as other lesson types | happy | Blocked until previous lesson complete |

### 5.4 Training Categories & Tags

| ID | Test | Category | Expected |
|---|---|---|---|
| T-CT-01 | Training requires a category at creation | edge | 422 if category missing |
| T-CT-02 | Training can be created with zero or more tags | happy | 201 |
| T-CT-03 | Learner can filter assigned trainings by category | happy | Filtered results returned |
| T-CT-04 | Learner can filter assigned trainings by status | happy | Filtered results returned |
| T-CT-05 | Manager can filter training library by category and tags when assigning | happy | Filtered results returned |
| T-CT-06 | Learner cannot see trainings from another tenant via search/filter | isolation | No cross-tenant results |

### 5.5 Dashboards

| ID | Test | Category | Expected |
|---|---|---|---|
| T-DB-01 | Employee dashboard returns correct in-progress, completed, and not-started counts | happy | 200, accurate counts |
| T-DB-02 | Employee dashboard shows upcoming due dates (next 7 days only) | happy | Only within 7-day window |
| T-DB-03 | Manager dashboard returns tenant-scoped completion rate | happy | 200, correct percentage |
| T-DB-04 | Manager dashboard shows overdue count and quiz lockout count | happy | Accurate counts |
| T-DB-05 | Creator dashboard shows completion rates only for owned/collaborated trainings | happy | Scoped correctly |
| T-DB-06 | SysAdmin dashboard shows platform-wide stats across all tenants | happy | Cross-tenant aggregates |
| T-DB-07 | Manager cannot access SysAdmin dashboard data | isolation | 403 |
| T-DB-08 | Employee cannot access Manager dashboard data | auth | 403 |
| T-DB-09 | Dashboard data is scoped to active tenant from JWT | isolation | No cross-tenant leakage |

---

## 7. Cross-Cutting: Audit Log

| ID | Test | Category | Expected |
|---|---|---|---|
| T-AU-LOG-01 | Enrollment creates an audit log entry | happy | Entry in `audit_logs` |
| T-AU-LOG-02 | Training completion creates an audit log entry | happy | Entry with `training_version_id` |
| T-AU-LOG-03 | Quiz attempt creates an audit log entry | happy | Entry in `audit_logs` |
| T-AU-LOG-04 | Progress reset creates an audit log entry with `event_type = "progress_reset"` and `version_id` | happy | Entry with correct fields |
| T-AU-LOG-05 | SysAdmin name correction creates an audit log entry with audit note | happy | Entry with note |
| T-AU-LOG-06 | `audit_logs` rejects `UPDATE` operations | edge | DB constraint error |
| T-AU-LOG-07 | `audit_logs` rejects `DELETE` operations | edge | DB constraint error |
| T-AU-LOG-08 | Audit log entries are always scoped to a `tenant_id` | isolation | No unscoped entries |

---

## 8. Cross-Cutting: Soft Deletes

| ID | Test | Category | Expected |
|---|---|---|---|
| T-SD-01 | Soft-deleted user does not appear in any list endpoint | edge | Excluded from results |
| T-SD-02 | Soft-deleted training does not appear in learner training list | edge | Excluded |
| T-SD-03 | Soft-deleted enrollment is excluded from active assignment queries | edge | Excluded |
| T-SD-04 | Hard delete attempt on any protected table is rejected | edge | 405/400 |
| T-SD-05 | Soft-deleted records are retained in audit log queries | happy | Still visible in audit context |
