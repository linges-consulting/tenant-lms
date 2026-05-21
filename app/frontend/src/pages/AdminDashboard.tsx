import React from 'react';
import { cn } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Building2, Users, Activity, Layers, ArrowRight, PlusCircle, LayoutDashboard } from 'lucide-react';
import { PageLoader } from '../components/ui/PageLoader';
import { tenantService } from '../api/tenants';
import type { Tenant } from '../api/auth';
import { Link } from 'react-router-dom';

const metricIconMap: Record<string, React.ElementType> = {
    "Active Tenants": Building2,
    "Global Users": Users,
    "Total Trainings": Layers,
    "System Status": Activity,
};

type HealthStatus = 'checking' | 'ok' | 'error';

const SERVICES: { key: 'auth' | 'core' | 'notification'; label: string }[] = [
    { key: 'auth', label: 'Auth Service' },
    { key: 'core', label: 'Core Service' },
    { key: 'notification', label: 'Notification Service' },
];



export const AdminDashboard: React.FC = () => {
    const [metrics, setMetrics] = React.useState<Record<string, unknown>[]>([]);
    const [recentTenants, setRecentTenants] = React.useState<Tenant[]>([]);
    const [isLoading, setIsLoading] = React.useState(true);
    const [healthStatus, setHealthStatus] = React.useState<Record<string, HealthStatus>>({
        auth: 'checking', core: 'checking', notification: 'checking',
    });

    React.useEffect(() => {
        const fetchData = async () => {
            try {
                const [metricsData, tenantsData] = await Promise.all([
                    tenantService.getMetrics(),
                    tenantService.list()
                ]);
                setMetrics(metricsData);
                setRecentTenants(tenantsData.slice(0, 5));
            } catch (error) {
                console.error('Failed to fetch admin dashboard data:', error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchData();

        // Check health of each service independently
        SERVICES.forEach(({ key }) => {
            tenantService.checkHealth(key)
                .then(() => setHealthStatus(prev => ({ ...prev, [key]: 'ok' })))
                .catch(() => setHealthStatus(prev => ({ ...prev, [key]: 'error' })));
        });
    }, []);

    if (isLoading) {
        return <PageLoader fullPage label="Assembling system overview..." />;
    }

    return (
        <div className="space-y-8 max-w-7xl mx-auto">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                            <LayoutDashboard className="w-6 h-6 text-violet-600 dark:text-violet-400" />
                        </div>
                        Admin Console
                    </h1>
                    <p className="text-muted-foreground mt-1">Platform overview and global health monitoring.</p>
                </div>
                <div className="flex flex-wrap gap-3">
                    <Link to="/admin/tenants/new">
                        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground">
                            <PlusCircle className="mr-2 h-4 w-4" />
                            New Tenant
                        </Button>
                    </Link>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                {metrics.filter(m => String(m.label) !== 'System Status').map((metric, index) => {
                    const Icon = metricIconMap[String(metric.label)] || Activity;
                    const trendText = String(metric.trend ?? '');
                    return (
                        <Card key={index} className="border-border/50 shadow-sm bg-card hover:border-primary/20 transition-colors">
                            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                                <CardTitle className="text-sm font-medium text-muted-foreground truncate pr-2">
                                    {String(metric.label)}
                                </CardTitle>
                                <div className="p-2 bg-primary/10 rounded-full shrink-0">
                                    <Icon className="w-4 h-4 text-primary" />
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className="text-2xl font-bold">{String(metric.value ?? '')}</div>
                                {trendText && !trendText.includes(' | ') && (
                                    <p className={cn('text-xs mt-1 font-medium', metric.isAlert ? 'text-primary' : 'text-muted-foreground')}>
                                        {trendText}
                                    </p>
                                )}
                            </CardContent>
                        </Card>
                    );
                })}

                {/* System Status — derived from live health checks, not backend */}
                {(() => {
                    const anyError = Object.values(healthStatus).some(s => s === 'error');
                    const allOk = Object.values(healthStatus).every(s => s === 'ok');
                    const degraded = SERVICES.filter(s => healthStatus[s.key] === 'error').map(s => s.label);
                    const value = anyError ? 'Degraded' : allOk ? 'Healthy' : 'Checking…';
                    const trend = anyError ? `${degraded.join(', ')} down` : allOk ? 'All systems nominal' : 'Checking services…';
                    const color = anyError ? 'text-destructive' : allOk ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground';
                    const iconBg = anyError ? 'bg-destructive/10' : allOk ? 'bg-green-500/10' : 'bg-muted';
                    const iconColor = anyError ? 'text-destructive' : allOk ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground';
                    return (
                        <Card className="border-border/50 shadow-sm bg-card hover:border-primary/20 transition-colors">
                            <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
                                <CardTitle className="text-sm font-medium text-muted-foreground truncate pr-2">
                                    System Status
                                </CardTitle>
                                <div className={cn('p-2 rounded-full shrink-0', iconBg)}>
                                    <Activity className={cn('w-4 h-4', iconColor)} />
                                </div>
                            </CardHeader>
                            <CardContent>
                                <div className={cn('text-2xl font-bold', color)}>{value}</div>
                                <p className="text-xs mt-1 font-medium text-muted-foreground line-clamp-2" title={trend}>
                                    {trend}
                                </p>
                            </CardContent>
                        </Card>
                    );
                })()}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Recent Tenants */}
                <Card className="border-border/50 shadow-sm">
                    <CardHeader className="flex flex-row items-center justify-between border-b border-border/50 pb-4">
                        <div>
                            <CardTitle className="text-lg">Recent Tenants</CardTitle>
                            <p className="text-sm text-muted-foreground mt-1">Active organizations on the platform.</p>
                        </div>
                        <Link to="/admin/tenants">
                            <Button variant="ghost" size="sm" className="text-primary hover:text-primary/90 hover:bg-primary/10">
                                View All <ArrowRight className="ml-2 w-4 h-4" />
                            </Button>
                        </Link>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader className="bg-muted/50">
                                <TableRow>
                                    <TableHead className="pl-6">Organization</TableHead>
                                    <TableHead className="text-right">Users</TableHead>
                                    <TableHead className="text-right">Certificates</TableHead>
                                    <TableHead className="pr-6 text-right">Status</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {recentTenants.map((tenant) => (
                                    <TableRow key={tenant.id} className="hover:bg-muted/30">
                                        <TableCell className="pl-6 font-medium">{tenant.name}</TableCell>
                                        <TableCell className="text-right text-muted-foreground">{tenant.user_count || 0}</TableCell>
                                        <TableCell className="text-right font-medium">{tenant.certificate_count || 0}</TableCell>
                                        <TableCell className="pr-6 text-right">
                                            <Badge variant="secondary" className="bg-primary/10 text-primary hover:bg-primary/20 border-0">
                                                Active
                                            </Badge>
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {recentTenants.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={4} className="h-24 text-center text-muted-foreground">
                                            No tenants registered yet.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>

                {/* Published Trainings by Tenant */}
                <Card className="border-border/50 shadow-sm">
                    <CardHeader className="border-b border-border/50 pb-4">
                        <CardTitle className="text-lg">Published Trainings</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">Training count per tenant.</p>
                    </CardHeader>
                    <CardContent className="p-0">
                        <Table>
                            <TableHeader className="bg-muted/50">
                                <TableRow>
                                    <TableHead className="pl-6">Organization</TableHead>
                                    <TableHead className="text-right pr-6">Trainings</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {recentTenants.map((tenant) => {
                                    const count = tenant.course_count || 0;
                                    const max = Math.max(...recentTenants.map(t => t.course_count || 0), 1);
                                    return (
                                        <TableRow key={tenant.id} className="hover:bg-muted/30">
                                            <TableCell className="pl-6 font-medium">{tenant.name}</TableCell>
                                            <TableCell className="pr-6">
                                                <div className="flex items-center justify-end gap-3">
                                                    <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                                                        <div
                                                            className="h-full rounded-full bg-primary/60 transition-all"
                                                            style={{ width: `${(count / max) * 100}%` }}
                                                        />
                                                    </div>
                                                    <span className="text-sm font-semibold text-foreground w-5 text-right">{count}</span>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                                {recentTenants.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={2} className="h-24 text-center text-muted-foreground">
                                            No training data available.
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};
