# Frontend Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install TanStack React Query and React Player; refactor data fetching; fix the sidebar architecture (unified 3-section, icon-only collapse, mobile Sheet drawer); eliminate all hardcoded colors and `any` types; add missing pages (Password Reset, Employee Dashboard, Manager Reports, Bulk CSV Import, PDF/SCORM/quiz viewers); implement heartbeat; fix route guards.

**Architecture:** Data fetching moves from `useState+useEffect` to TanStack React Query `useQuery`/`useMutation` hooks in a `src/queries/` directory (one file per resource). The sidebar is rewritten as a single component that renders all three sections (Learning, Management, Studio) and shows/hides each based on the user's roles. New pages are thin route components that compose existing query hooks and UI primitives. All `cn()` violations in pages are fixed file-by-file. Hardcoded hex/concrete colors are replaced with CSS variable classes globally.

**Tech Stack:** React 18, Vite, TanStack React Query v5, React Player, shadcn/ui, Tailwind CSS, TypeScript, lucide-react

**All commands run from `app/frontend/`.**
**After every change: `npm run lint` must pass before committing.**

---

## File Map

| File | Action |
|---|---|
| `package.json` | Modify — add @tanstack/react-query, react-player |
| `src/main.tsx` | Modify — wrap app in QueryClientProvider |
| `src/queries/trainings.ts` | Create — useQuery/useMutation hooks for trainings |
| `src/queries/users.ts` | Create — hooks for users |
| `src/queries/notifications.ts` | Create — hooks for notifications |
| `src/queries/certificates.ts` | Create — hooks for certificates |
| `src/queries/dashboards.ts` | Create — hooks for dashboard endpoints |
| `src/components/layout/Sidebar.tsx` | Rewrite — unified 3-section, icon-only collapse, typed props |
| `src/components/layout/MobileHeader.tsx` | Modify — add hamburger button, fix typed props |
| `src/components/layout/AppLayout.tsx` | Modify — replace hardcoded hex fallbacks |
| `src/layouts/AppLayout.tsx` | Modify — add Sheet sidebar for mobile |
| `src/pages/AuthPasswordReset.tsx` | Create — forgot-password + reset-password pages |
| `src/pages/LearnerDashboard.tsx` | Create — Employee dashboard with continue, upcoming, recent |
| `src/pages/ManagerReports.tsx` | Create — compliance reports page |
| `src/pages/AdminBulkImport.tsx` | Create — SysAdmin CSV upload page |
| `src/pages/TrainingViewer.tsx` | Modify — add React Player, PDF viewer, quiz type 3-5, heartbeat |
| `src/components/NotificationBell.tsx` | Create — bell with inline dropdown |
| `src/App.tsx` | Modify — add new routes, fix route guards, move MultiSelect/RichTextEditor out of components/ui/ |
| `src/components/MultiSelect.tsx` | Move from `components/ui/MultiSelect.tsx` |
| `src/components/RichTextEditor.tsx` | Move from `components/ui/RichTextEditor.tsx` |

---

### Task 1: Install TanStack React Query and React Player

**Files:**
- Modify: `package.json`
- Modify: `src/main.tsx`

- [ ] **Step 1: Install packages**

```bash
cd app/frontend
npm install @tanstack/react-query@5 react-player
```

- [ ] **Step 2: Wrap app in `QueryClientProvider` in `src/main.tsx`**

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.tsx';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 3: Verify lint passes**

```bash
npm run lint
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add app/frontend/package.json app/frontend/package-lock.json app/frontend/src/main.tsx
git commit -m "feat: install TanStack React Query v5 and React Player"
```

---

### Task 2: Create query hooks directory

**Files:**
- Create: `src/queries/trainings.ts`
- Create: `src/queries/notifications.ts`
- Create: `src/queries/dashboards.ts`

- [ ] **Step 1: Create `src/queries/trainings.ts`**

```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingsApi } from '../api/trainings';

export const trainingKeys = {
  all: ['trainings'] as const,
  list: (filters?: object) => [...trainingKeys.all, 'list', filters] as const,
  detail: (id: string) => [...trainingKeys.all, 'detail', id] as const,
};

export function useTrainings(filters?: { category?: string; status?: string }) {
  return useQuery({
    queryKey: trainingKeys.list(filters),
    queryFn: () => trainingsApi.list(filters),
  });
}

export function useTraining(id: string) {
  return useQuery({
    queryKey: trainingKeys.detail(id),
    queryFn: () => trainingsApi.get(id),
    enabled: !!id,
  });
}

export function usePublishTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => trainingsApi.publish(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: trainingKeys.all }),
  });
}
```

- [ ] **Step 2: Create `src/queries/notifications.ts`**

```ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../api/notifications';

export const notifKeys = {
  all: ['notifications'] as const,
  list: (page?: number) => [...notifKeys.all, 'list', page] as const,
  unreadCount: () => [...notifKeys.all, 'unread-count'] as const,
};

export function useNotifications(limit = 20, offset = 0) {
  return useQuery({
    queryKey: notifKeys.list(offset),
    queryFn: () => notificationsApi.list(limit, offset),
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: notifKeys.unreadCount(),
    queryFn: () => notificationsApi.unreadCount(),
    refetchInterval: 30_000,  // poll every 30s
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: notifKeys.all }),
  });
}
```

- [ ] **Step 3: Create `src/queries/dashboards.ts`**

```ts
import { useQuery } from '@tanstack/react-query';
import { dashboardsApi } from '../api/dashboards';

export function useManagerDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'manager'],
    queryFn: () => dashboardsApi.manager(),
  });
}

export function useCreatorDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'creator'],
    queryFn: () => dashboardsApi.creator(),
  });
}

export function useEmployeeDashboard() {
  return useQuery({
    queryKey: ['dashboard', 'employee'],
    queryFn: () => dashboardsApi.employee(),
  });
}
```

- [ ] **Step 4: Create `src/api/dashboards.ts`** (API client for the new dashboard endpoints)

```ts
import { apiClient } from './client';

export const dashboardsApi = {
  manager: () => apiClient.get('/api/v1/dashboards/manager').then(r => r.data),
  creator: () => apiClient.get('/api/v1/dashboards/creator').then(r => r.data),
  employee: () => apiClient.get('/api/v1/dashboards/employee').then(r => r.data),
};
```

Also update `src/api/notifications.ts` to add `unreadCount` and `list(limit, offset)` methods if missing:

```ts
export const notificationsApi = {
  list: (limit = 20, offset = 0) =>
    apiClient.get(`/api/v1/notifications?limit=${limit}&offset=${offset}`).then(r => r.data),
  unreadCount: () =>
    apiClient.get('/api/v1/notifications/unread-count').then(r => r.data),
  markAllRead: () =>
    apiClient.patch('/api/v1/notifications/mark-all-read').then(r => r.data),
  markRead: (id: string) =>
    apiClient.patch(`/api/v1/notifications/${id}/read`).then(r => r.data),
};
```

- [ ] **Step 5: Run lint**

```bash
npm run lint
```

- [ ] **Step 6: Commit**

```bash
git add app/frontend/src/queries/ app/frontend/src/api/
git commit -m "feat: add TanStack React Query hooks for trainings, notifications, dashboards"
```

---

### Task 3: Fix Sidebar — unified 3-section architecture, icon-only collapse, typed props

**Files:**
- Modify: `src/components/layout/Sidebar.tsx`

- [ ] **Step 1: Read current `Sidebar.tsx`**

```bash
cat app/frontend/src/components/layout/Sidebar.tsx
```

Note the current structure (separate nav arrays per role, `user: any`).

- [ ] **Step 2: Rewrite `Sidebar.tsx`**

