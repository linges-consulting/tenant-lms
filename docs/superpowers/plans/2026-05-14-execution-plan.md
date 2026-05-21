# Training Execution (Video Progress, Viewer Fixes, Completion Flow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the learner training viewer so that: (1) ReactPlayer is correctly wired with `onProgress`/`onEnded`/`onPause` and actually calls `POST /progress/video`; (2) video completion mode (`must_watch_full` / `can_continue`) controls the "Mark Complete" button; (3) flat-structure trainings render their chapters in the sidebar; (4) rich text chapters are styled with Tailwind Typography `prose` class; (5) the redundant explicit training-completion API call is removed.

**Architecture:** All work is in the frontend `TrainingViewer.tsx` file plus a one-line fix to the progress API call. The backend `POST /progress/video` endpoint already exists and is correct — the frontend just never called it. No DB changes. No backend schema changes.

**Prerequisite:** Subsystem 1 (Creation) must be complete — specifically `completion_mode` must be present on the `Chapter` type in `trainings.ts`.

**Tech Stack:** React + TypeScript, ReactPlayer library (`react-player`), Tailwind CSS + `@tailwindcss/typography` plugin, lucide-react.

**Run lint:** `cd app/frontend && npm run lint`

---

## File Map

**Frontend — changed:**
- `app/frontend/src/pages/TrainingViewer.tsx` — all viewer fixes
- `app/frontend/tailwind.config.js` — add typography plugin (if not already present)
- `app/frontend/package.json` — add `@tailwindcss/typography` if missing
- `app/frontend/src/api/trainings.ts` — add `updateVideoProgress` helper

**No backend changes needed.**

---

## Task 1: Add `@tailwindcss/typography` for rich text rendering

**Files:**
- Modify: `app/frontend/package.json`
- Modify: `app/frontend/tailwind.config.js` (or `tailwind.config.ts`)

- [ ] **Step 1: Check if plugin is installed**

```bash
cd app/frontend && cat package.json | grep typography
```

If `@tailwindcss/typography` appears, skip Step 2.

- [ ] **Step 2: Install the package (if missing)**

```bash
cd app/frontend && npm install @tailwindcss/typography
```

Expected: package added to `node_modules`, `package.json` updated.

- [ ] **Step 3: Register plugin in Tailwind config**

