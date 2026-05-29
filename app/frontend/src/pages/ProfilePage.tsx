import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    User as UserIcon,
    Award,
    BookOpen,
    ChevronLeft,
    Clock,
    Trophy,
    CheckCircle2,
    Loader2,
    AlertCircle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { userService, type User, type UserStats, type UserCertificate } from '../api/users';
import { analyticsApi, type ProfileTrainingItem } from '../api/analytics';
import { useAuth } from '../contexts/auth-context';
import { ProfileCard } from '../components/ProfileCard';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { cn } from '@/lib/utils';

// Helper function to check if currentUser can view the profile
function canViewProfile(currentUser: User | null, profileUser: User, activeTenantId?: string): boolean {
    if (!currentUser) return false;

    // Users can always view their own profile
    if (currentUser.id === profileUser.id) return true;

    // SysAdmins can view any profile
    if (currentUser.is_sysadmin) return true;

    // Find the current user's membership in the active tenant
    const activeMembership = currentUser.members?.find(m => m.tenant_id === activeTenantId);
    if (!activeMembership) return false;

    // Must be a manager or creator to view others' profiles
    if (!activeMembership.is_business_manager && !activeMembership.is_training_creator) return false;

    // Profile user must belong to the same active tenant
    const profileInTenant = profileUser.members?.some(m => m.tenant_id === activeTenantId);
    return Boolean(profileInTenant);
}

