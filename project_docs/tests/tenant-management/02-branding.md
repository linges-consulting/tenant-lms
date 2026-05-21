# Tenant Branding Test Cases

---

## CSS Variable Injection

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-25 | Selecting a tenant injects `--primary` CSS variable | Tenant with custom `primary_color` | User selects tenant | `document.documentElement.style.getPropertyValue('--primary')` equals tenant's primary color | happy |
| TC-TEN-26 | Selecting a tenant injects `--secondary` CSS variable | Tenant with custom `secondary_color` | User selects tenant | Secondary color variable set | happy |
| TC-TEN-27 | Updating tenant primary color reflects on next login | SysAdmin updates color | Update then user logs in and selects tenant | New color applied | happy |
| TC-TEN-28 | Tenant with no custom colors uses system default theme | Tenant with null colors | User selects tenant | Default CSS variables used, no overrides | edge |
| TC-TEN-29 | SysAdmin portal uses neutral system theme — no tenant branding | SysAdmin logs in | Open admin portal | No tenant-specific CSS variables injected | happy |

---

## Logo Display

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-30 | Tenant logo shown in sidebar / header after tenant selection | Tenant with `logo_url` | User selects tenant | Logo image rendered in sidebar | happy |
| TC-TEN-31 | Tenant with no logo falls back to initials or placeholder | Tenant with `logo_url = null` | User selects tenant | Fallback shown — no broken image | edge |
| TC-TEN-32 | Logo URL stored on tenant is used in certificate `{{tenant_logo}}` variable | Tenant with logo | Certificate generated | Logo URL resolved in PDF | happy |

---

## Tenant Settings Page

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-TEN-33 | SysAdmin sees all tenants in settings overview | SysAdmin | Open tenant settings | All tenants listed with status and stats | happy |
| TC-TEN-34 | Tenant list sorts by active status by default | Active + inactive tenants | Open settings | Active tenants first | happy |
| TC-TEN-35 | Saving branding from settings page shows success feedback | SysAdmin edits tenant | Click Save | Success message or toast shown | happy |
| TC-TEN-36 | Deactivating a tenant from settings page shows confirmation | SysAdmin | Toggle deactivate | User sees state change reflected immediately | happy |