Open `app/frontend/tailwind.config.js` (or `.ts`). Add the plugin:

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  // ... existing config ...
  plugins: [
    require('@tailwindcss/typography'),
    // ... any existing plugins ...
  ],
}
```

- [ ] **Step 4: Verify build succeeds**

```bash
cd app/frontend && npm run build 2>&1 | tail -5
```

Expected: build completes without errors.

- [ ] **Step 5: Commit**

```bash
git add app/frontend/package.json app/frontend/package-lock.json app/frontend/tailwind.config.js
git commit -m "feat: add @tailwindcss/typography for rich text prose styling"
```

---

## Task 2: Fix ReactPlayer ref typing and event wiring

**Files:**
- Modify: `app/frontend/src/pages/TrainingViewer.tsx`
- Modify: `app/frontend/src/api/trainings.ts`

**Problem:** `playerRef` is typed as `useRef<HTMLVideoElement>(null)` — ReactPlayer is not an HTML video element. `handleVideoProgress` uses `React.SyntheticEvent<HTMLVideoElement>` (native DOM event) but ReactPlayer calls `onProgress` with `{ played: number, playedSeconds: number, loaded: number, loadedSeconds: number }`. Milestones are tracked locally but never sent to the backend.

- [ ] **Step 1: Fix the ref type**

Find:
```tsx
const playerRef = useRef<HTMLVideoElement>(null);
```

Replace with:
```tsx
const playerRef = useRef<ReactPlayer>(null);
```

`ReactPlayer` is already imported at line 3.

- [ ] **Step 2: Replace `handleVideoProgress` with correct ReactPlayer signature**

Find (around line 106):
```tsx
const handleVideoProgress = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    ...
}, []);
```

Replace with:
```tsx
const handleVideoProgress = useCallback(
    ({ playedSeconds, played }: { playedSeconds: number; played: number }) => {
        if (!id || !activeChapter) return;
        const pct = played * 100;

        const newMilestones = {
            milestone_25: pct >= 25 && !milestonesReported.current.has(25),
            milestone_50: pct >= 50 && !milestonesReported.current.has(50),
            milestone_75: pct >= 75 && !milestonesReported.current.has(75),
        };

        if (newMilestones.milestone_25) milestonesReported.current.add(25);
        if (newMilestones.milestone_50) milestonesReported.current.add(50);
        if (newMilestones.milestone_75) milestonesReported.current.add(75);

        if (Object.values(newMilestones).some(Boolean)) {
            trainingsApi.updateVideoProgress({
                training_id: id,
                chapter_id: activeChapter.id,
                position_seconds: Math.floor(playedSeconds),
                ...newMilestones,
                milestone_100: false,
                video_ended: false,
            }).catch(() => {/* best-effort */});
        }
    },
    [id, activeChapter]
);
```

- [ ] **Step 3: Add `handleVideoEnded` callback**

Add `const [videoWatched, setVideoWatched] = useState(false);` near the other state declarations.

Add after `handleVideoProgress`:

```tsx
const handleVideoEnded = useCallback(() => {
    if (!id || !activeChapter) return;
    milestonesReported.current.add(100);
    setVideoWatched(true);
    trainingsApi.updateVideoProgress({
        training_id: id,
        chapter_id: activeChapter.id,
        position_seconds: 0,
        milestone_25: true,
        milestone_50: true,
        milestone_75: true,
        milestone_100: true,
        video_ended: true,
    }).catch(() => {});
}, [id, activeChapter]);
```

Reset `videoWatched` and milestones when chapter changes:
```tsx
useEffect(() => {
    setVideoWatched(false);
    milestonesReported.current = new Set();
}, [activeChapter?.id]);
```

- [ ] **Step 4: Add `handleVideoPause` for position tracking**

```tsx
const handleVideoPause = useCallback(() => {
    if (!id || !activeChapter || !playerRef.current) return;
    const playedSeconds = playerRef.current.getCurrentTime();
    trainingsApi.updateVideoProgress({
        training_id: id,
        chapter_id: activeChapter.id,
        position_seconds: Math.floor(playedSeconds),
        milestone_25: false,
        milestone_50: false,
        milestone_75: false,
        milestone_100: false,
        video_ended: false,
    }).catch(() => {});
}, [id, activeChapter]);
```

- [ ] **Step 5: Wire events onto the ReactPlayer component**

Find where `<ReactPlayer .../>` is rendered. Update props:

```tsx
<ReactPlayer
    ref={playerRef}
    url={activeChapter.video_url || activeChapter.content_data?.url}
    width="100%"
    height="100%"
    controls
    onProgress={handleVideoProgress}
    onEnded={handleVideoEnded}
    onPause={handleVideoPause}
    progressInterval={500}
    config={{ file: { attributes: { controlsList: 'nodownload' } } }}
/>
```

Remove any `onTimeUpdate` prop — that is a native DOM event and does not work with ReactPlayer.

- [ ] **Step 6: Add `updateVideoProgress` to `trainingsApi` in `trainings.ts`**

In `app/frontend/src/api/trainings.ts`, add to `trainingsApi`:

```typescript
updateVideoProgress: (data: {
    training_id: string;
    chapter_id: string;
    position_seconds: number;
    milestone_25: boolean;
    milestone_50: boolean;
    milestone_75: boolean;
    milestone_100: boolean;
    video_ended: boolean;
}) =>
    apiClient.post('/progress/video', data),
```

- [ ] **Step 7: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 8: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx app/frontend/src/api/trainings.ts
git commit -m "fix: ReactPlayer — correct ref type, onProgress/onEnded/onPause events, wire POST /progress/video"
```

---

## Task 3: Video completion mode enforcement

**Files:**
- Modify: `app/frontend/src/pages/TrainingViewer.tsx`

**Goal:** When a video chapter has `completion_mode === 'must_watch_full'`, the "Mark Complete" / "Next" button is disabled until `onEnded` fires (`videoWatched === true`). When `completion_mode === 'can_continue'`, the button is enabled immediately.

- [ ] **Step 1: Find the "Mark Complete" button in JSX**

Search for `handleCompleteChapter` or `Mark Complete` in `TrainingViewer.tsx`. The button looks like:

```tsx
<Button onClick={handleCompleteChapter} disabled={isCompleting}>
    Mark Complete
</Button>
```

- [ ] **Step 2: Add completion mode guard to the button**

Replace the button's `disabled` prop:

```tsx
{(() => {
    const isMustWatch =
        activeChapter?.content_type === 'VIDEO' &&
        activeChapter?.completion_mode === 'must_watch_full';
    const videoNotDone = isMustWatch && !videoWatched;

    return (
        <Button
            onClick={handleCompleteChapter}
            disabled={isCompleting || videoNotDone}
            title={videoNotDone ? 'Watch the full video to continue' : undefined}
        >
            {isCompleting && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            {activeChapter?.is_completed ? 'Next' : 'Mark Complete'}
        </Button>
    );
})()}
```

- [ ] **Step 3: Show a hint when the button is locked**

Directly above the button, add:

```tsx
{activeChapter?.content_type === 'VIDEO' &&
    activeChapter?.completion_mode === 'must_watch_full' &&
    !videoWatched && (
    <p className="text-xs text-muted-foreground">
        Watch the full video to unlock this button.
    </p>
)}
```

- [ ] **Step 4: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx
git commit -m "feat: disable Mark Complete button until video fully watched when completion_mode=must_watch_full"
```

---

## Task 4: Fix sidebar — render `orphan_chapters` for flat-structure trainings

**Files:**
- Modify: `app/frontend/src/pages/TrainingViewer.tsx`

**Problem:** The sidebar rendering loop only iterates over `structure.modules`. Flat-structure trainings have all chapters in `structure.orphan_chapters` with an empty `modules` array — so the sidebar appears completely empty.

- [ ] **Step 1: Find the sidebar rendering code**

Search for where `structure.modules.map` appears in the JSX sidebar section.

- [ ] **Step 2: Add orphan chapters rendering**

After the `structure.modules.map(...)` block, add:

```tsx
{structure.orphan_chapters.length > 0 && (
    <div className="space-y-1">
        {structure.modules.length > 0 && (
            <p className="px-2 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Chapters
            </p>
        )}
        {structure.orphan_chapters.map((chapter, index) => {
            const prevChapter = structure.orphan_chapters[index - 1];
            const isLocked = index > 0 && !prevChapter.is_completed;

            return (
                <button
                    key={chapter.id}
                    type="button"
                    onClick={() => { if (!isLocked) setActiveChapter(chapter); }}
                    disabled={isLocked}
                    className={cn(
                        "w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm text-left transition-colors",
                        activeChapter?.id === chapter.id
                            ? "bg-primary text-primary-foreground"
                            : "hover:bg-muted",
                        isLocked && "opacity-50 cursor-not-allowed"
                    )}
                >
                    {isLocked ? (
                        <Lock className="h-3.5 w-3.5 shrink-0" />
                    ) : chapter.is_completed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-500" />
                    ) : (
                        <div className="h-3.5 w-3.5 shrink-0 rounded-full border-2 border-current" />
                    )}
                    <span className="truncate">{chapter.title}</span>
                </button>
            );
        })}
    </div>
)}
```

`Lock` and `CheckCircle2` are already imported at the top of the file.

- [ ] **Step 3: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx
git commit -m "fix: sidebar renders orphan_chapters for flat-structure trainings"
```

---

## Task 5: Rich text chapter — Tailwind Typography `prose` styling

**Files:**
- Modify: `app/frontend/src/pages/TrainingViewer.tsx`

**Problem:** TipTap rich text content is stored as HTML strings. When rendered into the DOM the content has no visual styles — headings look like plain text, lists have no bullets. Wrapping in Tailwind Typography's `prose` class provides all heading, paragraph, and list styles automatically.

The content originates from TipTap, an internal editor — it is not user-supplied untrusted input. Standard React HTML rendering is appropriate here.

- [ ] **Step 1: Find where RICH_TEXT chapter content is rendered**

Search for `RICH_TEXT` or `rich_text` in `TrainingViewer.tsx`. The render block will contain a `div` that renders the HTML string.

- [ ] **Step 2: Add `prose` class to the wrapper**

Update the wrapper `div` for rich text content to include Tailwind Typography classes:

```tsx
className="prose prose-sm max-w-none dark:prose-invert"
```

`prose-sm` gives compact sizing. `max-w-none` removes the default max-width constraint. `dark:prose-invert` inverts colors for dark mode.