export const ProfilePage: React.FC = () => {
    const { username } = useParams<{ username: string }>();
    const navigate = useNavigate();
    const { user: currentUser, activeTenant: currentActiveTenant } = useAuth();
    const [user, setUser] = useState<User | null>(null);
    const [stats, setStats] = useState<UserStats | null>(null);
    const [certificates, setCertificates] = useState<UserCertificate[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [accessDenied, setAccessDenied] = useState(false);

    // Complex Tab System: Selected tenant for filtering
    const [selectedTenantId, setSelectedTenantId] = useState<string | 'global'>('global');

    // Trainings tab state
    const [profileTrainings, setProfileTrainings] = useState<ProfileTrainingItem[]>([]);
    const [loadingTrainings, setLoadingTrainings] = useState(false);

    const handleTrainingsTabActivate = async () => {
        if (!user || loadingTrainings || profileTrainings.length > 0) return;
        setLoadingTrainings(true);
        try {
            const data = await analyticsApi.getProfileHistory(user.id);
            setProfileTrainings(data);
        } catch {
            // silently fail — tab shows empty state
        } finally {
            setLoadingTrainings(false);
        }
    };

    // Edit Name Modal State (Admin Override)
    const [isEditNameOpen, setIsEditNameOpen] = useState(false);
    const [newName, setNewName] = useState('');
    const [editReason, setEditReason] = useState('');
    const [isUpdatingName, setIsUpdatingName] = useState(false);
    const [updateError, setUpdateError] = useState('');

    // Effect: Initial user load
    useEffect(() => {
        const fetchUserData = async () => {
            if (!username) return;
            try {
                const userData = await userService.getUserByUsername(username);

                if (!canViewProfile(currentUser, userData, currentActiveTenant?.id)) {
                    setAccessDenied(true);
                    setIsLoading(false);
                    return;
                }

                setUser(userData);
                setNewName(userData.full_name || '');

                // Set initial tenant context
                if (currentUser?.is_sysadmin) {
                    setSelectedTenantId('global');
                } else {
                    setSelectedTenantId(currentActiveTenant?.id || userData.members?.[0]?.tenant_id || 'global');
                }
            } catch (error) {
                console.error("Failed to fetch user profile data:", error);
            } finally {
                setIsLoading(false);
            }
        };

        fetchUserData();
    }, [username, currentUser, currentActiveTenant]);

    // Effect: Dynamic stats/certs re-fetching based on tenant context
    useEffect(() => {
        const fetchContextData = async () => {
            if (!user) return;
            
            try {
                const tenantParam = selectedTenantId === 'global' ? undefined : selectedTenantId;
                const [statsData, certsData] = await Promise.all([
                    userService.getUserStats(user.id, tenantParam),
                    userService.getUserCertificates(user.id, tenantParam)
                ]);
                setStats(statsData);
                setCertificates(certsData);
            } catch (error) {
                console.error("Failed to fetch context-specific data:", error);
            } finally {
                setIsLoading(false); // Using main isLoading instead or just removing the finally block if already handled
            }
        };

        if (user) {
            fetchContextData();
        }
    }, [user, selectedTenantId]);

    if (isLoading) {
        return (
            <div className="flex h-[400px] items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            </div>
        );
    }

    if (accessDenied) {
        return (
            <div className="flex h-[400px] flex-col items-center justify-center space-y-4">
                <h2 className="text-2xl font-bold">Access Denied</h2>
                <p className="text-muted-foreground">You don't have permission to view this profile.</p>
                <Button onClick={() => navigate(-1)} variant="outline">
                    <ChevronLeft className="mr-2 h-4 w-4" />
                    Go Back
                </Button>
            </div>
        );
    }

    if (!user) {
        return (
            <div className="flex h-[400px] flex-col items-center justify-center space-y-4">
                <h2 className="text-2xl font-bold">User Not Found</h2>
                <Button onClick={() => navigate(-1)} variant="outline">
                    <ChevronLeft className="mr-2 h-4 w-4" />
                    Go Back
                </Button>
            </div>
        );
    }

    const handleUpdateName = async () => {
        if (!newName.trim() || !editReason.trim()) {
            setUpdateError('Name and reasoning are required.');
            return;
        }

        setIsUpdatingName(true);
        setUpdateError('');
        try {
            const updatedUser = await userService.updateUserNameAdmin(user.id, newName, editReason);
            setUser(updatedUser);
            setIsEditNameOpen(false);
            setEditReason('');
        } catch (err: unknown) {
            setUpdateError(err instanceof Error ? err.message : 'Failed to update name.');
        } finally {
            setIsUpdatingName(false);
        }
    };

    return (
        <div className="space-y-6 max-w-6xl">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <UserIcon className="w-6 h-6 text-primary" />
                    </div>
                    {user?.full_name ?? 'Profile'}
                </h1>
            </div>

            <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
                {/* Left Column: Profile Card & Stats Overview */}
                <div className="space-y-6">
                    <ProfileCard
                        user={user}
                        isViewOnly={true}
                        activeTenantId={selectedTenantId === 'global' ? user.members?.[0]?.tenant_id : selectedTenantId}
                    />

                    <Card>
                        <CardHeader>
                            <CardTitle className="text-lg">Stats Overview</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex justify-between items-center">
                                <div className="flex items-center text-sm font-medium">
                                    <BookOpen className="mr-2 h-4 w-4 text-primary" />
                                    Courses
                                </div>
                                <span className="font-bold">{stats?.total_enrollments || 0}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <div className="flex items-center text-sm font-medium">
                                    <Trophy className="mr-2 h-4 w-4 text-muted-foreground" />
                                    Completed
                                </div>
                                <span className="font-bold text-primary">{stats?.completed_courses || 0}</span>
                            </div>
                            <div className="flex justify-between items-center">
                                <div className="flex items-center text-sm font-medium">
                                    <Clock className="mr-2 h-4 w-4 text-muted-foreground" />
                                    In Progress
                                </div>
                                <span className="font-bold text-muted-foreground">{stats?.in_progress_courses || 0}</span>
                            </div>
                            <div className="pt-2">
                                {(() => {
                                    const rate = stats && stats.total_enrollments > 0
                                        ? Math.round((stats.completed_courses / stats.total_enrollments) * 100)
                                        : 0;
                                    return (
                                        <>
                                            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                                                <span>Overall Completion</span>
                                                <span>{rate}%</span>
                                            </div>
                                            <Progress value={rate} className="h-2" />
                                        </>
                                    );
                                })()}
                            </div>
                        </CardContent>
                    </Card>

                    {currentUser?.is_sysadmin && (
                        <Card className="border-primary/10 bg-primary/5">
                            <CardHeader className="pb-2">
                                <CardTitle className="text-sm font-medium text-foreground">Admin Actions</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="w-full bg-background border-primary/20 text-primary hover:bg-primary/10"
                                    onClick={() => setIsEditNameOpen(true)}
                                >
                                    Force Name Update
                                </Button>
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Right Column: Detailed Info & Stats */}
                <div className="md:col-span-2 space-y-6">
                    <Tabs defaultValue="overview">
                        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-2">
                            <TabsList className="justify-start border-b rounded-none bg-transparent h-12 p-0 space-x-8">
                                <TabsTrigger
                                    value="overview"
                                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-0 h-12 font-semibold"
                                >
                                    Overview
                                </TabsTrigger>
                                <TabsTrigger
                                    value="certificates"
                                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-0 h-12 font-semibold"
                                >
                                    Certificates
                                </TabsTrigger>
                                <TabsTrigger
                                    value="activity"
                                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-0 h-12 font-semibold"
                                >
                                    Activity
                                </TabsTrigger>
                                <TabsTrigger
                                    value="trainings"
                                    onClick={handleTrainingsTabActivate}
                                    className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent px-0 h-12 font-semibold"
                                >
                                    Trainings
                                </TabsTrigger>
                            </TabsList>

                            {/* Complex Tab System: Tenant Selector for SysAdmins */}
                            {currentUser?.is_sysadmin && user.members && user.members.length > 1 && (
                                <div className="mt-4 sm:mt-0 flex items-center gap-2">
                                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Viewing Context:</span>
                                    <div className="flex bg-muted/50 p-1 rounded-lg border border-border/50">
                                        <button 
                                            onClick={() => setSelectedTenantId('global')}
                                            className={cn('px-3 py-1 text-xs font-medium rounded-md transition-all', selectedTenantId === 'global' ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground')}
                                        >
                                            Global
                                        </button>
                                        {user.members.map(m => (
                                            <button 
                                                key={m.tenant_id}
                                                onClick={() => setSelectedTenantId(m.tenant_id)}
                                                className={cn('px-3 py-1 text-xs font-medium rounded-md transition-all truncate max-w-[120px]', selectedTenantId === m.tenant_id ? 'bg-background shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground')}
                                            >
                                                {m.tenant?.name || 'Tenant'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        <TabsContent value="overview" className="pt-6 space-y-6">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <Card>
                                    <CardHeader className="pb-2">
                                        <CardDescription>Trainings Enrolled</CardDescription>
                                        <CardTitle className="text-3xl">{stats?.total_enrollments || 0}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-xs text-muted-foreground flex items-center">
                                            <Badge className="mr-2 bg-muted text-muted-foreground border-none">Total Count</Badge>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardHeader className="pb-2">
                                        <CardDescription>Completed Trainings</CardDescription>
                                        <CardTitle className="text-3xl">{stats?.completed_courses || 0}</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-xs text-muted-foreground flex items-center">
                                            <Badge className="mr-2 bg-primary/10 text-primary border-none">Certificates</Badge>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>

                            <Card>
                                <CardHeader>
                                    <CardTitle>In Progress Trainings</CardTitle>
                                    <CardDescription>{stats?.in_progress_courses || 0} active enrollments</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    {stats && stats.in_progress_courses > 0 ? (
                                        <div className="space-y-4">
                                            <p className="text-sm text-muted-foreground">
                                                This user is actively enrolled in {stats.in_progress_courses} course{stats.in_progress_courses !== 1 ? 's' : ''}.
                                            </p>
                                            <div className="flex items-center justify-center h-20 border border-dashed rounded-lg bg-muted/30">
                                                <p className="text-sm text-muted-foreground">
                                                    See the <button onClick={handleTrainingsTabActivate} className="underline text-primary">Trainings tab</button> for full history.
                                                </p>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center h-20 border border-dashed rounded-lg bg-muted/30">
                                            <p className="text-sm text-muted-foreground">No courses in progress</p>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="certificates" className="pt-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Earned Certificates</CardTitle>
                                    <CardDescription>
                                        {currentUser?.is_sysadmin ? 'Viewing all user certificates' : 'Your latest earned certificates'}
                                    </CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        {certificates.length > 0 ? (
                                            certificates.map((cert) => (
                                                <div key={cert.id} className="flex items-center p-4 border rounded-lg space-x-4 bg-muted/30">
                                                    <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center flex-shrink-0">
                                                        <Award className="h-6 w-6 text-primary" />
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <p className="font-semibold text-sm truncate">{cert.training_title}</p>
                                                        <p className="text-xs text-muted-foreground">Issued {new Date(cert.completed_at).toLocaleDateString()}</p>
                                                    </div>
                                                    <CheckCircle2 className="h-4 w-4 text-primary" />
                                                </div>
                                            ))
                                        ) : (
                                            <div className="col-span-full py-8 text-center text-muted-foreground italic">
                                                No certificates earned yet.
                                            </div>
                                        )}
                                    </div>
                                    {currentUser?.is_sysadmin && certificates.length > 0 && (
                                        <Button variant="outline" className="mt-6 w-full">
                                            View Full Archive
                                        </Button>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="activity" className="pt-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Recent Activity</CardTitle>
                                    <CardDescription>Latest enrollments and completions</CardDescription>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex items-center justify-center h-32 border border-dashed rounded-lg bg-muted/30">
                                        <p className="text-sm text-muted-foreground">Activity tracking coming soon</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="trainings" className="pt-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Training History</CardTitle>
                                    <CardDescription>All assigned trainings and their completion status</CardDescription>
                                </CardHeader>
                                <CardContent className="p-0">
                                    {loadingTrainings ? (
                                        <div className="p-8 flex justify-center">
                                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : profileTrainings.length === 0 ? (
                                        <div className="p-8 text-center text-muted-foreground text-sm italic">
                                            No trainings assigned.
                                        </div>
                                    ) : (
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Training</TableHead>
                                                    <TableHead>Category</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Due Date</TableHead>
                                                    <TableHead>Completed</TableHead>
                                                    <TableHead>Quizzes</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {profileTrainings.map((t: ProfileTrainingItem) => (
                                                    <TableRow key={t.training_id}>
                                                        <TableCell className="font-medium">{t.title}</TableCell>
                                                        <TableCell className="text-muted-foreground text-sm">{t.category}</TableCell>
                                                        <TableCell>
                                                            <Badge className={cn({
                                                                'bg-primary/10 text-primary border-primary/20': t.status === 'completed',
                                                                'bg-blue-500/10 text-blue-600 border-blue-500/20': t.status === 'in_progress',
                                                                'bg-destructive/10 text-destructive border-destructive/20': t.status === 'overdue',
                                                                'bg-muted text-muted-foreground border-border': t.status === 'not_started',
                                                            })}>
                                                                {{ completed: 'Completed', in_progress: 'In Progress', overdue: 'Overdue', not_started: 'Not Started' }[t.status]}
                                                            </Badge>
                                                        </TableCell>
                                                        <TableCell className="text-sm text-muted-foreground">
                                                            {t.due_date ? new Date(t.due_date).toLocaleDateString() : '—'}
                                                        </TableCell>
                                                        <TableCell className="text-sm text-muted-foreground">
                                                            {t.completed_at ? new Date(t.completed_at).toLocaleDateString() : '—'}
                                                        </TableCell>
                                                        <TableCell className="text-sm text-muted-foreground">
                                                            {t.quiz_total > 0 ? `${t.quiz_passed}/${t.quiz_total} passed` : '—'}
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>
                    </Tabs>
                </div>
            </div>

            {/* Edit Name Modal (SysAdmin only) */}
            <Dialog open={isEditNameOpen} onOpenChange={setIsEditNameOpen}>
                <DialogContent className="sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>Update User Name</DialogTitle>
                        <DialogDescription>
                            As a SysAdmin, you are updating the name of <strong>{user.email}</strong>.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="full-name">Full Name</Label>
                            <Input
                                id="full-name"
                                value={newName}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setNewName(e.target.value)}
                                placeholder="Enter full name"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="reason">Reasoning</Label>
                            <Textarea
                                id="reason"
                                value={editReason}
                                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setEditReason(e.target.value)}
                                placeholder="Provide a reason for this administrative update..."
                                className="min-h-[100px]"
                            />
                        </div>
                        {updateError && (
                            <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-2 rounded">
                                <AlertCircle className="h-4 w-4" />
                                {updateError}
                            </div>
                        )}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsEditNameOpen(false)} disabled={isUpdatingName}>
                            Cancel
                        </Button>
                        <Button onClick={handleUpdateName} disabled={isUpdatingName}>
                            {isUpdatingName && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Update Name
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