```tsx
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  BookOpen, Users, LayoutDashboard, Settings, Award,
  FileText, BarChart3, UserCheck, ChevronRight,
  GraduationCap, Layers, ClipboardList,
} from 'lucide-react';
import { UserDropdown } from './UserDropdown';

interface User {
  id: string;
  first_name: string;
  last_name: string;
  username: string;
  is_sysadmin: boolean;
  avatar_type?: string;
}

interface ActiveMembership {
  is_business_manager: boolean;
  is_training_creator: boolean;
}

interface SidebarProps {
  user: User;
  activeMembership: ActiveMembership | null;
  collapsed: boolean;
}

interface NavItem {
  to: string;
  icon: React.ElementType;
  label: string;
}

const LEARNING_NAV: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/my-trainings', icon: BookOpen, label: 'My Trainings' },
  { to: '/my-certificates', icon: Award, label: 'Certificates' },
];

const MANAGEMENT_NAV: NavItem[] = [
  { to: '/manage', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/manage/employees', icon: Users, label: 'Employees' },
  { to: '/manage/groups', icon: UserCheck, label: 'Groups' },
  { to: '/manage/reports', icon: BarChart3, label: 'Reports' },
];

const STUDIO_NAV: NavItem[] = [
  { to: '/manage/courses', icon: GraduationCap, label: 'My Trainings' },
];

const ADMIN_NAV: NavItem[] = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/tenants', icon: Layers, label: 'Tenants' },
  { to: '/admin/users', icon: Users, label: 'Users' },
  { to: '/admin/certificates', icon: Award, label: 'Templates' },
  { to: '/admin/bulk-import', icon: ClipboardList, label: 'Bulk Import' },
];

function NavSection({ title, items, collapsed }: { title: string; items: NavItem[]; collapsed: boolean }) {
  return (
    <div className="mb-4">
      {!collapsed && (
        <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </p>
      )}
      {items.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          end={to.split('/').length <= 2}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
              'hover:bg-accent hover:text-accent-foreground',
              isActive ? 'bg-primary text-primary-foreground font-medium' : 'text-foreground',
              collapsed && 'justify-center px-2',
            )
          }
          title={collapsed ? label : undefined}
        >
          <Icon className="h-4 w-4 shrink-0" />
          {!collapsed && <span>{label}</span>}
        </NavLink>
      ))}
    </div>
  );
}

export function Sidebar({ user, activeMembership, collapsed }: SidebarProps) {
  const isManager = activeMembership?.is_business_manager ?? false;
  const isCreator = activeMembership?.is_training_creator ?? false;
  const isAdmin = user.is_sysadmin;

  return (
    <aside
      className={cn(
        'flex flex-col h-full border-r bg-card transition-all duration-200',
        collapsed ? 'w-14' : 'w-56',
      )}
    >
      <div className="flex-1 overflow-y-auto py-4 px-2">
        {isAdmin ? (
          <NavSection title="Admin" items={ADMIN_NAV} collapsed={collapsed} />
        ) : (
          <>
            <NavSection title="Learning" items={LEARNING_NAV} collapsed={collapsed} />
            {(isManager || isAdmin) && (
              <NavSection title="Management" items={MANAGEMENT_NAV} collapsed={collapsed} />
            )}
            {isCreator && (
              <NavSection title="Studio" items={STUDIO_NAV} collapsed={collapsed} />
            )}
          </>
        )}
      </div>

      <div className={cn('border-t p-2', collapsed && 'flex justify-center')}>
        <NavLink
          to="/settings"
          className={cn(
            'flex items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-accent transition-colors',
            collapsed && 'justify-center px-2',
          )}
          title={collapsed ? 'Settings' : undefined}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Settings</span>}
        </NavLink>
        <UserDropdown user={user} collapsed={collapsed} />
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Update `UserDropdown` to accept typed props (fix `user: any`)**

In `src/components/layout/UserDropdown.tsx`, replace `user: any` with the same `User` interface above (export it from a shared types file or inline it).

- [ ] **Step 4: Run lint**

```bash
npm run lint
```

Fix any lint errors before continuing.

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/components/layout/Sidebar.tsx app/frontend/src/components/layout/UserDropdown.tsx
git commit -m "fix: rewrite Sidebar as unified 3-section with icon-only collapse and typed props (C-502, C-502a)"
```

---

### Task 4: Add mobile Sheet drawer, fix AppLayout

**Files:**
- Modify: `src/layouts/AppLayout.tsx` (or `src/components/layout/AppLayout.tsx`)
- Modify: `src/components/layout/MobileHeader.tsx`

- [ ] **Step 1: Install the Sheet component** (if not already present via shadcn)

```bash
npx shadcn@latest add sheet
```

- [ ] **Step 2: Update `AppLayout.tsx` to use Sheet for mobile**

```tsx
import { useState } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { Sheet, SheetContent } from '../components/ui/sheet';
import { MobileHeader } from '../components/layout/MobileHeader';
import { cn } from '@/lib/utils';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, activeMembership } = useAuth();  // from your auth context

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar — hidden on mobile */}
      <div className="hidden md:flex">
        <Sidebar
          user={user}
          activeMembership={activeMembership}
          collapsed={sidebarCollapsed}
        />
      </div>

      {/* Mobile sidebar — Sheet drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="p-0 w-56">
          <Sidebar
            user={user}
            activeMembership={activeMembership}
            collapsed={false}
          />
        </SheetContent>
      </Sheet>

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header with hamburger */}
        <div className="md:hidden">
          <MobileHeader
            user={user}
            onMenuClick={() => setMobileOpen(true)}
          />
        </div>

        {/* Desktop topbar with collapse toggle */}
        <div className="hidden md:flex items-center border-b px-4 py-2 bg-card">
          <button
            onClick={() => setSidebarCollapsed(c => !c)}
            className="rounded p-1 hover:bg-accent"
            aria-label="Toggle sidebar"
          >
            {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          <div className="ml-auto">
            <NotificationBell />
          </div>
        </div>

        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update `MobileHeader.tsx` to accept typed props and add hamburger**

```tsx
import { Menu } from 'lucide-react';
import { Button } from '../ui/button';
import { NotificationBell } from '../NotificationBell';
import { cn } from '@/lib/utils';

interface User {
  first_name: string;
  last_name: string;
  avatar_type?: string;
}

interface MobileHeaderProps {
  user: User;
  onMenuClick: () => void;
}

