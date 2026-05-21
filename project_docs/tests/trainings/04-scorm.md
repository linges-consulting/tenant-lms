# SCORM Test Cases

Tests covering SCORM upload, manifest parsing, player runtime, completion, and authentication.

> **Implementation gap (G-01):** `/storage/scorm/` is currently served without an auth guard because browsers do not send `Authorization` headers on iframe `src` requests. A token-based or cookie-based guard is required before these auth tests can pass. See README.md gap G-01.

---

## Upload & Processing

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SCO-01 | Upload valid SCORM 1.2 zip | Draft training with chapter | Upload zip containing `imsmanifest.xml` with SCORM 1.2 namespace | 201 — entry point stored, files extracted to `lms_scorm` volume | happy |
| TC-SCO-02 | Upload valid SCORM 2004 zip | Draft training with chapter | Upload zip with SCORM 2004 manifest | 201 — entry point stored | happy |
| TC-SCO-03 | Manifest with no namespace (bare XML) is parsed correctly | Draft training | Upload zip with no XML namespace declaration | Entry point extracted successfully | edge |
| TC-SCO-04 | Zip with no `imsmanifest.xml` is rejected | Draft training | Upload zip without manifest | 400 — error returned | edge |
| TC-SCO-05 | Zip with path traversal in member names is rejected | Draft training | Upload zip containing `../../../etc/passwd` path | 400 — path traversal blocked | edge |
| TC-SCO-06 | SCORM upload over size limit rejected at gateway | Draft training | Upload zip exceeding `SCORM_MAX_UPLOAD_MB` | 413 | edge |
| TC-SCO-07 | SCORM files stored in `lms_scorm` volume (not ephemeral filesystem) | Any SCORM lesson | Restart core-service container | SCORM content still accessible after restart | happy |
| TC-SCO-08 | Entry point URL stored as `/storage/scorm/{tenant}/{training}/{chapter}/{entry}` | SCORM lesson created | Read lesson `content_data.index_url` | URL follows expected pattern | happy |

---

## Player & Runtime (SCORM 1.2)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SCO-09 | SCORM iframe loads in training viewer | Training with SCORM lesson assigned | Open SCORM lesson | Iframe renders, SCO content loads | happy |
| TC-SCO-10 | `window.API` (SCORM 1.2 runtime) available in parent frame | SCORM lesson open | SCO calls `window.API.LMSInitialize("")` | Returns `"true"` | happy |
| TC-SCO-11 | `LMSInitialize` returns `"true"` | SCORM open | Call from SCO | `"true"` | happy |
| TC-SCO-12 | `LMSFinish` marks chapter complete | SCORM open | SCO calls `LMSFinish("")` | Chapter marked complete, next lesson unlocked | happy |
| TC-SCO-13 | `LMSSetValue("cmi.core.lesson_status", "completed")` marks complete | SCORM open | SCO reports `lesson_status=completed` | Chapter marked complete | happy |
| TC-SCO-14 | `LMSSetValue("cmi.core.lesson_status", "passed")` marks complete | SCORM open | SCO reports `lesson_status=passed` | Chapter marked complete | happy |
| TC-SCO-15 | `LMSSetValue("cmi.core.lesson_status", "failed")` does not mark complete | SCORM open | SCO reports `lesson_status=failed` | Chapter remains incomplete | edge |
| TC-SCO-16 | `LMSSetValue("cmi.core.lesson_status", "incomplete")` does not mark complete | SCORM open | SCO reports `lesson_status=incomplete` | Chapter remains incomplete | edge |
| TC-SCO-17 | `LMSGetValue("cmi.core.student_name")` returns learner's name | SCORM open | SCO calls LMSGetValue | Learner's name returned | happy |
| TC-SCO-18 | `LMSGetLastError` returns `"0"` (no error) | SCORM open | Call after valid operation | `"0"` | happy |
| TC-SCO-19 | `LMSCommit` returns `"true"` | SCORM open | SCO calls LMSCommit | `"true"` | happy |
| TC-SCO-20 | SCORM "Mark Complete" button available when SCO has not self-reported completion | SCORM lesson open, not yet complete | Observe UI | Manual "Mark Complete" button visible | edge |
| TC-SCO-21 | Manual "Mark Complete" marks chapter complete | SCORM open, auto-completion not fired | Click Mark Complete | Chapter complete, next unlocked | edge |

---

## Re-launch & Attempt Limits

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SCO-22 | SCORM can be re-launched unlimited times (exempt from attempt limits) | Learner completed SCORM | Re-open SCORM lesson | Iframe loads again without lockout | edge |
| TC-SCO-23 | SCORM re-launch after progress pushback loads cleanly (no corrupt suspend_data) | Progress pushback occurred | Reopen SCORM lesson | Loads cleanly; no runtime error from stale `cmi.suspend_data` | edge |

---

## Authentication Guard

> These tests require implementation of G-01 before they can pass.

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-SCO-24 | Authenticated learner can load SCORM content | Learner enrolled, valid JWT | Open SCORM lesson in viewer | Content loads (200 from `/storage/scorm/`) | happy |
| TC-SCO-25 | Unauthenticated request to SCORM URL is rejected | No session | Directly GET `/storage/scorm/{path}` without token | 401 or 403 | auth |
| TC-SCO-26 | Authenticated learner from a different tenant cannot access SCORM content | Two tenants | Tenant B learner requests Tenant A SCORM URL | 403 | isolation |
| TC-SCO-27 | Learner not enrolled in the training cannot access its SCORM content | Unenrolled learner | Request SCORM URL for training they are not enrolled in | 403 | auth |
