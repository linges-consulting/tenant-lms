# Quiz Engine Test Cases

Tests covering all 5 question types, scoring rules, attempt limits, lockout, and manager reset.

**Scoring rule for Multiple Select:** All-or-nothing — a question is correct only if the learner selects **every correct option and no incorrect options**. Partial selections receive zero credit.

---

## Quiz Creation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-01 | Create quiz with configurable max attempts | Draft training with chapter | Create quiz lesson, set `max_attempts=3`, `passing_score=80` | 201 — quiz stored with correct config | happy |
| TC-QUZ-02 | Quiz defaults to 10 max attempts | Draft training | Create quiz without specifying max_attempts | `max_attempts=10` in stored record | edge |
| TC-QUZ-03 | Quiz with 0 questions is rejected | Draft training | Save quiz with no questions | 422 or UI error — at least 1 question required | edge |
| TC-QUZ-04 | Create quiz with mixed question types | Draft training | Add MC, T/F, Multi-Select, Matching, and Ordering questions to one quiz | 201 — all question types stored | happy |

---

## Question Types

### Multiple Choice (Single Answer)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-05 | Create MC question with 4 options, 1 correct | Draft quiz | Add MC question, mark 1 option correct | 201 — question stored | happy |
| TC-QUZ-06 | Learner selects correct answer | Quiz with MC question | Submit correct answer | Question scored correct | happy |
| TC-QUZ-07 | Learner selects wrong answer | Quiz with MC question | Submit wrong answer | Question scored incorrect | happy |
| TC-QUZ-08 | MC only allows one selection in UI | Quiz in viewer | Attempt to select 2 options | Second selection deselects the first | edge |

### Multiple Select (Multi-Answer — All or Nothing)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-09 | Create MS question with 5 options, 2 correct | Draft quiz | Add MS question, mark 2 options correct | 201 — question stored | happy |
| TC-QUZ-10 | Learner selects all correct options and no wrong ones → scored correct | Quiz with MS question (2 of 5 correct) | Select exactly the 2 correct options | Question scored correct | happy |
| TC-QUZ-11 | Learner selects only 1 of 2 correct options → scored incorrect | Same quiz | Select only 1 correct option | Question scored incorrect — partial credit not given | edge |
| TC-QUZ-12 | Learner selects both correct options + 1 wrong option → scored incorrect | Same quiz | Select 2 correct + 1 wrong | Question scored incorrect | edge |
| TC-QUZ-13 | Learner selects no options → scored incorrect | Same quiz | Submit with nothing selected | Question scored incorrect | edge |
| TC-QUZ-14 | Learner selects all options (correct + wrong) → scored incorrect | Same quiz | Select all 5 | Question scored incorrect | edge |

### True/False

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-15 | Create True/False question | Draft quiz | Add T/F question, mark "True" as correct | 201 | happy |
| TC-QUZ-16 | Learner selects correct answer (True) | Quiz with T/F | Select True | Scored correct | happy |
| TC-QUZ-17 | Learner selects wrong answer (False) | Quiz with T/F | Select False | Scored incorrect | happy |

### Matching (Two-Column)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-18 | Create Matching question with 3 pairs | Draft quiz | Add Matching question with 3 left/right pairs | 201 — pairs stored | happy |
| TC-QUZ-19 | All pairs matched correctly → scored correct | Quiz with Matching | Match all 3 pairs correctly | Question scored correct | happy |
| TC-QUZ-20 | One pair matched incorrectly → scored incorrect (all-or-nothing) | Quiz with Matching | Match 2 of 3 correctly | Question scored incorrect | edge |
| TC-QUZ-21 | All pairs matched incorrectly → scored incorrect | Quiz with Matching | All pairs wrong | Question scored incorrect | edge |

### Ordering / Sequencing

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-22 | Create Ordering question with 4 items | Draft quiz | Add Ordering question, set correct sequence | 201 — sequence stored | happy |
| TC-QUZ-23 | Learner arranges items in correct order → scored correct | Quiz with Ordering | Drag items into correct order | Question scored correct | happy |
| TC-QUZ-24 | Learner arranges items in wrong order → scored incorrect | Quiz with Ordering | Drag 2 items into wrong position | Question scored incorrect — all-or-nothing | edge |
| TC-QUZ-25 | Single item out of place → scored incorrect | Quiz with Ordering | 3 of 4 correct position | Question scored incorrect | edge |

---

## Scoring & Pass/Fail

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-26 | Score at passing threshold → pass | Quiz with `passing_score=80`, learner answers 80% correct | Submit | Quiz marked complete | happy |
| TC-QUZ-27 | Score 1 below passing threshold → fail | Same quiz | Answer 79% correct | Attempt failed, attempt counter incremented | edge |
| TC-QUZ-28 | Score 100% → pass | Any quiz | Answer all correctly | Passed | happy |
| TC-QUZ-29 | Score 0% → fail | Any quiz | Answer nothing correctly | Failed | edge |
| TC-QUZ-30 | Passing quiz marks lesson complete | Training with quiz | Pass quiz | Lesson marked complete, next lesson unlocked | happy |

---

## Attempt Limits & Lockout

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-31 | Attempt counter increments on each failed submission | Quiz with `max_attempts=3` | Fail twice | Attempt count = 2 | happy |
| TC-QUZ-32 | Final attempt used on fail → learner locked out | Quiz with `max_attempts=3` | Fail all 3 attempts | Locked out — `is_locked=true`, no further submissions | edge |
| TC-QUZ-33 | Locked-out learner sees lockout state in UI | Locked learner | Open quiz lesson | Lockout message shown, submit button absent | edge |
| TC-QUZ-34 | Locked-out learner cannot submit via direct API call | Locked learner | POST attempt via API | 403 | auth |
| TC-QUZ-35 | Passing on last attempt before lockout — not locked | Quiz with `max_attempts=3` | Fail twice, pass on 3rd | Lesson complete, not locked | edge |
| TC-QUZ-36 | Attempt counter is per enrollment — different learner has own counter | Two learners enrolled | Learner A uses 2 of 3 attempts | Learner B still has 3 attempts | isolation |
| TC-QUZ-37 | Attempt counter resets after reassignment (new enrollment) | Locked learner | Manager reassigns training | New enrollment, fresh attempt counter | happy |

---

## Manager Reset

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-38 | Manager resets a locked-out quiz | Learner locked out | Manager calls reset endpoint | Attempt counter reset, learner can attempt again | happy |
| TC-QUZ-39 | Manager reset notification sent to learner | Learner locked out | Manager resets | Learner notified (in-app) | happy |
| TC-QUZ-40 | Non-manager cannot reset quiz lockout via API | Base Employee | Call reset endpoint | 403 | auth |
| TC-QUZ-41 | Manager cannot reset quiz for learner in another tenant | Manager of Tenant A | Call reset for Tenant B learner | 403 | isolation |

---

## Versioning Interaction

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-QUZ-42 | Quiz content unchanged in new version — previously passed learner does not retake | Learner passed quiz in v1 | Re-publish with no quiz changes | Progress preserved | edge |
| TC-QUZ-43 | Quiz question modified in new version — previously passed learner must retake (BR-404) | Learner passed quiz in v1 | Re-publish with changed quiz question | Learner's quiz marked as requiring retake, attempt count reset | edge |
| TC-QUZ-44 | Adding a new question to an existing quiz triggers retake requirement | Learner passed quiz in v1 | Re-publish with new question added | Retake required | edge |
