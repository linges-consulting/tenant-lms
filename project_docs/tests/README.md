# LMS Test Case Index

Structured manual and API test cases for the full application, organized by feature area.
Complements the backend automation spec in `project_docs/tests.md`.

## Test ID Convention

`TC-[AREA]-[NN]`

| Area Code | Feature |
|---|---|
| `LGN` | Login & Tenant Selection |
| `REG` | Registration & Magic Link |
| `PWD` | Password (Reset & Change) |
| `JWT` | Token Lifecycle & Heartbeat |
| `USR` | User Management (Admin/Manager) |
| `TEN` | Tenant Management |
| `GRP` | Group Management |
| `CTM` | Certificate Template Management (SysAdmin) |
| `CTL` | Certificate Lifecycle (Learner / Manager) |
| `PRF` | Profile Page |
| `SET` | Settings (Theme, Avatar, Password) |
| `ADM` | SysAdmin Overrides (name correction) |
| `NOT` | Notifications (in-app + scheduled reminders) |
| `CAT` | Category Management |
| `DSH` | Dashboards (Manager / Creator / Employee) |
| `CRE` | Training Creation |
| `CON` | Content Authoring (Video, Rich Text, PDF) |
| `QUZ` | Quiz Engine |
| `SCO` | SCORM |
| `LCY` | Training Lifecycle (Draft → Ready → Published → Archived) |
| `COL` | Collaboration |
| `ASN` | Assignment (Individual & Group) |
| `EXE` | Learner Execution & Sequential Gating |
| `CRT` | Certificates (Training completion) |
| `VER` | Versioning & Progress Pushback |
| `REC` | Re-certification |
| `ISO` | Tenant Isolation |

## Test Categories

| Tag | Meaning |
|---|---|
| `happy` | Expected successful path |
| `edge` | Boundary or uncommon but valid input |
| `auth` | Unauthenticated, wrong role, or insufficient permissions |
| `isolation` | Cross-tenant leakage attempts |

## Folders & Files

### `auth/`
| File | Coverage |
|---|---|
| [01-login.md](auth/01-login.md) | Login, tenant selection, multi-tenant users, SysAdmin flow |
| [02-registration.md](auth/02-registration.md) | Magic Link, invitation flows, new vs existing users |
| [03-password.md](auth/03-password.md) | Forgot password, reset by token, change password in settings |
| [04-token-lifecycle.md](auth/04-token-lifecycle.md) | JWT refresh, expiry, heartbeat, session management |
| [05-user-management.md](auth/05-user-management.md) | Manager invite, role changes, deactivate/reactivate, bulk import |

### `tenant-management/`
| File | Coverage |
|---|---|
| [01-tenant-crud.md](tenant-management/01-tenant-crud.md) | Create, view, update, deactivate tenants |
| [02-branding.md](tenant-management/02-branding.md) | Logo, primary/secondary colors, CSS variable injection |
| [03-tenant-isolation.md](tenant-management/03-tenant-isolation.md) | Cross-tenant access, SysAdmin scope |

### `group-management/`
| File | Coverage |
|---|---|
| [01-group-crud.md](group-management/01-group-crud.md) | Create, update, delete groups |
| [02-membership.md](group-management/02-membership.md) | Add/remove members, member list, edge cases |

### `certificate-management/`
| File | Coverage |
|---|---|
| [01-template-management.md](certificate-management/01-template-management.md) | SysAdmin create/edit/delete/activate templates |
| [02-template-assignment.md](certificate-management/02-template-assignment.md) | Assign templates to tenants, default template |
| [03-template-preview.md](certificate-management/03-template-preview.md) | Preview HTML rendering, PDF generation |

### `profile-management/`
| File | Coverage |
|---|---|
| [01-profile-view.md](profile-management/01-profile-view.md) | Role-based visibility, own vs others' profiles |
| [02-settings.md](profile-management/02-settings.md) | Theme preference, avatar, username, password |
| [03-admin-overrides.md](profile-management/03-admin-overrides.md) | SysAdmin name correction with audit note |

### `notifications/`
| File | Coverage |
|---|---|
| [01-notifications.md](notifications/01-notifications.md) | In-app notifications, email suppression, duplicate guard, scheduled jobs |

### `trainings/`
| File | Coverage |
|---|---|
| [01-training-creation.md](trainings/01-training-creation.md) | Settings, banner, certificate selection, structure type |
| [02-content-authoring.md](trainings/02-content-authoring.md) | Video, Rich Text, PDF lessons |
| [03-quiz-engine.md](trainings/03-quiz-engine.md) | All 5 question types, all-or-none scoring, lockout |
| [04-scorm.md](trainings/04-scorm.md) | Upload, manifest, SCORM 1.2 runtime, auth guard |
| [05-training-lifecycle.md](trainings/05-training-lifecycle.md) | Ready gate, publish, revert-to-draft, unpublish, archive gates, toasts |
| [06-collaboration.md](trainings/06-collaboration.md) | Collaborator add/remove, permissions, audit trail |
| [07-assignment.md](trainings/07-assignment.md) | Individual, group, due dates, completion lock |
| [08-learner-execution.md](trainings/08-learner-execution.md) | Sequential gating (flat + modular), completion |
| [09-certificates.md](trainings/09-certificates.md) | PDF generation, variables, None option, download |
| [10-versioning.md](trainings/10-versioning.md) | Re-publish, pushback, SCORM suspend data |
| [11-recertification.md](trainings/11-recertification.md) | Auto re-enrollment, reminders, notifications |
| [12-isolation.md](trainings/12-isolation.md) | Cross-tenant leakage across all training areas |
| [13-categories.md](trainings/13-categories.md) | Category CRUD (Manager only), tenant isolation, soft delete |
| [14-dashboards.md](trainings/14-dashboards.md) | Manager / Creator / Employee dashboard data endpoints |

## Implementation Gaps (require code changes before testing)

| ID | Gap | Affected Tests |
|---|---|---|
| G-01 | SCORM auth guard — `/storage/scorm/` served without authentication | TC-SCO-24 to TC-SCO-27 |
| G-02 | Assignment due dates — backend exists but UI does not expose them | TC-ASN-24 to TC-ASN-33 |
| G-03 | New group member auto-enrollment — adding user to group with active assignments | TC-ASN-21 to TC-ASN-23 |
| G-04 | Assignment user picker — must filter users already covered by a selected group | TC-ASN-18 to TC-ASN-20 |
| G-05 | PDF auth guard — `/storage/pdfs/` served without authentication (same shape as G-01 SCORM) | TC-CON-34 |
