# Certificate Template Management Test Cases

Covers SysAdmin create/edit/delete/activate templates. For certificate issuance on training completion see `trainings/09-certificates.md`.

---

## Create Template

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-01 | SysAdmin can create a certificate template | SysAdmin | POST `/certificates/templates` with `name` + `html_content` | 201 — template created | happy |
| TC-CTM-02 | Template created as active by default | TC-CTM-01 | Inspect response | `is_active: true` | happy |
| TC-CTM-03 | SysAdmin can create template and assign it to a specific tenant | SysAdmin | POST with `target_tenant_id` | 201 — template assigned to that tenant | happy |
| TC-CTM-04 | Template name is required | SysAdmin | Omit `name` | 422 | edge |
| TC-CTM-05 | HTML content is required | SysAdmin | Omit `html_content` | 422 | edge |
| TC-CTM-06 | Non-SysAdmin cannot create templates | Manager or Training Creator | POST templates | 403 | auth |

---

## Update Template

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-07 | SysAdmin can update template name | Existing template | PUT `/certificates/templates/{id}` with new `name` | 200 — name updated | happy |
| TC-CTM-08 | SysAdmin can update HTML content | Existing template | PUT with new `html_content` | 200 — content updated | happy |
| TC-CTM-09 | Partial update — only provided fields changed | SysAdmin | PUT with only `name` | 200 — only name changed, HTML unchanged | edge |
| TC-CTM-10 | Non-SysAdmin cannot update templates | Manager | PUT `/certificates/templates/{id}` | 403 | auth |
| TC-CTM-11 | Updating a template in use updates PDF output for future completions | Template used by published training | Update HTML | Next certificate generated uses new HTML | edge |

---

## Activate / Deactivate Template

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-12 | SysAdmin can deactivate a template | Active template | PUT with `is_active: false` | 200 — `is_active: false` | happy |
| TC-CTM-13 | Deactivated template does not appear in tenant's training certificate dropdown | TC-CTM-12 | Training Creator opens certificate dropdown | Deactivated template not listed | edge |
| TC-CTM-14 | SysAdmin can reactivate a deactivated template | Inactive template | PUT with `is_active: true` | 200 — `is_active: true` | happy |
| TC-CTM-15 | Reactivated template reappears in tenant's dropdown | TC-CTM-14 | Training Creator opens dropdown | Template listed again | edge |
| TC-CTM-16 | Default template cannot be deactivated (protected) | Default template (`is_default: true`) | Attempt deactivate | Blocked or warning — must remain active | edge |
| TC-CTM-17 | Template in use by a training cannot be deleted (`is_in_use: true`) | Template linked to a training | Attempt delete | Blocked — "template is in use" | edge |

---

## Delete Template

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CTM-18 | SysAdmin can delete an unused, non-default template | Template with `is_in_use: false`, `is_default: false` | DELETE `/certificates/templates/{id}` | 200 — deleted | happy |
| TC-CTM-19 | Deleting default template is blocked | Template with `is_default: true` | DELETE | 400 — cannot delete default template | edge |
| TC-CTM-20 | Deleting template in use by a training is blocked | Template with `is_in_use: true` | DELETE | 400 — template in use | edge |
| TC-CTM-21 | Non-SysAdmin cannot delete templates | Manager | DELETE `/certificates/templates/{id}` | 403 | auth |
