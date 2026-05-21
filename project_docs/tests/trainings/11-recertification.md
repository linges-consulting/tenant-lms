# Re-certification Test Cases

Tests covering automatic re-enrollment on expiry, configuration rules, notifications, and reminders.

---

## Configuration

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REC-01 | Training can be configured with `requires_recertification=true` | Draft training | Set `requires_recertification=true` and `recertification_period_days=365` | 200 — settings saved | happy |
| TC-REC-02 | Re-certification settings can be updated before publish | Draft or Ready training | Change `recertification_period_days` | 200 — updated | edge |
| TC-REC-03 | Re-certification settings cannot be changed after publish | Published training | Attempt to update `requires_recertification` | 400 — locked after publish | edge |
| TC-REC-04 | Training with `requires_recertification=false` has no expiry | Published training, recert off | Learner completes | No expiry date set; no re-enrollment ever triggered | happy |

---

## Auto Re-enrollment on Expiry

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REC-05 | Re-certification period elapses → new enrollment auto-created | Learner completed training; `recertification_period_days=30` | 30 days pass since completion | New enrollment created: new `attempt_id`, reset to Lesson 1 of latest version | happy |
| TC-REC-06 | Prior completion record preserved after re-enrollment | Same as above | After re-enrollment | Old completion record intact with original `version_id` and date | happy |
| TC-REC-07 | Re-enrollment uses the latest published version of the training | Training re-published to v2 before recert triggers | Recert triggers | New enrollment is on v2, not the original v1 | edge |
| TC-REC-08 | `requires_recertification=false` — no re-enrollment ever triggered | Training with recert off | Any time passes | No new enrollment created | edge |
| TC-REC-09 | Multiple completions over time each reset the expiry clock | Learner completes re-certification | New completion recorded | Expiry resets from new completion date, not original | edge |

---

## Notifications

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REC-10 | Employee receives in-app notification when re-certification triggers | Re-certification triggered | System creates new enrollment | Learner gets in-app: "Re-certification required for [Training]" | happy |
| TC-REC-11 | Employee receives email when re-certification triggers | Same | System creates new enrollment | Email sent via Mailgun | happy |
| TC-REC-12 | Business Manager receives in-app notification when re-certification triggers | Same | System creates new enrollment | Manager gets in-app: "[Learner] requires re-certification for [Training]" | happy |
| TC-REC-13 | Manager does NOT receive email on re-certification trigger | Same | Trigger | No email to Manager — in-app only | edge |

---

## Reminders

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-REC-14 | Reminder email queued 14 days before re-certification due | Re-enrollment with due date | Scheduler runs at 14-day mark | Email queued for learner | happy |
| TC-REC-15 | Reminder email queued 7 days before re-certification due | Re-enrollment with due date | Scheduler runs at 7-day mark | Email queued for learner | happy |
| TC-REC-16 | Reminder email queued 1 day before re-certification due | Re-enrollment with due date | Scheduler runs at 1-day mark | Email queued for learner | happy |
| TC-REC-17 | No reminder sent if learner completes re-certification before reminder fires | Learner completes before 14-day mark | 14-day mark passes | No duplicate reminder email | edge |
| TC-REC-18 | SCORM lessons exempt from attempt limits but still subject to re-certification at training level | Training with SCORM lesson, recert enabled | Recert period elapses | New enrollment created normally; SCORM re-launch still unlimited | edge |
