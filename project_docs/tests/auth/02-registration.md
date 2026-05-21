# Registration & Invitation Flow Test Cases

Covers Magic Link invitations, new user registration, existing-user auto-linking, and re-invitation.

---

## Manager Inviting a New User

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-01 | Manager invites new email — Magic Link generated | New email, no global account | Manager submits invite | 48-hour token created, Magic Link email queued | happy |
| TC-REG-02 | Magic Link email contains registration URL with token | TC-REG-01 | Check email job | Email contains `?token=...&email=...` link | happy |
| TC-REG-03 | Invited user clicks valid Magic Link — completes registration | Valid unexpired token | User clicks link, sets username + password | Account created, tenant membership `Active`, redirected to login | happy |
| TC-REG-04 | Completing registration with mismatched email is rejected (BR-101) | Token for user-a@x.com | Submit completion with user-b@x.com in body | 400 — email mismatch | edge |
| TC-REG-05 | Magic Link expires after 48 hours | Token older than 48 hours | User clicks link | 400/410 — token expired | edge |
| TC-REG-06 | Magic Link is single-use — clicking twice rejects second attempt | Token already used | Submit registration twice | Second attempt: 400 — token already used | edge |
| TC-REG-07 | Username must be globally unique at registration | Username already taken | User tries to register with taken username | 409 — username taken, prompt to choose another | edge |
| TC-REG-08 | Role assigned at invite time is reflected in membership | Manager invites with `is_business_manager=true` | User completes registration | Membership shows `is_business_manager=true` | happy |

---

## Manager Inviting an Existing Active User

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-09 | Existing active user invited to new tenant — auto-linked, no Magic Link | User already active globally | Manager invites email | No token created — user's membership set to `Active` immediately | happy |
| TC-REG-10 | Auto-linked user receives "You've been added to [Tenant]" notification email | TC-REG-09 | Check email queue | Notification email queued (not Magic Link) | happy |
| TC-REG-11 | Auto-linked user sees new tenant in selector on next login | TC-REG-09 | User logs in | New tenant appears in tenant selection list | happy |

---

## Re-invitation of Inactive User

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-12 | Inactive user re-invited to same tenant — status restored to Active (BR-103a) | User `Inactive` in Tenant A | Manager re-invites same email to Tenant A | Status → `Active`, no password reset | edge |
| TC-REG-13 | Restored user receives "Your access has been restored" email | TC-REG-12 | Check email | Restoration email queued | edge |
| TC-REG-14 | Re-invited inactive user can log in immediately without any registration step | TC-REG-12 | User logs in | Tenant A appears in selector | edge |

---

## Token Regeneration

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-15 | Manager regenerates invite for Pending user — old token invalidated | User in `Pending` state | Manager clicks "Resend Invite" | New token created, old token rejected | edge |
| TC-REG-16 | Old Magic Link returns 400 after regeneration | TC-REG-15 | Click old link | 400 — token invalid | edge |
| TC-REG-17 | New Magic Link from regeneration works correctly | TC-REG-15 | Click new link | Registration completes successfully | happy |
| TC-REG-18 | Only Manager or SysAdmin can regenerate tokens | Base Employee | Call regenerate-token endpoint | 403 | auth |

---

## Cross-Tenant Independence

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-19 | User Pending in Tenant A can independently receive invite from Tenant B | User Pending in Tenant A | Tenant B Manager invites same email | Separate token created for Tenant B; Tenant A invite unaffected | isolation |
| TC-REG-20 | Completing Tenant B registration does not activate Tenant A membership | TC-REG-19 | User completes Tenant B registration | Tenant A membership remains `Pending` | isolation |
| TC-REG-21 | Manager cannot invite user to a different tenant | Manager of Tenant A | POST invite with `tenant_id` of Tenant B | 403 | isolation |

---

## SysAdmin Invitation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REG-22 | SysAdmin can invite a user to any tenant with specified roles | SysAdmin + any tenant | POST `/users/admin/invite-to-tenant` with `tenant_id` + roles | Invite created for correct tenant | happy |
| TC-REG-23 | SysAdmin invite must include `tenant_id` | SysAdmin | Omit `tenant_id` from payload | 422 | edge |
| TC-REG-24 | SysAdmin can invite a new SysAdmin | Existing SysAdmin | POST `/users/invite-sysadmin` | Token created, instructions email queued | happy |
| TC-REG-25 | Inviting SysAdmin with email already in a tenant is rejected (BR-107) | Email has tenant membership | Attempt invite-sysadmin | 400 — cannot be both SysAdmin and tenant member | edge |
| TC-REG-26 | Non-SysAdmin cannot call invite-sysadmin | Manager | Call `/users/invite-sysadmin` | 403 | auth |
| TC-REG-27 | Duplicate SysAdmin email is rejected | Email already SysAdmin | Attempt invite-sysadmin with same email | 400 | edge |
