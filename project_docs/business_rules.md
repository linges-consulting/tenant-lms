# Business Rules — Custom LMS

> Specific behavioral rules that govern system logic.
> Rule IDs (BR-xxx) are stable — reference them in code comments, PRs, and tests.

---

## 1. Invitation & Identity

**BR-101 — 2-Step Email Matching**
Registration confirmation fails if the confirming email does not match the invited email.

**BR-102 — Auto-Association**
If the invited email belongs to an existing active global account, the user is linked to the new tenant immediately — no Magic Link or password setup required. A notification email is sent informing them they have been added to the tenant. They log in with their existing credentials.

**BR-103 — Invite Lifecycle**
Magic Link tokens expire after **48 hours** and apply to new users only. Managers or SysAdmins can regenerate links for users in `Pending` status; regeneration automatically invalidates any previous link. Each tenant invite is independent — a Pending status in one tenant does not block an invite from another tenant.

**BR-103a — Re-invite of Inactive User**
If a user is `Inactive` in a tenant and is re-invited to that same tenant, their status is automatically restored to `Active` upon invitation. A notification email is sent confirming restored access. No new password setup is required.

**BR-103b — All Tenants Inactive**
If a user attempts to log in and has no `Active` tenant memberships, login is blocked with the message: "Your account is not associated with any active organizations. Contact your administrator."

**BR-104 — Identity Immutability**
Email is fixed and strictly non-modifiable. First and last names are fixed for regular users.

**BR-105 — Identity Correction**
Only SysAdmins can modify `first_name` and `last_name`. This change is global across all tenants and requires a mandatory audit note explaining the reason, visible on the User's Activity Page.

**BR-106 — Username Management**
Users can update their username provided it is globally unique. Changing a username causes the old profile URL to return a 404.

**BR-107 — SysAdmin Authority**
Existing SysAdmins can create new SysAdmins. The new SysAdmin's email must be globally unique and NOT already associated with any tenant.

**BR-108 — SysAdmin Invitation Scope**
When a SysAdmin invites a user (non-SysAdmin), they must explicitly select the target tenant and the user's role(s) within that tenant.

**BR-109 — Role Assignment at Invite**
The inviting party selects the user's role(s) at the time of invitation: Business Manager, Training Creator, both, or neither (base Employee). Roles can be updated post-activation by a Business Manager (within their tenant) or a SysAdmin (any tenant).

---

## 2. Multi-Tenant Access & Branding

**BR-201 — Tenant Isolation**
Access is strictly denied unless the user's status is `Active` for the requested `tenant_id`.

**BR-202 — User Statuses**
Users within a tenant carry one of three statuses:
- `Pending` — invited but has not completed registration
- `Active` — fully registered and permitted access
- `Inactive` — access revoked for that specific tenant

**BR-203 — Dynamic UI Branding**
Upon tenant selection, the frontend must inject tenant-specific branding (logo, primary color, secondary color) into CSS variables to theme the application.

**BR-204 — SysAdmin Default Theme**
SysAdmins land on a global management dashboard using a neutral, non-tenant-specific system theme.

---

## 3. Training Content & Ownership

**BR-301 — Owner-Only Control**
Only the original creator (owner) can publish, unpublish, archive, or deactivate a training. Assignment of trainings to users and groups is a Business Manager responsibility, not a Training Creator responsibility.

**BR-301a — Training Assignment**
Business Managers assign published trainings from the tenant's training library to individual users, groups, or a combination of both. Training Creators have no assignment permissions.

**BR-302 — Collaborative Drafts**
Owners may invite other Training Creators as collaborators on a training. Collaborators can edit the training **only while it is in draft mode**. Collaborators cannot publish, unpublish, archive, deactivate, or assign users. Collaborators have access to compliance reports for that training.

**BR-303 — Training Hierarchy**
A training can contain standalone chapters, modules with chapters, or a mix of both. The `structure_type` DB column is retained for data history but is no longer enforced — creators can add modules or standalone chapters to any training at any time.

**BR-305 — Training Categories & Tags**
Every training must have a category selected at creation time. Tags are optional, free-form, and searchable. Both are used to filter the training library.

**BR-306 — Re-certification Configuration**
Re-certification settings (`requires_recertification`, `recertification_period_days`) are configured per training at creation time and can be updated before the training is published. Once published, re-certification settings apply to all future completions.

**BR-307 — Re-certification Trigger**
When `recertification_period_days` elapses after a learner's completion date, the system automatically creates a new enrollment (new `attempt_id`, full reset to first lesson of latest version). The learner receives an Email + In-App notification. The Manager receives an In-App notification. Due-date reminders (14d, 7d, 1d) apply.

