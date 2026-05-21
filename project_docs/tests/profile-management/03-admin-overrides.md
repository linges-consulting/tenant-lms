# Admin Override Test Cases

Covers SysAdmin-only name correction with mandatory audit note.

---

## SysAdmin Name Correction

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ADM-01 | SysAdmin can edit any user's full name | SysAdmin | View any profile → click Edit Name → submit new name with audit note | 200 — name updated globally across all tenants | happy |
| TC-ADM-02 | Audit note is required when SysAdmin changes a name | SysAdmin edits name | Submit without audit note | Validation error — audit note required | edge |
| TC-ADM-03 | Audit log entry created on name change | TC-ADM-01 | Inspect audit_logs | Entry with `event_type = "name_change"`, `changed_by`, old name, new name, and audit note | happy |
| TC-ADM-04 | Name change is reflected globally across all tenants | User is member of 3 tenants | SysAdmin changes name | New name shown in all 3 tenant contexts | happy |
| TC-ADM-05 | Non-SysAdmin cannot access Edit Name option on any profile | Manager or Training Creator | View any profile | No Edit Name button or option visible | auth |
| TC-ADM-06 | Non-SysAdmin cannot call name-change API directly | Manager | PATCH `/users/{id}/name` | 403 | auth |
| TC-ADM-07 | SysAdmin can correct their own name via same flow | SysAdmin views own profile | Edit Name with audit note | 200 — name updated | happy |
| TC-ADM-08 | Audit log is append-only — name-change entries cannot be altered | Audit entry exists | Attempt UPDATE or DELETE on audit_logs row | Blocked at DB or API level | edge |
| TC-ADM-09 | Name change does not affect email or username | TC-ADM-01 | Inspect user record | Email and username unchanged | edge |
| TC-ADM-10 | Old name no longer appears anywhere after change | TC-ADM-01 | Check sidebar, profile, assignments | New name shown everywhere | happy |
