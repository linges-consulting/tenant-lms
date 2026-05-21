# Versioning & Progress Pushback Test Cases

Tests covering re-publish, version snapshots, progress pushback rules, and SCORM suspend data reset.

---

## Versioning on Publish

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-VER-01 | First publish sets `current_version = 1` | Draft training | Publish | `current_version = 1` | happy |
| TC-VER-02 | Re-publish increments `current_version` | Published training (v1) | Unpublish, edit, mark ready, re-publish | `current_version = 2` | happy |
| TC-VER-03 | Each publish creates an immutable snapshot in `training_histories` | Any publish | Publish | New record in `training_histories` with `version_id` | happy |
| TC-VER-04 | Completion record captures `training_version_id` at time of completion | Training at v2, learner completes | Complete training | Completion record stores `version_id = v2`, not v1 or v3 | happy |
| TC-VER-05 | Completion record `version_id` is immutable after write | Completion record exists | Attempt to update `training_version_id` | Rejected — record immutable | edge |

---

## Progress Pushback

Pushback triggers when a re-published version edits a lesson **at or before** the learner's current progress position.

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-VER-06 | Learner at Lesson 3; Lesson 2 edited in new version → pushed back to Lesson 2 | Learner progress at Lesson 3 (v1) | Re-publish with Lesson 2 changed | Progress reset to Lesson 2; Lesson 3 locked | happy |
| TC-VER-07 | Learner at Lesson 3; Lesson 5 edited → no pushback | Learner progress at Lesson 3 | Re-publish with Lesson 5 changed | Progress unchanged — edit was ahead of learner | edge |
| TC-VER-08 | Learner at Lesson 3; Lesson 3 edited → pushed back to Lesson 3 | Learner progress at Lesson 3 | Re-publish with Lesson 3 changed | Learner must redo Lesson 3 | edge |
| TC-VER-09 | Learner at Lesson 3; Lesson 1 edited → pushed back to Lesson 1 | Learner progress at Lesson 3 | Re-publish with Lesson 1 changed | Progress reset to Lesson 1; Lessons 2 & 3 locked | edge |
| TC-VER-10 | Learner who has completed the training — re-publish with changes before completion position → no pushback on completed record | Learner completed training | Re-publish with lesson changes | Existing completion record unaffected; new enrollment if re-certified | edge |
| TC-VER-11 | Pushback creates in-app notification for Business Manager | Learner gets pushed back | Re-publish triggers pushback | Manager receives in-app: "Progress reset for [Learner] on [Training]" | happy |
| TC-VER-12 | Learner is NOT notified of pushback — sees updated progress on next open | Pushback occurred | Learner opens training viewer | No notification to learner; viewer shows updated (reset) progress | edge |
| TC-VER-13 | Multiple learners at different positions — each gets correct individual pushback | 3 learners at Lessons 2, 4, 6; Lesson 3 changed | Re-publish | Learner at L2: unaffected. Learner at L4: pushed to L3. Learner at L6: pushed to L3. | edge |

---

## SCORM Suspend Data Reset

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-VER-14 | Pushback on a SCORM lesson nulls `cmi.suspend_data` | Learner has SCORM bookmark; SCORM lesson edited in new version | Re-publish triggers pushback | `cmi.suspend_data` set to null for that learner's SCORM record | happy |
| TC-VER-15 | SCORM lesson reloads cleanly after pushback (no stale bookmark crash) | `cmi.suspend_data` nulled by pushback | Learner reopens SCORM | SCORM loads without runtime error | edge |
| TC-VER-16 | Pushback on non-SCORM lesson does not affect SCORM suspend data | Rich text lesson edited; SCORM later in training | Re-publish | `cmi.suspend_data` unchanged for the SCORM lesson | edge |

---

## Quiz Versioning (BR-404)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-VER-17 | Quiz content unchanged in new version — passed learner retains pass | Learner passed quiz in v1; no quiz changes in v2 | Re-publish | Quiz status preserved — no retake required | edge |
| TC-VER-18 | Quiz question modified in new version — passed learner must retake | Learner passed quiz in v1; question text changed in v2 | Re-publish | Learner's quiz marked as requiring retake, attempt count reset | edge |
| TC-VER-19 | New question added to quiz — passed learner must retake | Learner passed in v1; new question added in v2 | Re-publish | Retake required | edge |
| TC-VER-20 | Only the answer options changed — retake required | Learner passed in v1; correct answer option changed | Re-publish | Retake required | edge |