**BR-308 — Bulk User Import**
Only SysAdmins can perform bulk user imports. The SysAdmin must select the target tenant before uploading. Import applies the same invite logic as individual invites: existing active users are auto-linked; new users receive a Magic Link email. A result report is returned listing successes and failures with reasons. Partial success is permitted.

A training may contain any combination of:
- Standalone chapters: `Training → Chapter → Lesson`
- Modules with chapters: `Training → Module → Chapter → Lesson`

Lesson types: Video | Rich Text | Quiz | SCORM

**BR-304 — Sequential Locking**
Progress is strictly linear at every level:
- Lesson N is locked until Lesson N−1 is marked complete.
- Chapter N is locked until every lesson in Chapter N−1 is complete.
- Module N is locked until every chapter in Module N−1 is complete (applies to modules within a training).

Enforced server-side. Frontend lock is UX only.

---

## 4. Versioning, Progress & Reassignment

**BR-401 — Versioning**
Every **Publish** action generates a new immutable `version_id`. Completion reports must track the specific `version_id` at time of completion.

**BR-402 — Progress Pushback**
Publishing a new version that edits a lesson at or before an employee's current progress triggers an automatic reset to that lesson.

**BR-403 — SCORM Reset**
Any pushback event must explicitly null `cmi.suspend_data` (bookmark) to prevent runtime crashes when the employee resumes edited content.

**BR-404 — Quiz Retakes**
If a quiz or its associated study material changes in a new version, employees must retake that quiz even if previously passed.

**BR-406 — Quiz Question Types**
Supported question types: Multiple Choice (single answer), Multiple Select (multi-answer), True/False, Matching (two columns), Ordering/Sequencing. No text-based or open-ended types.

**BR-407 — Quiz Attempt Configuration**
Max attempts and passing score are configurable per quiz by the Training Creator. Default max attempts: 10.

**BR-405 — Reassignment Logic**
Managers can trigger a **Reassign** for failed or overdue trainings. This increments the `attempt_id` and performs a mandatory full reset to the first lesson of the latest version.

---

## 5. Management & Security

**BR-501 — Managerial Safeguards**
Managers can manage any other user in their tenant, including other Managers. They cannot manage their own account status, roles, or tenant associations. They are excluded from their own employee management views.

**BR-502 — Deletion Policy**
Trainings can only be deleted if they have **zero assignments**.

**BR-503 — Hard Archive**
If assignments exist, the owner must use **Hard Archive** to remove a training. This immediately terminates access for all enrolled employees while preserving data for historical reporting.

**BR-504 — Self-Service Password Recovery**
Password resets are strictly self-service via a secure Mailgun email flow. Admins cannot manually set or view user passwords.

---

## 6. Notifications & Reminders

**BR-601 — 3-Step Email Reminders**
The system automatically sends Mailgun reminders for assigned trainings with a due date:
- 14 days before due date
- 7 days before due date
- 1 day before due date

**BR-602 — Progress Notifications**
Progress pushback (triggered by a re-publish) notifies the affected employee's **Business Manager** via In-App only. The employee is not notified — they will see their updated progress when they next open the training. Internal notifications are also sent for collaborator invitations and identity corrections.

**BR-603 — Overdue Policy**
- If **Completion Lock** is active and the due date passes, the training becomes inaccessible to the employee.
- If Completion Lock is inactive, daily overdue reminders are sent instead.

---

## 7. Certificate Templates

**BR-701 — Admin-Only Template Management**
Certificate templates are created, edited, and assigned to tenants by SysAdmins only. No tenant-level user can create or modify templates.

**BR-702 — Default Template on Tenant Creation**
When a new tenant is created, the system automatically assigns the default certificate template to that tenant. The tenant is never left without at least one template.

**BR-703 — Multi-Template Assignment**
Multiple certificate templates can be assigned to a single tenant. Tenants maintain a library of available templates to choose from when configuring trainings.

**BR-704 — Training-Level Template Selection**
Each training must have a certificate template selected from its tenant's template library. The selected template is used when generating the PDF on 100% completion.

**BR-705 — Tenant-Aware Template Variables**
Templates support dynamic placeholders resolved at PDF generation time:
- `{{tenant_name}}`, `{{tenant_logo}}`, `{{tenant_primary_color}}`
- `{{learner_name}}`, `{{training_title}}`, `{{completion_date}}`

**BR-706 — Certificate Format**
All certificates are generated as single-page, landscape-orientation PDFs. Templates are authored in HTML (with inline CSS). The system renders the HTML with resolved variables and converts to PDF.
