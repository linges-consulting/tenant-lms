# Tenant Isolation Test Cases (Tenant Management)

---

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-37 | Manager cannot view another tenant's data | Manager of Tenant A | Any request with Tenant B `tenant_id` in JWT | Data scoped to Tenant A only | isolation |
| TC-TEN-38 | Manager cannot update another tenant's settings | Manager of Tenant A | PATCH `/tenants/admin/{tenantB_id}` | 403 | isolation |
| TC-TEN-39 | User list for Manager only returns own-tenant users | Manager of Tenant A | GET `/users` with Tenant A JWT | Only Tenant A users returned | isolation |
| TC-TEN-40 | Deactivated tenant's JWT rejected even if token is technically valid | Tenant A deactivated, user has valid JWT | Make API request | 403 — tenant deactivated check via Redis | edge |
| TC-TEN-41 | SysAdmin can view and manage any tenant | SysAdmin | Access Tenant B settings | 200 — full access | happy |
| TC-TEN-42 | SysAdmin cannot hold a tenant membership (BR-107) | Attempt to link SysAdmin to a tenant | Invite SysAdmin to tenant | 400 — SysAdmins are global-only | edge |
| TC-TEN-43 | Tenant branding does not bleed into another tenant's session | User switches tenants | Log out of Tenant A, select Tenant B | Tenant A colors replaced by Tenant B colors | isolation |
