# Token Lifecycle & Heartbeat Test Cases

---

## JWT Refresh

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-JWT-01 | Near-expiry JWT is refreshed automatically on API call | JWT with < refresh threshold remaining | Any protected API call | 401 interceptor fires, `POST /auth/refresh` called, new JWT used transparently | happy |
| TC-JWT-02 | `POST /auth/refresh` with valid token returns new token | Valid JWT | Call refresh endpoint | 200 — new JWT with same `tenant_id` and roles | happy |
| TC-JWT-03 | Refreshed token carries same `tenant_id` and role flags | TC-JWT-02 | Inspect new JWT claims | `tenant_id`, `is_business_manager`, `is_training_creator` identical | happy |
| TC-JWT-04 | Refresh with expired token is rejected | JWT expired | Call refresh | 401 — session expired, redirect to login | auth |
| TC-JWT-05 | Refresh with tampered token signature is rejected | Tampered JWT | Call refresh | 401 | auth |
| TC-JWT-06 | Concurrent 401 responses result in single refresh, not multiple | Multiple in-flight API calls | JWT expires mid-flight | Single refresh call; queued requests retried with new token | edge |

---

## Heartbeat (Training Viewer)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-JWT-07 | Heartbeat fires every 5 minutes while Training Viewer is open | Learner in Training Viewer | Wait 5 minutes | `POST /progress/heartbeat` called with `enrollment_id` | happy |
| TC-JWT-08 | Heartbeat updates `last_heartbeat_at` on session | Valid heartbeat | Send heartbeat | `last_heartbeat_at` updated in `user_sessions` | happy |
| TC-JWT-09 | Heartbeat with JWT expiring within 10 min returns `new_token` header | JWT expiry < 10 min | Send heartbeat | 200, `new_token` header present | edge |
| TC-JWT-10 | Heartbeat with JWT expiring > 10 min does NOT return `new_token` | JWT expiry > 10 min | Send heartbeat | 200, no `new_token` header | edge |
| TC-JWT-11 | Frontend consumes `new_token` header and replaces stored JWT | TC-JWT-09 | Inspect localStorage after heartbeat | New token stored, old token gone | happy |
| TC-JWT-12 | Heartbeat with expired JWT is rejected | JWT expired | Send heartbeat | 401 | auth |
| TC-JWT-13 | Heartbeat with enrollment_id from another tenant is rejected | Cross-tenant enrollment | POST heartbeat with wrong `enrollment_id` | 403 | isolation |
| TC-JWT-14 | Heartbeat with enrollment_id not belonging to calling user is rejected | Another user's enrollment | POST heartbeat | 403 | auth |
| TC-JWT-15 | Heartbeat stops when Training Viewer is unmounted | Learner closes viewer | Observe network | No further heartbeat requests sent | edge |

---

## General Token Security

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-JWT-16 | Request to protected route with no token returns 401 | No session | Any protected endpoint without `Authorization` header | 401 | auth |
| TC-JWT-17 | Request with tampered JWT signature returns 401 | Any JWT | Modify payload, keep original signature | 401 | auth |
| TC-JWT-18 | Deactivated tenant's users are rejected at gateway (Redis check) | Tenant deactivated | User with valid JWT for deactivated tenant makes request | 403 | edge |
| TC-JWT-19 | Direct request to internal service port bypassing gateway is rejected | Internal service | GET `core-service:8000/api/...` directly | 403 — internal secret required | auth |
