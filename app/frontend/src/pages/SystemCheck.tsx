import React, { useState } from 'react';
import {
    Activity,
    CheckCircle2,
    XCircle,
    RefreshCcw,
    Server,
    Database,
    ShieldCheck,
    HardDrive,
    MessageSquare,
    Search,
    ChevronRight
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

interface ServiceStatus {
    name: string;
    description: string;
    status: 'healthy' | 'degraded' | 'down' | 'checking';
    latency?: number;
    version?: string;
    icon: React.ElementType;
}

export const SystemCheck: React.FC = () => {
    const [isChecking, setIsChecking] = useState(false);
    const [lastCheck, setLastCheck] = useState<Date>(new Date());
    const [statuses, setStatuses] = useState<ServiceStatus[]>([
        { name: 'Auth Service', description: 'Authentication and User Management', status: 'healthy', latency: 45, version: 'v1.4.2', icon: ShieldCheck },
        { name: 'Core Service', description: 'Training and Course Management', status: 'healthy', latency: 32, version: 'v1.2.0', icon: Server },
        { name: 'Database', description: 'PostgreSQL Main Instance', status: 'healthy', latency: 12, icon: Database },
        { name: 'Storage', description: 'Asset Storage (S3/Local)', status: 'healthy', latency: 85, icon: HardDrive },
        { name: 'Email Gateway', description: 'SMTP Notification Service', status: 'healthy', icon: MessageSquare },
    ]);

    const runCheck = () => {
        setIsChecking(true);
        // Simulate checking
        setStatuses(prev => prev.map(s => ({ ...s, status: 'checking' })));

        setTimeout(() => {
            setStatuses([
                { name: 'Auth Service', description: 'Authentication and User Management', status: 'healthy', latency: 42, version: 'v1.4.2', icon: ShieldCheck },
                { name: 'Core Service', description: 'Training and Course Management', status: 'healthy', latency: 28, version: 'v1.2.0', icon: Server },
                { name: 'Database', description: 'PostgreSQL Main Instance', status: 'healthy', latency: 8, icon: Database },
                { name: 'Storage', description: 'Asset Storage (S3/Local)', status: 'healthy', latency: 74, icon: HardDrive },
                { name: 'Email Gateway', description: 'SMTP Notification Service', status: 'healthy', icon: MessageSquare },
            ]);
            setIsChecking(false);
            setLastCheck(new Date());
        }, 1500);
    };

    const getStatusBadge = (status: ServiceStatus['status']) => {
        switch (status) {
            case 'healthy':
                return <Badge variant="secondary" className="bg-primary/10 text-primary border-0">Healthy</Badge>;
            case 'degraded':
                return <Badge variant="secondary" className="bg-muted text-muted-foreground border-0">Degraded</Badge>;
            case 'down':
                return <Badge variant="destructive">Operational Failure</Badge>;
            case 'checking':
                return <Badge variant="secondary" className="animate-pulse">Checking...</Badge>;
            default:
                return null;
        }
    };

    const getStatusIcon = (status: ServiceStatus['status']) => {
        switch (status) {
            case 'healthy':
                return <CheckCircle2 className="w-5 h-5 text-primary" />;
            case 'down':
                return <XCircle className="w-5 h-5 text-destructive" />;
            case 'degraded':
                return <Activity className="w-5 h-5 text-muted-foreground" />;
            default:
                return <RefreshCcw className="w-5 h-5 text-muted-foreground animate-spin" />;
        }
    };

    return (
        <div className="p-8 space-y-8 animate-in fade-in duration-500 max-w-7xl mx-auto">
            <header className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                            <Server className="w-6 h-6 text-violet-600 dark:text-violet-400" />
                        </div>
                        System Status Check
                    </h1>
                    <p className="text-muted-foreground mt-1">Monitor and verify the health of all platform services.</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <Button
                        onClick={runCheck}
                        disabled={isChecking}
                        className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:scale-[1.02]"
                    >
                        <RefreshCcw className={cn('w-4 h-4 mr-2', isChecking && 'animate-spin')} />
                        {isChecking ? 'Running Diagnostics...' : 'Run System Check'}
                    </Button>
                    <p className="text-xs text-muted-foreground">
                        Last checked: {lastCheck.toLocaleTimeString()} {lastCheck.toLocaleDateString()}
                    </p>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <Card className="border-border/50 shadow-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5">
                        <Activity className="w-24 h-24" />
                    </div>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Overall Health</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-bold">100%</span>
                            <span className="text-primary text-sm font-medium mb-1">Operational</span>
                        </div>
                        <Progress value={100} className="h-1.5 mt-4" />
                    </CardContent>
                </Card>

                <Card className="border-border/50 shadow-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5">
                        <Search className="w-24 h-24" />
                    </div>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Active Alerts</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-bold">0</span>
                            <span className="text-muted-foreground text-sm font-medium mb-1">Critical issues</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-4 flex items-center">
                            <CheckCircle2 className="w-3 h-3 mr-1 text-primary" /> All systems nominal
                        </p>
                    </CardContent>
                </Card>

                <Card className="border-border/50 shadow-sm relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-5">
                        <RefreshCcw className="w-24 h-24" />
                    </div>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Uptime (30d)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-end gap-2">
                            <span className="text-3xl font-bold">99.98%</span>
                            <span className="text-muted-foreground text-sm font-medium mb-1">Reliability</span>
                        </div>
                        <p className="text-xs text-muted-foreground mt-4">Calculated across all managed regions</p>
                    </CardContent>
                </Card>
            </div>

            <Card className="border-border/50 shadow-sm overflow-hidden">
                <CardHeader className="border-b border-border/50 bg-muted/30">
                    <CardTitle className="text-lg flex items-center">
                        <Search className="w-5 h-5 mr-3 text-primary" />
                        Service Breakdown
                    </CardTitle>
                    <CardDescription>Real-time status of individual core components.</CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader className="bg-muted/10">
                            <TableRow>
                                <TableHead className="pl-6 w-[300px]">Service</TableHead>
                                <TableHead>Status</TableHead>
                                <TableHead>Latency</TableHead>
                                <TableHead>Version</TableHead>
                                <TableHead className="pr-6 text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {statuses.map((service) => (
                                <TableRow key={service.name} className="hover:bg-muted/30">
                                    <TableCell className="pl-6">
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 bg-primary/10 rounded-lg text-primary">
                                                <service.icon className="w-5 h-5" />
                                            </div>
                                            <div>
                                                <div className="font-medium">{service.name}</div>
                                                <div className="text-xs text-muted-foreground">{service.description}</div>
                                            </div>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            {getStatusIcon(service.status)}
                                            {getStatusBadge(service.status)}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-muted-foreground font-mono text-sm">
                                        {service.latency ? `${service.latency}ms` : '—'}
                                    </TableCell>
                                    <TableCell className="text-muted-foreground text-sm">
                                        {service.version || '—'}
                                    </TableCell>
                                    <TableCell className="pr-6 text-right">
                                        <Button variant="ghost" size="sm" className="text-primary hover:text-primary/90 hover:bg-primary/10">
                                            Details <ChevronRight className="ml-1 w-4 h-4" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="border-border/50 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-md">Recent Events</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {[
                            { time: '10:24 AM', event: 'Database automated backup completed', type: 'info' },
                            { time: '09:15 AM', event: 'System health check: All nominal', type: 'success' },
                            { time: '08:00 AM', event: 'Scheduled maintenance ended', type: 'info' },
                        ].map((item, i) => (
                            <div key={i} className="flex gap-3 text-sm border-l-2 border-muted pl-3 py-1">
                                <span className="text-muted-foreground whitespace-nowrap">{item.time}</span>
                                <span className="text-foreground">{item.event}</span>
                            </div>
                        ))}
                    </CardContent>
                </Card>

                <Card className="border-border/50 shadow-sm">
                    <CardHeader>
                        <CardTitle className="text-md">Infrastructure Metrics</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Error Rate (Global)</span>
                                <span className="font-medium text-primary">0.02%</span>
                            </div>
                            <Progress value={2} className="h-1 bg-muted" />
                        </div>
                        <div className="space-y-2">
                            <div className="flex justify-between text-sm">
                                <span className="text-muted-foreground">Request Throughput</span>
                                <span className="font-medium">1,240 req/min</span>
                            </div>
                            <Progress value={45} className="h-1 bg-muted" />
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};
