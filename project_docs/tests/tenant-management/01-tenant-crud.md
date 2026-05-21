# Tenant CRUD Test Cases

---

## Create Tenant

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-01 | SysAdmin creates a new tenant with required fields | SysAdmin | POST `/tenants` with `name`, `admin_email`, `admin_name` | 201 — tenant created, initial Manager account invited | happy |
| TC-TEN-02 | New tenant auto-receives default certificate template (BR-702) | TC-TEN-01 | Check tenant's certificate templates | Default template assigned; tenant has ≥1 template | happy |
| TC-TEN-03 | Initial Business Manager receives Magic Link (if new email) | TC-TEN-01, new admin email | Check email queue | Magic Link email sent to `admin_email` | happy |
| TC-TEN-04 | Initial Manager auto-linked (if existing active email) | TC-TEN-01, existing email | Check membership | Manager membership `Active` immediately | edge |
| TC-TEN-05 | Tenant created with optional logo URL stored | SysAdmin | Create tenant with `logo_url` | Logo URL stored in tenant record | happy |
| TC-TEN-06 | Tenant created with optional brand colors stored | SysAdmin | Create tenant with `primary_color` and `secondary_color` | Colors stored | happy |
| TC-TEN-07 | Tenant name is required | SysAdmin | Omit `name` from payload | 422 | edge |
| TC-TEN-08 | Admin email is required | SysAdmin | Omit `admin_email` | 422 | edge |
| TC-TEN-09 | Non-SysAdmin cannot create a tenant | Manager | POST `/tenants` | 403 | auth |

---

## View Tenants

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-10 | SysAdmin can list all tenants | SysAdmin | GET `/tenants` | All tenants returned | happy |
| TC-TEN-11 | SysAdmin can view individual tenant details | SysAdmin | GET `/tenants/admin/{id}` | Tenant record with stats | happy |
| TC-TEN-12 | Non-SysAdmin cannot list all tenants | Manager | GET `/tenants` | 403 | auth |
| TC-TEN-13 | Tenant list includes active and inactive tenants | SysAdmin | GET `/tenants` | Both states shown with `is_active` flag | happy |

---

## Update Tenant

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-14 | SysAdmin can update tenant name | SysAdmin | PATCH `/tenants/admin/{id}` with new `name` | 200 — name updated | happy |
| TC-TEN-15 | SysAdmin can update tenant logo URL | SysAdmin | PATCH with new `logo_url` | 200 — logo updated | happy |
| TC-TEN-16 | SysAdmin can update primary and secondary colors | SysAdmin | PATCH with `primary_color` + `secondary_color` | 200 — colors updated | happy |
| TC-TEN-17 | Non-SysAdmin cannot update tenant settings | Manager | PATCH `/tenants/admin/{id}` | 403 | auth |
| TC-TEN-18 | Partial update — only provided fields are changed | SysAdmin | PATCH with only `primary_color` | 200 — only color changed, name unchanged | edge |

---

## Deactivate Tenant

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-19 | SysAdmin can deactivate an active tenant | Active tenant | PATCH with `is_active: false` | 200 — `is_active = false` | happy |
| TC-TEN-20 | Deactivated tenant's users are blocked at gateway on next request | TC-TEN-19 | User with valid JWT for deactivated tenant makes request | 403 — Redis invalidation check | edge |
| TC-TEN-21 | Deactivated tenant not shown to users in tenant selector | TC-TEN-19 | User logs in | Deactivated tenant absent from tenant list | edge |
| TC-TEN-22 | SysAdmin can reactivate a deactivated tenant | Deactivated tenant | PATCH with `is_active: true` | 200 — tenant reactivated | happy |
| TC-TEN-23 | Reactivated tenant's users can log in again | TC-TEN-22 | User logs in | Tenant appears in selector | happy |
| TC-TEN-24 | Non-SysAdmin cannot deactivate a tenant | Manager | PATCH `is_active` | 403 | auth |
