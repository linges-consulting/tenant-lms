import { useManagerDashboard } from '../queries/dashboards';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { PageLoader } from '../components/ui/PageLoader';
import { AlertCircle, BarChart3 } from 'lucide-react';

export function ManagerReports() {
  const { data, isLoading, isError } = useManagerDashboard();

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
    </div>
  );
}
