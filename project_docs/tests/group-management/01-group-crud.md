# Group CRUD Test Cases

---

## Create Group

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-01 | Manager can create a group | Business Manager | POST `/groups` with `name` | 201 — group created in active tenant | happy |
| TC-GRP-02 | Group created with optional description | Manager | POST with `name` + `description` | 201 — description stored | happy |
| TC-GRP-03 | Group name is required | Manager | POST with no `name` | 422 | edge |
| TC-GRP-04 | Group scoped to manager's active tenant | Manager of Tenant A | Create group | Group's `tenant_id` = Tenant A | happy |
| TC-GRP-05 | Non-manager cannot create a group | Base Employee | POST `/groups` | 403 | auth |
| TC-GRP-06 | Manager cannot create group in another tenant | Manager of Tenant A | POST `/groups` with Tenant B JWT | 403 | isolation |
| TC-GRP-07 | Duplicate group name within same tenant | Two groups, same name | Create second group with same name | 409 or accepted — documented behaviour | edge |

---

## Update Group

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-08 | Manager can rename a group | Existing group | PUT `/groups/{id}` with new `name` | 200 — name updated | happy |
| TC-GRP-09 | Manager can update group description | Existing group | PUT with new `description` | 200 — description updated | happy |
| TC-GRP-10 | Manager cannot update group from another tenant | Group in Tenant B | Tenant A Manager calls update | 403 | isolation |
| TC-GRP-11 | Non-manager cannot update a group | Employee | PUT `/groups/{id}` | 403 | auth |

---

## Delete Group

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-GRP-12 | Manager can delete an empty group | Group with 0 members | DELETE `/groups/{id}` | 200 — group soft-deleted | happy |
| TC-GRP-13 | Manager can delete a group that has members | Group with members | DELETE `/groups/{id}` | 200 — group deleted; members unaffected (not deleted) | happy |
| TC-GRP-14 | Deleting a group does not delete its members | TC-GRP-13 | List users | All former members still exist and active | edge |
| TC-GRP-15 | Deleting a group does not remove existing training enrollments | Group had assigned training | Delete group | Enrollments from that assignment persist | edge |
| TC-GRP-16 | Manager cannot delete group from another tenant | Group in Tenant B | Tenant A Manager calls delete | 403 | isolation |
| TC-GRP-17 | Non-manager cannot delete a group | Employee | DELETE `/groups/{id}` | 403 | auth |
| TC-GRP-18 | Bulk delete removes all selected groups | 3 groups selected | Bulk delete | All 3 soft-deleted | happy |
| TC-GRP-19 | Deleted group no longer appears in group list | TC-GRP-12 | GET `/groups` | Deleted group absent | edge |
