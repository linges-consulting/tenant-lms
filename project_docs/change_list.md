# Change / Bug List

Add new items under **Open**. Move to **Completed** when done.

---

## Open


## Completed

| Area | Change | Notes | Commit |
|------|--------|-------|--------|
| Training Banner | Banner upload returned 500 — endpoint returned ORM `Training` with lazy `collaborators` relationship, triggering `MissingGreenlet` during Pydantic serialization | Eager-load `collaborators` via `selectinload`; re-fetch after commit; surface storage error in detail | — |
| Rich Text Editor | TipTap `Duplicate extension names found: ['link', 'underline']` warning in console | `StarterKit` v3 now bundles Link & Underline; disabled them in StarterKit config so the explicit extensions are the only instances | — |
| Quiz Editor | Editor only supported a single multi-choice question shape; viewer can render 5 types | Added per-question type picker for Multiple Choice / Multiple Select / True-False / Matching / Ordering. Type-aware option editors: true-false locks True/False options; matching shows left/right lists + pair selector; ordering uses up/down arrows and saves the option order as the correct answer | — |
| Manage Assignments | New Assignment tab — Groups column had no way to see who's inside a group before assigning it | Added expand chevron per group that loads & shows member list inline, reusing the existing `toggleGroupExpand` + `groupMembers` state from the Active tab | — |
| Training Player | Progress was not updating after completing a chapter for up to 5 minutes — root cause: `invalidate_cache("training_detail", training_id)` and `("training_structure", training_id)` passed `training_id` where the helper expects `tenant_id`, so cache invalidation silently missed every key and stale data was served until TTL | Fixed 9 call sites across `trainings.py` (update, mark-ready, send-to-draft, complete-chapter, submit-quiz, complete-training, unpublish, banner upload, reassign) to pass `tenant_id` | — |
| Training Player | Sidebar showed chapter-level completion but no module-level indicator | Module accordion header now shows a check icon when all chapters in the module are complete, plus `{done}/{total}` count badge | — |
| Profile Page | Fixed margin — removed `container` wrapper; uses standard `space-y-6 max-w-6xl` | — | 4ac5403 |
| Profile Page | URL now username-only — route `:id` → `:username`; UUID fallback removed from ProfilePage; all nav links prefer username | — | 4ac5403 |
| Profile Page | Backend enforces 403 for plain employees viewing others; only managers/creators can view other profiles within shared tenant | `get_user_profile_by_username` tightened with privilege check | 4ac5403 |
| Notifications | Bell unread count now updates immediately after mark-as-read / mark-all / delete | `NotificationPage` invalidates React Query `unreadCount` cache via `qc.invalidateQueries` | 4ac5403 |
| All Tables | Action column moved to first; dots unified to vertical (MoreVertical) | AdminCertificateTemplates, AdminTenants, UserTable, ManagerTrainings, ManagerPublishTrainings; old trailing action cells removed | a58ee71 |
| Certificate Template | Fixed PDF preview returning 500 error | WeasyPrint downgraded from 62.3 → 61.2; broken `transform` method in 62.3 `pdf/stream.py` | — |
| Admin → Sidebar | No logo or avatar shown when user is a SysAdmin | `BrandingHeader` accepts `isAdmin` prop; skips logo block when true | — |
| Sidebar | User dropdown popup opens above avatar, not to the right | `DropdownMenuContent` `side="top"` on the bottom `UserDropdown` | — |
| Admin → Dashboard | Service health wired up with real status and color coding | `checkHealth()` calls per service; green = Operational, red = Degraded, muted = Checking | — |
| Nginx Gateway | Health proxy routes added for all three services | `/api/v1/health/{auth,core,notification}` → each service's `/health` endpoint | — |
| Notifications | Fixed crash — bell and context unwrap paginated response correctly | Backend returns `{items, total}` envelope; frontend now reads `.items` and `.unread_count` | — |
| Admin → Users | `getRoleLabels` console warning eliminated | Row rendering passes row-specific `membership.tenant_id` instead of table-level `activeTenantId` | — |
| Admin → Bulk Import | Tenant field changed from free-text UUID to dropdown | Uses existing tenant list API | — |
| Admin → Users | Role modal no longer asks to pick a tenant — tenant is implied from the row | Tenant name shown as label in modal | — |
| Admin → Users | Multi-tenant user now shows correct role badge per tenant row | Was using table-level filter tenant instead of row tenant | — |
| Studio nav | "My Trainings" renamed to "Manage Trainings" | Label only — route unchanged | — |
| Learning nav | Added "My Trainings" page for learners | Route: `/dashboard/my-trainings` | — |
| Learning → Dashboard | Card design updated to match Management → Dashboard style | Large number, muted label, icon | — |
| Management → Reports | Card design updated to match Management → Dashboard style | Large number, muted label, icon | — |
| Training creation | Fixed "Create Training" button returning an error | Missing required `category` field; defaults to `general`, editable after creation | — |
| Notifications | Fixed 502 Bad Gateway on all notification endpoints | Notification service was crashing (`jinja2` missing); DB migrations also applied | — |
| Notifications | Polling interval changed from 30 s to 5 min | Configurable via `VITE_NOTIFICATION_POLL_MS` in `app/frontend/.env` | — |
| Certificate Templates | Default template auto-provisioned on new tenant creation | Wired up in tenant creation endpoint via `provision_default_certificate` | — |
| Seed Scripts | Unified `scripts/seed.py` with `--mode admin-only` and `--mode mock` | Config-driven via `scripts/seed_config.json`; old per-service scripts superseded | — |
| GitHub Actions | Added `seed.yml` manual workflow with mode dropdown + CONFIRM guard | `deploy.yml` updated to run admin-only seed on every deploy (idempotent) | — |
| Deployment Docs | `project_docs/deployment.md` rewritten to reflect current workflows | Covers seed script, both GH Actions workflows, secrets, runbook | — |
| Learning → Dashboard | "Continue Learning" strip with top 3 in-progress trainings, progress bars, Continue button | Dummy data — wire up to real API when backend endpoint is ready | — |
| Management → Reports | Per-training breakdown table (Assigned / Completed / In Progress / Overdue / %) | Dummy data — wire up to real API when backend endpoint is ready | — |
| Tenant Creation | Duplicate tenant name returns 409 | Check added before insert in `create_tenant` | — |
| Certificate Template | Duplicate template name per tenant returns 409 | Check added in `create_template` | — |
| Certificate Template | Deactivate/Delete blocked when last active or in use | Guards added in `update_template` and `delete_template`; icon added to toggle menu item | — |
| Certificate Template | Preview PDF shows loading spinner and error toast | Wrapped in try/catch with loading state in both list and editor pages | — |
| Certificate Templates | Activate/Deactivate action now shows ToggleLeft/ToggleRight icon | Lucide icons added to dropdown menu items in list page | — |
| Certificate Templates | Default and in-use templates blocked from deactivate/delete | Backend 400 guard + frontend disabled states driven by `is_default`/`is_in_use` flags; error toast via `getApiError` | — |
| All Pages | Common `PageLoader` spinner used across all pages during data fetch | `src/components/ui/PageLoader.tsx` created; replaces all inline spinners and skeleton placeholders | `b1fc2b7` |
| Certificate Templates | PDF preview shows loading spinner while generating | Loading state + error toast added to both list and editor pages | `b1fc2b7` |
| Admin → Sidebar | Service health moved from dashboard cards to sidebar dots | Colored dots (green/red/muted) above profile; click opens detail modal; polls every 60 s | `b1fc2b7` |
| Admin → Dashboard | Recent Tenants card split to half-width; Published Trainings card added alongside | Two-column grid layout with progress bar per tenant | `b1fc2b7` |
| Dark Mode | Card/popover surfaces were pure black (same as background) | `--card` and `--popover` raised to `220 40% 9%` in dark mode | `0bd1827` |
| Admin → Sidebar | Health dots placed vertically beside profile avatar (compact button) | Three stacked dots open detail modal on click; polls every 60 s | `0bd1827` |
| Sidebar | Tenant logo area height aligned with top bar | `BrandingHeader` changed from `h-14` → `h-16` to match `AppLayout` topbar | `0bd1827` |
| Sidebar | Small margin added between each menu item | `NavSection` items wrapped in `space-y-0.5` | `0bd1827` |
| Management | Added "Publish Trainings" page for Business Managers | Route `/manage/publish`; default filter = Ready; supports all lifecycle filters | `f6ac875` |
| Training Lifecycle | Publish/Unpublish restricted to Business Managers and SysAdmins only | Removed from Training Creator dropdown; gated by `is_business_manager` in editor and studio list | `f6ac875` |
| Admin → Tenants | Tenant avatar consistency with login page | `w-10 h-10 rounded-md`, 2-char initials, logo_url support | 3c27791 |
| Course Studio | Publish flow replaced with "Mark Ready" / "Revert to Draft" | Backend `/mark-ready` endpoint wired; status badge shows Draft/Ready/Published | 3c27791 |
| Training Assignment | Assignment removed from Studio; Business Manager only via Review & Publish page | Route guard changed to `requireBusinessManager`; backend already restricted | 3c27791 |
| Sidebar | Studio renamed "Course Studio"; Publish page renamed "Review & Publish" | Clearer distinction for dual-role users | 3c27791 |
| Dark Mode | Destructive red too dark in dark mode | `--destructive` raised from `0 62.8% 30.6%` → `0 80% 60%` | 3c27791 |
| Profile Page | Managers could not view other users' profiles | `canViewProfile` now uses `activeTenantId` to find correct membership | 3c27791 |
| Invite Employee Modal | Submit enabled despite existing user already in org | Button disabled + warning shown when `isAlreadyInCurrentTenant` | 3c27791 |
| Invite Employee Modal | Fields stay populated after changing to a new email | `fullName`, `isManager`, `isCreator` reset when existingUser lookup returns nothing | 3c27791 |
| Notifications | Page margin/header inconsistent with other pages | Switched to `space-y-6 max-w-4xl` + standard page title with icon | 3c27791 |
| All Pages | Inconsistent page titles and spacing across /manage, /dashboard, /settings, /admin, /certificates, /reports, /notifications | Unified to `text-3xl font-bold tracking-tight`, icon block, `space-y-6`; admin pages use muted icons | 3c27791 |
| Dashboard | Unified /dashboard and /manage into single role-aware dashboard | `UnifiedDashboard` shows learner stats always + creator/manager sections based on role; both index routes use same component | 9e205f4 |
| Admin → Dashboard | Admin icon changed from muted to violet accent | `bg-violet-500/10` + `text-violet-600 dark:text-violet-400` distinguishes admin context from tenant primary color | 9e205f4 |
| Course Studio | manage/courses now scoped to creator-owned or collaborating trainings | Backend `GET /trainings/manager` filters by `created_by_id` or collaborator for non-manager roles; collaborators see Edit only (no Mark Ready, no archive) | 9e205f4 |
| Course Studio | Action column: removed standalone edit icon, kept only dropdown dots | Edit icon removed; dropdown hidden entirely when no actions available for that row | 9e205f4 |
| Training Editor | Fixed layout inconsistency on /manage/courses/:id | Replaced `flex min-h-screen` outer wrapper with standard `space-y-6` page layout | 9e205f4 |
| Training Editor | Certificate template fetch shows error toast; filters inactive templates | `toast.error` on catch; `is_active` filter applied client-side so only selectable templates appear | 9e205f4 |
| Sidebar | Learning section "My Trainings" renamed to "Dashboard" and now uses LayoutDashboard icon | Consistent label since /dashboard now shows unified dashboard, not just course list | 9e205f4 |
| Auth Pages | Login redesigned with split-screen photo layout; forgot-password matches; invite-only messaging; Privacy Policy and Terms of Service pages with legal verbiage | Photo left panel, gradient overlay, GraduationCap logo | 1aeefa2 |
| App Naming | "CustomLMS" renamed to "Enterprise Learning Platform" everywhere; stats block removed from login left panel | index.html, useDynamicTitle.ts, all auth pages | 43fcf15 |
| Register Page | Redesigned to match forgot-password split-screen photo layout; step-aware left panel; GraduationCap logo | Unsplash photo, gradient overlay, back navigation between steps | eac674b |
| Browser Tab Title | Page title updated from "CPVM Training Portal" to "Enterprise Learning Platform" | index.html `<title>` + all useDynamicTitle.ts references updated | eac674b |
| All Pages | Unified page title icon style — all icons now inside `w-10 h-10 rounded-xl bg-*/10` containers; admin=violet, tenant=primary | 12 pages updated; text-2xl → text-3xl on 4 pages | 2df8f56 |
| Profile Page | Removed back button; replaced with standard User icon + user's full name as title | Consistent with all other page headers | 2df8f56 |
| Manager → Review & Publish | "Preview training" button now navigates to TrainingViewer (`/manage/learn/:id`) instead of editor | Editor route requires Training Creator role — caused redirect to dashboard for pure Business Managers | 2df8f56 |
| Training Editor | Margin/layout now consistent with other pages | Removed inner `max-w-4xl mx-auto` wrapper; content inherits `max-w-7xl` from AppLayout | — |
| Training Editor | Certificate toggle auto-selects default template; removed None option from dropdown | On enable: picks `is_default` template first, falls back to first active template | — |
| Training Editor | Save blocked if training has 0 chapters | Validation added to `handleSaveMetadata`; error shown in publish-errors modal | — |
| Training Editor | Save blocked and toasts error if title already exists in tenant | 409 from backend update endpoint caught; toast shown | — |
| Course Studio | "Create Training" no longer immediately creates DB record on click | New dialog collects title, description, category, structure type before saving | — |
| Course Studio | Closing new-training dialog with content shows discard confirmation | AlertDialog prompts before discarding typed content | — |
| Course Studio | New training dialog opens with blank title | Dialog resets all fields (including title) on open | — |
| Course Studio | Duplicate training name returns 409 on create and update | Backend checks tenant-scoped title uniqueness in both endpoints | — |
| Course Studio | New training dialog — category and structure type removed | Defaults to `general` / `flat`; category now editable in the editor settings | — |
| Training Editor | Publish button replaced with Mark Ready / Revert to Draft | Publish action belongs on Review & Publish page only; `handlePublish` / `handleUnpublish` removed from editor | — |
| Training Editor | Save button moved to header alongside History/Preview/Mark Ready | Removed from inside the settings card; color is `secondary` (gray) to contrast green Mark Ready | — |
| Training Editor | Settings card 4-column layout (Title, Description, Category, Certificate Template) | `grid-cols-2 lg:grid-cols-4`; category select added; Certificate column shows template picker inline | — |
| Training Archive | Archive restricted to managers; allows Ready OR Published trainings | Backend state guard updated; frontend dropdown shows Archive only when `isManager && (is_ready OR is_published)` | — |
| Training Archive | Archived trainings show "Archived" amber badge in Course Studio list | Badge added before Published/Ready/Draft in the status cell | — |
| Training Delete | Delete option added for creators (draft, own training only) | Backend guards: owner only + draft-only; frontend shows Delete only when `isCreator && !isManager && isDraft && isOwner` | — |
| Training Delete | Revert to Draft in list now calls correct `send-to-draft` endpoint | Previously called `markReady` by mistake; `handleSendToDraft` added | — |
| Course Studio | Delete action not visible for dual-role (creator + manager) users on own draft training | Removed `!isManager` from `canDeleteAction`; condition now: `isCreator && !isCollaboratorOnly && isOwner && isDraft` | — |
| Course Studio | Mark Ready error showed generic message instead of backend detail | `handleMarkReady` now surfaces `error.response.data.detail` in the toast (e.g. "Training must have a description") | — |
| Auth / Token | Expired JWT returned 403 from auth service, blocking frontend refresh logic | Auth service `get_current_user` now returns 401 for JWT decode failure; core service propagates the original status code so 401 triggers the frontend refresh and 403 stays for real permission denials | — |
| Course Studio / Mark Ready | Mark Ready 400 errors showed generic message — no backend detail surfaced | Fixed wrong `ApiError` property path: `error?.response?.data?.detail` → `error?.message`; same fix applied to status checks in `handleSaveMetadata` and `handleSaveNewTraining` | — |
| Training Viewer | Clicking a completed training relaunched chapter 1 instead of showing completion screen | `loadTraining` now uses `tData.status === 'completed'` (progress-based, from `getTraining`) as the authoritative check; skips chapter navigation when training is already completed | — |
| My Trainings | Status tabs replaced with pill-style filter buttons | `Tab` type renamed to `Filter`; renders `inline-flex rounded-full` buttons; active = filled primary, inactive = outlined | — |
| My Trainings | Default filter changed from "All" to "Active" (non-completed) | Default state is now `'active'` which shows assigned + in_progress trainings | — |
| My Trainings | "View Certificate" button on completed cards was never showing | `UserCertificate` schema + `/me/certificates` endpoint now return `certificate_id`; button condition changed from `cert.certificate_url` to `cert.certificate_id`; uses `certificatesApi.viewCertificatePdf` (blob URL, auth headers included) | — |
| Notifications | Training completed notification now includes "View Certificate" button | `Notification` model gains nullable `data JSON` column (migration `a1b2c3d4e5f6`); TRAINING_COMPLETED event payload includes `certificate_id`; consumer stores it in `data`; `notif_to_dict` returns `data`; `NotificationPage` renders View Certificate button when `notif.data?.certificate_id` is set | — |
| Training Viewer | Completion screen now shows chapter count, completion date, and certificate button with auth headers | `get_training` endpoint populates `completed_at` from enrollment; `Training` schema + TS interface extended with `completed_at`; viewer renders stats grid + `viewCertificatePdf` (blob URL) instead of window.open | — |
| Training Editor | "Revert to Draft" no longer shown for published trainings | Condition changed from `training.is_ready` to `training.is_ready && !training.is_published` | — |
| Training Editor | Save button disabled when title is empty or certificate template is missing | `disabled` prop extended to `!title.trim() \|\| (requiresCertificate && !templateId)`; inline error messages shown under each field | — |
| Notifications | 500 on `/api/v1/notifications` | Root cause: `data JSON` column added to Notification model requires migration — **run `docker compose exec notification-service alembic upgrade head`** before starting the service | — |
| Training Editor | Video URL validated before chapter save | `isValidUrl()` helper added; `handleSaveChapter` returns early on invalid URL; inline error shown under the video URL input | — |
| Training Editor | Mark Ready / Revert to Draft now show success toasts | `toast.success('Training marked as ready.')` and `toast.success('Reverted to draft.')` added | — |
| Training Editor | Description field moved to its own full-width row as a `<Textarea>` | Settings card now: 3-col grid (Title, Category, Certificate) on row 1; Description `<Textarea>` on row 2 | — |
| Group Assignment | Users in a group with a training assigned now see it in My Trainings | `assignment_sub` in `read_trainings` now includes `tenant_id` filter and correctly matches group memberships | — |
| Review & Publish → Assignments | Active sidebar item was "Course Studio" instead of "Review & Publish" | Assignment route changed from `/manage/courses/:id/assignments` to `/manage/publish/:id/assignments`; back button navigates to `/manage/publish`; "Back to Trainings" label updated to "Back to Review & Publish" | — |
| Training Editor | Save error modal said "Cannot Publish" — action is Save, not Publish | Modal title changed to "Cannot Save"; description updated to "before saving" | — |
| Training Editor | No option to delete a module | Delete button (trash icon) added to module header row; confirmation dialog added; `deleteModule` API method added; `handleConfirmDeleteModule` handler added | — |
| Training Editor | Preview opened in new tab with no back navigation | Preview button changed from `window.open(..., '_blank')` to `navigate('/manage/learn/:id?preview=true')`; `canPreview` extended to include Training Creators; "Back" button added to both preview banners | — |
| My Trainings | Group-assigned training showed "1 Available" in stats card but no cards in the list | Root cause: backend returns `status: "not_started"` but frontend filtered for `status === 'assigned'`; fixed across `Training` interface, `MyTrainings.tsx` filter and badge logic | — |
| Training Progress | Progress always showed 0% for all users; certificate_id missing after completion | `read_training` cache was shared across users (`include_user_id=False`); fixed with `include_user_id=True`; added `certificate_id` from enrollment to response; status `"assigned"` → `"not_started"` | 86453f2 |
| Certificate Preview | Fixed width `800px` overflowed modal on smaller screens | Changed to `w-full max-w-[760px]` with `aspect-ratio: 4/3` so it scales within the container | 86453f2 |
| My Trainings | "Available: 1 / Completed: 1" after completion — same training counted twice | "Available" renamed to "Active"; value changed to `activeTrainings.length` (not-started + in-progress only) — matches the "Active" filter button | 86453f2 |
| My Trainings | Stat cards redundant alongside filter pills showing the same info | Stat cards removed entirely; filter pills updated to: Active \| Completed \| Expired \| All | — |
| Dashboard | "Draft Trainings" stat shown in manager view; no role differentiation | Removed Draft Trainings from manager view; role-based stat strips: Manager Only (Published + Total Employees), Creator Only (Published + Ready + Drafts), Manager+Creator (Published + Ready + Drafts + Total Employees), Learner Only (learner stats only) | — |
| SCORM Upload | SCORM ZIP upload silently failed — entry point never found; files stored on ephemeral container filesystem | (1) Fixed namespace-agnostic manifest parsing (SCORM 1.2 uses `imsproject.org` namespace, not `imsglobal.org`); (2) Changed storage path from `/mnt/media/` (unmounted) to `/mnt/scorm/` (persistent volume); (3) Fixed URL prefix from `/media/` to `/storage/scorm/` | — |
| SCORM Player | No SCORM player in TrainingViewer — content_type SCORM fell through to text render | (1) Injected SCORM 1.2 `window.API` when SCORM chapter is active; (2) Added iframe loading `content_data.index_url`; (3) Auto-completes on `LMSFinish`/`lesson_status=passed`; (4) "Mark Complete" fallback button for SCOs that don't call the API | — |
| SCORM Nginx | `auth_request` on `/storage/scorm/` blocked all sub-resource loads (CSS/JS/images) from the iframe | Removed `auth_request`; added `X-Frame-Options: SAMEORIGIN` and `X-Content-Type-Options: nosniff` | — |
| Training Banner | Trainings had no visual identity — cards showed generic gradient | Added optional banner image to training: 2×2 preset grid (Ocean/Sunset/Forest/Ember gradients) + custom image upload. Stored in `thumbnail` field (`preset:*` or `/storage/banners/` URL). Backend: `POST /trainings/{id}/banner` saves to `lms_images` volume, served via public `/storage/banners/` nginx route. Cards in My Trainings show banner/preset/fallback gradient | — |
