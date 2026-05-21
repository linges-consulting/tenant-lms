# Certificate Template Preview & PDF Test Cases

---

## HTML Preview

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-32 | SysAdmin can preview template HTML in editor | Template with HTML content | Open template editor, click Preview | Rendered HTML shown — variables shown as placeholders (e.g. `{{learner_name}}`) | happy |
| TC-CTM-33 | Preview renders with sample variable values | Template with variables | Preview with sample data payload | Variables substituted with sample data | happy |
| TC-CTM-34 | Preview opens in new browser tab (PDF) | SysAdmin | Click PDF preview button | PDF opens in new tab | happy |
| TC-CTM-35 | Preview with invalid HTML does not crash the preview page | Broken HTML in template | Preview | Graceful error or best-effort rendering | edge |

---

## PDF Generation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-36 | SysAdmin can generate a PDF preview of any template | Any template | Call `/certificates/templates/{id}/pdf` | PDF blob returned, Content-Type: `application/pdf` | happy |
| TC-CTM-37 | Generated PDF is single-page, landscape orientation | Any template | Download and inspect PDF | 1 page, landscape | happy |
| TC-CTM-38 | All supported variables resolved in generated PDF | Template with all 6 variables | Generate with real learner/training data | All `{{...}}` replaced with real values | happy |
| TC-CTM-39 | `{{tenant_logo}}` renders as an inline image in PDF | Template with logo variable | Generate PDF for tenant with logo | Logo image appears in PDF | happy |
| TC-CTM-40 | `{{tenant_primary_color}}` inlined correctly in PDF CSS | Template uses color in style attribute | Generate PDF | Color matches tenant's `primary_color` | happy |
| TC-CTM-41 | Unknown variable `{{custom_field}}` handled gracefully | Template with unknown variable | Generate PDF | Variable removed or left blank — no crash | edge |
| TC-CTM-42 | Non-SysAdmin cannot generate template preview PDF | Manager | GET `/certificates/templates/{id}/pdf` | 403 | auth |

---

## In-Training-Editor Preview (Training Creator)

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-43 | Training Creator can preview selected template in editor | Template selected in training settings | Click eye icon | Modal opens with rendered HTML | happy |
| TC-CTM-44 | Preview scales to fit modal width with no scroll | TC-CTM-43 | Inspect modal | Certificate fits container width, no scroll | happy |
| TC-CTM-45 | Preview shows variable placeholders (not resolved values) | TC-CTM-43 | Inspect rendered HTML | `{{learner_name}}` etc. visible as literal text | edge |
| TC-CTM-46 | Preview button is disabled when certificate = None | Training with `template_id = null` | Observe eye icon | Button disabled | edge |