export function MobileHeader({ user, onMenuClick }: MobileHeaderProps) {
  return (
    <header className="flex items-center justify-between border-b px-4 py-2 bg-card">
      <Button variant="ghost" size="icon" onClick={onMenuClick} aria-label="Open menu">
        <Menu className="h-5 w-5" />
      </Button>
      <span className="text-sm font-semibold text-foreground">LMS</span>
      <NotificationBell />
    </header>
  );
}
```

- [ ] **Step 4: Run lint**

```bash
npm run lint
```

- [ ] **Step 5: Commit**

```bash
git add app/frontend/src/
git commit -m "fix: add mobile Sheet drawer sidebar, hamburger in header (C-502a)"
```

---

### Task 5: Add NotificationBell dropdown

**Files:**
- Create: `src/components/NotificationBell.tsx`

- [ ] **Step 1: Create `NotificationBell.tsx`**

```tsx
import { Bell } from 'lucide-react';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { ScrollArea } from './ui/scroll-area';
import { cn } from '@/lib/utils';
import { useUnreadCount, useNotifications, useMarkAllRead } from '../queries/notifications';
import { NavLink } from 'react-router-dom';

export function NotificationBell() {
  const { data: unreadData } = useUnreadCount();
  const { data: notifData } = useNotifications(5, 0);
  const markAllRead = useMarkAllRead();
  const unreadCount = unreadData?.unread_count ?? 0;
  const items = notifData?.items ?? [];

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-destructive-foreground text-xs font-bold">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="flex items-center justify-between border-b px-4 py-2">
          <span className="text-sm font-semibold">Notifications</span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs"
              onClick={() => markAllRead.mutate()}
            >
              Mark all read
            </Button>
          )}
        </div>
        <ScrollArea className="h-72">
          {items.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-6">No notifications</p>
          ) : (
            items.map((n: { id: string; title: string; body: string; is_read: boolean }) => (
              <div
                key={n.id}
                className={cn(
                  'border-b px-4 py-3 text-sm',
                  !n.is_read && 'bg-accent/50',
                )}
              >
                <p className="font-medium">{n.title}</p>
                <p className="text-muted-foreground text-xs mt-0.5 line-clamp-2">{n.body}</p>
              </div>
            ))
          )}
        </ScrollArea>
        <div className="border-t px-4 py-2">
          <NavLink to="/notifications" className="text-xs text-primary hover:underline">
            View all notifications
          </NavLink>
        </div>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 2: Run lint**

```bash
npm run lint
```

- [ ] **Step 3: Commit**

```bash
git add app/frontend/src/components/NotificationBell.tsx
git commit -m "feat: add notification bell with inline dropdown (replaces full-page navigation)"
```

---

### Task 6: Add React Player to Training Viewer + heartbeat

**Files:**
- Modify: `src/pages/TrainingViewer.tsx`

- [ ] **Step 1: Read current video rendering in `TrainingViewer.tsx`**

```bash
grep -n "iframe\|video\|getEmbedUrl" app/frontend/src/pages/TrainingViewer.tsx | head -20
```

- [ ] **Step 2: Replace iframe with React Player**

Find the `content_type === 'VIDEO'` render branch and replace:

```tsx
import ReactPlayer from 'react-player';
import { useRef, useState, useCallback } from 'react';

// In the component, add state for resume position:
const [resumePosition, setResumePosition] = useState<number>(
  currentChapter?.progress?.resume_position_seconds ?? 0
);
const playerRef = useRef<ReactPlayer>(null);
const milestonesReported = useRef<Set<number>>(new Set());

const handleProgress = useCallback(({ playedSeconds, played }: { playedSeconds: number; played: number }) => {
  const pct = played * 100;
  const newMilestones: Record<string, boolean> = {};
  if (pct >= 25 && !milestonesReported.current.has(25)) {
    newMilestones.milestone_25 = true;
    milestonesReported.current.add(25);
  }
  if (pct >= 50 && !milestonesReported.current.has(50)) {
    newMilestones.milestone_50 = true;
    milestonesReported.current.add(50);
  }
  if (pct >= 75 && !milestonesReported.current.has(75)) {
    newMilestones.milestone_75 = true;
    milestonesReported.current.add(75);
  }
  // Save progress to API
  progressApi.saveVideoProgress({
    training_id: trainingId,
    chapter_id: currentChapter.id,
    position_seconds: Math.floor(playedSeconds),
    ...newMilestones,
  });
}, [trainingId, currentChapter]);

const handleEnded = useCallback(() => {
  progressApi.saveVideoProgress({
    training_id: trainingId,
    chapter_id: currentChapter.id,
    position_seconds: 0,
    milestone_100: true,
    video_ended: true,
  }).then(() => {
    // Mark chapter complete and refresh
    queryClient.invalidateQueries({ queryKey: ['training', trainingId] });
  });
}, [trainingId, currentChapter]);

// Render:
{chapter.content_type === 'VIDEO' && (
  <div className="aspect-video w-full rounded-lg overflow-hidden bg-black">
    <ReactPlayer
      ref={playerRef}
      url={chapter.content_data?.url}
      width="100%"
      height="100%"
      controls
      onProgress={handleProgress}
      onEnded={handleEnded}
      onReady={() => {
        if (resumePosition > 0) {
          playerRef.current?.seekTo(resumePosition);
        }
      }}
      progressInterval={10000}
    />
  </div>
)}
```

