# Assignment Test Cases

Tests covering individual assignment, group assignment, due dates, completion lock, deduplication, auto-enrollment, and reassignment.

> **Implementation gaps:**
> - **G-02:** Due dates exist in the backend model but the assignment UI does not currently expose them. UI implementation required before TC-ASN-26 through TC-ASN-33 can be tested end-to-end.
> - **G-03:** Auto-enrollment when a user is added to a group that already has training assignments is not yet implemented. Required for TC-ASN-21 through TC-ASN-23.
> - **G-04:** The individual user picker on the assignment UI must filter out users already covered by a selected group. Required for TC-ASN-18 through TC-ASN-20.

---

## Role Permissions

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-01 | Business Manager can assign training to a user | Published training, active user | Manager assigns training | 201 — enrollment created | happy |
| TC-ASN-02 | Business Manager can assign training to a group | Published training, group with members | Manager assigns training to group | 201 — all group members enrolled | happy |
| TC-ASN-03 | Training Creator cannot assign training | Published training | Training Creator calls assign endpoint | 403 | auth |
| TC-ASN-04 | Base Employee cannot assign training | Published training | Employee calls assign endpoint | 403 | auth |
| TC-ASN-05 | Manager cannot assign training from another tenant | Cross-tenant training | Manager calls assign with foreign training_id | 403 | isolation |

---

## Individual Assignment

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-06 | Assign published training to individual user | Published training, active user | Manager assigns | 201 — enrollment created, learner notified (in-app + email) | happy |
| TC-ASN-07 | Assign unpublished training to user is rejected | Draft or archived training | Manager assigns | 400 — only published trainings can be assigned | edge |
| TC-ASN-08 | Assign training to user in another tenant is rejected | User from Tenant B | Manager of Tenant A assigns to Tenant B user | 403 | isolation |
| TC-ASN-09 | Duplicate assignment for same user + training handled gracefully | User already enrolled | Manager assigns same training again | 200 or 409 — no duplicate enrollment created | edge |
| TC-ASN-10 | Assigned training appears in learner's My Trainings | Active enrollment | Learner opens My Trainings | Training listed | happy |

---

## Group Assignment

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-11 | Assign training to group — all members enrolled | Group with 5 members, published training | Manager assigns to group | 201 — 5 enrollments created | happy |
| TC-ASN-12 | Assign training to group + individual users simultaneously | Group + 2 individual users | Manager assigns both | All group members + 2 individuals enrolled | happy |
| TC-ASN-13 | User in group also assigned individually — no duplicate enrollment | User is in assigned group AND individually assigned | Submit combined assignment | Only 1 enrollment for that user | edge |
| TC-ASN-14 | Deleting a group does not remove existing enrollments | Group with assigned training, then group deleted | Manager deletes group | Enrollments persist, learners retain access | edge |
| TC-ASN-15 | Assigning training to an empty group enrolls no one | Empty group | Manager assigns to empty group | 0 enrollments created, no error | edge |

---

## User Picker Filtering (requires G-04)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-16 | Individual user picker shows all active users | Assignment modal open, no group selected | Open user picker | All active tenant users shown | happy |
| TC-ASN-17 | Individual user picker excludes inactive users | Tenant has inactive users | Open user picker | Inactive users not shown | edge |
| TC-ASN-18 | User picker filters out members of an already-selected group | Group A (5 members) already selected | Open individual user picker | The 5 group members are excluded from the picker | edge |
| TC-ASN-19 | Adding a second group — picker updates to exclude both groups' members | Groups A and B selected | Open individual user picker | Members from both groups excluded | edge |
| TC-ASN-20 | Removing a selected group — excluded users reappear in picker | Group A selected, then removed | Open individual user picker | Group A members visible again | edge |

---

## Auto-Enrollment on Group Membership Change (requires G-03)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-21 | New user added to group with active assignment → auto-enrolled | Group has assigned training, new user added | Manager adds new member to group | New member automatically enrolled in the training | happy |
| TC-ASN-22 | Auto-enrolled user receives assignment notification | Same as above | New member auto-enrolled | Learner receives in-app + email notification | happy |
| TC-ASN-23 | User removed from group — existing enrollment unaffected | User in group with assigned training, removed from group | Manager removes user from group | User retains existing enrollment and progress | edge |

---

## Due Dates (requires G-02 for UI)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-24 | Manager can set a due date when assigning training | Assignment modal | Select a due date | Due date stored on enrollment | happy |
| TC-ASN-25 | Manager can assign training without a due date | Assignment modal | Leave due date blank | Enrollment created with no due date | happy |
| TC-ASN-26 | Manager can update the due date on an existing assignment | Existing enrollment | Manager edits due date | Due date updated | happy |
| TC-ASN-27 | Due date shown in learner's My Trainings list | Enrollment with due date | Learner views My Trainings | Due date displayed on training card | happy |
| TC-ASN-28 | Due date shown in learner's Training Viewer | Enrollment with due date | Learner opens Training Viewer | Due date shown in sidebar or header | happy |
| TC-ASN-29 | Due date 14 days away — reminder email queued | Enrollment with due date 14 days from now | System scheduler runs | Reminder email queued (Mailgun) | happy |
| TC-ASN-30 | Due date 7 days away — reminder email queued | Enrollment with due date 7 days from now | System scheduler runs | Reminder email queued | happy |
| TC-ASN-31 | Due date 1 day away — reminder email queued | Enrollment with due date 1 day from now | System scheduler runs | Reminder email queued | happy |
| TC-ASN-32 | Past due date, Completion Lock OFF — daily overdue reminder sent, access retained | Overdue enrollment, lock disabled | Due date passes | Daily email sent, learner can still access training | edge |
| TC-ASN-33 | Past due date, Completion Lock ON — training inaccessible | Overdue enrollment, lock enabled | Due date passes | Learner cannot open training; sees locked state | edge |

---

## Completion Lock

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-34 | Enable Completion Lock on assignment | Existing enrollment | Manager enables lock | Lock stored on enrollment | happy |
| TC-ASN-35 | Completion Lock blocks access after due date | Lock enabled, due date passed | Learner opens training | 403 — access denied, locked state shown | edge |
| TC-ASN-36 | Completion Lock inactive — no access block, only reminders | Lock disabled, due date passed | Learner opens training | Access permitted, reminders sent | edge |
| TC-ASN-37 | Completing training before due date — lock irrelevant | Lock enabled, completed early | Learner completes | No issue — training complete, certificate (if any) issued | happy |

---

## Reassignment

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-ASN-38 | Manager can reassign training | Existing enrollment | Manager clicks Reassign | New `attempt_id` created, progress reset to lesson 1 | happy |
| TC-ASN-39 | Reassignment preserves prior completion record | Previously completed enrollment | Manager reassigns | Old completion record intact; new enrollment at lesson 1 | happy |
| TC-ASN-40 | Learner sees fresh progress after reassignment | Reassigned training | Learner opens training | All lessons show as incomplete | happy |
| TC-ASN-41 | Quiz attempt counter reset on reassignment | Learner was locked out | Manager reassigns | New enrollment, fresh attempt counter | happy |
| TC-ASN-42 | Non-manager cannot trigger reassignment | Base Employee | Call reassign endpoint | 403 | auth |
