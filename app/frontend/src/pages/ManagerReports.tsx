import { useState } from 'react';
import { useManagerDashboard } from '../queries/dashboards';
import { managerTrainingsApi } from '../api/trainings';
import type { Training, QuizAttemptsSummaryChapter } from '../api/trainings';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { PageLoader } from '../components/ui/PageLoader';
import { AlertCircle, BarChart3, BookOpen, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

export function ManagerReports() {
  const { data, isLoading, isError } = useManagerDashboard();
  const [trainings, setTrainings] = useState<Training[]>([]);
  const [selectedTrainingId, setSelectedTrainingId] = useState('');
  const [loadingTrainings, setLoadingTrainings] = useState(false);
  const [summary, setSummary] = useState<QuizAttemptsSummaryChapter[]>([]);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [resettingKey, setResettingKey] = useState('');
  const [trainingsLoaded, setTrainingsLoaded] = useState(false);

  const loadTrainings = async () => {
    if (trainingsLoaded) return;
    setLoadingTrainings(true);
    try {
      const data = await managerTrainingsApi.getManagerTrainings();
      setTrainings(data.filter(t => t.is_published));
      setTrainingsLoaded(true);
    } catch {
      toast.error('Failed to load trainings');
    } finally {
      setLoadingTrainings(false);
    }
  };

  const loadSummary = async (trainingId: string) => {
    setSelectedTrainingId(trainingId);
    setLoadingSummary(true);
    setSummary([]);
    try {
      const data = await managerTrainingsApi.getQuizAttemptsSummary(trainingId);
      setSummary(data);
    } catch {
      toast.error('Failed to load quiz attempts');
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleReset = async (chapterId: string, userId: string) => {
    const key = `${chapterId}:${userId}`;
    setResettingKey(key);
    try {
      await managerTrainingsApi.resetUserQuizAttempts(selectedTrainingId, chapterId, userId);
      toast.success('Quiz attempts reset');
      await loadSummary(selectedTrainingId);
    } catch {
      toast.error('Failed to reset attempts');
    } finally {
      setResettingKey('');
    }
  };

  if (isLoading) return <PageLoader />;

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-muted-foreground">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm">Failed to load report data. Please refresh the page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
            <BarChart3 className="w-6 h-6 text-primary" />
          </div>
          Compliance Reports
        </h1>
        <p className="text-muted-foreground mt-1">Team training completion and progress metrics.</p>
      </div>

      {/* Summary stat cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Completion Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.completion_rate ?? 0}%</p>
            <p className="text-xs text-muted-foreground mt-1">Across all active assignments</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Overdue</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold text-destructive">{data?.overdue_count ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Assignments past due date</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Active Assignments</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.active_assignments ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Currently in progress</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total Trainings</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{data?.total_trainings ?? 0}</p>
            <p className="text-xs text-muted-foreground mt-1">Published in your organization</p>
          </CardContent>
        </Card>
      </div>

      {/* Quiz Lockouts section */}
      <Card>
        <CardHeader className="border-b border-border/50">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-primary" />
                Quiz Lockouts
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                Identify employees who have reached their maximum quiz attempts and reset them.
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4 space-y-4">
          {/* Training selector */}
          <div className="flex items-center gap-3">
            <select
              className="flex-1 max-w-sm h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              value={selectedTrainingId}
              onFocus={loadTrainings}
              onChange={e => e.target.value && loadSummary(e.target.value)}
            >
              <option value="">— Select a training —</option>
              {trainings.map(t => (
                <option key={t.id} value={t.id}>{t.title}</option>
              ))}
            </select>
            {loadingTrainings && <span className="text-xs text-muted-foreground">Loading…</span>}
          </div>

          {loadingSummary ? (
            <PageLoader label="Loading quiz attempts…" />
          ) : selectedTrainingId && summary.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-sm">
              No employees are currently locked out of any quiz in this training.
            </div>
          ) : summary.length > 0 ? (
            <div className="space-y-4">
              {summary.map(chapter => (
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
                      {chapter.users_at_limit.map(u => {
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
                              <span className="text-sm text-destructive font-medium">{u.attempts} / {chapter.max_attempts}</span>
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
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