- [ ] **Step 3: Add heartbeat interval**

Add inside the Training Viewer component's `useEffect`:

```tsx
useEffect(() => {
  const interval = setInterval(async () => {
    try {
      const resp = await fetch('/api/v1/auth/heartbeat', {
        method: 'POST',
        headers: { Authorization: `Bearer ${getAccessToken()}` },
      });
      const newToken = resp.headers.get('new_token');
      if (newToken) {
        setAccessToken(newToken);  // update stored token via your auth utility
      }
    } catch {
      // silent fail — user will be redirected on next 401
    }
  }, 60_000);  // every 60 seconds

  return () => clearInterval(interval);
}, []);
```

Note: `getAccessToken` and `setAccessToken` should use your existing `auth-storage.ts` utility.

- [ ] **Step 4: Add PDF viewer for PDF lesson type**

Find the render switch for content types and add a PDF branch:

```tsx
{chapter.content_type === 'PDF' && (
  <div className="w-full h-[70vh] rounded-lg overflow-hidden border">
    <iframe
      src={chapter.content_data?.url}
      title={chapter.title}
      className="w-full h-full"
      aria-label={`PDF: ${chapter.title}`}
    />
  </div>
)}
```

Note: The PDF URL should point to `/storage/images/{tenant_id}/{filename}` served by Nginx. For a more full-featured PDF viewer, the `react-pdf` library can be added, but the iframe approach is sufficient for MVP.

- [ ] **Step 5: Add True/False, Matching, Ordering quiz type rendering**

Find the quiz question render loop in `TrainingViewer.tsx`. Add branches for the missing types:

