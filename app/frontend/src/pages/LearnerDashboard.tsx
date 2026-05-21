import { useEmployeeDashboard } from '../queries/dashboards';
import { BookOpen, Clock, CheckCircle, AlertCircle, LayoutDashboard } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { PageLoader } from '../components/ui/PageLoader';

const STAT_CARDS = [
  { key: 'assigned_trainings' as const, label: 'Assigned', description: 'Total trainings assigned to you', icon: BookOpen, color: 'text-primary' },
  { key: 'in_progress_trainings' as const, label: 'In Progress', description: 'Currently underway', icon: Clock, color: 'text-primary' },
  { key: 'completed_trainings' as const, label: 'Completed', description: 'Successfully finished', icon: CheckCircle, color: 'text-primary' },
  { key: 'overdue_trainings' as const, label: 'Overdue', description: 'Past due date', icon: AlertCircle, color: 'text-destructive' },
];

export function LearnerDashboard() {
  const { data, isLoading, isError } = useEmployeeDashboard();

  if (isLoading) return <PageLoader />;

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-muted-foreground">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <p className="text-sm">Failed to load dashboard. Please refresh the page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
            <LayoutDashboard className="w-6 h-6 text-primary" />
          </div>
          My Dashboard
        </h1>
        <p className="text-muted-foreground mt-1">Your learning progress at a glance.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {STAT_CARDS.map(({ key, label, description, icon: Icon, color }) => (
          <Card key={key}>
            <CardHeader className="flex flex-row items-center gap-2 pb-2">
              <Icon className={`h-4 w-4 ${color}`} />
              <CardTitle className="text-sm">{label}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className={`text-2xl font-bold ${color === 'text-destructive' ? color : ''}`}>
                {data?.[key] ?? 0}
              </p>
              <p className="text-xs text-muted-foreground mt-1">{description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
