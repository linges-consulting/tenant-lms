# Manager Analytics — Design Spec

**Date:** 2026-05-29  
**Status:** Approved for implementation  
**Scope:** Manager-facing training analytics, employee profile training history, proactive lockout alerting

---

## 1. Overview

Managers currently have no visibility into training performance beyond the coarse stats on the Reports page. They cannot identify employees approaching quiz lockout, see per-training completion trends, or drill into an employee's cross-training history without leaving the app.

This feature adds:
- A two-level Training Analytics section (list → detail)
- Proactive quiz lockout card on the Manager Dashboard
- PDF + CSV exports on both levels
- A Trainings tab on the existing ProfilePage for cross-training employee history
- Navigation wiring from ManagerEmployees to ProfilePage

---

## 2. Information Architecture

### Routes

| Route | Page | Auth |
|---|---|---|
| `/manage/analytics` | Analytics list — all trainings with stats preview | Business Manager |
| `/manage/analytics/:trainingId` | Analytics detail — single training | Business Manager |
| `/profile/:username` | ProfilePage (existing) — extended with Trainings tab | Self, Manager, Creator, SysAdmin |

### Sidebar

Add **"Analytics"** (BarChart3 icon) to the Management section in `Sidebar.tsx`, between Reports and Review & Publish.

---

## 3. Manager Dashboard — Lockout Card

**File:** `app/frontend/src/pages/ManagerDashboard.tsx`

Add a fourth stat card to the metrics grid: **"Quiz Lockouts"**.

- Data source: `quiz_lockouts` from the existing `GET /api/v1/dashboards/manager` response (already returned, not yet displayed on this page).
- Style: neutral/muted when value is 0. Destructive red (text + icon) when value > 0.
- Behaviour: clicking the card navigates to `/manage/analytics`.
- Only visible to users with `is_business_manager`.

---

## 4. Analytics List Page (`/manage/analytics`)

**File:** `app/frontend/src/pages/ManagerAnalytics.tsx` (new)

### 4.1 Filters Bar

| Filter | Type | Options |
|---|---|---|
| Search | Text input | Matches title |
| Status | Select | All / Published / Draft |
| Creator | Select | Populated from training list |
| Category | Select | Populated from training list |

Filters are applied client-side against the full training list returned from the API.

### 4.2 Table

| Column | Notes |
|---|---|
| Title | Sortable |
| Creator | Display name |
| Category | — |
| Status | Published / Draft badge |
| Enrolled | Count of non-deleted assignments |
| Completion % | Completed enrollments / total enrolled × 100 |
| Overdue | Assignments past due date, not completed |
| Lockouts | Red badge when > 0 |
| Last Published | Date of last `is_published = true` state |

Clicking a row navigates to `/manage/analytics/:trainingId`.

### 4.3 Download

"Download" split button (top-right of page):
- **PDF**: formatted A4 landscape table — report title, date, applied filters in header, then the training table. Generated server-side via WeasyPrint.
- **CSV**: one row per training, same columns as the table. Generated server-side.

Filter state is passed as query params to the download endpoint.

---

## 5. Analytics Detail Page (`/manage/analytics/:trainingId`)

**File:** `app/frontend/src/pages/ManagerAnalyticsDetail.tsx` (new)

### 5.1 Header

Training title, creator, category, status badge. Back link to `/manage/analytics`. "Download" split button (PDF / CSV).

### 5.2 Overview Stat Cards

| Card | Value | Notes |
|---|---|---|
| Enrolled | Count of non-deleted assignments for this training | |
| Completion % | Completed / enrolled × 100 | |
| Due Soon | Assignments due within N days, not completed | N selector: 7 / 14 / 30 days; default 7 |
| Overdue | Past due date, not completed | |
| Quiz Lockouts | Users at max attempts without passing | Red when > 0; clicking scrolls to employee table filtered to "Locked" |

### 5.3 Quiz Performance Table

One row per quiz chapter in this training.

