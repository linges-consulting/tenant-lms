import React, { useState, useEffect, useCallback } from 'react';
import { cn } from '../lib/utils';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
    ChevronLeft,
    Users,
    BookOpen,
    Award,
    Shield,
    ShieldOff,
    ShieldCheck,
    Save,
    Loader2,
    ArrowUpDown,
    Mail,
    UserRound,
    CheckCircle2,
    XCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { tenantService } from '../api/tenants';
import { userService, type User } from '../api/users';
import { UserAvatar } from '../components/UserAvatar';
import type { Tenant } from '../api/auth';

// ---- Helpers ----
function getRoleBadge(m: { is_business_manager: boolean; is_training_creator: boolean }): string {
    if (m.is_business_manager) return 'Manager';
    if (m.is_training_creator) return 'Creator';
    return 'Employee';
}

function roleColor(role: string): string {
    switch (role) {
        case 'Manager': return 'bg-primary/10 text-primary border-0';
        case 'Creator': return 'bg-secondary text-secondary-foreground border-0';
        default: return 'bg-muted text-muted-foreground border-0';
    }
}

// ---- Stat Card ----
interface StatCardProps {
    label: string;
    value: number | string;
    icon: React.ReactNode;
    color: string;
}
const StatCard: React.FC<StatCardProps> = ({ label, value, icon, color }) => (
    <Card className="border-border/50">
        <CardContent className="p-4 flex items-center gap-4">
            <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', color)}>
                {icon}
            </div>
            <div>
                <p className="text-2xl font-bold">{value}</p>
                <p className="text-sm text-muted-foreground">{label}</p>
            </div>
        </CardContent>
    </Card>
);

