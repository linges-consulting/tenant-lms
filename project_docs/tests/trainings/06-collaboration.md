# Collaboration Test Cases

Tests covering collaborator add/remove, edit permissions, audit trail, and access boundaries.

---

## Adding Collaborators

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-COL-01 | Owner adds a Training Creator as collaborator | Draft training, two Training Creators in tenant | Owner adds Creator B as collaborator | 201 — collaborator linked, Creator B can edit | happy |
| TC-COL-02 | Owner can add multiple collaborators | Draft training | Add 3 collaborators | All 3 linked | happy |
| TC-COL-03 | Only Training Creators can be added as collaborators | Draft training | Attempt to add a base Employee as collaborator | 400 — only Training Creators allowed | edge |
| TC-COL-04 | User from another tenant cannot be added as collaborator | Draft training | Attempt to add user from Tenant B | 403 — cross-tenant rejected | isolation |
| TC-COL-05 | Adding the owner themselves as collaborator is rejected | Draft training | Owner adds own user_id as collaborator | 400 — already the owner | edge |
| TC-COL-06 | Only the owner can invite collaborators — collaborator cannot | Training with existing collaborator | Collaborator A tries to add Collaborator B | 403 | auth |

---

## Collaborator Edit Permissions

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-COL-07 | Collaborator can add chapter to draft training | Training in Draft with collaborator | Collaborator adds a chapter | 201 — chapter created | happy |
| TC-COL-08 | Collaborator can edit lesson content in draft | Draft training with collaborator | Collaborator edits a lesson | 200 — saved | happy |
| TC-COL-09 | Collaborator cannot edit a published training | Published training with collaborator | Collaborator attempts to add chapter | 400 — edit rejected while published | edge |
| TC-COL-10 | Collaborator cannot mark training as Ready | Draft training with collaborator | Collaborator calls mark-ready | 403 | auth |
| TC-COL-11 | Collaborator cannot publish training | Ready training with collaborator | Collaborator calls publish | 403 | auth |
| TC-COL-12 | Collaborator cannot unpublish training | Published training with collaborator | Collaborator calls unpublish | 403 | auth |
| TC-COL-13 | Collaborator cannot archive training | Published training with collaborator | Collaborator calls archive | 403 | auth |
| TC-COL-14 | Collaborator cannot delete training | Draft training with collaborator | Collaborator calls delete | 403 | auth |
| TC-COL-15 | Collaborator can view compliance report for that training | Training with collaborator | Collaborator fetches compliance report for this training | 200 — scoped report returned | happy |
| TC-COL-16 | Collaborator cannot view compliance reports for other trainings they are not on | Training with collaborator | Collaborator fetches report for a different training | 403 | isolation |

---

## Removing Collaborators

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-COL-17 | Owner removes a collaborator | Training with collaborator | Owner removes Collaborator A | 200 — collaborator unlinked | happy |
| TC-COL-18 | Removed collaborator loses edit access immediately | Collaborator just removed | Removed collaborator attempts to edit chapter | 403 — access denied | edge |
| TC-COL-19 | Removed collaborator loses compliance report access | Collaborator just removed | Removed collaborator fetches compliance report | 403 | edge |
| TC-COL-20 | Only owner can remove collaborators | Training with collaborator | Collaborator A tries to remove Collaborator B | 403 | auth |

---

## Audit Trail

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-COL-21 | Adding a collaborator creates an audit log entry | Draft training | Owner adds collaborator | `audit_logs` entry with `event_type = "collaborator_added"` and collaborator's `user_id` | happy |
| TC-COL-22 | Removing a collaborator creates an audit log entry | Training with collaborator | Owner removes collaborator | `audit_logs` entry with `event_type = "collaborator_removed"` | happy |
| TC-COL-23 | Collaborator edits are attributed to collaborator's `user_id` in audit log | Collaborator edits a chapter | Collaborator saves changes | Audit entry records collaborator's `user_id`, not owner's | happy |
| TC-COL-24 | Audit log entries are immutable — no UPDATE or DELETE on collaborator events | Any audit entry | Attempt UPDATE on `audit_logs` | DB constraint error | edge |
