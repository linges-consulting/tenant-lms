import React, { useState } from 'react';
import { cn } from '../lib/utils';
import { useNavigate } from 'react-router-dom';
import { Badge } from './ui/badge';
import { UserInviteDialog } from './UserInviteDialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from './ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { UserAvatar } from './UserAvatar';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from './ui/dropdown-menu';
import {
    MoreVertical,
    ChevronLeft,
    ChevronRight,
    UserRound,
    ShieldOff,
    Shield,
    Loader2,
    PlusCircle,
    ArrowUpDown,
    Trash2,
    Mail,
    Settings2,
} from 'lucide-react';
import { userService, type User } from '../api/users';
import { authService, type Tenant } from '../api/auth';
import { TokenDisplayModal } from './TokenDisplayModal';
import { useAuth } from '../contexts/auth-context';

export type UserTableMode = 'sysadmin' | 'manager';

export interface UserTableProps {
    users: User[];
    isLoading: boolean;
    mode: UserTableMode;
    /** For manager mode — the active tenant */
    activeTenantId?: string;
    activeTenantName?: string;
    onRefresh: () => void;
}

const PAGE_SIZES = [10, 25, 50];

// ---- Role helpers ----
function getRoleLabels(user: User | undefined, activeTenantId: string | undefined): string[] {
    // SysAdmin exclusivity: if the user is a sysadmin, we don't show tenant roles
    if (user?.is_sysadmin) return ['SysAdmin'];
    if (!user?.members) return [];

    // Find membership for active tenant context - dash-agnostic matching
    const targetId = String(activeTenantId || '').replace(/-/g, '').toLowerCase().trim();
    let membership = user.members.find((m) =>
        String(m.tenant_id).replace(/-/g, '').toLowerCase().trim() === targetId
    );

    // Defensive fallback: if activeTenantId is missing or match fails,
    // try to find ANY membership that has a specialized role (Manager/Creator)
    if (!membership && (!activeTenantId || activeTenantId === '')) {
        membership = user.members.find((m) => m.is_business_manager || m.is_training_creator);
    }

    const m = membership || user.members[0];
    if (!m) return ['Employee'];

    const roles: string[] = [];
    
    // Aggressive check: snake_case, camelCase, and role string from computed field
    const isManager = m.is_business_manager || m.role === 'Business Manager' || m.role === 'Manager';
    const isCreator = m.is_training_creator || m.role === 'Training Creator' || m.role === 'Creator';
    const isEmployee = m.is_employee || m.role === 'Employee';

    if (isManager) roles.push('Manager');
    if (isCreator) roles.push('Creator');
    
    // Fallback: if the user object itself has a role matching ours (e.g. from a different serialization path)
    if (roles.length === 0 && user.role) {
        if (user.role === 'Business Manager' || user.role === 'Manager') roles.push('Manager');
        else if (user.role === 'Training Creator' || user.role === 'Creator') roles.push('Creator');
    }
    
    // Fallback to Employee if no other roles OR if explicitly marked as Employee
    if (roles.length === 0 || isEmployee) {
        roles.push('Employee');
    }
    
    return roles;
}

function getRoleBadgeStyle(label: string): string {
    const l = label.toLowerCase();
    if (l.includes('manager')) return 'bg-primary/10 text-primary border-primary/20 shadow-sm';
    if (l.includes('creator')) return 'bg-secondary text-secondary-foreground border-border/60 shadow-sm';
    if (l.includes('employee')) return 'bg-muted text-muted-foreground border-border/60 shadow-sm';
    if (l.includes('sysadmin')) return 'bg-primary/10 text-primary border-primary/20 shadow-sm';
    return 'bg-muted text-muted-foreground border-border/60 shadow-sm';
}

