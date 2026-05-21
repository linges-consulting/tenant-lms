# Tenant Isolation Test Cases

Tests verifying that no data leaks across tenant boundaries in any part of the training system.
Every row in every table is tied to a `tenant_id` from the JWT — these tests confirm that boundary holds.

---

## Training Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-01 | Training from Tenant A is not visible to Tenant B users | Two tenants with trainings | Tenant B user fetches training list | Only Tenant B trainings returned | isolation |
| TC-ISO-02 | Training Creator from Tenant A cannot access Tenant B's training editor | Training exists in Tenant B | Tenant A creator requests `/trainings/{b_training_id}` | 403 or 404 | isolation |
| TC-ISO-03 | Manager from Tenant A cannot assign Tenant B's training | Published Tenant B training | Tenant A Manager calls assign endpoint with Tenant B training_id | 403 | isolation |
| TC-ISO-04 | Collaborator from Tenant A cannot be added to Tenant B's training | Two tenants | Tenant B owner tries to add Tenant A user as collaborator | 403 | isolation |

---

## Assignment & Enrollment Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-05 | Tenant A Manager cannot assign training to Tenant B user | Cross-tenant | Tenant A Manager assigns to Tenant B user_id | 403 | isolation |
| TC-ISO-06 | Tenant A group cannot be assigned Tenant B training | Cross-tenant | Assign Tenant B training to Tenant A group | 403 | isolation |
| TC-ISO-07 | Learner's enrollment list only returns their own tenant's enrollments | Learner in two tenants with different active JWTs | Each JWT returns different training list | Only active-tenant enrollments returned per JWT | isolation |

---

## Progress Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-08 | Learner cannot read another learner's progress via API | Two learners, same training | Learner A requests Learner B's progress endpoint | 403 | isolation |
| TC-ISO-09 | Heartbeat with enrollment_id from another tenant is rejected | Cross-tenant enrollment_id | POST heartbeat with wrong tenant's enrollment_id | 403 | isolation |
| TC-ISO-10 | Progress records not visible across tenants in report endpoints | Two tenants | Tenant A Manager fetches reports | Only Tenant A learner progress shown | isolation |

---

## Certificate Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-11 | Learner cannot download a certificate from another tenant | Certificate exists in Tenant A | Tenant B learner requests that certificate | 403 | isolation |
| TC-ISO-12 | Manager cannot view certificates of users from another tenant | Two tenants | Tenant A Manager requests Tenant B user's certificates | 403 | isolation |
| TC-ISO-13 | Certificate template not assigned to a tenant does not appear in that tenant's dropdown | Template assigned to Tenant A only | Tenant B Training Creator opens certificate dropdown | Template not listed | isolation |

---

## Content Storage Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-14 | PDF lesson from Tenant A is inaccessible to Tenant B learner | Tenant A PDF lesson | Tenant B learner requests Tenant A PDF URL | 403 | isolation |
| TC-ISO-15 | Banner image URL from Tenant A can be loaded publicly (banners are public) | Tenant A banner | Anyone loads `/storage/banners/{tenantA_id}/...` | 200 — banners are public, no auth required | edge |
| TC-ISO-16 | Video from Tenant A is inaccessible to Tenant B learner | Tenant A video | Tenant B learner requests Tenant A video URL | 403 (auth_request gate) | isolation |
| TC-ISO-17 | SCORM from Tenant A is inaccessible to Tenant B learner (post G-01) | Tenant A SCORM (after auth guard implemented) | Tenant B learner requests Tenant A SCORM URL | 403 | isolation |

---

## Quiz & Attempt Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-18 | Quiz attempt counter is per enrollment — different learners are independent | Two learners on same quiz | Learner A uses 2 of 3 attempts | Learner B still has 3 attempts | isolation |
| TC-ISO-19 | Manager from Tenant A cannot reset quiz lockout for Tenant B learner | Cross-tenant | Tenant A Manager calls reset for Tenant B learner_id | 403 | isolation |

---

## Group Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-20 | Manager cannot view or modify groups from another tenant | Two tenants with groups | Tenant A Manager requests Tenant B group list | 403 or empty result | isolation |
| TC-ISO-21 | Manager cannot add users from another tenant to a group | Cross-tenant | Tenant A Manager adds Tenant B user to Tenant A group | 403 | isolation |

---

## Audit Log Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ISO-22 | All audit log entries include `tenant_id` | Any audited event | Inspect `audit_logs` table | Every row has a non-null `tenant_id` | isolation |
| TC-ISO-23 | Manager's report/audit queries return only their tenant's entries | Cross-tenant audit data | Manager fetches activity log | Only own-tenant entries returned | isolation |