// ---- Main Page ----
export const TenantSettingsPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();

    const [tenant, setTenant] = useState<Tenant | null>(null);
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState('');

    // Edit form state
    const [name, setName] = useState('');
    const [primaryColor, setPrimaryColor] = useState('#6366f1');
    const [secondaryColor, setSecondaryColor] = useState('#ffffff');
    const [logoUrl, setLogoUrl] = useState('');

    // User table state
    const [userSort, setUserSort] = useState<'name' | 'role' | 'status'>('name');
    const [userSortDir, setUserSortDir] = useState<'asc' | 'desc'>('asc');

    const fetchData = useCallback(async () => {
        if (!id) return;
        setIsLoading(true);
        try {
            const [tenantData, allUsers] = await Promise.all([
                tenantService.getTenant(id),
                userService.listGlobalUsers(),
            ]);
            setTenant(tenantData);
            setName(tenantData.name);
            setPrimaryColor(tenantData.primary_color || '#6366f1');
            setSecondaryColor(tenantData.secondary_color || '#ffffff');
            setLogoUrl(tenantData.logo_url || '');

            // Filter users to those who belong to this tenant
            const tenantUsers = allUsers.filter(u =>
                u.members?.some(m => m.tenant_id === id)
            );
            setUsers(tenantUsers);
        } catch (err) {
            console.error('Failed to load tenant details:', err);
        } finally {
            setIsLoading(false);
        }
    }, [id]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleSave = async () => {
        if (!id) return;
        setIsSaving(true);
        setSaveMessage('');
        try {
            await tenantService.update(id, {
                name,
                primary_color: primaryColor,
                secondary_color: secondaryColor,
                logo_url: logoUrl || undefined,
            });
            setSaveMessage('Settings saved successfully');
            fetchData();
            setTimeout(() => setSaveMessage(''), 3000);
        } catch (err: unknown) {
            setSaveMessage(`Error: ${err instanceof Error ? err.message : 'Failed to save'}`);
        } finally {
            setIsSaving(false);
        }
    };

    const handleToggleActive = async () => {
        if (!id || !tenant) return;
        setIsSaving(true);
        setSaveMessage('');
        try {
            await tenantService.update(id, { is_active: !tenant.is_active });
            setSaveMessage(tenant.is_active ? 'Tenant deactivated' : 'Tenant reactivated');
            fetchData();
            setTimeout(() => setSaveMessage(''), 3000);
        } catch (err: unknown) {
            setSaveMessage(`Error: ${err instanceof Error ? err.message : 'Failed to update status'}`);
        } finally {
            setIsSaving(false);
        }
    };

    const sortUsers = (field: typeof userSort) => {
        if (userSort === field) setUserSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setUserSort(field); setUserSortDir('asc'); }
    };

    const sortedUsers = [...users].sort((a, b) => {
        const membership = (u: User) => u.members?.find(m => m.tenant_id === id);
        let valA: string | number = '';
        let valB: string | number = '';
        if (userSort === 'name') {
            valA = a.full_name?.toLowerCase() || a.email.toLowerCase();
            valB = b.full_name?.toLowerCase() || b.email.toLowerCase();
        } else if (userSort === 'role') {
            valA = getRoleBadge(membership(a) || { is_business_manager: false, is_training_creator: false });
            valB = getRoleBadge(membership(b) || { is_business_manager: false, is_training_creator: false });
        } else if (userSort === 'status') {
            valA = a.is_active ? 1 : 0;
            valB = b.is_active ? 1 : 0;
        }
        if (valA < valB) return userSortDir === 'asc' ? -1 : 1;
        if (valA > valB) return userSortDir === 'asc' ? 1 : -1;
        return 0;
    });

    if (isLoading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    if (!tenant) {
        return (
            <div className="flex h-64 flex-col items-center justify-center gap-4">
                <h2 className="text-2xl font-bold">Tenant Not Found</h2>
                <Button onClick={() => navigate('/admin/tenants')} variant="outline">
                    <ChevronLeft className="mr-2 h-4 w-4" /> Back to Tenants
                </Button>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => navigate('/admin/tenants')}>
                    <ChevronLeft className="h-5 w-5" />
                </Button>
                <div className="flex items-center gap-3 flex-1">
                    <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-lg shadow"
                        style={{ backgroundColor: tenant.primary_color || '#6366f1' }}
                    >
                        {tenant.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">{tenant.name}</h1>
                        <p className="text-sm text-muted-foreground">Tenant Settings & Overview</p>
                    </div>
                </div>
                <Badge
                    variant="secondary"
                    className={tenant.is_active
                        ? 'bg-primary/10 text-primary border-0 text-sm px-3 py-1'
                        : 'bg-destructive/10 text-destructive border-0 text-sm px-3 py-1'}
                >
                    {tenant.is_active ? (
                        <><CheckCircle2 className="inline w-3 h-3 mr-1" />Active</>
                    ) : (
                        <><XCircle className="inline w-3 h-3 mr-1" />Deactivated</>
                    )}
                </Badge>
            </div>

            {/* Stat Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                    label="Members"
                    value={tenant.user_count || users.length}
                    icon={<Users className="w-5 h-5 text-primary" />}
                    color="bg-primary/10"
                />
                <StatCard
                    label="Trainings"
                    value={tenant.course_count || 0}
                    icon={<BookOpen className="w-5 h-5 text-primary" />}
                    color="bg-primary/10"
                />
                <StatCard
                    label="Certificates"
                    value={tenant.certificate_count || 0}
                    icon={<Award className="w-5 h-5 text-foreground" />}
                    color="bg-muted"
                />
                <StatCard
                    label="Status"
                    value={tenant.is_active ? 'Active' : 'Inactive'}
                    icon={<Shield className="w-5 h-5 text-primary" />}
                    color="bg-primary/10"
                />
            </div>

            {/* Main Content Tabs */}
            <Tabs defaultValue="settings" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="settings">Settings</TabsTrigger>
                    <TabsTrigger value="members">Members ({users.length})</TabsTrigger>
                </TabsList>

                {/* ---- Settings Tab ---- */}
                <TabsContent value="settings" className="space-y-4">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Branding */}
                        <div className="lg:col-span-2">
                            <Card className="border-border/50">
                                <CardHeader className="border-b border-border/50">
                                    <CardTitle className="text-base">Branding & Identity</CardTitle>
                                    <CardDescription>Customize how this tenant appears on the platform.</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-5 pt-5">
                                    <div className="space-y-2">
                                        <Label htmlFor="tenantName">Tenant Name</Label>
                                        <Input
                                            id="tenantName"
                                            value={name}
                                            onChange={e => setName(e.target.value)}
                                            placeholder="Organization name"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="logoUrl">Logo URL</Label>
                                        <Input
                                            id="logoUrl"
                                            value={logoUrl}
                                            onChange={e => setLogoUrl(e.target.value)}
                                            placeholder="https://example.com/logo.png"
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <Label htmlFor="primaryColor">Primary Color</Label>
                                            <div className="flex gap-2">
                                                <Input
                                                    type="color"
                                                    id="primaryColor"
                                                    value={primaryColor}
                                                    onChange={e => setPrimaryColor(e.target.value)}
                                                    className="w-12 h-10 p-1 px-2"
                                                />
                                                <Input
                                                    value={primaryColor}
                                                    onChange={e => setPrimaryColor(e.target.value)}
                                                    className="flex-1 uppercase font-mono text-sm"
                                                    maxLength={7}
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label htmlFor="secondaryColor">Secondary Color</Label>
                                            <div className="flex gap-2">
                                                <Input
                                                    type="color"
                                                    id="secondaryColor"
                                                    value={secondaryColor}
                                                    onChange={e => setSecondaryColor(e.target.value)}
                                                    className="w-12 h-10 p-1 px-2"
                                                />
                                                <Input
                                                    value={secondaryColor}
                                                    onChange={e => setSecondaryColor(e.target.value)}
                                                    className="flex-1 uppercase font-mono text-sm"
                                                    maxLength={7}
                                                />
                                            </div>
                                        </div>
                                    </div>

                                    {saveMessage && (
                                        <p className={saveMessage.startsWith('Error') ? 'text-sm text-destructive' : 'text-sm text-foreground'}>
                                            {saveMessage}
                                        </p>
                                    )}

                                    <div className="flex justify-end">
                                        <Button onClick={handleSave} disabled={isSaving || !name.trim()}>
                                            {isSaving
                                                ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                                : <Save className="mr-2 h-4 w-4" />}
                                            Save Changes
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Danger Zone */}
                        <div>
                            <Card className="border-border/50">
                                <CardHeader className="border-b border-border/50">
                                    <CardTitle className="text-base">Tenant Status</CardTitle>
                                    <CardDescription>
                                        {tenant.is_active
                                            ? 'Deactivating prevents all users from accessing this tenant.'
                                            : 'Reactivating restores access for all users.'}
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="pt-5 space-y-4">
                                    {/* Color Preview */}
                                    <div className="rounded-lg overflow-hidden border border-border/50">
                                        <div
                                            className="h-16 flex items-center justify-center text-white font-semibold text-sm"
                                            style={{ backgroundColor: primaryColor }}
                                        >
                                            Primary Accent
                                        </div>
                                        <div
                                            className="h-8 flex items-center justify-center text-xs font-medium"
                                            style={{ backgroundColor: secondaryColor, color: primaryColor }}
                                        >
                                            Secondary
                                        </div>
                                    </div>

                                    <Button
                                        variant={tenant.is_active ? 'destructive' : 'default'}
                                        className={!tenant.is_active ? 'w-full bg-primary hover:bg-primary/90 text-primary-foreground' : 'w-full'}
                                        onClick={handleToggleActive}
                                        disabled={isSaving}
                                    >
                                        {tenant.is_active
                                            ? <><ShieldOff className="mr-2 h-4 w-4" />Deactivate Tenant</>
                                            : <><ShieldCheck className="mr-2 h-4 w-4" />Reactivate Tenant</>}
                                    </Button>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </TabsContent>

                {/* ---- Members Tab ---- */}
                <TabsContent value="members">
                    <Card className="border-border/50">
                        <CardHeader className="border-b border-border/50 pb-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <CardTitle className="text-base">Tenant Members</CardTitle>
                                    <CardDescription>{users.length} user{users.length !== 1 ? 's' : ''} in this organization</CardDescription>
                                </div>
                                <Link to={`/admin/users`}>
                                    <Button variant="outline" size="sm">
                                        <Users className="mr-2 h-4 w-4" />
                                        Manage in User Table
                                    </Button>
                                </Link>
                            </div>
                        </CardHeader>
                        <CardContent className="p-0">
                            <Table>
                                <TableHeader className="bg-muted/50">
                                    <TableRow>
                                        <TableHead className="pl-6">
                                            <button
                                                onClick={() => sortUsers('name')}
                                                className="flex items-center gap-1 hover:text-foreground transition-colors group"
                                            >
                                                User
                                                <ArrowUpDown className={cn('w-3 h-3 transition-opacity', userSort === 'name' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                            </button>
                                        </TableHead>
                                        <TableHead>
                                            <button
                                                onClick={() => sortUsers('role')}
                                                className="flex items-center gap-1 hover:text-foreground transition-colors group"
                                            >
                                                Role
                                                <ArrowUpDown className={cn('w-3 h-3 transition-opacity', userSort === 'role' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                            </button>
                                        </TableHead>
                                        <TableHead>
                                            <button
                                                onClick={() => sortUsers('status')}
                                                className="flex items-center gap-1 hover:text-foreground transition-colors group"
                                            >
                                                Status
                                                <ArrowUpDown className={cn('w-3 h-3 transition-opacity', userSort === 'status' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                            </button>
                                        </TableHead>
                                        <TableHead className="pr-6">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {sortedUsers.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                                                No users in this organization.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        sortedUsers.map(user => {
                                            const membership = user.members?.find(m => m.tenant_id === id);
                                            const role = getRoleBadge(membership || { is_business_manager: false, is_training_creator: false });
                                            const initials = user.full_name
                                                ?.split(' ').map(n => n[0]).join('').toUpperCase() || user.email[0].toUpperCase();
                                            return (
                                                <TableRow key={user.id} className="hover:bg-muted/30">
                                                    <TableCell className="pl-6">
                                                        <div className="flex items-center gap-3">
                                                            <UserAvatar
                                                                initials={initials}
                                                                shapeId={user.avatar_url || null}
                                                                className="w-8 h-8"
                                                            />
                                                            <div>
                                                                <p className="font-medium text-sm">
                                                                    {user.full_name || user.email}
                                                                </p>
                                                                <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                                    <Mail className="w-3 h-3" /> {user.email}
                                                                </p>
                                                                {user.username && (
                                                                    <p className="text-xs text-muted-foreground flex items-center gap-1">
                                                                        <UserRound className="w-3 h-3" /> @{user.username}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="secondary" className={roleColor(role)}>
                                                            {role}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        {user.is_active ? (
                                                            <Badge variant="secondary" className="bg-primary/10 text-primary border-0">Active</Badge>
                                                        ) : (
                                                            <Badge variant="secondary" className="bg-destructive/10 text-destructive border-0">Inactive</Badge>
                                                        )}
                                                    </TableCell>
                                                    <TableCell className="pr-6">
                                                        <Link
                                                            to={`/profile/${user.username || user.id}`}
                                                            className="text-sm text-primary hover:underline"
                                                        >
                                                            View Profile
                                                        </Link>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })
                                    )}
                                </TableBody>
                            </Table>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};