| Column | Notes |
|---|---|
| Quiz Name | Chapter title |
| Enrolled | Users who have at least one attempt |
| Pass Rate | % of enrolled who passed |
| Avg Score | Mean score across all attempts |
| Avg Attempts to Pass | Mean attempt_number at which users passed (excludes non-passers) |
| Locked Out | Users at max_attempts without passing |
| Approaching | Users at `max_attempts − threshold` attempts without passing |

**Warning threshold control:** Number input in the section header. Default: 1. Stored in `localStorage` key `analytics_warning_threshold_{trainingId}`. Threshold is applied client-side — the backend returns raw attempt counts, the frontend calculates "approaching."

### 5.4 Employee Status Table

**Filters:** Search by name · Status filter (All / Completed / In Progress / Overdue / Not Started / Locked)  
**Group filter:** Select dropdown populated from groups returned in the employee payload.

| Column | Notes |
|---|---|
| Name | Links to `/profile/:username` |
| Status | Completed ✅ / In Progress ⏳ / Overdue 🔴 / Not Started / Locked ⚠️ |
| Due Date | From assignment |
| Completed | Completion date or — |
| Locked Quizzes | Count of quiz chapters where user is locked out |
| Approaching | Count of quiz chapters where user is approaching limit |
| ▼ | Expand toggle |

**Inline drill-down (expand):** Shows a sub-table of quiz chapters for this training:

| Column | Notes |
|---|---|
| Quiz | Chapter title |
| Attempts | Current attempt count / max_attempts |
| Best Score | Highest score across attempts |
| Passed | Yes / No |
| Status | Locked / Approaching / Clear |

Attempt detail (individual attempt rows with score, date) is loaded lazily via `GET /trainings/{id}/analytics/employees/{user_id}` when the user expands a row.

**Send Reminder button:** Appears on each employee row with status In Progress, Overdue, or Not Started. Sends a manual on-demand reminder via `POST /trainings/{id}/send-reminder`. Distinct from the automated scheduler reminders (14d, 7d, 1d, overdue) — this is manager-initiated. Shows loading state and success/error toast.

### 5.5 Lockout Management Section

Below the employee table. Mirrors the existing "Quiz Lockouts" section on the Reports page — quiz chapters with locked users, Reset button per user (`POST /trainings/{id}/chapters/{chapter_id}/quiz/reset/{user_id}`). Reports page lockout section is retained as-is; this is a second surface for the same action.

### 5.6 Download

Same split button as list page. Detail-page PDF includes: training header, stat card summary row, quiz performance table, full employee status table. CSV: one row per employee — name, email, status, due_date, completed_at, locked_quizzes, approaching_quizzes, plus one column per quiz chapter (attempts / max_attempts, passed).

---

## 6. ProfilePage — Trainings Tab

**File:** `app/frontend/src/pages/ProfilePage.tsx` (extend)

Add a **"Trainings"** tab alongside Overview / Certificates / Activity.

Content: a table of all training assignments for this user (scoped to the active tenant context):

| Column | Notes |
|---|---|
| Training | Title, links to `/manage/analytics/:trainingId` if viewer is a manager |
| Status | Completed / In Progress / Overdue / Not Started |
| Due Date | From assignment |
| Completed | Completion date or — |
| Quiz Summary | e.g. "2/3 quizzes passed" |
| Certificate | Link if issued |

Data source: new `GET /api/v1/trainings/analytics/profile/{user_id}` endpoint.

The existing "In Progress Trainings" placeholder in the Overview tab is replaced with a link: "See full training history in the Trainings tab."

---

## 7. ManagerEmployees Navigation

**File:** `app/frontend/src/pages/ManagerEmployees.tsx`

Make each employee row clickable → navigate to `/profile/:username`. Currently rows have no click action.

---

## 8. Backend — New Endpoints

All new endpoints live in a new router file: `app/core_service/app/api/v1/endpoints/analytics.py`, registered at `/api/v1/trainings` prefix (or a new `/api/v1/analytics` prefix — either works; `/api/v1/analytics` is cleaner).

All endpoints require Business Manager role (`deps.get_business_manager`).

### 8.1 Training List with Stats

```
GET /api/v1/analytics/trainings
```

