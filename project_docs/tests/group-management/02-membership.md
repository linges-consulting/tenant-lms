# Group Membership Test Cases

---

## Adding Members

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-20 | Manager can add one user to a group | Group + active user, same tenant | POST `/groups/{id}/members` with `user_ids` | 200 — member added, `member_count` incremented | happy |
| TC-GRP-21 | Manager can add multiple users in one call | Group + 5 users | POST with array of 5 `user_ids` | 200 — all 5 added | happy |
| TC-GRP-22 | Adding user already in group is handled gracefully | User already a member | POST with same `user_id` | 200 — no duplicate; `added: 0` or idempotent | edge |
| TC-GRP-23 | Cannot add user from another tenant to group | Tenant A group, Tenant B user | POST with Tenant B user_id | 403 | isolation |
| TC-GRP-24 | Cannot add inactive user to group | Inactive user | POST with inactive user_id | 400 — user not active | edge |
| TC-GRP-25 | Non-manager cannot add members | Employee | POST `/groups/{id}/members` | 403 | auth |
| TC-GRP-26 | Manager cannot add members to group in another tenant | Tenant B group | Tenant A Manager calls add-members | 403 | isolation |

---

## Removing Members

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-27 | Manager can remove a member from a group | Group with member | DELETE `/groups/{id}/members/{userId}` | 200 — member removed | happy |
| TC-GRP-28 | Removing member does not delete the user account | TC-GRP-27 | Check user list | User still exists and active | edge |
| TC-GRP-29 | Removing member does not cancel their existing training enrollments | Member has enrollment from group assignment | Remove from group | Enrollment and progress preserved | edge |
| TC-GRP-30 | Removing non-existent member returns 404 | User not in group | DELETE member | 404 | edge |
| TC-GRP-31 | Non-manager cannot remove members | Employee | DELETE `/groups/{id}/members/{userId}` | 403 | auth |
| TC-GRP-32 | Manager cannot remove members from another tenant's group | Tenant B group | Tenant A Manager calls remove | 403 | isolation |

---

## Viewing Members

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-33 | Manager can list members of a group | Group with 3 members | GET `/groups/{id}/members` | 200 — list with `user_id`, `user_name`, `user_email`, `added_at` | happy |
| TC-GRP-34 | Empty group returns empty member list | Empty group | GET members | 200 — empty array | edge |
| TC-GRP-35 | `member_count` in group listing is accurate | Group with 3 members | GET `/groups` | `member_count: 3` | happy |
| TC-GRP-36 | Member count updates after add/remove operations | Group with 2 members | Add 1, remove 1 | Count remains 2 | edge |
| TC-GRP-37 | Non-manager cannot list group members | Employee | GET `/groups/{id}/members` | 403 | auth |
| TC-GRP-38 | Manager cannot list members of group in another tenant | Tenant B group | GET with Tenant A JWT | 403 | isolation |
