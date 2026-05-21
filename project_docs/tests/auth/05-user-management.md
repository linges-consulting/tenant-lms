# User Management Test Cases

Covers Manager and SysAdmin user management: listing, role changes, deactivation, reactivation, and bulk import.

---

## Listing Users

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-USR-01 | Manager lists users in their tenant | Business Manager | GET `/users` | 200 — only users in the manager's active tenant | happy |
| TC-USR-02 | Manager list excludes themselves (BR-501) | Manager viewing user list | Observe list | Manager's own account not shown | edge |
| TC-USR-03 | Manager list excludes soft-deleted users | Deleted user in tenant | GET `/users` | Deleted user absent | edge |
| TC-USR-04 | SysAdmin lists all global users | SysAdmin | GET `/users/admin/list` | All users across all tenants | happy |
| TC-USR-05 | Base Employee cannot list users | Employee | GET `/users` | 403 | auth |
| TC-USR-06 | Manager cannot list users from another tenant | Cross-tenant | GET `/users` with Tenant B JWT | Only own-tenant users | isolation |

---

## Role Management

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-USR-07 | Manager can update another user's roles | Manager + target user in same tenant | PATCH `/users/{id}/role` | 200 — roles updated | happy |
| TC-USR-08 | Manager cannot update their own roles (BR-501) | Manager | PATCH `/users/{own_id}/role` | 403 | auth |
| TC-USR-09 | Manager can promote Employee to Business Manager | Manager + Employee | Update role to `is_business_manager=true` | 200, user now has Manager rights | happy |
| TC-USR-10 | Manager can grant both Manager and Creator roles simultaneously | Manager | Set both flags to `true` | 200 — user has combined access | happy |
| TC-USR-11 | Manager can demote a Manager to base Employee | Manager + another Manager | Set all role flags to `false` | 200 — user reverts to base Employee | happy |
| TC-USR-12 | Manager cannot change roles of user from another tenant | Cross-tenant | PATCH with Tenant B user_id | 403 | isolation |
| TC-USR-13 | Base Employee cannot modify roles | Employee | PATCH role endpoint | 403 | auth |
| TC-USR-14 | SysAdmin can update roles for any user in any tenant | SysAdmin | PATCH role with `tenant_id` specified | 200 | happy |

---

## Deactivate & Reactivate

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-USR-15 | Manager can deactivate a user in their tenant | Active user | POST `/users/{id}/deactivate` | 200 — status → `Inactive` | happy |
| TC-USR-16 | Deactivated user cannot log in to that tenant | TC-USR-15 | User attempts login + tenant selection | Tenant not shown (Inactive = hidden) | edge |
| TC-USR-17 | Manager can reactivate an inactive user | Inactive user | POST `/users/{id}/reactivate` | 200 — status → `Active` | happy |
| TC-USR-18 | Reactivated user can log in again | TC-USR-17 | User logs in | Tenant appears in selector | happy |
| TC-USR-19 | Manager cannot deactivate themselves | Manager | POST deactivate own `user_id` | 403 | auth |
| TC-USR-20 | Manager cannot deactivate user from another tenant | Cross-tenant | POST deactivate with Tenant B user_id | 403 | isolation |
| TC-USR-21 | Deactivating user does not soft-delete their data | Deactivated user | Check enrollments, completions | Records preserved | edge |

---

## Bulk Import (SysAdmin)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-USR-22 | SysAdmin uploads valid CSV — all rows processed | Valid CSV, SysAdmin selects tenant | Upload | All users invited/linked; result report shows all successes | happy |
| TC-USR-23 | Existing active users in CSV are auto-linked (no Magic Link) | Email already active globally | Upload CSV with existing email | Auto-linked; notification email sent, not Magic Link | edge |
| TC-USR-24 | New users in CSV receive Magic Link email | New email in CSV | Upload | Token created, Magic Link queued | happy |
| TC-USR-25 | Invalid email format in CSV row is flagged, others proceed | CSV with 1 bad email | Upload | Bad row in failures list, valid rows succeed | edge |
| TC-USR-26 | Duplicate email within same CSV flagged in report | CSV with same email twice | Upload | Second occurrence in failures with "duplicate" reason | edge |
| TC-USR-27 | Partial success — valid rows succeed, failures listed | Mixed CSV | Upload | Successes + failures both returned | edge |
| TC-USR-28 | SysAdmin must select tenant before uploading | SysAdmin, no tenant selected | Submit without `tenant_id` | 422 | edge |
| TC-USR-29 | Import into non-existent tenant is rejected | Fake `tenant_id` | Upload | 404 | edge |
| TC-USR-30 | CSV with no valid rows returns full failure report | All-invalid CSV | Upload | 400 — all rows listed as failed | edge |
| TC-USR-31 | Non-SysAdmin cannot access bulk import endpoint | Manager | POST bulk-import | 403 | auth |
| TC-USR-32 | Result report shows row number, email, and reason for each failure | Mixed CSV | Upload | Report includes `row`, `email`, `reason` per failure | happy |