- [ ] **Step 3: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx
git commit -m "feat: rich text chapters styled with Tailwind Typography prose class"
```

---

## Task 6: Remove redundant training-completion API call

**Files:**
- Modify: `app/frontend/src/pages/TrainingViewer.tsx`

**Problem:** `handleFinishCourse` calls `trainingsApi.completeTraining(id)` which hits `POST /trainings/{id}/complete-training`. That endpoint calls `_process_training_completion` internally. But `complete_chapter` already calls `_process_training_completion` server-side — so the explicit `completeTraining` call after the last chapter is completed is redundant and causes a double-completion attempt.

**Fix:** After `handleCompleteChapter`, detect completion from the reloaded structure instead. Keep `handleFinishCourse` but have it only update UI state (read certificates, update flags) without the API call.

- [ ] **Step 1: Update `handleCompleteChapter` to detect training completion**

Find `handleCompleteChapter`. After the `loadTraining` silent reload, check if all chapters are now done:

```tsx
const handleCompleteChapter = async () => {
    if (!id || !activeChapter || isCompleting || isPreview) return;
    setIsCompleting(true);
    try {
        await trainingsApi.completeChapter(id, activeChapter.id);
        const sData = await loadTraining(id, true, true);

        if (sData) {
            const allChapters = [
                ...(sData.modules?.flatMap((m) => m.chapters) ?? []),
                ...(sData.orphan_chapters ?? []),
            ];
            const allDone =
                allChapters.length > 0 && allChapters.every((c) => c.is_completed);
            if (allDone || sData.status === 'completed') {
                const certs = await trainingsApi.getCertificates();
                const cert = certs.find((c) => c.training_id === id);
                setCertificateId(cert?.id ?? null);
                setTrainingCompleted(true);
                setIsSidebarOpen(false);
                return;
            }
        }

        // Advance to next chapter if training not yet done
        goToNextChapter(sData);
    } catch (err) {
        console.error('Failed to complete chapter', err);
        alert('Failed to mark chapter as complete. You may need to complete previous chapters first.');
    } finally {
        setIsCompleting(false);
    }
};
```

Where `goToNextChapter` is a helper that selects the next uncompleted chapter from `sData`.

- [ ] **Step 2: Add `goToNextChapter` helper**

```tsx
const goToNextChapter = (sData: TrainingStructure | null) => {
    if (!sData) return;
    const allChapters = [
        ...(sData.modules?.flatMap((m) => m.chapters) ?? []),
        ...(sData.orphan_chapters ?? []),
    ];
    const next = allChapters.find((c) => !c.is_completed);
    if (next) setActiveChapter(next);
};
```

- [ ] **Step 3: Simplify `handleFinishCourse`**

Replace `handleFinishCourse`:

```tsx
const handleFinishCourse = async () => {
    if (!id) return;
    if (isPreview) {
        setTrainingCompleted(true);
        return;
    }
    const certs = await trainingsApi.getCertificates();
    const cert = certs.find((c) => c.training_id === id);
    setCertificateId(cert?.id ?? null);
    setTrainingCompleted(true);
    setIsSidebarOpen(false);
};
```

- [ ] **Step 4: Add expired training banner**

Before the main chapter content area, add:

```tsx
{training?.status === 'expired' && (
    <div className="mb-4 flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" />
        <span>
            Access to this training has expired. Contact your manager to request an extension or reassignment.
        </span>
    </div>
)}
```

`AlertCircle` is already imported.

- [ ] **Step 5: Lint check**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.

- [ ] **Step 6: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx
git commit -m "fix: detect training completion via chapter reload; remove redundant completeTraining API call; add expired banner"
```

---

## Task 7: Final validation

- [ ] **Step 1: Start the stack**

```bash
docker compose up
```

- [ ] **Step 2: Manual smoke test checklist**

As a learner with a Published training:

**Flat-structure training:**
- [ ] Open viewer → sidebar shows chapters (not empty)
- [ ] Chapters lock sequentially — Chapter 2 disabled until Chapter 1 is complete

**Video chapter with `completion_mode = 'must_watch_full'`:**
- [ ] "Mark Complete" button is disabled on page load
- [ ] Play video to 100% → `onEnded` fires → button becomes enabled
- [ ] Browser network tab → `POST /api/v1/progress/video` called at 25%, 50%, 75%, 100%
- [ ] Pause video → `POST /api/v1/progress/video` called with current position

**Video chapter with `completion_mode = 'can_continue'`:**
- [ ] "Mark Complete" button is enabled immediately on load

**Rich text chapter:**
- [ ] Headings, bullet lists, bold text render with proper styles (not plain text)

**Completion flow:**
- [ ] Complete last chapter → training shows completion screen
- [ ] Browser network tab → only `POST /chapters/{id}/complete` fires; no extra `POST /complete-training`

**Expired training:**
- [ ] A training past its due date shows the "Access has expired" banner

- [ ] **Step 3: Final lint**

```bash
cd app/frontend && npm run lint
```

Expected: zero errors.
