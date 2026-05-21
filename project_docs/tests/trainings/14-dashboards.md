# Dashboard Endpoint Test Cases

Tests covering Manager, Creator, and Employee dashboard data endpoints.

---

## Manager Dashboard

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-DSH-01 | Manager can access the manager dashboard | Business Manager | GET `/trainings/dashboard/manager` | 200 — dashboard data returned | happy |
| TC-DSH-02 | Base Employee cannot access manager dashboard | Employee | GET `/trainings/dashboard/manager` | 403 | auth |

---

## Training Creator Dashboard

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-DSH-03 | Training Creator can access creator dashboard | Training Creator | GET `/trainings/dashboard/creator` | 200 — dashboard data returned | happy |
| TC-DSH-04 | Base Employee cannot access creator dashboard | Employee | GET `/trainings/dashboard/creator` | 403 | auth |

---

## Employee Dashboard

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-DSH-05 | Employee can access employee dashboard | Base Employee | GET `/trainings/dashboard/employee` | 200 — dashboard data returned | happy |
| TC-DSH-06 | Manager can also access employee dashboard (scoped to manager as learner) | Business Manager | GET `/trainings/dashboard/employee` | 200 — manager's own learner data returned | happy |
