# Notification Test Cases

Tests covering in-app notifications, email suppression, event deduplication, and scheduled reminder jobs.

---

## In-App Notifications

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-NOT-01 | GET /notifications returns paginated results | User with multiple notifications | GET `/notifications` | 200 — paginated list with `items`, `total`, `page` | happy |
| TC-NOT-02 | GET /notifications/unread-count returns correct count | User with 3 unread notifications | GET `/notifications/unread-count` | 200 — `count: 3` | happy |
| TC-NOT-03 | Duplicate event_id is silently ignored (idempotent) | Event already stored | Publish same event_id again | No duplicate created, no error | edge |

---

## Event-Driven Notification Logic

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-NOT-04 | PROGRESS_RESET event creates in-app notification for the assigned Manager, not the learner | Learner's progress is reset | Event published | Manager receives in-app notification; learner does not | happy |
| TC-NOT-05 | TRAINING_COMPLETED event creates in-app notification for learner | Learner completes training | Event published | Learner receives in-app notification | happy |
| TC-NOT-06 | TRAINING_COMPLETED does NOT send an email (in-app only) | Learner completes training | Event published | No Mailgun email queued for completion | edge |
| TC-NOT-07 | EMPLOYEE_ACTIVATED event notifies the Manager | Manager reactivates employee | Event published | Manager receives in-app notification about the activation | happy |

---

## Email Suppression

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-NOT-08 | Email is suppressed when `USE_MAILGUN=False` | `USE_MAILGUN=False` in env | Any action that would queue an email | Email suppressed — returns True without calling Mailgun | edge |

---

## Scheduled Reminder Jobs

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-NOT-09 | Scheduler registers exactly 4 cron jobs on startup | Notification service starts | Check registered jobs | 4 cron jobs registered | happy |
| TC-NOT-10 | Due date reminder job calls send_email for each eligible assignment | Assignments with upcoming due dates | Scheduler runs due date check | send_email called once per matching assignment | happy |
| TC-NOT-11 | Overdue reminder job skips assignments that have completion_lock set | Mix of locked and unlocked overdue assignments | Scheduler runs overdue check | Only non-locked overdue assignments receive reminder email | edge |
