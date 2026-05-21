# Category Management Test Cases

Tests covering tenant-scoped category CRUD used to tag and filter trainings. Categories are Manager-managed; Training Creators can read but not write.

---

## Listing Categories

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CAT-01 | Manager lists categories — returns only active (non-deleted) entries | Tenant with 3 active + 1 soft-deleted category | GET `/categories` | Only 3 active categories returned | happy |
| TC-CAT-02 | Training Creator can list categories | Logged in as Training Creator | GET `/categories` | 200 — categories listed | happy |
| TC-CAT-03 | Category list is tenant-scoped — other tenant's categories not shown | Two tenants with separate categories | Tenant A Manager lists categories | Only Tenant A categories returned | isolation |

---

## Creating Categories

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CAT-04 | Manager can create a category | Active Manager | POST `/categories` with `name` | 201 — category created, `is_active=true` | happy |
| TC-CAT-05 | Duplicate category name within same tenant returns 409 | Category "Safety" exists | POST with `name="Safety"` | 409 — duplicate name | edge |
| TC-CAT-06 | Deleted category name can be reused (soft-delete allows reinsertion) | Category "Safety" soft-deleted | POST with `name="Safety"` | 201 — new active category created | edge |
| TC-CAT-07 | Training Creator cannot create a category | Training Creator | POST `/categories` | 403 | auth |

---

## Updating Categories

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CAT-08 | Manager can update a category name | Existing active category | PATCH `/categories/{id}` with new `name` | 200 — name updated | happy |
| TC-CAT-09 | Updating a non-existent category returns 404 | No such category | PATCH with unknown `id` | 404 | edge |
| TC-CAT-10 | Manager cannot update a category belonging to another tenant | Cross-tenant category | PATCH with Tenant B's category `id` | 403 or 404 — cross-tenant blocked | isolation |

---

## Deleting Categories

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CAT-11 | Manager can soft-delete a category | Active category not in use | DELETE `/categories/{id}` | 200 — category soft-deleted (`deleted_at` set) | happy |
| TC-CAT-12 | Deleting a non-existent category returns 404 | No such category | DELETE with unknown `id` | 404 | edge |
| TC-CAT-13 | Training Creator cannot delete a category | Training Creator | DELETE `/categories/{id}` | 403 | auth |
