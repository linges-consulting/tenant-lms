# Training Lifecycle Test Cases

Tests covering the Draft → Ready → Published → Archived state machine, validation gates, and UI feedback.

---

## Ready Gate (Draft → Ready)

All four conditions must pass for `mark-ready` to succeed.

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-01 | Mark Ready fails — no title | Draft training, no title | Call mark-ready | 400 — "Training must have a title", toast error shown | edge |
| TC-LCY-02 | Mark Ready fails — no category | Draft training, no category | Call mark-ready | 400 — "Training must have a category", toast error shown | edge |
| TC-LCY-03 | Mark Ready fails — no chapters | Draft training with title + category but zero chapters | Call mark-ready | 400 — "Training must have at least one lesson", toast error shown | edge |
| TC-LCY-04 | Mark Ready fails — training with empty module | Training with a module that has no chapters | Call mark-ready | 400 — module has no chapters | edge |
| TC-LCY-05 | Mark Ready succeeds — title + category + ≥1 chapter | Valid draft training | Call mark-ready | 200 — `is_ready=true`, toast success shown | happy |
| TC-LCY-06 | Mark Ready succeeds with no description (description is optional) | Valid draft training, blank description | Call mark-ready | 200 — description is not required | happy |
| TC-LCY-07 | Mark Ready succeeds with certificate = None | Valid draft training, `template_id=null` | Call mark-ready | 200 — no template required | happy |
| TC-LCY-08 | Only owner can mark Ready — collaborator cannot | Training with collaborator | Collaborator calls mark-ready | 403 | auth |
| TC-LCY-09 | Only owner can mark Ready — other Training Creator cannot | Two Training Creators | Non-owner calls mark-ready | 403 | auth |
| TC-LCY-10 | Ready state shown in editor UI | Training just marked ready | Open editor | Status badge shows "Ready" | happy |

---

## Publish (Ready → Published)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-11 | Manager publishes Ready training | Training in Ready state | Manager calls publish | 200 — `is_published=true`, `current_version` incremented | happy |
| TC-LCY-12 | Publish from Draft state (not Ready) is rejected | Draft training | Attempt direct publish | 400 — must be in Ready state | edge |
| TC-LCY-13 | Training Creator cannot publish — only Managers can | Training in Ready state | Training Creator calls publish | 403 | auth |
| TC-LCY-14 | Published training visible to assigned learners | Published + assigned training | Learner opens My Trainings | Training appears | happy |
| TC-LCY-15 | Version number incremented on each publish | Draft training | Publish | `current_version` starts at 1, increments on re-publish | happy |
| TC-LCY-16 | Snapshot created in `training_histories` on publish | Any publish | Publish training | History record created with `version_id` | happy |
| TC-LCY-17 | Already-published training cannot be published again | Published training | Manager calls publish again | 400 — already published | edge |

---

## Revert to Draft (Ready → Draft)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-36 | Owner (Training Creator) can revert a Ready training to Draft | Training in Ready state | Owner calls send-to-draft | 200 — training returns to Draft state | happy |
| TC-LCY-37 | Business Manager can revert a Ready training to Draft | Training in Ready state | Manager calls send-to-draft | 200 — training returns to Draft state | happy |
| TC-LCY-38 | Revert to Draft from Draft state is rejected | Training already in Draft | Call send-to-draft | 400 — already in Draft | edge |
| TC-LCY-39 | Non-owner Training Creator cannot revert another creator's Ready training | Two Training Creators | Non-owner calls send-to-draft | 403 | auth |
| TC-LCY-40 | send-to-draft on non-existent training returns 404 | No such training | Call send-to-draft | 404 | edge |
| TC-LCY-41 | send-to-draft on an Archived training returns 400 | Archived training | Call send-to-draft | 400 | edge |

---

## Unpublish (Published → Draft)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-18 | Business Manager can unpublish a published training | Published training | Manager calls send-to-draft (unpublish) | 200 — `is_published=false` | happy |
| TC-LCY-19 | Unpublished training disappears from learner training list | Published + assigned, then unpublished | Learner opens My Trainings | Training no longer accessible | edge |
| TC-LCY-20 | Training Creator (even owner) cannot unpublish from Published state — Manager only | Published training | Training Creator calls unpublish | 403 | auth |
| TC-LCY-21 | Unpublish + re-publish increments version | Published training | Unpublish, make edits, mark ready, re-publish | `current_version` incremented again | happy |

---

## Archive & Delete

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-22 | Delete training with zero assignments | Draft training, no assignments | Delete training | 200 — soft deleted | happy |
| TC-LCY-23 | Delete training with active assignments is rejected | Published + assigned training | Call delete | 400 — must use Hard Archive | edge |
| TC-LCY-24 | Hard Archive immediately removes learner access | Published + assigned training | Manager calls Hard Archive | All enrolled learners see training as inaccessible; data preserved | happy |
| TC-LCY-25 | Archived training data preserved for reporting | Archived training | Manager views compliance report | Completion records still visible | happy |
| TC-LCY-26 | Only Managers and SysAdmins can archive — Training Creators (including owner) cannot | Published training | Training Creator calls archive | 403 — archive requires Manager or SysAdmin | auth |
| TC-LCY-27 | Archived training not visible in training library | Archived | Learner/Manager browses library | Training not shown | edge |
| TC-LCY-42 | Archive blocked — learner has incomplete enrollment with future due date (BR-503) | Published training; learner enrolled, not completed, due_date in future | Manager calls archive | 400 — "Cannot archive" with active learners | edge |
| TC-LCY-43 | Archive allowed — all learners have completed the training | Published training; all enrollments completed | Manager calls archive | 200 — archived successfully | happy |
| TC-LCY-44 | Archive allowed — all assignments have a past due date (even if enrollment incomplete) | Published training; enrollment not completed but due_date in the past | Manager calls archive | 200 — overdue-but-past-due not blocking | edge |
| TC-LCY-45 | Archive blocked — training is not Published (Draft or Ready) | Draft or Ready training | Manager calls archive | 400 — must be Published | edge |

---

## UI Feedback (Toast Notifications)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-LCY-28 | Toast success on Mark Ready | Valid training | Click Mark Ready | Green success toast appears | happy |
| TC-LCY-29 | Toast error on Mark Ready failure | Invalid training | Click Mark Ready | Red error toast with backend detail message shown | edge |
| TC-LCY-30 | Toast success on Publish | Ready training | Click Publish | Green success toast appears | happy |
| TC-LCY-31 | Toast error on Publish failure | Wrong state or permissions | Click Publish | Red error toast appears | edge |
| TC-LCY-32 | Toast success on Save Settings | Any training | Edit title, click Save | Success toast appears | happy |
| TC-LCY-33 | Toast error on duplicate title conflict (409) | Two trainings, same title | Save training with duplicate title | Toast: "A training with this name already exists" | edge |
| TC-LCY-34 | Toast success on Revert to Draft | Ready training | Click Revert to Draft | Toast confirms reversion | happy |
| TC-LCY-35 | Toast shown across all pages that use sonner (not just editor) | Any page with training actions | Trigger any action | Toast renders — Toaster is mounted at app root | happy |
