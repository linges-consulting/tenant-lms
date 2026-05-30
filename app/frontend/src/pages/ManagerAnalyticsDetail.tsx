import React, { useState, useMemo, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { analyticsApi, type EmployeeAttemptDetail, type EmployeeSummary } from '../api/analytics';
import { managerTrainingsApi } from '../api/trainings';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { PageLoader } from '../components/ui/PageLoader';
import {
  AlertCircle, ArrowLeft, BarChart3, ChevronDown, ChevronRight,
  Download, FileText, RotateCcw, Send, Users,
} from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

type StatusFilter = 'all' | 'completed' | 'in_progress' | 'overdue' | 'not_started' | 'locked';
type DueSoonWindow = 7 | 14 | 30;

const STATUS_LABELS: Record<string, string> = {
  completed: 'Completed',
  in_progress: 'In Progress',
  overdue: 'Overdue',
  not_started: 'Not Started',
  locked: 'Locked',
};

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: 'bg-primary/10 text-primary border-primary/20',
    in_progress: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    overdue: 'bg-destructive/10 text-destructive border-destructive/20',
    not_started: 'bg-muted text-muted-foreground border-border',
    locked: 'bg-orange-500/10 text-orange-600 border-orange-500/20',
  };
  return (
    <Badge className={cn(colors[status] ?? 'bg-muted text-muted-foreground')}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

function EmployeeDrillDown({ trainingId, userId }: { trainingId: string; userId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics', 'employee-detail', trainingId, userId],
    queryFn: () => analyticsApi.getEmployeeDetail(trainingId, userId),
  });

  if (isLoading) return <div className="px-4 py-3 text-sm text-muted-foreground">Loading attempts…</div>;
  if (!data?.length) return <div className="px-4 py-3 text-sm text-muted-foreground">No quiz attempts recorded.</div>;

  return (
    <div className="px-4 py-3 bg-muted/20 space-y-3">
      {(data as EmployeeAttemptDetail[]).map(ch => (
        <div key={ch.chapter_id}>
          <p className="text-sm font-medium mb-1">
            {ch.chapter_title}
            {ch.is_locked && <span className="ml-2 text-xs text-orange-600">(locked)</span>}
            <span className="ml-2 text-xs text-muted-foreground">max {ch.max_attempts} attempts</span>
          </p>
          <div className="flex gap-3 flex-wrap">
            {ch.attempts.map(a => (
              <div key={a.attempt_number} className={cn(
                'text-xs rounded px-2 py-1 border',
                a.passed
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'bg-muted text-muted-foreground border-border'
              )}>
                #{a.attempt_number} — {a.score.toFixed(0)}% {a.passed ? '✓' : '✗'}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

type EmployeeWithApproaching = EmployeeSummary & { approaching_count: number };

export function ManagerAnalyticsDetail() {
  const { trainingId } = useParams<{ trainingId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [dueSoonWindow, setDueSoonWindow] = useState<DueSoonWindow>(7);
  const [reminderLoading, setReminderLoading] = useState<string | null>(null);
  const [resettingKey, setResettingKey] = useState('');

  const thresholdKey = `analytics_warning_threshold_${trainingId}`;
  const [warningThreshold, setWarningThreshold] = useState<number>(() => {
    const saved = localStorage.getItem(thresholdKey);
    return saved ? Math.max(1, parseInt(saved, 10)) : 1;
  });
  useEffect(() => {
    localStorage.setItem(thresholdKey, String(warningThreshold));
  }, [warningThreshold, thresholdKey]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['analytics', 'detail', trainingId],
    queryFn: () => analyticsApi.getTrainingDetail(trainingId!),
    enabled: !!trainingId,
  });

  const { data: lockoutSummary = [], refetch: refetchLockouts } = useQuery({
    queryKey: ['quiz-lockouts', trainingId],
    queryFn: () => managerTrainingsApi.getQuizAttemptsSummary(trainingId!),
    enabled: !!trainingId,
  });

  const employees = useMemo((): EmployeeWithApproaching[] => {
    if (!data) return [];
    return data.employees.filter((emp: EmployeeSummary) => {
      if (statusFilter !== 'all' && emp.status !== statusFilter) return false;
      if (search && !emp.full_name.toLowerCase().includes(search.toLowerCase()) &&
          !emp.email.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    }).map((emp: EmployeeSummary) => {
      const approaching = emp.quiz_attempts.filter(qa =>
        !qa.passed &&
        qa.attempt_count < qa.max_attempts &&
        qa.attempt_count >= qa.max_attempts - warningThreshold
      ).length;
      return { ...emp, approaching_count: approaching };
    });
  }, [data, statusFilter, search, warningThreshold]);

  const toggleRow = (userId: string) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(userId)) {
        next.delete(userId);
      } else {
        next.add(userId);
      }
      return next;
    });
  };

  const handleSendReminder = async (userId: string) => {
    if (!trainingId) return;
    setReminderLoading(userId);
    try {
      await analyticsApi.sendReminder(trainingId, [userId]);
      toast.success('Reminder sent');
    } catch {
      toast.error('Failed to send reminder');
    } finally {
      setReminderLoading(null);
    }
  };

  const handleReset = async (chapterId: string, userId: string) => {
    if (!trainingId) return;
    const key = `${chapterId}:${userId}`;
    setResettingKey(key);
    try {
      await managerTrainingsApi.resetUserQuizAttempts(trainingId, chapterId, userId);
      toast.success('Quiz attempts reset');
      refetchLockouts();
      queryClient.invalidateQueries({ queryKey: ['analytics', 'detail', trainingId] });
    } catch {
      toast.error('Failed to reset attempts');
    } finally {
      setResettingKey('');
    }
  };

  const handleDownload = async (format: 'pdf' | 'csv') => {
    if (!trainingId) return;
    try {
      const blob = await analyticsApi.downloadDetailReport(trainingId, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `training-analytics.${format}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('Failed to download report');
    }
  };

  if (isLoading) return <PageLoader />;
  if (isError || !data) return (
    <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="text-sm">Failed to load analytics.</p>
    </div>
  );

  const dueSoonCount = dueSoonWindow === 7
    ? data.due_soon_7d
    : dueSoonWindow === 14 ? data.due_soon_14d : data.due_soon_30d;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <button
            onClick={() => navigate('/manage/analytics')}
            className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="h-4 w-4" /> Back to Analytics
          </button>
          <h1 className="text-2xl font-bold tracking-tight">{data.title}</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {data.category} · {data.creator_name}
            <Badge className={cn('ml-2 text-xs', data.is_published ? 'bg-primary/10 text-primary border-primary/20' : 'bg-muted text-muted-foreground')}>
              {data.is_published ? 'Published' : 'Draft'}
            </Badge>
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => handleDownload('csv')}>
            <Download className="h-4 w-4 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleDownload('pdf')}>
            <FileText className="h-4 w-4 mr-1" /> PDF
          </Button>
        </div>
      </div>

      {/* Overview stat cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Enrolled</p>
          <p className="text-2xl font-bold mt-1">{data.enrolled_count}</p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Completion</p>
          <p className="text-2xl font-bold mt-1 text-primary">{data.completion_pct}%</p>
          <p className="text-xs text-muted-foreground">{data.completed_count} completed</p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground flex items-center gap-1">
            Due Soon
            <select
              value={dueSoonWindow}
              onChange={e => setDueSoonWindow(Number(e.target.value) as DueSoonWindow)}
              className="ml-1 text-xs border rounded px-1 bg-background"
              onClick={e => e.stopPropagation()}
            >
              <option value={7}>7d</option>
              <option value={14}>14d</option>
              <option value={30}>30d</option>
            </select>
          </p>
          <p className={cn('text-2xl font-bold mt-1', dueSoonCount > 0 ? 'text-amber-600' : '')}>
            {dueSoonCount}
          </p>
        </CardContent></Card>

        <Card><CardContent className="p-4">
          <p className="text-xs text-muted-foreground">Overdue</p>
          <p className={cn('text-2xl font-bold mt-1', data.overdue_count > 0 ? 'text-destructive' : '')}>
            {data.overdue_count}
          </p>
        </CardContent></Card>

        <Card
          className={cn('cursor-pointer', data.lockout_count > 0 ? 'border-destructive/40' : '')}
          onClick={() => setStatusFilter('locked')}
        >
          <CardContent className="p-4">
            <p className={cn('text-xs', data.lockout_count > 0 ? 'text-destructive' : 'text-muted-foreground')}>
              Quiz Lockouts
            </p>
            <p className={cn('text-2xl font-bold mt-1', data.lockout_count > 0 ? 'text-destructive' : '')}>
              {data.lockout_count}
            </p>
            {data.lockout_count > 0 && <p className="text-xs text-destructive">Click to filter ↓</p>}
          </CardContent>
        </Card>
      </div>

      {/* Quiz Performance */}
      {data.quiz_chapters.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border/50 pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" /> Quiz Performance
              </CardTitle>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                Warning threshold:
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={warningThreshold}
                  onChange={e => setWarningThreshold(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  className="w-14 h-7 text-center border rounded text-sm bg-background"
                />
                attempts remaining
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Quiz</TableHead>
                  <TableHead className="text-right">Attempted</TableHead>
                  <TableHead className="text-right">Pass Rate</TableHead>
                  <TableHead className="text-right">Avg Score</TableHead>
                  <TableHead className="text-right">Avg Attempts to Pass</TableHead>
                  <TableHead className="text-right">Locked</TableHead>
                  <TableHead className="text-right">Approaching</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.quiz_chapters.map(ch => {
                  const approachingCount = data.employees.filter((emp: EmployeeSummary) =>
                    emp.quiz_attempts.some(qa =>
                      qa.chapter_id === ch.chapter_id &&
                      !qa.passed &&
                      qa.attempt_count < qa.max_attempts &&
                      qa.attempt_count >= qa.max_attempts - warningThreshold
                    )
                  ).length;
                  return (
                    <TableRow key={ch.chapter_id}>
                      <TableCell className="font-medium">{ch.chapter_title}</TableCell>
                      <TableCell className="text-right">{ch.attempted_count}</TableCell>
                      <TableCell className="text-right">
                        <span className={cn(ch.pass_rate < 60 ? 'text-destructive' : 'text-primary')}>
                          {ch.pass_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">{ch.avg_score}%</TableCell>
                      <TableCell className="text-right">{ch.avg_attempts_to_pass || '—'}</TableCell>
                      <TableCell className="text-right">
                        {ch.locked_count > 0
                          ? <span className="text-destructive font-medium">{ch.locked_count}</span>
                          : <span className="text-muted-foreground">0</span>}
                      </TableCell>
                      <TableCell className="text-right">
                        {approachingCount > 0
                          ? <span className="text-amber-600 font-medium">{approachingCount}</span>
                          : <span className="text-muted-foreground">0</span>}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Employee Status Table */}
      <Card>
        <CardHeader className="border-b border-border/50 pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-4 w-4 text-primary" /> Employee Status
          </CardTitle>
          <div className="flex flex-wrap gap-3 mt-2">
            <Input
              placeholder="Search by name or email…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="max-w-xs h-8 text-sm"
            />
            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value as StatusFilter)}
              className="h-8 rounded-md border border-input bg-background px-3 text-sm focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="in_progress">In Progress</option>
              <option value="overdue">Overdue</option>
              <option value="not_started">Not Started</option>
              <option value="locked">Locked</option>
            </select>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {employees.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No employees match the current filters.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Due Date</TableHead>
                  <TableHead>Completed</TableHead>
                  <TableHead className="text-right">Locked</TableHead>
                  <TableHead className="text-right">Approaching</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {employees.map((emp: EmployeeWithApproaching) => {
                  const isExpanded = expandedRows.has(emp.user_id);
                  const canRemind = ['in_progress', 'overdue', 'not_started'].includes(emp.status);
                  return (
                    <React.Fragment key={emp.user_id}>
                      <TableRow className="hover:bg-muted/20">
                        <TableCell>
                          <button
                            onClick={() => toggleRow(emp.user_id)}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            {isExpanded
                              ? <ChevronDown className="h-4 w-4" />
                              : <ChevronRight className="h-4 w-4" />}
                          </button>
                        </TableCell>
                        <TableCell>
                          <div>
                            <Link
                              to={`/profile/${emp.username}`}
                              className="text-sm font-medium hover:text-primary hover:underline"
                              onClick={e => e.stopPropagation()}
                            >
                              {emp.full_name || emp.email}
                            </Link>
                            <p className="text-xs text-muted-foreground">{emp.email}</p>
                          </div>
                        </TableCell>
                        <TableCell><StatusBadge status={emp.status} /></TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {emp.due_date ? new Date(emp.due_date).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {emp.completed_at ? new Date(emp.completed_at).toLocaleDateString() : '—'}
                        </TableCell>
                        <TableCell className="text-right">
                          {emp.locked_quiz_count > 0
                            ? <span className="text-destructive font-medium">{emp.locked_quiz_count}</span>
                            : <span className="text-muted-foreground">0</span>}
                        </TableCell>
                        <TableCell className="text-right">
                          {emp.approaching_count > 0
                            ? <span className="text-amber-600 font-medium">{emp.approaching_count}</span>
                            : <span className="text-muted-foreground">0</span>}
                        </TableCell>
                        <TableCell className="text-right">
                          {canRemind && (
                            <Button
                              size="sm"
                              variant="ghost"
                              className="h-7 text-xs"
                              disabled={reminderLoading === emp.user_id}
                              onClick={() => handleSendReminder(emp.user_id)}
                            >
                              <Send className="h-3 w-3 mr-1" />
                              {reminderLoading === emp.user_id ? 'Sending…' : 'Remind'}
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${emp.user_id}-detail`}>
                          <TableCell colSpan={8} className="p-0">
                            <EmployeeDrillDown trainingId={trainingId!} userId={emp.user_id} />
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Lockout Management */}
      {lockoutSummary.length > 0 && (
        <Card>
          <CardHeader className="border-b border-border/50 pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-destructive" /> Lockout Management
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Reset quiz attempts for locked-out employees.
            </p>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            {lockoutSummary.map((chapter: { chapter_id: string; chapter_title: string; max_attempts: number; users_at_limit: { user_id: string; name: string; email: string; attempts: number }[] }) => (
              <div key={chapter.chapter_id}>
                <p className="text-sm font-medium mb-2">
                  {chapter.chapter_title}
                  <span className="ml-2 text-xs text-muted-foreground">(max {chapter.max_attempts} attempts)</span>
                </p>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Employee</TableHead>
                      <TableHead>Attempts</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {chapter.users_at_limit.map((u: { user_id: string; name: string; email: string; attempts: number }) => {
                      const key = `${chapter.chapter_id}:${u.user_id}`;
                      return (
                        <TableRow key={u.user_id}>
                          <TableCell>
                            <div className="flex flex-col">
                              <span className="text-sm font-medium">{u.name}</span>
                              <span className="text-xs text-muted-foreground">{u.email}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <span className="text-sm text-destructive font-medium">
                              {u.attempts} / {chapter.max_attempts}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={resettingKey === key}
                              onClick={() => handleReset(chapter.chapter_id, u.user_id)}
                              className="h-7 text-xs"
                            >
                              <RotateCcw className="h-3 w-3 mr-1" />
                              {resettingKey === key ? 'Resetting…' : 'Reset'}
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
