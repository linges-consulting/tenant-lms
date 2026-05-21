# Settings Test Cases

Covers theme preference, avatar selection, username change, and password change from the Settings page.

---

## Theme Preference

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SET-01 | User can switch to Light mode | Settings → Appearance | Click Light | Theme switches to light, CSS class updated | happy |
| TC-SET-02 | User can switch to Dark mode | Settings → Appearance | Click Dark | Theme switches to dark | happy |
| TC-SET-03 | User can switch to System mode | Settings → Appearance | Click System | Theme follows OS preference | happy |
| TC-SET-04 | Theme preference persisted to backend | User changes theme | Change to Dark | `PATCH /users/me` called with `theme_preference: "dark"` | happy |
| TC-SET-05 | Theme preference reloaded on next login | User set Dark, logs out, logs back in | Open app | Dark theme applied immediately | happy |
| TC-SET-06 | Selected theme card shows active indicator (ring/checkmark) | Settings → Appearance | Select Dark | Dark card shows ring or check, others do not | happy |

---

## Avatar

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SET-07 | User can select a predefined avatar shape | Settings → Profile | Select avatar option | Avatar updates in sidebar and profile | happy |
| TC-SET-08 | Avatar selection persisted to backend | TC-SET-07 | Inspect API call | `PATCH /users/me` with `avatar_url` | happy |
| TC-SET-09 | Fallback to initials when no avatar set | User with `avatar_url = null` | View sidebar | Initials shown in avatar circle | edge |
| TC-SET-10 | Avatar change reflected in sidebar immediately (no reload) | Logged-in user | Change avatar | Sidebar avatar updates without page reload | happy |

---

## Username

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SET-11 | User can update their username to a globally unique value | Logged-in user | Settings → Profile → Change username | 200 — username updated, profile URL changes to new username | happy |
| TC-SET-12 | Username must be globally unique | Another user has the username | Attempt to set taken username | 409 — "Username already taken" | edge |
| TC-SET-13 | Old profile URL returns 404 after username change | TC-SET-11 | Navigate to old URL | 404 | edge |
| TC-SET-14 | New profile URL works immediately after username change | TC-SET-11 | Navigate to new URL | Profile loads | happy |
| TC-SET-15 | Username availability checked live (as-you-type or on blur) | Settings form | Type username | Availability indicator updates (available/taken) | happy |
| TC-SET-16 | Username cannot contain special characters (if enforced) | Settings form | Enter "user name!" | Validation error | edge |

---

## Tenant Memberships Display

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SET-17 | Settings page shows all tenant memberships for current user | User in 2 tenants | Open Settings → Memberships tab | Both tenants listed with roles | happy |
| TC-SET-18 | Role shown correctly per tenant | User is Manager in Tenant A, Creator in Tenant B | View memberships | Each tenant shows correct role | happy |
| TC-SET-19 | User cannot change their own roles from settings | Any user | Settings | No role change UI available | auth |