// ---- Modify Role Modal ----
interface ModifyRoleModalProps {
    user: User;
    tenantId: string;
    tenantName: string;
    onClose: () => void;
    onSaved: () => void;
}
const ModifyRoleModal: React.FC<ModifyRoleModalProps> = ({ user, tenantId, tenantName, onClose, onSaved }) => {
    const membership = user.members?.find(m => m.tenant_id === tenantId);
    const [isManager, setIsManager] = useState(membership?.is_business_manager ?? false);
    const [isCreator, setIsCreator] = useState(membership?.is_training_creator ?? false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    const handleSave = async () => {
        setIsSaving(true);
        setError('');
        try {
            await userService.modifyUserRole(user.id, {
                tenant_id: tenantId,
                is_business_manager: isManager,
                is_training_creator: isCreator,
            });
            onSaved();
            onClose();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to update role.');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Modify Role</DialogTitle>
                    <DialogDescription className="sr-only">Change the role of the selected user</DialogDescription>
                    <DialogDescription>
                        Set role flags for <strong>{user.full_name || user.email}</strong> in <strong>{tenantName}</strong>.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                    <label className="flex items-center gap-3 p-3 rounded-md border border-border hover:bg-muted/30 cursor-pointer">
                        <input type="checkbox" checked={isManager} onChange={e => setIsManager(e.target.checked)} className="h-4 w-4 accent-primary" />
                        <div>
                            <p className="font-medium text-sm">Business Manager</p>
                            <p className="text-xs text-muted-foreground">Can manage users and view reports</p>
                        </div>
                    </label>
                    <label className="flex items-center gap-3 p-3 rounded-md border border-border hover:bg-muted/30 cursor-pointer">
                        <input type="checkbox" checked={isCreator} onChange={e => setIsCreator(e.target.checked)} className="h-4 w-4 accent-primary" />
                        <div>
                            <p className="font-medium text-sm">Training Creator</p>
                            <p className="text-xs text-muted-foreground">Can create and manage courses</p>
                        </div>
                    </label>
                    {!isManager && !isCreator && (
                        <p className="text-xs text-muted-foreground px-1">
                            ℹ️ User will have base Employee access — can view assigned courses only.
                        </p>
                    )}
                    {error && <p className="text-sm text-destructive">{error}</p>}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Save Changes
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Admin Modify Role Modal ----
interface AdminModifyRoleModalProps {
    user: User;
    presetTenantId?: string;
    presetTenantName?: string;
    onClose: () => void;
    onSaved: () => void;
}
const AdminModifyRoleModal: React.FC<AdminModifyRoleModalProps> = ({ user, presetTenantId, presetTenantName, onClose, onSaved }) => {
    const hasPreset = !!presetTenantId;
    const existingMembership = presetTenantId ? user.members?.find(m => m.tenant_id === presetTenantId) : undefined;

    const [isManager, setIsManager] = useState(existingMembership?.is_business_manager ?? false);
    const [isCreator, setIsCreator] = useState(existingMembership?.is_training_creator ?? false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    const handleSave = async () => {
        if (!presetTenantId) return;
        setIsSaving(true); setError('');
        try {
            const isExistingMember = user.members?.some(m => m.tenant_id === presetTenantId);
            if (isExistingMember) {
                await userService.modifyUserRole(user.id, {
                    tenant_id: presetTenantId,
                    is_business_manager: isManager,
                    is_training_creator: isCreator,
                });
            } else {
                await userService.adminInviteToTenant({
                    email: user.email,
                    tenant_id: presetTenantId,
                    is_business_manager: isManager,
                    is_training_creator: isCreator,
                });
            }
            onSaved();
            onClose();
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : 'Failed to update role.';
            setError(msg);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Modify Role</DialogTitle>
                    <DialogDescription className="sr-only">Update user roles for the selected tenant</DialogDescription>
                    <DialogDescription>
                        Set role flags for <strong>{user.full_name || user.email}</strong>
                        {hasPreset && presetTenantName && <> in <strong>{presetTenantName}</strong></>}.
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                    <label className="flex items-center gap-3 p-3 rounded-md border border-border hover:bg-muted/30 cursor-pointer">
                        <input type="checkbox" checked={isManager} onChange={e => setIsManager(e.target.checked)} className="h-4 w-4 accent-primary" />
                        <div>
                            <p className="font-medium text-sm">Business Manager</p>
                            <p className="text-xs text-muted-foreground">Can manage users and view reports</p>
                        </div>
                    </label>
                    <label className="flex items-center gap-3 p-3 rounded-md border border-border hover:bg-muted/30 cursor-pointer">
                        <input type="checkbox" checked={isCreator} onChange={e => setIsCreator(e.target.checked)} className="h-4 w-4 accent-primary" />
                        <div>
                            <p className="font-medium text-sm">Training Creator</p>
                            <p className="text-xs text-muted-foreground">Can create and manage courses</p>
                        </div>
                    </label>
                    {!isManager && !isCreator && (
                        <p className="text-xs text-muted-foreground px-1">
                            User will have base Employee access in this tenant.
                        </p>
                    )}
                    {error && <p className="text-sm text-destructive">{error}</p>}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Save Changes
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};


// ---- View Profile Modal ----
interface ViewProfileModalProps {
    user: User;
    mode: UserTableMode;
    onClose: () => void;
}
const ViewProfileModal: React.FC<ViewProfileModalProps> = ({ user, mode, onClose }) => {

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>User Profile</DialogTitle>
                    <DialogDescription className="sr-only">View full profile details of the user</DialogDescription>
                </DialogHeader>
                <div className="flex flex-col items-center gap-4 py-4">
                    <UserAvatar
                        initials={(user.full_name || user.email).charAt(0).toUpperCase()}
                        shapeId={user.avatar_url || null}
                        className="w-20 h-20"
                        variant="rounded-square"
                    />
                    <div className="text-center">
                        <h3 className="text-lg font-semibold">{user.full_name || 'Anonymous User'}</h3>
                        <p className="text-sm text-muted-foreground">{user.email}</p>
                    </div>

                    <div className="w-full space-y-4 mt-4 border-t border-border pt-4">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <p className="text-muted-foreground mb-1">Status</p>
                                <Badge className={user.is_active ? 'border-0 bg-primary/10 text-primary' : 'border-0 bg-destructive/10 text-destructive'}>
                                    {user.is_active ? 'Active' : 'Inactive'}
                                </Badge>
                            </div>
                            <div>
                                <p className="text-muted-foreground mb-1">Joined</p>
                                <p className="font-medium">{new Date(user.created_at).toLocaleDateString()}</p>
                            </div>
                        </div>

                        <div>
                            <p className="text-muted-foreground mb-2 text-sm">Roles & Tenants</p>
                            <div className="space-y-2">
                                {user.is_sysadmin && (
                                    <Badge className="bg-primary/10 text-primary border-primary/20">SYSADMIN</Badge>
                                )}
                                {user.members?.map(m => {
                                    const roles = getRoleLabels(m as unknown as User, m.tenant_id);
                                    return (
                                        <div key={m.tenant_id} className="flex justify-between items-center bg-muted/30 p-2 rounded border border-border">
                                            <span className="text-sm truncate w-1/2">{m.tenant?.name || m.tenant_id}</span>
                                            <div className="flex gap-1">
                                                {roles.length > 0 ? roles.map(role => (
                                                    <Badge key={role} className={cn('border text-[10px]', getRoleBadgeStyle(role))}>{role}</Badge>
                                                )) : (
                                                    <span className="text-[10px] text-muted-foreground uppercase font-bold italic">Employee</span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {mode === 'manager' && user.groups && user.groups.length > 0 && (
                            <div>
                                <p className="text-muted-foreground mb-2 text-sm">Groups</p>
                                <div className="flex flex-wrap gap-2">
                                    {user.groups.map(g => (
                                        <span key={g} className="px-2 py-1 text-xs rounded bg-muted border border-border text-muted-foreground">{g}</span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
                <DialogFooter>
                    <Button onClick={onClose}>Close</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Main UserTable ----
type SortField = 'name' | 'username' | 'email' | 'role' | 'status' | 'joined' | 'tenant';

export const UserTable: React.FC<UserTableProps> = ({
    users,
    isLoading,
    mode,
    activeTenantId,
    activeTenantName,
    onRefresh,
}) => {
    const navigate = useNavigate();
    const { user: currentUser } = useAuth();

    // State
    const [searchTerm, setSearchTerm] = useState('');
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [sortField, setSortField] = useState<SortField>('name');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
    const [roleFilter, setRoleFilter] = useState('all');
    const [statusFilter, setStatusFilter] = useState('all');
    const [tenantFilter, setTenantFilter] = useState('all');
    const [joinedAfter, setJoinedAfter] = useState('');
    const [joinedBefore, setJoinedBefore] = useState('');
    const [allTenants, setAllTenants] = useState<Tenant[]>([]);

    const [showAddUser, setShowAddUser] = useState(false);
    const [confirmDeactivate, setConfirmDeactivate] = useState<User | null>(null);
    const [confirmReactivate, setConfirmReactivate] = useState<User | null>(null);
    const [confirmReset, setConfirmReset] = useState<User | null>(null);
    const [confirmDelete, setConfirmDelete] = useState<User | null>(null);
    const [tokenDisplayTarget, setTokenDisplayTarget] = useState<User | null>(null);
    const [showTokenDisplay, setShowTokenDisplay] = useState(false);
    const [viewingProfile, setViewingProfile] = useState<User | null>(null);
    const [actionLoading, setActionLoading] = useState(false);
    const [actionMessage, setActionMessage] = useState('');
    const [selectedActionTenantId, setSelectedActionTenantId] = useState<string>('');

    // Role Modification State
    const [showModifyRole, setShowModifyRole] = useState(false);
    const [modifyRoleTarget, setModifyRoleTarget] = useState<User | null>(null);
    const [modifyRoleTenantId, setModifyRoleTenantId] = useState('');
    const [modifyRoleTenantName, setModifyRoleTenantName] = useState('');

    React.useEffect(() => {
        if (mode === 'sysadmin') {
            authService.getAllTenants().then(setAllTenants).catch(() => { });
        }
    }, [mode]);

    // Reset page on filter changes
    React.useEffect(() => { setPage(1); }, [searchTerm, pageSize, roleFilter, statusFilter, tenantFilter, joinedAfter, joinedBefore]);

    const handleSort = (field: SortField) => {
        if (sortField === field) {
            setSortDirection(d => d === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('asc');
        }
    };

    // Filter logic
    const filtered = users.filter(u => {

        const q = searchTerm.toLowerCase();
        const matchesSearch = !searchTerm || (
            u.full_name?.toLowerCase().includes(q) ||
            u.username?.toLowerCase().includes(q) ||
            u.email.toLowerCase().includes(q) ||
            u.members?.some(m => m.tenant?.name?.toLowerCase().includes(q))
        );
        if (!matchesSearch) return false;

        if (statusFilter !== 'all') {
            if (u.is_active !== (statusFilter === 'active')) return false;
        }

        if (roleFilter !== 'all') {
            if (roleFilter === 'sysadmin') {
                if (!u.is_sysadmin) return false;
            } else {
                const relevantMembers = mode === 'manager'
                    ? u.members?.filter(m => m.tenant_id === activeTenantId)
                    : u.members;
                if (!relevantMembers || relevantMembers.length === 0) return false;
                if (roleFilter === 'manager' && !relevantMembers.some(m => m.is_business_manager)) return false;
                if (roleFilter === 'creator' && !relevantMembers.some(m => m.is_training_creator)) return false;
                if (roleFilter === 'employee' && !relevantMembers.some(m => m.is_employee)) return false;
            }
        }

        if (mode === 'sysadmin' && tenantFilter !== 'all') {
            if (!u.members?.some(m => m.tenant_id === tenantFilter)) return false;
        }

        if (joinedAfter && new Date(u.created_at) < new Date(joinedAfter)) return false;
        if (joinedBefore) {
            const bDate = new Date(joinedBefore);
            bDate.setHours(23, 59, 59, 999);
            if (new Date(u.created_at) > bDate) return false;
        }

        return true;
    });

    // Sort logic
    const sorted = [...filtered].sort((a, b) => {
        let valA: string | number = '';
        let valB: string | number = '';
        switch (sortField) {
            case 'name': valA = a.full_name || a.email; valB = b.full_name || b.email; break;
            case 'email': valA = a.email; valB = b.email; break;
            case 'username': valA = a.username || ''; valB = b.username || ''; break;
            case 'status': valA = a.is_active ? 1 : 0; valB = b.is_active ? 1 : 0; break;
            case 'joined':
                valA = new Date(a.created_at).getTime();
                valB = new Date(b.created_at).getTime();
                break;
            case 'role':
                valA = getRoleLabels(a, activeTenantId).join(', ');
                valB = getRoleLabels(b, activeTenantId).join(', ');
                break;
            case 'tenant':
                valA = a.members?.[0]?.tenant?.name || '';
                valB = b.members?.[0]?.tenant?.name || '';
                break;
        }
        if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    const totalPages = Math.ceil(sorted.length / pageSize);
    const paginated = sorted.slice((page - 1) * pageSize, page * pageSize);

    // Flatten data for display
    const displayRows = React.useMemo(() => {
        if (mode === 'manager') {
            return paginated.map(user => {
                // Robust UUID matching (remove dashes, trim, lower)
                const targetId = String(activeTenantId || '').replace(/-/g, '').toLowerCase().trim();
                let membership = user.members?.find(m => 
                    String(m.tenant_id).replace(/-/g, '').toLowerCase().trim() === targetId
                );
                
                // Fallback: search for any membership with management roles if specific catch fails
                if (!membership && user.members && user.members.length > 0) {
                    membership = user.members.find(m => m.is_business_manager || m.is_training_creator) || user.members[0];
                }

                const tenant = membership?.tenant ? { id: membership.tenant_id, name: membership.tenant.name } : (membership ? { id: membership.tenant_id, name: 'Current' } : null);
                return {
                    user,
                    membership,
                    tenant,
                    isFirstInGroup: true,
                    rowSpan: 1
                };
            });
        } else {
            const rows: { user: User; membership: typeof paginated[number]['members'][number] | null; tenant: { id?: string; name?: string } | undefined; isFirstInGroup: boolean; rowSpan: number }[] = [];
            paginated.forEach(user => {
                // Sysadmin mode - flatten tenants
                const memberships = user.members && user.members.length > 0 ? user.members : [null];
                memberships.forEach((m, idx) => {
                    rows.push({
                        user,
                        membership: m,
                        tenant: m?.tenant,
                        isFirstInGroup: idx === 0,
                        rowSpan: memberships.length
                    });
                });
            });
            return rows;
        }
    }, [paginated, mode, activeTenantId]);

    const columnsCount = mode === 'sysadmin' ? 7 : 6;

    const handleDeactivateClick = (u: User, tenantId?: string) => {
        setConfirmDeactivate(u);
        if (tenantId) {
            setSelectedActionTenantId(tenantId);
        } else if (mode === 'manager' && activeTenantId) {
            setSelectedActionTenantId(activeTenantId);
        } else if (mode === 'sysadmin' && u.members?.length > 0) {
            setSelectedActionTenantId(u.members[0].tenant_id);
        } else {
            setSelectedActionTenantId('');
        }
    };

    const handleReactivateClick = (u: User, tenantId?: string) => {
        setConfirmReactivate(u);
        if (tenantId) {
            setSelectedActionTenantId(tenantId);
        } else if (mode === 'manager' && activeTenantId) {
            setSelectedActionTenantId(activeTenantId);
        } else if (mode === 'sysadmin' && u.members?.length > 0) {
            setSelectedActionTenantId(u.members[0].tenant_id);
        } else {
            setSelectedActionTenantId('');
        }
    };

    const doDeactivate = async () => {
        if (!confirmDeactivate) return;
        setActionLoading(true);
        try {
            await userService.deactivateUser(confirmDeactivate.id, selectedActionTenantId || undefined);
            onRefresh();
            setConfirmDeactivate(null);
            setActionMessage('User deactivated successfully.');
            setTimeout(() => setActionMessage(''), 4000);
        } catch { setActionMessage('Failed to deactivate user.'); } finally { setActionLoading(false); }
    };

    const doReactivate = async () => {
        if (!confirmReactivate) return;
        setActionLoading(true);
        try {
            await userService.reactivateUser(confirmReactivate.id, selectedActionTenantId || undefined);
            onRefresh();
            setConfirmReactivate(null);
            setActionMessage('User reactivated successfully.');
            setTimeout(() => setActionMessage(''), 4000);
        } catch { setActionMessage('Failed to reactivate user.'); } finally { setActionLoading(false); }
    };

    const doResetPassword = async () => {
        if (!confirmReset) return;
        setActionLoading(true);
        try {
            await userService.resetPassword(confirmReset.id);
            setConfirmReset(null);
            setActionMessage('Password reset link sent.');
            setTimeout(() => setActionMessage(''), 4000);
        } catch { setActionMessage('Failed to send password reset.'); } finally { setActionLoading(false); }
    };

    const handleDeleteClick = (u: User, tenantId?: string) => {
        setConfirmDelete(u);
        if (tenantId) {
            setSelectedActionTenantId(tenantId);
        } else if (mode === 'manager' && activeTenantId) {
            setSelectedActionTenantId(activeTenantId);
        } else if (mode === 'sysadmin' && u.members?.length > 0) {
            // Default to first tenant if none provided (shouldn't happen in flattened row but safe fallback)
            setSelectedActionTenantId(u.members[0].tenant_id);
        } else {
            setSelectedActionTenantId('');
        }
    };

    const doDeleteUser = async () => {
        if (!confirmDelete) return;
        setActionLoading(true);
        try {
            await userService.deleteUser(confirmDelete.id, selectedActionTenantId || undefined);
            onRefresh();
            setConfirmDelete(null);
            setActionMessage('User deleted successfully.');
            setTimeout(() => setActionMessage(''), 4000);
        } catch { setActionMessage('Failed to delete user.'); } finally { setActionLoading(false); }
    };

    const hasActiveFilters = searchTerm || statusFilter !== 'all' || roleFilter !== 'all' || tenantFilter !== 'all' || joinedAfter || joinedBefore;

    return (
        <div className="space-y-4">
            {actionMessage && (
                <div className={actionMessage.includes('Failed') ? 'text-sm px-3 py-2 rounded-md border text-destructive bg-destructive/10 border-destructive/30' : 'text-sm px-3 py-2 rounded-md border text-foreground bg-muted border-border'}>
                    {actionMessage}
                </div>
            )}

            {/* Header Row: Search + Filters + Action Button */}
            <div className="flex flex-col gap-3">
                <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                    {/* Search */}
                    <form 
                        className="relative flex-1 sm:max-w-sm" 
                        onSubmit={(e) => e.preventDefault()}
                        autoComplete="off"
                    >
                        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                        <Input
                            placeholder="Search users..."
                            className="pl-9 h-10 bg-muted/30"
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            autoComplete="one-time-code"
                            data-lpignore="true"
                            data-form-type="search"
                            spellCheck="false"
                            name={`search_${Math.random().toString(36).substring(7)}`}
                        />
                    </form>

                    {/* Filters inline with header */}
                    <div className="flex flex-wrap items-center gap-2">
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="h-9 w-[110px] text-xs bg-muted/30">
                                <SelectValue placeholder="Status" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Status</SelectItem>
                                <SelectItem value="active">Active</SelectItem>
                                <SelectItem value="inactive">Inactive</SelectItem>
                            </SelectContent>
                        </Select>

                        <Select value={roleFilter} onValueChange={setRoleFilter}>
                            <SelectTrigger className="h-9 w-[110px] text-xs bg-muted/30">
                                <SelectValue placeholder="Role" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">All Roles</SelectItem>
                                <SelectItem value="manager">Manager</SelectItem>
                                <SelectItem value="creator">Creator</SelectItem>
                                <SelectItem value="employee">Employee</SelectItem>
                                {mode === 'sysadmin' && <SelectItem value="sysadmin">SysAdmin</SelectItem>}
                            </SelectContent>
                        </Select>

                        {mode === 'sysadmin' && (
                            <Select value={tenantFilter} onValueChange={setTenantFilter}>
                                <SelectTrigger className="h-9 w-[130px] text-xs bg-muted/30">
                                    <SelectValue placeholder="Tenant" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">All Tenants</SelectItem>
                                    {allTenants.map(t => (
                                        <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}

                        {hasActiveFilters && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-9 text-xs text-muted-foreground hover:text-foreground px-2"
                                onClick={() => {
                                    setSearchTerm('');
                                    setStatusFilter('all');
                                    setRoleFilter('all');
                                    setTenantFilter('all');
                                    setJoinedAfter('');
                                    setJoinedBefore('');
                                }}
                            >
                                Reset
                            </Button>
                        )}

                        <Button onClick={() => setShowAddUser(true)} className="shrink-0 h-9 shadow-sm">
                            <PlusCircle className="mr-2 h-4 w-4" />
                            {mode === 'sysadmin' ? 'Add User to Tenant' : 'Invite Employee'}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Table */}
            <div className="rounded-md border border-border overflow-hidden">
                <Table>
                    <TableHeader className="bg-muted/50">
                        <TableRow>
                            <TableHead className="pl-4 pt-4 w-[50px]"></TableHead>
                            <TableHead className="pl-6 pt-4">
                                <button onClick={() => handleSort('name')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                    User <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'name' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                </button>
                            </TableHead>
                            <TableHead className="pt-4">
                                <button onClick={() => handleSort('username')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                    Username <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'username' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                </button>
                            </TableHead>
                            {mode === 'sysadmin' && (
                                <TableHead className="pt-4">
                                    <button onClick={() => handleSort('tenant')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                        Tenant <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'tenant' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                            )}
                            <TableHead className="pt-4">
                                <button onClick={() => handleSort('role')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                    Roles <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'role' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                </button>
                            </TableHead>
                            <TableHead className="pt-4">
                                <button onClick={() => handleSort('status')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                    Status <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'status' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                </button>
                            </TableHead>
                            <TableHead className="pt-4">
                                <button onClick={() => handleSort('joined')} className="flex items-center gap-1 hover:text-foreground transition-colors group text-xs uppercase tracking-wider font-semibold">
                                    Joined <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'joined' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                </button>
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {isLoading ? (
                            <TableRow>
                                <TableCell colSpan={columnsCount} className="h-32 text-center">
                                    <div className="flex flex-col items-center justify-center gap-2">
                                        <Loader2 className="h-6 w-6 animate-spin text-primary" />
                                        <p className="text-sm text-muted-foreground">Loading users...</p>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ) : displayRows.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={columnsCount} className="h-32 text-center text-muted-foreground">
                                    {searchTerm ? 'No users match your search.' : 'No users found.'}
                                </TableCell>
                            </TableRow>
                        ) : (
                            displayRows.map((row, index) => {
                                const { user, membership, tenant, isFirstInGroup, rowSpan } = row;
                                const roles = getRoleLabels(user, membership?.tenant_id || activeTenantId);
                                const isSysAdmin = !!user.is_sysadmin;
                                const status = user.status?.toLowerCase();
                                const isActive = user.is_active;

                                return (
                                    <TableRow
                                        key={`${user.id}-${tenant?.id || index}`}
                                        className="hover:bg-muted/30 group"
                                    >
                                        <TableCell className="pl-4 w-[50px]">
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-muted transition-all">
                                                        <span className="sr-only">Open menu</span>
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="start" className="w-52">
                                                    <DropdownMenuLabel className="text-xs text-muted-foreground uppercase tracking-wider font-bold p-2">Actions</DropdownMenuLabel>
                                                    <DropdownMenuSeparator />

                                                    {/* 1. View Profile: Only for registered users */}
                                                    {status !== 'pending' && (
                                                        <DropdownMenuItem
                                                            onClick={() => navigate(`/profile/${user.username || user.id}`)}
                                                            className="cursor-pointer gap-2 text-sm"
                                                        >
                                                            <UserRound className="h-4 w-4" /> View Profile
                                                        </DropdownMenuItem>
                                                    )}

                                                    {/* 2. Send Invite Link: ONLY for Pending Users */}
                                                    {status === 'pending' && (
                                                        <DropdownMenuItem
                                                            onClick={async () => {
                                                                setTokenDisplayTarget(user);
                                                                setShowTokenDisplay(true);
                                                            }}
                                                            className="cursor-pointer gap-2 text-sm"
                                                        >
                                                            <Mail className="h-4 w-4" /> Send Invite Link
                                                        </DropdownMenuItem>
                                                    )}

                                                    {/* 3. Status Toggles: Activate / Deactivate (Context Aware) */}
                                                    {isActive && (
                                                        <DropdownMenuItem
                                                            disabled={user.id === currentUser?.id}
                                                            className={user.id === currentUser?.id ? "text-muted-foreground gap-2 text-sm" : "text-destructive cursor-pointer gap-2 text-sm"}
                                                            onClick={() => {
                                                                handleDeactivateClick(user, membership?.tenant_id);
                                                            }}
                                                        >
                                                            <ShieldOff className="h-4 w-4" /> Deactivate {membership ? 'in Tenant' : 'User'}
                                                        </DropdownMenuItem>
                                                    )}

                                                    {(!isActive && status !== 'pending') && (
                                                        <DropdownMenuItem
                                                            disabled={user.id === currentUser?.id}
                                                            className={user.id === currentUser?.id ? "text-muted-foreground gap-2 text-sm" : "text-primary cursor-pointer gap-2 text-sm"}
                                                            onClick={() => {
                                                                handleReactivateClick(user, membership?.tenant_id);
                                                            }}
                                                        >
                                                            <Shield className="h-4 w-4" /> Activate {membership ? 'in Tenant' : 'User'}
                                                        </DropdownMenuItem>
                                                    )}

                                                    {/* 5. Manage Roles: Context Aware */}
                                                    {status !== 'pending' && (
                                                        <DropdownMenuItem
                                                            onClick={() => {
                                                                setModifyRoleTarget(user);
                                                                if (mode === 'manager') {
                                                                    setModifyRoleTenantId(activeTenantId || '');
                                                                    setModifyRoleTenantName(activeTenantName || 'Current Tenant');
                                                                } else if (membership) {
                                                                    setModifyRoleTenantId(membership.tenant_id);
                                                                    setModifyRoleTenantName(membership.tenant?.name || 'Selected Tenant');
                                                                }
                                                                setShowModifyRole(true);
                                                            }}
                                                            className="cursor-pointer gap-2 text-sm"
                                                        >
                                                            <Settings2 className="h-4 w-4" /> Manage Roles
                                                        </DropdownMenuItem>
                                                    )}

                                                    {/* 4. Delete User / Cancel Invite: SysAdmin OR Manager (for Pending) */}
                                                    {(mode === 'sysadmin' || (mode === 'manager' && status === 'pending')) && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                disabled={user.id === currentUser?.id}
                                                                className={user.id === currentUser?.id ? "text-muted-foreground gap-2 text-sm" : "text-destructive cursor-pointer gap-2 text-sm"}
                                                                onClick={() => handleDeleteClick(user, membership?.tenant_id)}
                                                            >
                                                                <Trash2 className="h-4 w-4" /> {status === 'pending' ? 'Cancel Invite' : 'Delete User'}
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                        {isFirstInGroup && (
                                            <TableCell className="pl-6 align-middle" rowSpan={rowSpan}>
                                                <div className="flex items-center gap-3">
                                                    <UserAvatar
                                                        initials={(user.full_name || user.email).charAt(0).toUpperCase()}
                                                        shapeId={user.avatar_url || null}
                                                        variant="rounded-square"
                                                        className="w-8 h-8 shadow-sm border border-border/50"
                                                    />
                                                    <div className="flex flex-col min-w-0">
                                                        <span className="font-semibold text-sm text-foreground truncate">{user.full_name || 'Anonymous'}</span>
                                                        <span className="text-xs text-muted-foreground truncate">{user.email}</span>
                                                    </div>
                                                </div>
                                            </TableCell>
                                        )}
                                        {isFirstInGroup && (
                                            <TableCell className="align-middle" rowSpan={rowSpan}>
                                                <span className="text-sm font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded border border-border/40">{user.username || '—'}</span>
                                            </TableCell>
                                        )}
                                        {mode === 'sysadmin' && (
                                            <TableCell>
                                                <span className="text-sm text-foreground font-medium">{tenant?.name || (user.is_sysadmin ? 'Global' : '—')}</span>
                                            </TableCell>
                                        )}
                                        <TableCell>
                                            <div className="flex flex-wrap gap-1">
                                                {isSysAdmin ? (
                                                    <Badge 
                                                        variant="outline" 
                                                        className="bg-primary/10 text-primary border-primary/20 rounded-full text-[10px] uppercase font-bold px-2 py-0"
                                                    >
                                                        SYSADMIN
                                                    </Badge>
                                                ) : (
                                                    <>
                                                        {roles.length > 0 ? roles.map((role, rIdx) => (
                                                            <Badge
                                                                key={rIdx}
                                                                variant="outline"
                                                                className={cn('rounded-full text-[10px] uppercase font-bold px-2 py-0 border', getRoleBadgeStyle(role))}
                                                            >
                                                                {role}
                                                            </Badge>
                                                        )) : (
                                                            <Badge 
                                                                variant="outline" 
                                                                className="rounded-full text-[10px] uppercase font-bold px-2 py-0 border bg-muted/30 border-border/50 text-muted-foreground"
                                                            >
                                                                Employee
                                                            </Badge>
                                                        )}
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            {(() => {
                                                if (status === 'pending') {
                                                    return <Badge variant="outline" className="rounded-full bg-muted text-muted-foreground border-border text-[10px] font-bold px-2 uppercase py-0 leading-tight">Pending</Badge>;
                                                }
                                                if (isActive) {
                                                    return <Badge variant="outline" className="rounded-full bg-primary/10 text-primary border-primary/20 text-[10px] font-bold px-2 uppercase py-0 leading-tight">Active</Badge>;
                                                }
                                                return <Badge variant="outline" className="rounded-full bg-destructive/10 text-destructive border-destructive/20 text-[10px] font-bold px-2 uppercase py-0 leading-tight">Inactive</Badge>;
                                            })()}
                                        </TableCell>
                                        <TableCell className="text-muted-foreground text-xs whitespace-nowrap">
                                            {new Date(user.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                                        </TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination: "Showing X–Y of Z" + per-page selector + page buttons */}
            {!isLoading && filtered.length > 0 && (
                <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground border-t border-border/40 pt-4">
                    {/* Left: count + per-page selector */}
                    <div className="flex items-center gap-3">
                        <span>
                            Showing <span className="font-medium text-foreground">{Math.min((page - 1) * pageSize + 1, filtered.length)}</span>–<span className="font-medium text-foreground">{Math.min(page * pageSize, filtered.length)}</span> of <span className="font-medium text-foreground">{filtered.length}</span> users
                        </span>
                        <Select value={String(pageSize)} onValueChange={v => { setPageSize(Number(v)); setPage(1); }}>
                            <SelectTrigger className="h-8 w-[70px] bg-muted/20">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {PAGE_SIZES.map(s => <SelectItem key={s} value={String(s)}>{s}</SelectItem>)}
                            </SelectContent>
                        </Select>
                        <span className="text-xs">per page</span>
                    </div>

                    {/* Right: page buttons */}
                    <div className="flex items-center gap-1">
                        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        {Array.from({ length: totalPages }, (_, i) => i + 1)
                            .filter(p => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                            .reduce<(number | '...')[]>((acc, p, i, arr) => {
                                if (i > 0 && (p as number) - (arr[i - 1] as number) > 1) acc.push('...');
                                acc.push(p);
                                return acc;
                            }, [])
                            .map((p, i) =>
                                p === '...' ? (
                                    <span key={`ellipsis-${i}`} className="px-2">…</span>
                                ) : (
                                    <Button key={p} variant={p === page ? 'default' : 'outline'} size="icon" className="h-8 w-8" onClick={() => setPage(p as number)}>
                                        {p}
                                    </Button>
                                )
                            )}
                        <Button variant="outline" size="icon" className="h-8 w-8" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}

            {/* --- Confirmation Dialogs --- */}
            {confirmDeactivate && (
                <Dialog open onOpenChange={() => setConfirmDeactivate(null)}>
                    <DialogContent className="sm:max-w-sm">
                        <DialogHeader>
                            <DialogTitle>Deactivate User</DialogTitle>
                            <DialogDescription className="sr-only">Confirm deactivation</DialogDescription>
                            <DialogDescription>
                                Deactivate <strong>{confirmDeactivate.full_name || confirmDeactivate.email}</strong>? They will no longer be able to log in to the selected tenant.
                            </DialogDescription>
                        </DialogHeader>
                        {mode === 'sysadmin' && confirmDeactivate.members.length > 0 && !selectedActionTenantId && (
                            <div className="py-4 space-y-2">
                                <Label>Select Tenant context for this action:</Label>
                                <Select value={selectedActionTenantId} onValueChange={setSelectedActionTenantId}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a tenant" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {confirmDeactivate.members.map(m => (
                                            <SelectItem key={m.tenant_id} value={m.tenant_id}>
                                                {m.tenant?.name || m.tenant_id}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        {selectedActionTenantId && (
                            <div className="py-2 text-sm text-muted-foreground italic">
                                Target Tenant: <span className="font-semibold text-foreground">
                                    {confirmDeactivate.members.find(m => m.tenant_id === selectedActionTenantId)?.tenant?.name || selectedActionTenantId}
                                </span>
                            </div>
                        )}
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConfirmDeactivate(null)} disabled={actionLoading}>Cancel</Button>
                            <Button variant="destructive" onClick={doDeactivate} disabled={actionLoading}>
                                {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Deactivate
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
            {confirmReactivate && (
                <Dialog open onOpenChange={() => setConfirmReactivate(null)}>
                    <DialogContent className="sm:max-w-sm">
                        <DialogHeader>
                            <DialogTitle>Reactivate User</DialogTitle>
                            <DialogDescription className="sr-only">Confirm reactivation</DialogDescription>
                            <DialogDescription>
                                Reactivate <strong>{confirmReactivate.full_name || confirmReactivate.email}</strong>? They will be able to log in again.
                            </DialogDescription>
                        </DialogHeader>
                        {mode === 'sysadmin' && confirmReactivate.members.length > 0 && !selectedActionTenantId && (
                            <div className="py-4 space-y-2">
                                <Label>Select Tenant context for this action:</Label>
                                <Select value={selectedActionTenantId} onValueChange={setSelectedActionTenantId}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a tenant" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {confirmReactivate.members.map(m => (
                                            <SelectItem key={m.tenant_id} value={m.tenant_id}>
                                                {m.tenant?.name || m.tenant_id}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                        {selectedActionTenantId && (
                            <div className="py-2 text-sm text-muted-foreground italic">
                                Target Tenant: <span className="font-semibold text-foreground">
                                    {confirmReactivate.members.find(m => m.tenant_id === selectedActionTenantId)?.tenant?.name || selectedActionTenantId}
                                </span>
                            </div>
                        )}
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConfirmReactivate(null)} disabled={actionLoading}>Cancel</Button>
                            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground" onClick={doReactivate} disabled={actionLoading}>
                                {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Reactivate
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
            {confirmReset && (
                <Dialog open onOpenChange={() => setConfirmReset(null)}>
                    <DialogContent className="sm:max-w-sm">
                        <DialogHeader>
                            <DialogTitle>Reset Password</DialogTitle>
                            <DialogDescription className="sr-only">Confirm password reset</DialogDescription>
                            <DialogDescription>
                                Send a password reset link to <strong>{confirmReset.email}</strong>?
                            </DialogDescription>
                        </DialogHeader>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConfirmReset(null)} disabled={actionLoading}>Cancel</Button>
                            <Button onClick={doResetPassword} disabled={actionLoading}>
                                {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Send Reset
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}
            {confirmDelete && (
                <Dialog open onOpenChange={() => setConfirmDelete(null)}>
                    <DialogContent className="sm:max-w-sm">
                        <DialogHeader>
                            <DialogTitle>Delete User</DialogTitle>
                            <DialogDescription className="sr-only">Confirm user deletion</DialogDescription>
                            <DialogDescription>
                                Permanently delete <strong>{confirmDelete.full_name || confirmDelete.email}</strong>? This action cannot be undone.
                            </DialogDescription>
                        </DialogHeader>
                        {selectedActionTenantId && (
                            <div className="py-2 text-sm text-muted-foreground italic">
                                Target Tenant: <span className="font-semibold text-foreground">
                                    {confirmDelete.members?.find(m => m.tenant_id === selectedActionTenantId)?.tenant?.name || selectedActionTenantId}
                                </span>
                                <p className="mt-1 text-[10px] text-destructive font-bold">This will remove the user from ONLY this tenant.</p>
                            </div>
                        )}
                        {!selectedActionTenantId && mode === 'sysadmin' && (
                            <div className="py-2 text-sm text-destructive font-bold italic">
                                WARNING: No tenant selected. This will delete the user GLOBALLY from the entire system.
                            </div>
                        )}
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setConfirmDelete(null)} disabled={actionLoading}>Cancel</Button>
                            <Button variant="destructive" onClick={doDeleteUser} disabled={actionLoading}>
                                {actionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Delete
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            )}

            {/* Token Display Modal */}
            {tokenDisplayTarget && (
                <TokenDisplayModal
                    open={showTokenDisplay}
                    onOpenChange={(open) => {
                        setShowTokenDisplay(open);
                        if (!open) setTokenDisplayTarget(null);
                    }}
                    userId={tokenDisplayTarget.id}
                    email={tokenDisplayTarget.email}
                    onTokenRegenerated={onRefresh}
                />
            )}

            {showAddUser && (
                <UserInviteDialog
                    mode={mode === 'sysadmin' ? 'admin' : 'manager'}
                    tenantId={activeTenantId || ''}
                    tenantName={activeTenantName || ''}
                    onClose={() => setShowAddUser(false)}
                    onSaved={onRefresh}
                />
            )}
            {viewingProfile && (
                <ViewProfileModal
                    user={viewingProfile}
                    mode={mode}
                    onClose={() => setViewingProfile(null)}
                />
            )}
            {/* --- Modals for Role Management --- */}
            {showModifyRole && modifyRoleTarget && mode === 'manager' && (
                <ModifyRoleModal
                    user={modifyRoleTarget}
                    tenantId={modifyRoleTenantId}
                    tenantName={modifyRoleTenantName}
                    onClose={() => { setShowModifyRole(false); setModifyRoleTarget(null); }}
                    onSaved={() => onRefresh && onRefresh()}
                />
            )}

            {showModifyRole && modifyRoleTarget && mode === 'sysadmin' && (
                <AdminModifyRoleModal
                    user={modifyRoleTarget}
                    presetTenantId={modifyRoleTenantId || undefined}
                    presetTenantName={modifyRoleTenantName || undefined}
                    onClose={() => { setShowModifyRole(false); setModifyRoleTarget(null); }}
                    onSaved={() => onRefresh && onRefresh()}
                />
            )}
        </div>
    );
};

