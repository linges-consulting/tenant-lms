# Login & Tenant Selection Test Cases

---

## Basic Login

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LGN-01 | Single-tenant user logs in successfully | Active user in one tenant | Enter valid email + password | 200 — JWT with `tenant_id` auto-selected, redirected to `/dashboard` | happy |
| TC-LGN-02 | Multi-tenant user sees tenant selection screen | User active in two tenants | Enter valid email + password | Temporary session token + tenant list shown; redirected to `/select-tenant` | happy |
| TC-LGN-03 | SysAdmin logs in and lands on `/admin` | SysAdmin account | Enter valid credentials | 200 — `is_sysadmin: true`, redirected to `/admin` | happy |
| TC-LGN-04 | Wrong password returns 401 | Valid account | Enter correct email, wrong password | 401 — generic "Invalid credentials" (no enumeration) | auth |
| TC-LGN-05 | Non-existent email returns 401 | No account | Enter random email | 401 — same generic error (no user enumeration) | auth |
| TC-LGN-06 | Deactivated user account returns 401 | Account deactivated globally | Enter valid credentials | 401 — blocked | auth |
| TC-LGN-07 | User with all tenants inactive is blocked with clear message | User has two inactive tenant memberships | Enter valid credentials | 403 — "Your account is not associated with any active organizations. Contact your administrator." | edge |
| TC-LGN-08 | Email matching is case-insensitive (or consistent) | Account with mixed-case email | Login with different case | Result consistent with registration case — documented behaviour | edge |
| TC-LGN-09 | Login form shows password | Login page | Click show/hide toggle | Password field toggles between text/password | happy |
| TC-LGN-10 | Submitting empty form shows inline validation | Login page | Click login without filling fields | Field-level errors shown, no API call made | edge |

---

## Tenant Selection

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LGN-11 | `GET /auth/tenants` returns only Active memberships | User active in Tenant A, inactive in Tenant B | Reach tenant selection | Only Tenant A listed | happy |
| TC-LGN-12 | Pending memberships not shown in tenant list | User pending in Tenant C | Reach tenant selection | Tenant C not listed | edge |
| TC-LGN-13 | Selecting tenant issues scoped JWT with `tenant_id` + roles | Multi-tenant user | Select Tenant A | JWT contains correct `tenant_id` and role flags for Tenant A | happy |
| TC-LGN-14 | Selecting tenant applies tenant branding (colors, logo) | Tenant with custom primary color | Select tenant | CSS variables `--primary` updated to tenant's primary color | happy |
| TC-LGN-15 | Selecting a tenant the user is not `Active` in is rejected | Tampered request | POST `/auth/select-tenant` with foreign `tenant_id` | 403 | isolation |
| TC-LGN-16 | SysAdmin cannot call `POST /auth/select-tenant` | SysAdmin session | SysAdmin calls select-tenant | 403 | auth |
| TC-LGN-17 | Single-tenant user skips selection screen | One active tenant | Login | Redirected directly to `/dashboard`, no selection shown | happy |

---

## Logout & Session End

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LGN-18 | Logout clears JWT and local storage | Authenticated user | Click logout | Token cleared, redirected to `/login` | happy |
| TC-LGN-19 | Accessing protected route after logout redirects to login | Logged out | Navigate to `/dashboard` | Redirected to `/login` | happy |
| TC-LGN-20 | Expired JWT on any request triggers 401 and redirects to login | JWT expired | Any API call | 401, redirected to login | auth |
