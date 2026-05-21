import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { TrendingUp, Users, BookOpen, AlertCircle, UserPlus, LayoutDashboard } from 'lucide-react';
import { PageLoader } from '../components/ui/PageLoader';
import { useAuth } from '../contexts/auth-context';
import { userService } from '../api/users';
import { managerTrainingsApi } from '../api/trainings';
import { UserAvatar } from '../components/UserAvatar';
import type { User } from '../api/users';
import type { Training } from '../api/trainings';
import { useNavigate } from 'react-router-dom';

export const ManagerDashboard: React.FC = () => {
    const { user, activeMembership } = useAuth();
    const navigate = useNavigate();
    const [employees, setEmployees] = useState<User[]>([]);
    const [trainings, setTrainings] = useState<Training[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const isManager = activeMembership?.is_business_manager;
    const isCreator = activeMembership?.is_training_creator;

    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true);
            try {
                const promises: Promise<unknown>[] = [];
                if (isManager) {
                    promises.push(userService.listTenantUsers());
                }
                if (isManager || isCreator) {
                    promises.push(managerTrainingsApi.getManagerTrainings());
                }
                const results = await Promise.allSettled(promises);

                let idx = 0;
                if (isManager && results[idx]?.status === 'fulfilled') {
                    setEmployees((results[idx] as PromiseFulfilledResult<User[]>).value);
                    idx++;
                }
                if ((isManager || isCreator) && results[idx]?.status === 'fulfilled') {
                    setTrainings((results[idx] as PromiseFulfilledResult<Training[]>).value);
                }
            } catch (err) {
                console.error('Failed to load dashboard data', err);
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, [isManager, isCreator]);

    const displayName = user?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'Manager';
    const publishedCount = trainings.filter(t => t.is_published).length;
    const draftCount = trainings.filter(t => !t.is_published).length;

    return (
        <div className="space-y-8 animate-in fade-in duration-300">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                            <LayoutDashboard className="w-6 h-6 text-primary" />
                        </div>
                        Oversight Dashboard
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Here's what's happening across your team, {displayName}.
                    </p>
                </div>
                <div className="flex gap-3">
                    {isManager && (
                        <Button onClick={() => navigate('/manage/employees')} className="shadow-md">
                            <UserPlus className="mr-2 w-4 h-4" /> Manage Employees
                        </Button>
                    )}
                    {isCreator && (
                        <Button variant="outline" onClick={() => navigate('/manage/courses')} className="shadow-sm">
                            <BookOpen className="mr-2 w-4 h-4" /> Manage Trainings
                        </Button>
                    )}
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
                {isManager && (
                    <Card className="border-border/50 shadow-sm">
                        <CardContent className="p-6">
                            <p className="text-sm font-medium text-muted-foreground mb-1">Total Employees</p>
                            <div className="flex items-baseline gap-3">
                                <p className="text-3xl font-bold">{isLoading ? '—' : employees.length}</p>
                                <Users className="w-4 h-4 text-muted-foreground" />
                            </div>
                        </CardContent>
                    </Card>
                )}
                {(isManager || isCreator) && (
                    <>
                        <Card className="border-border/50 shadow-sm">
                            <CardContent className="p-6">
                                <p className="text-sm font-medium text-muted-foreground mb-1">Published Trainings</p>
                                <div className="flex items-baseline gap-3">
                                    <p className="text-3xl font-bold text-primary">{isLoading ? '—' : publishedCount}</p>
                                    <TrendingUp className="w-4 h-4 text-primary" />
                                </div>
                            </CardContent>
                        </Card>
                        <Card className="border-border/50 shadow-sm">
                            <CardContent className="p-6">
                                <p className="text-sm font-medium text-muted-foreground mb-1">Draft Trainings</p>
                                <div className="flex items-baseline gap-3">
                                    <p className="text-3xl font-bold text-muted-foreground">{isLoading ? '—' : draftCount}</p>
                                    <AlertCircle className="w-4 h-4 text-muted-foreground" />
                                </div>
                            </CardContent>
                        </Card>
                    </>
                )}
            </div>

            {isLoading ? (
                <PageLoader />
            ) : (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
                    {/* Employee List — Business Manager only */}
                    {isManager && (
                        <Card className="xl:col-span-2 border-border/50 shadow-sm h-full flex flex-col">
                            <CardHeader className="border-b border-border/50 bg-muted/20 pb-4">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <CardTitle className="text-xl">Employee Directory</CardTitle>
                                        <CardDescription>All active employees in your organization</CardDescription>
                                    </div>
                                    <Button variant="ghost" size="sm" className="hidden sm:flex text-primary" onClick={() => navigate('/manage/employees')}>
                                        View All
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent className="p-0 flex-1">
                                {employees.length === 0 ? (
                                    <div className="p-8 text-center text-muted-foreground">
                                        No employees found. Invite someone to get started.
                                    </div>
                                ) : (
                                    <Table>
                                        <TableHeader className="bg-muted/10">
                                            <TableRow className="hover:bg-transparent">
                                                <TableHead className="w-[250px] pl-6">Employee</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead className="text-right pr-6">Joined</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {employees.slice(0, 5).map(emp => (
                                                <TableRow key={emp.id} className="cursor-pointer hover:bg-muted/30">
                                                    <TableCell className="pl-6 py-4">
                                                        <div className="flex items-center gap-3">
                                                            <UserAvatar
                                                                initials={(emp.full_name || emp.email).charAt(0).toUpperCase()}
                                                                shapeId={emp.avatar_url || null}
                                                                className="w-9 h-9"
                                                            />
                                                            <div className="flex flex-col">
                                                                <span className="font-medium text-sm text-foreground">{emp.full_name || emp.email}</span>
                                                                <span className="text-xs text-muted-foreground">{emp.email}</span>
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge className={cn(emp.is_active ? 'bg-primary/10 text-primary border-primary/20' : 'bg-destructive/10 text-destructive border-destructive/20')}>
                                                            {emp.is_active ? 'Active' : 'Inactive'}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-right pr-6 text-sm text-muted-foreground">
                                                        {new Date(emp.created_at).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Training List — Training Creator / Manager */}
                    {(isManager || isCreator) && (
                        <Card className={cn('border-border/50 shadow-sm', !isManager && 'xl:col-span-2')}>
                            <CardHeader className="pb-3 border-b border-border/50">
                                <CardTitle className="text-lg flex items-center">
                                    <BookOpen className="w-5 h-5 mr-2 text-primary" /> Recent Trainings
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-0">
                                {trainings.length === 0 ? (
                                    <div className="p-6 text-center text-muted-foreground text-sm">
                                        No trainings yet. <Button variant="link" className="p-0 h-auto" onClick={() => navigate('/manage/courses')}>Create one?</Button>
                                    </div>
                                ) : (
                                    <div className="divide-y divide-border/50">
                                        {trainings.slice(0, 5).map(t => (
                                            <div key={t.id} className="px-5 py-3 flex items-center justify-between hover:bg-muted/20 transition-colors cursor-pointer group" onClick={() => navigate(`/manage/courses/${t.id}`)}>
                                                <div className="flex flex-col">
                                                    <span className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-1">{t.title}</span>
                                                    <span className="text-xs text-muted-foreground">{t.category || 'General'}</span>
                                                </div>
                                                <Badge className={cn(t.is_published ? 'bg-primary/10 text-primary border-primary/20' : 'bg-muted text-muted-foreground border-border')}>
                                                    {t.is_published ? 'Live' : 'Draft'}
                                                </Badge>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}
        </div>
    );
};
