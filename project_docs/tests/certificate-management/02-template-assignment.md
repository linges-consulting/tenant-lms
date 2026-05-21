# Certificate Template Assignment Test Cases

Covers assigning templates to tenants and the default template behaviour.

---

## Assigning Templates to Tenants

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-22 | SysAdmin can assign a template to a tenant | Template + tenant exist | Assign template via `target_tenant_id` | Template appears in that tenant's training certificate dropdown | happy |
| TC-CTM-23 | Multiple templates can be assigned to one tenant | SysAdmin | Assign 3 templates to Tenant A | All 3 appear in Tenant A's dropdown | happy |
| TC-CTM-24 | Same template can be assigned to multiple tenants | SysAdmin | Assign Template X to Tenant A and Tenant B | Template visible in both tenants' dropdowns | happy |
| TC-CTM-25 | Template not assigned to a tenant does not appear in that tenant's dropdown | Template assigned to Tenant A only | Tenant B Training Creator opens dropdown | Template not shown | isolation |
| TC-CTM-26 | Non-SysAdmin cannot assign templates to tenants | Manager | Attempt assignment | 403 | auth |

---

## Default Template

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-27 | New tenant automatically receives default template on creation (BR-702) | Create new tenant | Create | Default template linked; tenant has ≥1 template | happy |
| TC-CTM-28 | Default template appears in newly created tenant's certificate dropdown | TC-CTM-27 | Training Creator opens dropdown | Default template listed | happy |
| TC-CTM-29 | Only one template can be marked `is_default` at a time | Two templates | Mark second as default | First default status removed | edge |
| TC-CTM-30 | Default template cannot be deleted | `is_default: true` template | Attempt DELETE | Blocked | edge |
| TC-CTM-31 | Tenant always has at least one template (invariant) | Any tenant | Check after all non-default templates removed | Default template still present | edge |
