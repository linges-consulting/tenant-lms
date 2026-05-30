import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { analyticsApi, type TrainingListItem } from '../api/analytics';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { PageLoader } from '../components/ui/PageLoader';
import { AlertCircle, BarChart3, Download, FileText } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../lib/utils';

type StatusFilter = 'all' | 'published' | 'draft';

export function ManagerAnalytics() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [creator, setCreator] = useState('');
  const [category, setCategory] = useState('');

  const { data: trainings = [], isLoading, isError } = useQuery({
    queryKey: ['analytics', 'list'],
    queryFn: analyticsApi.getTrainingList,
  });

  const creators = useMemo(
    () => Array.from(new Set(trainings.map((t: TrainingListItem) => t.creator_name).filter(Boolean))).sort() as string[],
    [trainings]
  );
  const categories = useMemo(
    () => Array.from(new Set(trainings.map((t: TrainingListItem) => t.category).filter(Boolean))).sort() as string[],
    [trainings]
  );

  const filtered = useMemo(() => {
    return trainings.filter((t: TrainingListItem) => {
      if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false;
      if (status === 'published' && !t.is_published) return false;
      if (status === 'draft' && t.is_published) return false;
      if (creator && t.creator_name !== creator) return false;
      if (category && t.category !== category) return false;
      return true;
    });
  }, [trainings, search, status, creator, category]);

  const handleDownload = async (format: 'pdf' | 'csv') => {
    try {
      const blob = await analyticsApi.downloadListReport(format);
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
  if (isError) return (
    <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
      <AlertCircle className="h-8 w-8 text-destructive" />
      <p className="text-sm">Failed to load analytics.</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
              <BarChart3 className="w-6 h-6 text-primary" />
            </div>
            Training Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Select a training to view completion stats, quiz performance, and employee progress.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => handleDownload('csv')}>
            <Download className="h-4 w-4 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleDownload('pdf')}>
            <FileText className="h-4 w-4 mr-1" /> PDF
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <Input
          placeholder="Search trainings…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-xs h-9"
        />
        <select
          value={status}
          onChange={e => setStatus(e.target.value as StatusFilter)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All Statuses</option>
          <option value="published">Published</option>
          <option value="draft">Draft</option>
        </select>
        <select
          value={creator}
          onChange={e => setCreator(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Creators</option>
          {creators.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={category}
          onChange={e => setCategory(e.target.value)}
          className="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="">All Categories</option>
          {categories.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>

      <Card>
        <CardHeader className="border-b border-border/50 pb-3">
          <CardTitle className="text-base">
            {filtered.length} training{filtered.length !== 1 ? 's' : ''}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-sm">No trainings match the current filters.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Creator</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Enrolled</TableHead>
                  <TableHead className="text-right">Completion %</TableHead>
                  <TableHead className="text-right">Overdue</TableHead>
                  <TableHead className="text-right">Lockouts</TableHead>
                  <TableHead className="text-right">Last Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((t: TrainingListItem) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer hover:bg-muted/30"
                    onClick={() => navigate(`/manage/analytics/${t.id}`)}
                  >
                    <TableCell className="font-medium">{t.title}</TableCell>
                    <TableCell className="text-muted-foreground">{t.creator_name || '—'}</TableCell>
                    <TableCell className="text-muted-foreground">{t.category}</TableCell>
                    <TableCell>
                      <Badge className={cn(
                        t.is_published
                          ? 'bg-primary/10 text-primary border-primary/20'
                          : 'bg-muted text-muted-foreground border-border'
                      )}>
                        {t.is_published ? 'Published' : 'Draft'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{t.enrolled_count}</TableCell>
                    <TableCell className="text-right">{t.completion_pct}%</TableCell>
                    <TableCell className="text-right">
                      {t.overdue_count > 0
                        ? <span className="text-destructive font-medium">{t.overdue_count}</span>
                        : t.overdue_count}
                    </TableCell>
                    <TableCell className="text-right">
                      {t.lockout_count > 0
                        ? <Badge className="bg-destructive/10 text-destructive border-destructive/20">{t.lockout_count}</Badge>
                        : <span className="text-muted-foreground">0</span>}
                    </TableCell>
                    <TableCell className="text-right text-muted-foreground text-sm">
                      {t.updated_at ? new Date(t.updated_at).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
