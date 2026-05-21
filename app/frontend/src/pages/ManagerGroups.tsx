import React, { useState, useEffect, useCallback } from 'react';
import {
    Card, CardContent, CardHeader, CardTitle, CardDescription,
} from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Users, PlusCircle, Trash2, UserMinus, Loader2, ChevronDown, ChevronRight, UserPlus } from 'lucide-react';
import { groupService, type Group, type GroupMember } from '../api/groups';
import { userService, type User } from '../api/users';
import { useAuth } from '../contexts/auth-context';
import { UserAvatar } from '../components/UserAvatar';

// ---- Create/Edit Group Modal ----
interface GroupFormModalProps {
    existing?: Group;
    onClose: () => void;
    onSaved: () => void;
}
const GroupFormModal: React.FC<GroupFormModalProps> = ({ existing, onClose, onSaved }) => {
    const [name, setName] = useState(existing?.name ?? '');
    const [description, setDescription] = useState(existing?.description ?? '');
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');

    const handleSave = async () => {
        if (!name.trim()) { setError('Group name is required.'); return; }
        setIsSaving(true); setError('');
        try {
            if (existing) {
                await groupService.update(existing.id, { name, description: description || undefined });
            } else {
                await groupService.create({ name, description: description || undefined });
            }
            onSaved();
            onClose();
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Failed to save group.');
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>{existing ? 'Edit Group' : 'Create Group'}</DialogTitle>
                    <DialogDescription>
                        {existing ? 'Update group name or description.' : 'Create a new user group for your tenant.'}
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                    <div>
                        <Label>Group Name *</Label>
                        <Input placeholder="e.g. Sales Team" value={name} onChange={e => setName(e.target.value)} className="mt-1" />
                    </div>
                    <div>
                        <Label>Description</Label>
                        <Input placeholder="Optional description" value={description} onChange={e => setDescription(e.target.value)} className="mt-1" />
                    </div>
                    {error && <p className="text-sm text-destructive">{error}</p>}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} {existing ? 'Save Changes' : 'Create Group'}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Delete Group Confirm Modal ----
interface DeleteGroupModalProps {
    group: Group;
    onClose: () => void;
    onDeleted: () => void;
}
const DeleteGroupModal: React.FC<DeleteGroupModalProps> = ({ group, onClose, onDeleted }) => {
    const [isDeleting, setIsDeleting] = useState(false);
    const handleDelete = async () => {
        setIsDeleting(true);
        try { await groupService.delete(group.id); onDeleted(); onClose(); }
        catch { setIsDeleting(false); }
    };
    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle>Delete Group</DialogTitle>
                    <DialogDescription>
                        Delete <strong>{group.name}</strong>? This removes the group and all memberships. Users are not deleted.
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isDeleting}>Cancel</Button>
                    <Button variant="destructive" onClick={handleDelete} disabled={isDeleting}>
                        {isDeleting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Delete
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Add Members Modal ----
interface AddMembersModalProps {
    group: Group;
    existingMemberIds: string[];
    tenantUsers: User[];
    onClose: () => void;
    onSaved: () => void;
}
const AddMembersModal: React.FC<AddMembersModalProps> = ({ group, existingMemberIds, tenantUsers, onClose, onSaved }) => {
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [isSaving, setIsSaving] = useState(false);
    const [searchQ, setSearchQ] = useState('');

    const available = tenantUsers.filter(u =>
        !existingMemberIds.includes(u.id) &&
        (u.full_name?.toLowerCase().includes(searchQ.toLowerCase()) || u.email.toLowerCase().includes(searchQ.toLowerCase()))
    );

    const toggle = (id: string) => setSelected(s => {
        const n = new Set(s);
        if (n.has(id)) { n.delete(id); } else { n.add(id); }
        return n;
    });

    const handleAdd = async () => {
        if (selected.size === 0) return;
        setIsSaving(true);
        try {
            await groupService.addMembers(group.id, [...selected]);
            onSaved();
            onClose();
        } catch {
            setIsSaving(false);
        }
    };

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Members to {group.name}</DialogTitle>
                    <DialogDescription>Select employees to add to this group.</DialogDescription>
                </DialogHeader>
                <div className="space-y-3 py-1">
                    <Input
                        placeholder="Search employees..."
                        value={searchQ}
                        onChange={e => setSearchQ(e.target.value)}
                    />
                    <div className="max-h-60 overflow-y-auto space-y-1 border border-border rounded-md p-2">
                        {available.length === 0 ? (
                            <p className="text-sm text-muted-foreground text-center py-4">
                                {searchQ ? 'No matches.' : 'All employees are already members.'}
                            </p>
                        ) : available.map(u => (
                            <label key={u.id} className="flex items-center gap-3 p-2 rounded-md hover:bg-muted/40 cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={selected.has(u.id)}
                                    onChange={() => toggle(u.id)}
                                    className="h-4 w-4 accent-primary"
                                />
                                <UserAvatar
                                    initials={(u.full_name || u.email).charAt(0).toUpperCase()}
                                    shapeId={u.avatar_url || null}
                                    className="w-7 h-7"
                                    variant="circle"
                                />
                                <div className="flex flex-col min-w-0">
                                    <span className="text-sm font-medium truncate">{u.full_name || 'Anonymous'}</span>
                                    <span className="text-xs text-muted-foreground truncate">{u.email}</span>
                                </div>
                            </label>
                        ))}
                    </div>
                    {selected.size > 0 && (
                        <p className="text-xs text-muted-foreground">{selected.size} selected</p>
                    )}
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
                    <Button onClick={handleAdd} disabled={isSaving || selected.size === 0}>
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Add {selected.size > 0 ? `(${selected.size})` : ''} Members
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Remove Member Confirm Modal ----
interface RemoveMemberModalProps {
    groupId: string;
    member: GroupMember;
    onClose: () => void;
    onRemoved: () => void;
}
const RemoveMemberModal: React.FC<RemoveMemberModalProps> = ({ groupId, member, onClose, onRemoved }) => {
    const [isRemoving, setIsRemoving] = useState(false);
    const handleRemove = async () => {
        setIsRemoving(true);
        try { await groupService.removeMember(groupId, member.user_id); onRemoved(); onClose(); }
        catch { setIsRemoving(false); }
    };
    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-sm">
                <DialogHeader>
                    <DialogTitle>Remove Member</DialogTitle>
                    <DialogDescription>
                        Remove <strong>{member.user_name || member.user_email}</strong> from this group?
                    </DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose} disabled={isRemoving}>Cancel</Button>
                    <Button variant="destructive" onClick={handleRemove} disabled={isRemoving}>
                        {isRemoving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} Remove
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

// ---- Group Row (expandable) ----
interface GroupRowProps {
    group: Group;
    tenantUsers: User[];
    onEdit: () => void;
    onDelete: () => void;
    onRefresh: () => void;
}

const GroupRow: React.FC<GroupRowProps> = ({ group, tenantUsers, onEdit, onDelete, onRefresh }) => {
    const [expanded, setExpanded] = useState(false);
    const [members, setMembers] = useState<GroupMember[]>([]);
    const [loadingMembers, setLoadingMembers] = useState(false);
    const [showAddMembers, setShowAddMembers] = useState(false);
    const [removeMemberTarget, setRemoveMemberTarget] = useState<GroupMember | null>(null);

    const fetchMembers = useCallback(async () => {
        setLoadingMembers(true);
        try { setMembers(await groupService.listMembers(group.id)); }
        finally { setLoadingMembers(false); }
    }, [group.id]);

    useEffect(() => { if (expanded) fetchMembers(); }, [expanded, fetchMembers]);

    return (
        <div className="border border-border rounded-lg overflow-hidden">
            {/* Group Header Row */}
            <div
                className="flex items-center gap-3 px-4 py-3 bg-muted/20 hover:bg-muted/40 cursor-pointer transition-colors"
            >
                <div className="flex-1 flex items-center gap-3" onClick={() => setExpanded(e => !e)}>
                    {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" /> : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />}
                    <Users className="h-4 w-4 text-primary shrink-0" />
                    <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{group.name}</p>
                        {group.description && <p className="text-xs text-muted-foreground truncate">{group.description}</p>}
                    </div>
                    <Badge variant="outline" className="shrink-0">{group.member_count} member{group.member_count !== 1 ? 's' : ''}</Badge>
                    <div className="flex gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                        <Button size="sm" variant="ghost" onClick={onEdit} className="h-7 px-2 text-xs">Edit</Button>
                        <Button size="sm" variant="ghost" onClick={onDelete} className="h-7 px-2 text-xs text-destructive hover:text-destructive">
                            <Trash2 className="h-3 w-3" />
                        </Button>
                    </div>
                </div>
            </div>

            {/* Expanded Members List */}
            {expanded && (
                <div className="border-t border-border px-4 py-3 space-y-2 bg-background">
                    <div className="flex items-center justify-between mb-2">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">Members</p>
                        <Button size="sm" variant="outline" className="h-7 px-2 text-xs gap-1"
                            onClick={() => setShowAddMembers(true)}>
                            <UserPlus className="h-3 w-3" /> Add Members
                        </Button>
                    </div>
                    {loadingMembers ? (
                        <div className="flex items-center gap-2 py-2 text-muted-foreground text-sm">
                            <Loader2 className="h-4 w-4 animate-spin" /> Loading...
                        </div>
                    ) : members.length === 0 ? (
                        <p className="text-sm text-muted-foreground py-2">No members yet. Add employees above.</p>
                    ) : (
                        <div className="space-y-1">
                            {members.map(m => (
                                <div key={m.user_id} className="flex items-center gap-3 py-1.5 px-2 rounded-md hover:bg-muted/30 group">
                                    <UserAvatar
                                        initials={(m.user_name || m.user_email || '?').charAt(0).toUpperCase()}
                                        shapeId={m.user_avatar_url || null}
                                        className="w-8 h-8"
                                        variant="circle"
                                    />
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium truncate">{m.user_name || 'Unknown'}</p>
                                        <p className="text-xs text-muted-foreground truncate">{m.user_email}</p>
                                    </div>
                                    <Button
                                        size="icon"
                                        variant="ghost"
                                        className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
                                        onClick={() => setRemoveMemberTarget(m)}
                                    >
                                        <UserMinus className="h-3.5 w-3.5" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {/* Modals */}
            {showAddMembers && (
                <AddMembersModal
                    group={group}
                    existingMemberIds={members.map(m => m.user_id)}
                    tenantUsers={tenantUsers}
                    onClose={() => setShowAddMembers(false)}
                    onSaved={() => { fetchMembers(); onRefresh(); }}
                />
            )}
            {removeMemberTarget && (
                <RemoveMemberModal
                    groupId={group.id}
                    member={removeMemberTarget}
                    onClose={() => setRemoveMemberTarget(null)}
                    onRemoved={() => { fetchMembers(); onRefresh(); }}
                />
            )}
        </div>
    );
};

// ---- Main Page ----
export const ManagerGroups: React.FC = () => {
    const { activeMembership } = useAuth();
    const [groups, setGroups] = useState<Group[]>([]);
    const [tenantUsers, setTenantUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showCreateGroup, setShowCreateGroup] = useState(false);
    const [editTarget, setEditTarget] = useState<Group | null>(null);
    const [deleteTarget, setDeleteTarget] = useState<Group | null>(null);
    const fetchData = useCallback(async () => {
        setIsLoading(true);
        try {
            const [g, u] = await Promise.all([groupService.list(), userService.listTenantUsers()]);
            setGroups(g);
            setTenantUsers(u);
        } catch (e) {
            console.error('Failed to load groups:', e);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    if (!activeMembership?.is_business_manager) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <Users className="w-10 h-10 mb-3 opacity-30" />
                <p className="text-lg font-medium">Access Restricted</p>
                <p className="text-sm mt-1">Business Manager permissions required.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto animate-in fade-in duration-500">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                            <Users className="w-6 h-6 text-primary" />
                        </div>
                        User Groups
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Organize employees into groups and assign courses effectively.
                    </p>
                </div>
                <div className="flex items-center gap-2 w-full sm:w-auto">
                    <Button size="sm" onClick={() => setShowCreateGroup(true)} className="flex-1 sm:flex-none">
                        <PlusCircle className="mr-2 h-4 w-4" /> New Group
                    </Button>
                </div>
            </div>

            <Card className="border-border/50 shadow-sm">
                <CardHeader className="pb-4 border-b border-border/50">
                    <CardTitle className="text-lg">Groups</CardTitle>
                    <CardDescription>
                        {isLoading ? 'Loading...' : `${groups.length} group${groups.length !== 1 ? 's' : ''}`}
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-4">
                    {isLoading ? (
                        <div className="flex items-center gap-2 py-8 justify-center text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin" /> Loading groups...
                        </div>
                    ) : groups.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <Users className="w-10 h-10 mb-3 opacity-30" />
                            <p className="font-medium">No groups yet</p>
                            <p className="text-sm mt-1">Create your first group to start organising employees.</p>
                            <Button className="mt-4" onClick={() => setShowCreateGroup(true)}>
                                <PlusCircle className="mr-2 h-4 w-4" /> Create Group
                            </Button>
                        </div>
                    ) : (
                        <div className="space-y-2">
                            {groups.map(g => (
                                <GroupRow
                                    key={g.id}
                                    group={g}
                                    tenantUsers={tenantUsers}
                                    onEdit={() => setEditTarget(g)}
                                    onDelete={() => setDeleteTarget(g)}
                                    onRefresh={fetchData}
                                />
                            ))}
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Modals */}
            {showCreateGroup && (
                <GroupFormModal onClose={() => setShowCreateGroup(false)} onSaved={fetchData} />
            )}
            {editTarget && (
                <GroupFormModal existing={editTarget} onClose={() => setEditTarget(null)} onSaved={fetchData} />
            )}
            {deleteTarget && (
                <DeleteGroupModal group={deleteTarget} onClose={() => setDeleteTarget(null)} onDeleted={fetchData} />
            )}
        </div>
    );
};