```tsx
function QuizQuestion({ question, answer, onChange }: QuizQuestionProps) {
  if (question.type === 'true_false') {
    return (
      <div className="flex gap-4">
        {['True', 'False'].map(opt => (
          <button
            key={opt}
            onClick={() => onChange([opt.toLowerCase()])}
            className={cn(
              'flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-colors',
              answer?.includes(opt.toLowerCase())
                ? 'border-primary bg-primary text-primary-foreground'
                : 'border-border hover:bg-accent',
            )}
          >
            {opt}
          </button>
        ))}
      </div>
    );
  }

  if (question.type === 'matching') {
    // Two-column matching: left items matched to right items via dropdowns
    return (
      <div className="space-y-2">
        {question.left_items?.map((left: { id: string; text: string }) => (
          <div key={left.id} className="flex items-center gap-4">
            <span className="w-1/2 text-sm">{left.text}</span>
            <select
              className="w-1/2 rounded border border-border px-2 py-1 text-sm bg-background"
              value={answer?.find((p: string) => p.startsWith(left.id))?.split('::')[1] ?? ''}
              onChange={e => {
                const pairs = (answer ?? []).filter((p: string) => !p.startsWith(left.id));
                onChange([...pairs, `${left.id}::${e.target.value}`]);
              }}
            >
              <option value="">Select...</option>
              {question.right_items?.map((right: { id: string; text: string }) => (
                <option key={right.id} value={right.id}>{right.text}</option>
              ))}
            </select>
          </div>
        ))}
      </div>
    );
  }

  if (question.type === 'ordering') {
    // Drag-to-reorder list; use a simple up/down button approach for MVP
    const orderedItems: string[] = answer ?? question.options?.map((o: { id: string }) => o.id) ?? [];
    return (
      <div className="space-y-2">
        {orderedItems.map((itemId, idx) => {
          const item = question.options?.find((o: { id: string; text: string }) => o.id === itemId);
          return (
            <div key={itemId} className="flex items-center gap-2 rounded border border-border px-3 py-2 bg-card">
              <span className="flex-1 text-sm">{item?.text}</span>
              <button
                disabled={idx === 0}
                onClick={() => {
                  const next = [...orderedItems];
                  [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                  onChange(next);
                }}
                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                aria-label="Move up"
              >▲</button>
              <button
                disabled={idx === orderedItems.length - 1}
                onClick={() => {
                  const next = [...orderedItems];
                  [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
                  onChange(next);
                }}
                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                aria-label="Move down"
              >▼</button>
            </div>
          );
        })}
      </div>
    );
  }

  // Default: multiple_choice / multiple_select
  return (
    <div className="space-y-2">
      {question.options?.map((opt: { id: string; text: string }) => (
        <button
          key={opt.id}
          onClick={() => {
            if (question.type === 'multiple_select') {
              const current = answer ?? [];
              onChange(current.includes(opt.id) ? current.filter((id: string) => id !== opt.id) : [...current, opt.id]);
            } else {
              onChange([opt.id]);
            }
          }}
          className={cn(
            'w-full text-left rounded-lg border px-4 py-3 text-sm transition-colors',
            answer?.includes(opt.id)
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border hover:bg-accent',
          )}
        >
          {opt.text}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Run lint**

```bash
npm run lint
```

Fix any errors.

- [ ] **Step 7: Commit**

```bash
git add app/frontend/src/pages/TrainingViewer.tsx
git commit -m "feat: React Player in viewer, PDF lesson type, True/False+Matching+Ordering quiz types, heartbeat (C-510, BR-406)"
```

---

### Task 7: Add missing pages — Password Reset, Employee Dashboard, Manager Reports, Bulk Import

**Files:**
- Create: `src/pages/AuthPasswordReset.tsx`
- Create: `src/pages/LearnerDashboard.tsx`
- Create: `src/pages/ManagerReports.tsx`
- Create: `src/pages/AdminBulkImport.tsx`
- Modify: `src/App.tsx`

- [ ] **Step 1: Create `AuthPasswordReset.tsx`**

```tsx
import { useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { authApi } from '../api/auth';
import { cn } from '@/lib/utils';

export function AuthPasswordReset() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState<'idle' | 'sent' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault();
    try {
      await authApi.forgotPassword(email);
      setStatus('sent');
    } catch {
      setError('Something went wrong. Please try again.');
    }
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    try {
      await authApi.resetPassword(token!, password);
      setStatus('done');
      setTimeout(() => navigate('/login'), 2000);
    } catch {
      setError('Invalid or expired reset link.');
    }
  }

  if (status === 'sent') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-center">
            <p className="text-foreground">Check your email for a password reset link.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'done') {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-center">
            <p className="text-foreground">Password updated. Redirecting to login…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{token ? 'Set New Password' : 'Forgot Password'}</CardTitle>
        </CardHeader>
        <CardContent>
          {error && <p className="mb-3 text-sm text-destructive">{error}</p>}
          {token ? (
            <form onSubmit={handleReset} className="space-y-4">
              <div>
                <Label htmlFor="password">New Password</Label>
                <Input id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
              </div>
              <Button type="submit" className="w-full">Update Password</Button>
            </form>
          ) : (
            <form onSubmit={handleForgot} className="space-y-4">
              <div>
                <Label htmlFor="email">Email Address</Label>
                <Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} required />
              </div>
              <Button type="submit" className="w-full">Send Reset Link</Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
```

Add to `src/api/auth.ts`:
```ts
forgotPassword: (email: string) =>
  apiClient.post('/api/v1/auth/forgot-password', { email }).then(r => r.data),
resetPassword: (token: string, new_password: string) =>
  apiClient.post('/api/v1/auth/reset-password', { token, new_password }).then(r => r.data),
```

- [ ] **Step 2: Create `LearnerDashboard.tsx`**

```tsx
import { useEmployeeDashboard } from '../queries/dashboards';
import { BookOpen, Clock, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { cn } from '@/lib/utils';

export function LearnerDashboard() {
  const { data, isLoading } = useEmployeeDashboard();

  if (isLoading) return <div className="animate-pulse h-32 rounded-lg bg-muted" />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-foreground">My Dashboard</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <BookOpen className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">In Progress</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.in_progress?.length ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <Clock className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">Due This Week</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.upcoming_due?.length ?? 0}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <CheckCircle className="h-4 w-4 text-primary" />
            <CardTitle className="text-sm">Recently Completed</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.recently_completed?.length ?? 0}</p>
          </CardContent>
        </Card>
      </div>
      {(data?.in_progress ?? []).length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Continue Learning</h2>
          <div className="space-y-2">
            {data!.in_progress.map((item: { training_id: string; due_date: string | null }) => (
              <Card key={item.training_id} className="hover:bg-accent/50 transition-colors cursor-pointer">
                <CardContent className="flex items-center justify-between py-3">
                  <span className="text-sm font-medium">{item.training_id}</span>
                  {item.due_date && (
                    <span className="text-xs text-muted-foreground">
                      Due {new Date(item.due_date).toLocaleDateString()}
                    </span>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `ManagerReports.tsx`**

```tsx
import { useManagerDashboard } from '../queries/dashboards';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { BarChart3 } from 'lucide-react';

export function ManagerReports() {
  const { data, isLoading } = useManagerDashboard();

  if (isLoading) return <div className="animate-pulse h-32 rounded-lg bg-muted" />;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-foreground">Compliance Reports</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Completion Rate</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{data?.completion_rate ?? 0}%</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Overdue</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold text-destructive">{data?.overdue_assignments ?? 0}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Quiz Lockouts</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{data?.quiz_lockouts ?? 0}</p></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2"><CardTitle className="text-sm">Total Assignments</CardTitle></CardHeader>
          <CardContent><p className="text-2xl font-bold">{data?.total_assignments ?? 0}</p></CardContent>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `AdminBulkImport.tsx`**

```tsx
import { useState, useRef } from 'react';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { usersApi } from '../api/users';
import { cn } from '@/lib/utils';

interface ImportResult {
  successes: Array<{ row: number; email: string }>;
  failures: Array<{ row: number; email: string; reason: string }>;
  total_rows: number;
}

export function AdminBulkImport() {
  const [tenantId, setTenantId] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !tenantId) return;

    setIsLoading(true);
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await usersApi.bulkImport(tenantId, formData);
      setResult(data);
    } catch {
      setError('Import failed. Please check your CSV format.');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-foreground">Bulk User Import</h1>
      <Card>
        <CardHeader><CardTitle>Upload CSV</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">Target Tenant ID</label>
              <input
                type="text"
                value={tenantId}
                onChange={e => setTenantId(e.target.value)}
                required
                placeholder="Enter tenant UUID"
                className="w-full rounded border border-border px-3 py-2 text-sm bg-background text-foreground"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground block mb-1">
                CSV File
                <span className="ml-2 text-xs text-muted-foreground">(columns: email, first_name, last_name, is_business_manager, is_training_creator)</span>
              </label>
              <input ref={fileRef} type="file" accept=".csv" required className="text-sm text-foreground" />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={isLoading}>
              {isLoading ? 'Importing…' : 'Import Users'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>
              Result: {result.successes.length} succeeded, {result.failures.length} failed
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.failures.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-destructive mb-2">Failures</h3>
                <div className="space-y-1">
                  {result.failures.map(f => (
                    <p key={f.row} className="text-sm text-muted-foreground">
                      Row {f.row} ({f.email}): {f.reason}
                    </p>
                  ))}
                </div>
              </div>
            )}
            {result.successes.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-2">Successes</h3>
                <p className="text-sm text-muted-foreground">{result.successes.map(s => s.email).join(', ')}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

Add to `src/api/users.ts`:
```ts
bulkImport: (tenantId: string, formData: FormData) =>
  apiClient.post(`/api/v1/users/bulk-import?tenant_id=${tenantId}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data),
```

- [ ] **Step 5: Register all new routes in `App.tsx`**

```tsx
import { AuthPasswordReset } from './pages/AuthPasswordReset';
import { LearnerDashboard } from './pages/LearnerDashboard';
import { ManagerReports } from './pages/ManagerReports';
import { AdminBulkImport } from './pages/AdminBulkImport';

// Add to router:
<Route path="/forgot-password" element={<AuthPasswordReset />} />
<Route path="/reset-password" element={<AuthPasswordReset />} />
<Route path="/dashboard" element={<AuthGuard><LearnerDashboard /></AuthGuard>} />
<Route path="/manage/reports" element={<AuthGuard requireBusinessManager><ManagerReports /></AuthGuard>} />
<Route path="/admin/bulk-import" element={<AuthGuard requireSysAdmin><AdminBulkImport /></AuthGuard>} />
```

- [ ] **Step 6: Fix the dead "Forgot password?" link in `AuthLogin.tsx`**

Find `href="#"` on the forgot password link and replace:

```tsx
// Before:
<a href="#">Forgot password?</a>

// After:
<Link to="/forgot-password" className="text-sm text-primary hover:underline">
  Forgot password?
</Link>
```

- [ ] **Step 7: Add `requireBusinessManager` guard to `AuthGuard`**

In `AuthGuard.tsx` (or wherever the guard is defined), add the new prop:

```tsx
interface AuthGuardProps {
  children: React.ReactNode;
  requireSysAdmin?: boolean;
  requireTrainingCreator?: boolean;
  requireBusinessManager?: boolean;  // ADD THIS
}

// In the guard logic:
if (requireBusinessManager && !activeMembership?.is_business_manager) {
  return <Navigate to="/dashboard" replace />;
}
```

Apply `requireBusinessManager` to `/manage`, `/manage/employees`, `/manage/groups`, `/manage/reports` routes in `App.tsx`.

- [ ] **Step 8: Run lint**

```bash
npm run lint
```

Fix all errors before committing.

- [ ] **Step 9: Commit**

```bash
git add app/frontend/src/
git commit -m "feat: add Password Reset, Employee Dashboard, Manager Reports, Admin Bulk Import pages; fix route guards"
```

---

### Task 8: Fix cn() usage and hardcoded colors across page files

**Files:**
- Modify: multiple `src/pages/*.tsx` and `src/components/*.tsx`

- [ ] **Step 1: Find all files with template literal class concatenation**

```bash
grep -rn "className={\`" app/frontend/src/pages/ app/frontend/src/components/ | grep -v "components/ui/" | wc -l
```

- [ ] **Step 2: Find all hardcoded hex and concrete color class usages**

```bash
grep -rn "bg-emerald-\|bg-indigo-\|bg-amber-\|bg-slate-\|text-slate-\|bg-red-\|bg-green-\|bg-blue-\|text-purple-\|bg-zinc-" app/frontend/src/pages/ app/frontend/src/components/ | grep -v "components/ui/" | wc -l
```

- [ ] **Step 3: Apply systematic replacements**

For each file with violations, replace concrete color classes with semantic equivalents:

| Concrete class | Semantic replacement |
|---|---|
| `bg-slate-50`, `bg-zinc-50` | `bg-background` or `bg-muted` |
| `bg-slate-100`, `bg-zinc-100` | `bg-muted` |
| `bg-slate-800`, `bg-zinc-800` | `bg-secondary` |
| `text-slate-500`, `text-zinc-500` | `text-muted-foreground` |
| `text-slate-900` | `text-foreground` |
| `bg-indigo-600`, `bg-blue-600` | `bg-primary` |
| `text-indigo-600`, `text-blue-600` | `text-primary` |
| `bg-emerald-500`, `bg-green-500` | `bg-success` or keep `bg-emerald-500` only for static status badges that don't need per-tenant branding |
| `bg-red-500`, `bg-red-600` | `bg-destructive` |
| `text-red-500` | `text-destructive` |

Hardcoded inline hex styles (e.g., `style={{ backgroundColor: '#4f46e5' }}`):
```tsx
// Before:
style={{ backgroundColor: branding.primaryColor || '#4f46e5' }}

// After — use CSS variable already set on :root by the auth flow:
className="bg-primary"
// and remove the inline style entirely (the CSS variable handles it)
```

- [ ] **Step 4: Replace template literal class merging with `cn()`**

For each page, add `import { cn } from '@/lib/utils';` at the top and wrap conditional classes:

```tsx
// Before:
className={`flex items-center gap-3 ${isActive ? 'bg-primary' : 'text-muted-foreground'}`}

// After:
className={cn('flex items-center gap-3', isActive ? 'bg-primary' : 'text-muted-foreground')}
```

Work through files in this order (most violations first):
1. `TrainingViewer.tsx`
2. `ManagerDashboard.tsx`
3. `MyTrainings.tsx`
4. `AdminDashboard.tsx`
5. `ProfilePage.tsx`
6. `SettingsPage.tsx`
7. `LearnerCertificates.tsx`
8. `components/layout/AppLayout.tsx`

- [ ] **Step 5: Run lint after each file**

```bash
npm run lint
```

Fix all errors before moving to the next file.

- [ ] **Step 6: Move `MultiSelect.tsx` and `RichTextEditor.tsx` out of `components/ui/`**

```bash
mv app/frontend/src/components/ui/MultiSelect.tsx app/frontend/src/components/MultiSelect.tsx
mv app/frontend/src/components/ui/RichTextEditor.tsx app/frontend/src/components/RichTextEditor.tsx
```

Update all imports referencing these files:

```bash
grep -rn "components/ui/MultiSelect\|components/ui/RichTextEditor" app/frontend/src/
```

Update each import path to `../components/MultiSelect` or `../components/RichTextEditor`.

- [ ] **Step 7: Final lint check**

```bash
npm run lint
```

Expected: zero errors.

- [ ] **Step 8: Commit**

```bash
git add app/frontend/src/
git commit -m "fix: replace all hardcoded colors with CSS variable classes, use cn() throughout pages (C-504, C-505)"
```

---

### Task 9: Final validation

- [ ] **Step 1: Build the frontend to catch TypeScript errors**

```bash
cd app/frontend && npm run build
```

Expected: zero TypeScript errors, build succeeds.

- [ ] **Step 2: Run lint one final time**

```bash
npm run lint
```

Expected: zero errors.

- [ ] **Step 3: Start the full stack and manually verify key flows**

```bash
docker compose up --build -d
```

Test these flows manually in the browser:
- [ ] Login → tenant selection → sidebar shows correct sections per role
- [ ] Employee: Dashboard shows in-progress, upcoming due, recently completed
- [ ] Manager: Sidebar shows Management section with Reports link (not "coming soon")
- [ ] Training Viewer: video plays via React Player, progress bar updates
- [ ] Training Viewer: quiz renders True/False and MC correctly
- [ ] Notification bell shows dropdown with recent items
- [ ] Forgot password link navigates to the reset page
- [ ] SysAdmin: Bulk Import page accessible at `/admin/bulk-import`
- [ ] Mobile: hamburger opens sidebar Sheet drawer
- [ ] Desktop collapsed: sidebar shows icons only (no labels)

- [ ] **Step 4: Final commit**

```bash
git add app/frontend/
git commit -m "fix: frontend zero-error policy verified; all C-5xx constraints met"
```