Returns all non-deleted trainings for the tenant, enriched with:
- `enrolled_count` — non-deleted assignment count
- `completed_count` — completed enrollment count
- `completion_pct` — completed / enrolled × 100
- `overdue_count` — past due_date, not completed
- `lockout_count` — users at max attempts without passing (any quiz in this training)
- `last_published_at` — last time `is_published` was set true

### 8.2 Training Detail Analytics

```
GET /api/v1/analytics/trainings/{training_id}
```

Returns:
- Overview stats: enrolled, completed, completion_pct, overdue, lockouts, due_soon_7d, due_soon_14d, due_soon_30d
- `quiz_chapters`: array of quiz chapter stats (chapter_id, title, max_attempts, enrolled, pass_count, pass_rate, avg_score, avg_attempts_to_pass, locked_count, per-user attempt counts)
- `employees`: array of employee summaries (user_id, username, full_name, email, group_ids, status, due_date, completed_at, locked_quiz_count, per-quiz attempt_count/max_attempts/passed)

Groups are resolved by calling the auth service internally via `deps.get_users_batch` pattern.

### 8.3 Employee Attempt Detail (lazy-load)

```
GET /api/v1/analytics/trainings/{training_id}/employees/{user_id}
```

Returns full attempt history per quiz chapter: attempt_number, score, passed, created_at.

### 8.4 Send Manual Reminder

```
POST /api/v1/analytics/trainings/{training_id}/send-reminder
Body: { "user_ids": ["uid1", "uid2"] }
```

Enqueues a reminder notification for each user_id via the Redis notification queue. Uses the existing `due_date_reminder.html` template if due_date is set, otherwise a generic "training reminder" template.

### 8.5 List-Level Report Download

```
GET /api/v1/analytics/report?format=pdf|csv&status=&creator_id=&category=
```

Returns `Content-Type: application/pdf` or `text/csv`. PDF generated with WeasyPrint from an HTML template. CSV uses Python `csv` module streaming response.

### 8.6 Training Detail Report Download

```
GET /api/v1/analytics/trainings/{training_id}/report?format=pdf|csv
```

Same pattern as above, scoped to one training.

### 8.7 Profile Training History

```
GET /api/v1/analytics/profile/{user_id}
```

Returns all training assignments for a user (scoped to tenant from JWT). Accessible by the user themselves, Business Managers, Training Creators, and SysAdmins — enforced via role check matching the existing `canViewProfile` logic.

---

## 9. Files Changed

### New files
| File | Purpose |
|---|---|
| `app/frontend/src/pages/ManagerAnalytics.tsx` | Analytics list page |
| `app/frontend/src/pages/ManagerAnalyticsDetail.tsx` | Analytics detail page |
| `app/frontend/src/api/analytics.ts` | Frontend API client for analytics endpoints |
| `app/core_service/app/api/v1/endpoints/analytics.py` | All new analytics endpoints |

### Modified files
| File | Change |
|---|---|
| `app/frontend/src/App.tsx` | Add routes for `/manage/analytics` and `/manage/analytics/:trainingId` |
| `app/frontend/src/components/layout/Sidebar.tsx` | Add Analytics nav item under Management |
| `app/frontend/src/pages/ManagerDashboard.tsx` | Add Quiz Lockouts stat card |
| `app/frontend/src/pages/ManagerEmployees.tsx` | Make rows clickable → `/profile/:username` |
| `app/frontend/src/pages/ProfilePage.tsx` | Add Trainings tab, replace In Progress placeholder |
| `app/core_service/app/api/v1/api.py` | Register analytics router |

No database migrations required — all data is derived from existing tables (enrollments, user_progress, quiz_attempts, training_assignments, trainings, chapters).

---

## 10. Out of Scope (Deferred)

- **Creator analytics** — content-performance view in Studio (quiz difficulty, chapter drop-off, most-missed questions, version adoption)
- **Training lifecycle / modification locks** — when to warn/block unpublishing or content changes
- **Employee self-service analytics** — learner-facing quiz attempt history, prominent due dates
