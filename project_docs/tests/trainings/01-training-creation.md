# Training Creation Test Cases

Tests covering training settings, structure type, banner image, certificate selection, and creation validation.

---

## Settings & Validation

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRE-01 | Create training successfully | Logged in as Training Creator | Fill title, select category, click Create | 201 — training created in Draft state, `is_published=false` | happy |
| TC-CRE-02 | Create training and add a module | Training in Draft state | Fill title, select category, create training, then add a module via API | 201 for training creation, 201 for module creation — modules can be added to any training | happy |
| TC-CRE-03 | Title is required | Logged in as Training Creator | Leave title blank, fill all other fields, click Create | Blocked — inline error "Title is required" | edge |
| TC-CRE-04 | Category is required | Logged in as Training Creator | Fill title, leave category unset, click Create | 422 — creation rejected | edge |
| TC-CRE-05 | Description is optional | Logged in as Training Creator | Fill title + category, leave description blank, click Create | 201 — training created without description | edge |
| TC-CRE-06 | Modules can be added to any training | Any draft training | Call API to add a module to a training | 201 — module created regardless of `structure_type` | happy |
| TC-CRE-07 | Non-Training-Creator cannot create training | Logged in as base Employee | Call `POST /trainings` | 403 | auth |
| TC-CRE-08 | Newly created training is in Draft state | Any Training Creator | Create training | `is_ready=false`, `is_published=false`, `is_archived=false` | happy |

---

## Banner Image

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRE-09 | Banner auto-selected on new training load | Training has no saved `thumbnail` | Open editor for new training | A random preset (ocean/sunset/forest/ember) is pre-selected | happy |
| TC-CRE-10 | Preset banner persists on save | Any training | Select a preset (e.g. Forest), click Save | `thumbnail = "preset:forest"` stored; card shows gradient on training list | happy |
| TC-CRE-11 | Changing preset selection updates UI immediately | Any training | Select Ocean, then switch to Sunset | Sunset gradient shows, checkmark moves | happy |
| TC-CRE-12 | Upload custom banner — jpg | Any training | Click "Upload image", select valid jpg | Image uploaded, preview shown in editor, stored at `/storage/banners/...` | happy |
| TC-CRE-13 | Upload custom banner — png | Any training | Click "Upload image", select valid png | Image uploaded successfully | happy |
| TC-CRE-14 | Upload custom banner — webp | Any training | Click "Upload image", select valid webp | Image uploaded successfully | happy |
| TC-CRE-15 | Upload invalid file type as banner | Any training | Click "Upload image", select a PDF or MP4 | Upload rejected — toast error, banner unchanged | edge |
| TC-CRE-16 | Custom banner shows on training card | Training with uploaded banner | Open training list | Custom image renders on the card thumbnail | happy |
| TC-CRE-17 | Preset banner shows on training card | Training with `preset:ocean` | Open training list | Ocean gradient renders on the card thumbnail | happy |
| TC-CRE-18 | Remove custom banner → reverts to upload zone (no blank state) | Training with custom banner | Hover image, click Remove | Upload zone shown; a preset should be manually selected or auto-selected | edge |
| TC-CRE-19 | Banner validation — saving with no banner selected is rejected | Edge: user somehow clears banner without selecting preset | Attempt to save with `thumbnail=null` | Validation error — banner is required | edge |

---

## Certificate Selection

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CRE-20 | Certificate dropdown defaults to "None" on new training | New training editor open | Observe certificate dropdown | "None" selected by default | happy |
| TC-CRE-21 | Select "None" — training saved and marked ready without error | Training with no certificate | Select None, save, mark ready | Succeeds — no certificate template required | happy |
| TC-CRE-22 | Select a template — saved and appears in dropdown | Templates exist for tenant | Select a template from dropdown, save | Template stored in `template_id`, `requires_certificate=true` | happy |
| TC-CRE-23 | Switch from template to None — certificate requirement cleared | Training had a template | Change dropdown to None, save | `requires_certificate=false`, `template_id=null` | happy |
| TC-CRE-24 | Preview button disabled when None selected | Certificate dropdown = None | Observe preview button (eye icon) | Button disabled | edge |
| TC-CRE-25 | Preview button shows certificate HTML when template selected | Template selected | Click preview button | Modal opens with rendered certificate HTML at correct scale | happy |
| TC-CRE-26 | Certificate preview scales to fit modal width with no scroll | Template selected | Click preview | Certificate fits width, no vertical scroll | edge |
| TC-CRE-27 | Only templates assigned to this tenant appear in dropdown | Tenant has 2 of 5 global templates | Open dropdown | Only 2 tenant-assigned templates shown | isolation |
