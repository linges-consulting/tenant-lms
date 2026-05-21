# Certificate Test Cases

Tests covering certificate generation on completion, template variable substitution, the None option, download/view, and SysAdmin template management.

---

## Certificate Generation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRT-01 | Completing 100% of a training with a template set triggers PDF generation | Training with template, learner completes | Complete final lesson | Certificate PDF generated and stored; certificate record created | happy |
| TC-CRT-02 | Completing training with certificate = None does not generate PDF | Training with `requires_certificate=false` | Complete final lesson | No PDF generated, no certificate record created, no error | edge |
| TC-CRT-03 | Certificate record created only once per completion — no duplicates | Learner completes training | Verify DB | Single certificate record per `(user_id, training_id, version_id)` | edge |
| TC-CRT-04 | Certificate PDF is single-page, landscape orientation | Any completion with template | Download certificate | PDF: 1 page, landscape (A4 or Letter landscape) | happy |
| TC-CRT-05 | Correct template applied — training uses its selected template | Training with Template B | Complete training | PDF matches Template B's layout, not Template A | happy |

---

## Template Variable Substitution

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRT-06 | `{{learner_name}}` replaced with learner's full name | Template contains `{{learner_name}}` | Learner completes training | PDF shows learner's actual name | happy |
| TC-CRT-07 | `{{training_title}}` replaced with training's title | Template contains `{{training_title}}` | Learner completes training | PDF shows training title | happy |
| TC-CRT-08 | `{{completion_date}}` replaced with ISO date of completion | Template contains `{{completion_date}}` | Learner completes training | PDF shows the correct completion date | happy |
| TC-CRT-09 | `{{tenant_name}}` replaced with tenant's display name | Template contains `{{tenant_name}}` | Learner completes training | PDF shows tenant name | happy |
| TC-CRT-10 | `{{tenant_logo}}` replaced with tenant's logo URL | Template contains `{{tenant_logo}}` | Learner completes training | Logo renders in PDF | happy |
| TC-CRT-11 | `{{tenant_primary_color}}` inlined correctly in PDF CSS | Template uses primary color in CSS | Learner completes training | PDF styling matches tenant's primary color | happy |
| TC-CRT-12 | Unknown placeholder `{{unknown_var}}` left blank or removed gracefully | Template has unrecognised variable | Generate certificate | No crash — placeholder replaced with empty string | edge |

---

## Access & Download

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRT-13 | Learner can view and download their own certificates | Learner has completed training with template | Open My Certificates | Certificate listed, download link works | happy |
| TC-CRT-14 | Business Manager can view certificates of employees in their tenant | Manager + completed learner in same tenant | Manager views employee profile | Certificates listed | happy |
| TC-CRT-15 | Employee cannot view another employee's certificates | Two learners in same tenant | Learner A requests Learner B's certificates | 403 | auth |
| TC-CRT-16 | Training Creator cannot view another user's certificates | Training Creator | Call certificates endpoint for another user | 403 | auth |
| TC-CRT-17 | Manager cannot view certificates from another tenant | Manager of Tenant A | Request certificates of Tenant B user | 403 | isolation |
| TC-CRT-18 | Certificate PDF download returns correct Content-Type (`application/pdf`) | Certificate exists | Download certificate | Response headers include `Content-Type: application/pdf` | happy |

---

## Certificate Preview (Editor)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRT-19 | Certificate preview renders actual HTML template, not mock | Training editor with template selected | Click preview (eye icon) | Modal shows HTML-rendered certificate with variable placeholders visible | happy |
| TC-CRT-20 | Certificate preview scales to fit modal width with no scroll | Certificate preview open | Observe modal | Certificate fits width; no vertical or horizontal scroll bar | happy |
| TC-CRT-21 | Preview disabled when certificate = None | Editor with None selected | Observe preview button | Eye icon button is disabled | edge |
| TC-CRT-22 | Switching templates updates preview to new template | Two templates available | Change template, click preview | New template shown, not the previous one | happy |

---

## SysAdmin Template Management

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRT-23 | SysAdmin can create a new certificate template | Logged in as SysAdmin | Submit new HTML template | 201 — template created | happy |
| TC-CRT-24 | SysAdmin can assign template to a tenant | Template + tenant exist | Assign template to tenant | Template appears in that tenant's dropdown | happy |
| TC-CRT-25 | Non-SysAdmin cannot create certificate templates | Training Creator or Manager | Call create template endpoint | 403 | auth |
| TC-CRT-26 | New tenant automatically receives default template | Create new tenant | Tenant created | Default template assigned; tenant has ≥1 template | happy |
| TC-CRT-27 | Multiple templates can be assigned to a single tenant | SysAdmin + tenant | Assign 3 templates to tenant | All 3 appear in tenant's training certificate dropdown | happy |
| TC-CRT-28 | Template not assigned to a tenant does not appear in that tenant's dropdown | Template assigned only to Tenant A | Tenant B Training Creator opens certificate dropdown | Unassigned template not shown | isolation |
