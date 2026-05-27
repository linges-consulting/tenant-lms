# Content Authoring Test Cases

Tests covering Video, Rich Text, and PDF lesson authoring. See `03-quiz-engine.md` and `04-scorm.md` for those lesson types.

---

## General Chapter/Lesson Rules

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CON-01 | Add standalone chapter to training | Any draft training | Add a chapter directly under training | 201 — chapter created | happy |
| TC-CON-02 | Add module to any training | Any draft training | Add a module via API | 201 — module created regardless of `structure_type` | happy |
| TC-CON-03 | Add module to training that already has standalone chapters | Draft training with existing chapters | Add a module | 201 — module created; training can mix modules and standalone chapters | happy |
| TC-CON-04 | Add chapter to module | Training with a module | Add chapter under the module | 201 — chapter created | happy |
| TC-CON-05 | Lesson sequence order respected on retrieval | Chapter with 3 lessons | Retrieve chapter structure | Lessons returned in `sequence_order` | happy |
| TC-CON-06 | Reordering lessons updates sequence | Chapter with 3 lessons | Move Lesson 3 to position 1 | 200 — `sequence_order` updated, order reflected in viewer | happy |
| TC-CON-07 | Cannot add lesson to published training (must revert to draft) | Published training | Attempt to add chapter/lesson | 400 — edit rejected while published | auth |

---

## Video Lessons

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CON-08 | Add video lesson with YouTube URL | Draft training with chapter | Paste YouTube URL, save chapter | 201 — lesson stored, ReactPlayer renders correctly in viewer | happy |
| TC-CON-09 | Add video lesson with Vimeo URL | Draft training with chapter | Paste Vimeo URL, save chapter | 201 — renders in viewer | happy |
| TC-CON-10 | Add video lesson with Dailymotion URL | Draft training with chapter | Paste Dailymotion URL, save chapter | 201 — renders in viewer | happy |
| TC-CON-11 | Add video lesson with uploaded file | Draft training with chapter | Upload an mp4 file | 201 — stored in `lms_videos` volume, served via `/storage/videos/` | happy |
| TC-CON-12 | Video does not mark complete until `onEnded` fires | Training assigned to learner | Learner opens video, pauses before end, clicks away | Lesson remains incomplete | edge |
| TC-CON-13 | "Mark Complete" unavailable until video ends | Training assigned to learner | Learner opens video | Button absent or disabled before `onEnded` | edge |
| TC-CON-14 | Video marks complete immediately after `onEnded` | Training assigned to learner | Learner watches video to end | Lesson marked complete, next unlocked | happy |
| TC-CON-15 | Resume position saved on progress event | Learner mid-way through video | Learner pauses at 2:30, closes viewer | Reopening viewer resumes from ~2:30 | happy |
| TC-CON-16 | 25% milestone recorded | Learner watching video | Video plays past 25% | `milestone_25=true` in progress record | happy |
| TC-CON-17 | 50% milestone recorded | Learner watching video | Video plays past 50% | `milestone_50=true` in progress record | happy |
| TC-CON-18 | 75% milestone recorded | Learner watching video | Video plays past 75% | `milestone_75=true` in progress record | happy |
| TC-CON-19 | 100% milestone recorded on end | Learner watches to end | `onEnded` fires | `milestone_100=true`, lesson marked complete | happy |

---

## Rich Text Lessons

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CON-20 | Create rich text lesson with TipTap content | Draft training with chapter | Author content with bold, bullet lists, headings; save | 201 — HTML stored | happy |
| TC-CON-21 | Rich text renders formatted content in viewer | Training with rich text lesson assigned | Open lesson in viewer | Content displayed with formatting (not raw HTML) | happy |
| TC-CON-22 | "Mark Complete" button marks lesson complete | Learner on rich text lesson | Click Mark Complete | Lesson marked complete, next lesson unlocked | happy |
| TC-CON-23 | "Next" button on last lesson in chapter completes chapter | Training with single-lesson chapter | Click Next on last lesson | Chapter marked complete | edge |
| TC-CON-24 | Images embedded in TipTap content render correctly | Rich text lesson with embedded image | Open in viewer | Image renders inline | happy |

---

## PDF Lessons

Storage: PDFs are saved to `/mnt/images/pdfs/<tenant_id>/<training_id>/<chapter_id>.pdf` (the `lms_images` Docker volume) and served by the gateway under `/storage/pdfs/`. The viewer embeds them in an `<iframe>` so they render inline. The chapter must be created with `content_type=PDF` first; the file is then uploaded via `POST /trainings/{training_id}/chapters/{chapter_id}/upload`, which writes `content_data.url` + `content_data.original_filename` on success.

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-CON-25 | Add PDF chapter type in the editor | Draft training open in editor | Click + Chapter → select **PDF** content type | PDF panel appears with file picker, description textarea, and per-file size hint | happy |
| TC-CON-26 | Upload PDF persists URL and filename | Draft training with PDF chapter | Save chapter with a `.pdf` file attached | 200 — `content_data.url = /storage/pdfs/<tenant>/<training>/<chapter>.pdf`, `original_filename` set | happy |
| TC-CON-27 | PDF renders inline in the viewer | Learner on a PDF lesson | Open lesson in viewer | `<iframe>` loads the PDF inline at full chapter width | happy |
| TC-CON-28 | "Mark Complete" marks PDF lesson complete | Learner on PDF lesson | Click Mark Complete | Lesson complete, next unlocked | happy |
| TC-CON-29 | PDF lesson follows sequential gating | Training with PDF as lesson 2 | Learner tries to access PDF before completing lesson 1 | Lesson 2 locked | happy |
| TC-CON-30 | Non-PDF MIME rejected by upload endpoint | Draft training with PDF chapter | Upload a `.exe` / `.docx` to the chapter | `400 — Invalid file type. Only PDF files are accepted for PDF chapters.` | edge |
| TC-CON-31 | VIDEO chapter rejects PDF upload | Draft training with VIDEO chapter | Upload a `.pdf` to the chapter | `400 — Only SCORM and PDF chapters accept file uploads on this endpoint.` | edge |
| TC-CON-32 | Editor blocks save without a PDF file | New PDF chapter (not editing existing) | Click Save Chapter without choosing a file | Toast: "Please choose a PDF file to upload." — no API call fires | edge |
| TC-CON-33 | Editing an existing PDF chapter without re-uploading | Existing PDF chapter | Open editor, change title/description, save without picking a new file | Chapter title/description update; URL and filename unchanged | happy |
| TC-CON-34 | PDF from another tenant is inaccessible | Two tenants with PDF lessons | Tenant B learner requests Tenant A's PDF URL | 403 — gateway `auth_request` rejects | isolation |
