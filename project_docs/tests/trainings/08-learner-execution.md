# Learner Execution & Sequential Gating Test Cases

Tests covering the learner's experience: sequential gating across both structure types, lesson completion per type, and the training viewer.

---

## Sequential Gating — Flat Structure (Training → Chapter → Lesson)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-01 | Only Lesson 1 accessible on first open (flat) | Flat training assigned, 3 lessons in chapter | Learner opens training | Lesson 1 unlocked, Lessons 2 & 3 locked | happy |
| TC-EXE-02 | Completing Lesson 1 unlocks Lesson 2 | Learner on flat training | Complete Lesson 1 | Lesson 2 becomes accessible | happy |
| TC-EXE-03 | Completing Lesson 2 unlocks Lesson 3 | Learner completed Lesson 1 | Complete Lesson 2 | Lesson 3 becomes accessible | happy |
| TC-EXE-04 | Only Chapter 1 accessible initially (flat, multiple chapters) | Flat training with 2 chapters, each with 2 lessons | Learner opens training | Chapter 1 lessons accessible, Chapter 2 locked | happy |
| TC-EXE-05 | All lessons in Chapter 1 complete → Chapter 2 unlocked | Learner completes Chapter 1 | Complete last lesson in Chapter 1 | Chapter 2 Lesson 1 becomes accessible | happy |
| TC-EXE-06 | Direct API call to mark locked lesson complete → rejected server-side | Learner on Lesson 1 | API call: mark Lesson 3 complete | 403 — lesson is locked | auth |
| TC-EXE-07 | Single-chapter, single-lesson flat training — completion triggers training completion | Flat training with 1 lesson | Complete the lesson | Training marked 100% complete | edge |

---

## Sequential Gating — Modular Structure (Training → Module → Chapter → Lesson)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-08 | Only Module 1 accessible initially | Modular training with 2 modules assigned | Learner opens training | Module 1 unlocked, Module 2 locked | happy |
| TC-EXE-09 | All chapters in Module 1 complete → Module 2 unlocked | Learner completes all Module 1 chapters | Complete Module 1 | Module 2 Chapter 1 Lesson 1 accessible | happy |
| TC-EXE-10 | Within Module 1: Chapter 1 complete → Chapter 2 unlocked | Learner on Module 1 | Complete Chapter 1 | Chapter 2 unlocked within Module 1 | happy |
| TC-EXE-11 | Within a chapter: Lesson 1 complete → Lesson 2 unlocked | Modular training | Complete Lesson 1 in Chapter | Lesson 2 unlocked | happy |
| TC-EXE-12 | Learner cannot skip to Module 2 via direct API while Module 1 incomplete | Learner mid-Module 1 | API call to mark Module 2 lesson complete | 403 | auth |
| TC-EXE-13 | Single-module, single-chapter, single-lesson — completion triggers training completion | Minimal modular training | Complete the lesson | Training marked complete | edge |

---

## Completion by Lesson Type

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-14 | Video lesson — only `onEnded` marks it complete | Assigned video lesson | Watch to end | Lesson complete, next unlocked | happy |
| TC-EXE-15 | Video lesson — pausing and leaving does not complete | Assigned video lesson | Pause at 50%, close viewer | Lesson still incomplete | edge |
| TC-EXE-16 | Rich text lesson — "Mark Complete" completes it | Assigned rich text lesson | Click Mark Complete | Lesson complete | happy |
| TC-EXE-17 | PDF lesson — "Mark Complete" completes it | Assigned PDF lesson | Click Mark Complete | Lesson complete | happy |
| TC-EXE-18 | Quiz lesson — passing the quiz completes it | Assigned quiz | Submit passing score | Lesson complete, next unlocked | happy |
| TC-EXE-19 | Quiz lesson — failing does not complete it | Assigned quiz | Submit failing score | Lesson remains incomplete, attempt counter incremented | edge |
| TC-EXE-20 | SCORM lesson — SCO-reported `lesson_status=completed` completes it | Assigned SCORM | SCO calls LMSFinish or sets lesson_status=completed | Lesson complete | happy |
| TC-EXE-21 | SCORM lesson — "Mark Complete" button completes when SCO doesn't self-report | SCORM not auto-completing | Click Mark Complete | Lesson complete | edge |

---

## Training Completion

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-22 | Completing last lesson triggers 100% completion event | Training with 3 lessons | Complete last lesson | Training marked 100% complete | happy |
| TC-EXE-23 | 100% completion triggers certificate generation (if template set) | Training with certificate template | Complete training | Certificate PDF generated, record stored | happy |
| TC-EXE-24 | 100% completion with certificate = None — no PDF generated, no error | Training with `requires_certificate=false` | Complete training | Training complete, no certificate record created | edge |
| TC-EXE-25 | Completion record stores `training_version_id` at time of completion | Training published at version 2 | Learner completes | Completion record shows `training_version_id = v2` | happy |
| TC-EXE-26 | Completion record is immutable — cannot be updated after write | Completion record exists | Attempt to UPDATE the record | Rejected — immutable once written | edge |
| TC-EXE-27 | In-app notification sent to learner on completion | Learner completes training | Complete training | In-app notification: "You completed [Training Title]" | happy |

---

## Progress Isolation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-28 | Learner cannot access another learner's progress via API | Two learners enrolled | Learner A requests Learner B's progress | 403 | isolation |
| TC-EXE-29 | Progress scoped to enrollment — reassignment creates separate progress | Learner with completed enrollment, then reassigned | Check old and new progress | Old completion record intact, new attempt starts at lesson 1 | happy |
| TC-EXE-30 | Two learners independently track progress — no interference | Two learners in same training | Each progresses independently | Each has separate progress, independent lesson unlocking | isolation |

---

## Viewer Behaviour

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-EXE-31 | Training sidebar shows correct locked/unlocked state | Learner on lesson 1 of 3 | Open viewer | Lesson 1 active, Lessons 2 & 3 shown as locked | happy |
| TC-EXE-32 | Sidebar updates after completing a lesson — next item unlocks | Learner completes lesson | Completion registered | Sidebar updates — next lesson unlocked without page reload | happy |
| TC-EXE-33 | Heartbeat fires every 5 minutes while viewer is open | Learner with 9-min-to-expire JWT | Keep viewer open for 5 min | Heartbeat fired; if JWT < 10 min from expiry, new_token returned | happy |
| TC-EXE-34 | Heartbeat with enrollment from another tenant is rejected | Cross-tenant enrollment_id | POST heartbeat with wrong enrollment_id | 403 | isolation |
