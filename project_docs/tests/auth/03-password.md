# Password Test Cases

Covers self-service forgot/reset flow and in-settings password change.

---

## Forgot Password (Self-Service)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PWD-01 | Valid email triggers reset email | Active account | POST `/auth/forgot-password` with registered email | 200 — reset email queued via Mailgun | happy |
| TC-PWD-02 | Unknown email returns 200 without revealing existence | No account for email | POST forgot-password with random email | 200 — same response, no indication email is unknown | edge |
| TC-PWD-03 | Reset link is single-use | Reset email received | Use reset link, then click it again | Second click: 400 — token already used | edge |
| TC-PWD-04 | Reset link expires after 48 hours | Token older than 48h | Click expired link | 400/410 — token expired | edge |
| TC-PWD-05 | Valid token + new password resets credentials | Active token | POST `/auth/reset-password` with token + new_password | 200 — password updated, user can log in with new password | happy |
| TC-PWD-06 | Reset with mismatched email + token is rejected | Token issued for email A | Submit token with email B | 400 — mismatch rejected | edge |
| TC-PWD-07 | Admin cannot reset another user's password via API (BR-504) | SysAdmin | Call `POST /users/{id}/reset-password` | 404 — endpoint does not exist; admin password reset is not implemented by design | auth |
| TC-PWD-08 | Rate limiting on forgot-password endpoint | Any | Submit >3 requests/min from same IP | 429 | edge |

---

## Change Password (In-App Settings)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PWD-09 | User can change password with correct current password | Logged-in user | Settings → Security → enter current + new password | 200 — password updated | happy |
| TC-PWD-10 | Wrong current password rejected | Logged-in user | Enter incorrect current password | 400/401 — wrong current password | edge |
| TC-PWD-11 | New password same as current password is rejected | Logged-in user | Enter same password as current | UI validation: "New password must differ from your current password" | edge |
| TC-PWD-12 | New password below minimum strength rejected | Logged-in user | Enter weak password (e.g. "abc") | UI validation error from PasswordStrengthIndicator | edge |
| TC-PWD-13 | Password confirmation mismatch blocked before submit | Logged-in user | Enter non-matching confirm password | UI validation error, no API call | edge |
| TC-PWD-14 | Show/hide toggle works on all three password fields | Settings → Security | Click show/hide icon on each field | Field toggles between text/password type | happy |
| TC-PWD-15 | Successful password change shows success toast | Logged-in user | Complete valid password change | Success toast shown | happy |
| TC-PWD-16 | Unauthenticated call to change-password rejected | No session | PATCH `/users/me/password` without JWT | 401 | auth |
