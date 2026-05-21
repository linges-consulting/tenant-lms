import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import { ScrollArea } from '../components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
    Search,
    Users,
    User,
    Calendar,
    Trash2,
    Loader2,
    Info,
    ArrowLeft,
    UserPlus,
    ChevronDown,
    ChevronRight,
} from 'lucide-react';
import { managerTrainingsApi, type TrainingAssignment } from '../api/trainings';
import { userService, type User as UserType } from '../api/users';
import { groupService, type Group } from '../api/groups';

export const ManagerTrainingAssignments: React.FC = () => {
    const { id: trainingId } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const backPath = location.pathname.includes('/publish/') ? '/manage/publish' : '/manage/courses';

    const [trainingTitle, setTrainingTitle] = useState('');
    const [activeAssignments, setActiveAssignments] = useState<TrainingAssignment[]>([]);
    const [allUsers, setAllUsers] = useState<UserType[]>([]);
    const [allGroups, setAllGroups] = useState<Group[]>([]);
    const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
    const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [dueDate, setDueDate] = useState('');
    const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
    const [groupMembers, setGroupMembers] = useState<Record<string, UserType[]>>({});
    const [allAssignedUserIds, setAllAssignedUserIds] = useState<Set<string>>(new Set());

    useEffect(() => {
        if (trainingId) loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [trainingId]);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const [assignments, users, groups, trainings] = await Promise.all([
                managerTrainingsApi.listAssignments(trainingId!),
                userService.listTenantUsers(),
                groupService.list(),
                managerTrainingsApi.getManagerTrainings(),
            ]);
            setActiveAssignments(assignments);
            setAllUsers(users);
            setAllGroups(groups);
            const t = trainings.find(tr => tr.id === trainingId);
            if (t) setTrainingTitle(t.title);

            // Fetch members for all assigned groups to handle filtering
            const assignedGroupIds = assignments
                .filter(a => a.group_id)
                .map(a => a.group_id!);
            
            if (assignedGroupIds.length > 0) {
                const memberData: Record<string, UserType[]> = {};
                const allUserIds = new Set<string>();

                await Promise.all(assignedGroupIds.map(async (gid) => {
                    try {
                        const members = await groupService.listMembers(gid);
                        // Map GroupMember to UserType for consistent display
                        const mappedMembers = members.map(m => ({
                            id: m.user_id,
                            email: m.user_email || '',
                            full_name: m.user_name || '',
                        } as UserType));
                        memberData[gid] = mappedMembers;
                        mappedMembers.forEach(m => allUserIds.add(m.id));
                    } catch (err) {
                        console.error(`Failed to load members for group ${gid}`, err);
                    }
                }));
                setGroupMembers(memberData);
                setAllAssignedUserIds(allUserIds);
            } else {
                setGroupMembers({});
                setAllAssignedUserIds(new Set());
            }
        } catch (error) {
            console.error('Failed to load assignment data', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAssign = async () => {
        if (selectedUserIds.length === 0 && selectedGroupIds.length === 0) return;
        setIsSaving(true);
        try {
            await managerTrainingsApi.bulkAssign(trainingId!, {
                user_ids: selectedUserIds,
                group_ids: selectedGroupIds,
                due_date: dueDate || undefined,
            });
            setSelectedUserIds([]);
            setSelectedGroupIds([]);
            setDueDate('');
            loadData();
        } catch (error) {
            console.error('Failed to assign training', error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteAssignment = async (assignmentId: string) => {
        try {
            await managerTrainingsApi.deleteAssignment(assignmentId);
            const deleted = activeAssignments.find(a => a.id === assignmentId);
            setActiveAssignments(prev => prev.filter(a => a.id !== assignmentId));
            
            // If it was a group assignment, we need to recalculate the assigned users set
            if (deleted?.group_id) {
                loadData(); // Easiest way to refresh the set
            }
        } catch (error) {
            console.error('Failed to delete assignment', error);
        }
    };

    const toggleGroupExpand = async (groupId: string) => {
        if (expandedGroups.includes(groupId)) {
            setExpandedGroups(prev => prev.filter(id => id !== groupId));
        } else {
            setExpandedGroups(prev => [...prev, groupId]);
            // Load members if not already loaded
            if (!groupMembers[groupId]) {
                try {
                    const members = await groupService.listMembers(groupId);
                    const mappedMembers = members.map(m => ({
                        id: m.user_id,
                        email: m.user_email || '',
                        full_name: m.user_name || '',
                    } as UserType));
                    setGroupMembers(prev => ({ ...prev, [groupId]: mappedMembers }));
                } catch (err) {
                    console.error('Failed to load group members', err);
                }
            }
        }
    };

    const filteredUsers = allUsers.filter(u =>
        (u.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.email.toLowerCase().includes(searchQuery.toLowerCase())) &&
        !activeAssignments.some(a => a.user_id === u.id) &&
        !allAssignedUserIds.has(u.id)
    );

    const filteredGroups = allGroups.filter(g =>
        g.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !activeAssignments.some(a => a.group_id === g.id)
    );

    const selectionCount = selectedUserIds.length + selectedGroupIds.length;

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Page Header */}
            <div className="px-6 pt-6 pb-4 shrink-0 border-b">
                <Button
                    variant="ghost"
                    size="sm"
                    className="mb-3 -ml-2 text-muted-foreground hover:text-foreground"
                    onClick={() => navigate(backPath)}
                >
                    <ArrowLeft className="h-4 w-4 mr-1" /> {location.pathname.includes('/publish/') ? 'Back to Review & Publish' : 'Back to Trainings'}
                </Button>
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                                <Users className="w-6 h-6 text-primary" />
                            </div>
                            Manage Assignments
                        </h1>
                        {trainingTitle && (
                            <p className="text-muted-foreground mt-0.5">
                                Course: <span className="text-primary font-medium">{trainingTitle}</span>
                            </p>
                        )}
                    </div>
                    <Badge variant="secondary" className="mt-1">
                        {activeAssignments.length} active assignment{activeAssignments.length !== 1 ? 's' : ''}
                    </Badge>
                </div>
            </div>

            {/* Tabs */}
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                <Tabs defaultValue="assign" className="flex-1 min-h-0 flex flex-col">
                    <div className="px-6 border-b shrink-0">
                        <TabsList className="w-full justify-start bg-transparent h-12 p-0 gap-8">
                            <TabsTrigger
                                value="assign"
                                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-1"
                            >
                                New Assignment
                            </TabsTrigger>
                            <TabsTrigger
                                value="active"
                                className="data-[state=active]:bg-transparent data-[state=active]:shadow-none data-[state=active]:border-b-2 data-[state=active]:border-primary rounded-none h-full px-1 flex gap-2"
                            >
                                Active Assignments
                                <Badge variant="secondary" className="h-5 px-1.5 min-w-[20px] justify-center">
                                    {activeAssignments.length}
                                </Badge>
                            </TabsTrigger>
                        </TabsList>
                    </div>

                    {/* New Assignment Tab */}
                    <TabsContent
                        value="assign"
                        className="flex-1 min-h-0 flex flex-col m-0 p-6 gap-4 data-[state=inactive]:hidden"
                    >
                        {/* Search + Due Date */}
                        <div className="flex flex-col sm:flex-row gap-4 shrink-0">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <input
                                    className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all text-sm"
                                    placeholder="Search people or groups..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                            <div className="flex items-center gap-2 border rounded-lg px-3 py-1.5 bg-background shrink-0">
                                <Calendar className="h-4 w-4 text-muted-foreground" />
                                <input
                                    type="date"
                                    className="outline-none bg-transparent text-sm h-7"
                                    value={dueDate}
                                    onChange={(e) => setDueDate(e.target.value)}
                                />
                                <span className="text-xs text-muted-foreground">Due Date (Optional)</span>
                            </div>
                        </div>

                        {/* Groups + Users grid */}
                        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Groups */}
                            <div className="flex flex-col min-h-0 border rounded-xl bg-muted/30 overflow-hidden">
                                <div className="p-3 border-b bg-background/50 flex items-center justify-between shrink-0">
                                    <h4 className="text-sm font-semibold flex items-center gap-2">
                                        <Users className="h-4 w-4 text-primary" /> Groups
                                    </h4>
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                        Available: {filteredGroups.length}
                                    </span>
                                </div>
                                <ScrollArea className="flex-1">
                                    <div className="p-3 space-y-2">
                                        {isLoading ? (
                                            <div className="flex justify-center py-8">
                                                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                            </div>
                                        ) : filteredGroups.length === 0 ? (
                                            <p className="text-xs text-muted-foreground text-center py-8">
                                                No groups available to assign.
                                            </p>
                                        ) : (
                                            filteredGroups.map(group => {
                                                const isExpanded = expandedGroups.includes(group.id);
                                                const members = groupMembers[group.id];
                                                return (
                                                    <div key={group.id} className="space-y-1">
                                                        <div
                                                            className={cn('flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer hover:bg-background', selectedGroupIds.includes(group.id) && 'bg-background ring-1 ring-primary/20')}
                                                            onClick={() =>
                                                                setSelectedGroupIds(prev =>
                                                                    prev.includes(group.id)
                                                                        ? prev.filter(id => id !== group.id)
                                                                        : [...prev, group.id]
                                                                )
                                                            }
                                                        >
                                                            <Checkbox
                                                                checked={selectedGroupIds.includes(group.id)}
                                                                className="pointer-events-none"
                                                                tabIndex={-1}
                                                            />
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-sm font-medium truncate">{group.name}</p>
                                                                <p className="text-[10px] text-muted-foreground">
                                                                    {group.member_count} members
                                                                </p>
                                                            </div>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                className="h-6 w-6 p-0 hover:bg-muted shrink-0"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    toggleGroupExpand(group.id);
                                                                }}
                                                                title={isExpanded ? 'Hide members' : 'View members'}
                                                            >
                                                                {isExpanded ? (
                                                                    <ChevronDown className="h-3.5 w-3.5" />
                                                                ) : (
                                                                    <ChevronRight className="h-3.5 w-3.5" />
                                                                )}
                                                            </Button>
                                                        </div>
                                                        {isExpanded && (
                                                            <div className="ml-8 pl-3 border-l-2 border-border/60 space-y-1 py-1">
                                                                {!members ? (
                                                                    <div className="flex items-center gap-2 py-1">
                                                                        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                                                                        <span className="text-xs text-muted-foreground">Loading members...</span>
                                                                    </div>
                                                                ) : members.length === 0 ? (
                                                                    <p className="text-xs text-muted-foreground italic py-1">No members in this group.</p>
                                                                ) : (
                                                                    members.map(member => (
                                                                        <div key={member.id} className="flex flex-col py-0.5">
                                                                            <span className="text-xs font-medium truncate">{member.full_name || member.email}</span>
                                                                            <span className="text-[10px] text-muted-foreground truncate">{member.email}</span>
                                                                        </div>
                                                                    ))
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })
                                        )}
                                    </div>
                                </ScrollArea>
                            </div>

                            {/* Individual Employees */}
                            <div className="flex flex-col min-h-0 border rounded-xl bg-muted/30 overflow-hidden">
                                <div className="p-3 border-b bg-background/50 flex items-center justify-between shrink-0">
                                    <h4 className="text-sm font-semibold flex items-center gap-2">
                                        <User className="h-4 w-4 text-muted-foreground" /> Individual Employees
                                    </h4>
                                    <span className="text-[10px] text-muted-foreground uppercase tracking-wider">
                                        Available: {filteredUsers.length}
                                    </span>
                                </div>
                                <ScrollArea className="flex-1">
                                    <div className="p-3 space-y-2">
                                        {isLoading ? (
                                            <div className="flex justify-center py-8">
                                                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                            </div>
                                        ) : filteredUsers.length === 0 ? (
                                            <p className="text-xs text-muted-foreground text-center py-8">
                                                No employees available to assign.
                                            </p>
                                        ) : (
                                            filteredUsers.map(user => (
                                                <div
                                                    key={user.id}
                                                    className={cn('flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer hover:bg-background', selectedUserIds.includes(user.id) && 'bg-background ring-1 ring-primary/20')}
                                                    onClick={() =>
                                                        setSelectedUserIds(prev =>
                                                            prev.includes(user.id)
                                                                ? prev.filter(id => id !== user.id)
                                                                : [...prev, user.id]
                                                        )
                                                    }
                                                >
                                                    <Checkbox
                                                        checked={selectedUserIds.includes(user.id)}
                                                        className="pointer-events-none"
                                                        tabIndex={-1}
                                                    />
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-sm font-medium truncate">
                                                            {user.full_name || user.email}
                                                        </p>
                                                        <p className="text-[10px] text-muted-foreground truncate">
                                                            {user.email}
                                                        </p>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </ScrollArea>
                            </div>
                        </div>

                        {/* Assign Action Bar */}
                        <div className="flex items-center justify-between shrink-0 pt-2 border-t">
                            <p className="text-sm text-muted-foreground">
                                {selectionCount > 0
                                    ? `${selectionCount} selected`
                                    : 'Select groups or employees above'}
                            </p>
                            <Button
                                onClick={handleAssign}
                                disabled={isSaving || selectionCount === 0}
                                className="min-w-[160px]"
                            >
                                {isSaving ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Assigning...
                                    </>
                                ) : (
                                    <>
                                        <UserPlus className="mr-2 h-4 w-4" />
                                        Assign Selected ({selectionCount})
                                    </>
                                )}
                            </Button>
                        </div>
                    </TabsContent>

                    {/* Active Assignments Tab */}
                    <TabsContent
                        value="active"
                        className="flex-1 min-h-0 flex flex-col m-0 p-6 data-[state=inactive]:hidden"
                    >
                        {isLoading ? (
                            <div className="flex flex-col items-center justify-center flex-1 gap-4">
                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                <p className="text-sm text-muted-foreground">Loading active assignments...</p>
                            </div>
                        ) : activeAssignments.length === 0 ? (
                            <div className="flex flex-col items-center justify-center flex-1 gap-4 text-muted-foreground border-2 border-dashed rounded-xl">
                                <Info className="h-8 w-8 opacity-20" />
                                <p className="text-sm">No active assignments for this course.</p>
                            </div>
                        ) : (
                            <ScrollArea className="flex-1">
                                <div className="space-y-3 pr-2">
                                    {activeAssignments.map(assignment => (
                                        <div key={assignment.id} className="flex flex-col border rounded-lg bg-background hover:border-primary/20 transition-all overflow-hidden">
                                            <div className="flex items-center justify-between p-3 group">
                                                <div className="flex items-center gap-3">
                                                    <div
                                                        className={cn('w-9 h-9 rounded-full flex items-center justify-center', assignment.group_id ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground')}
                                                    >
                                                        {assignment.group_id ? (
                                                            <Users className="h-4 w-4" />
                                                        ) : (
                                                            <User className="h-4 w-4" />
                                                        )}
                                                    </div>
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <p className="text-sm font-semibold">
                                                                {assignment.group_name || assignment.user_name}
                                                            </p>
                                                            {assignment.group_id && (
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="h-6 w-6 p-0 hover:bg-muted"
                                                                    onClick={() => toggleGroupExpand(assignment.group_id!)}
                                                                >
                                                                    {expandedGroups.includes(assignment.group_id) ? (
                                                                        <ChevronDown className="h-3 w-3" />
                                                                    ) : (
                                                                        <ChevronRight className="h-3 w-3" />
                                                                    )}
                                                                </Button>
                                                            )}
                                                        </div>
                                                        <div className="flex items-center gap-2 mt-0.5">
                                                            <Badge
                                                                variant="outline"
                                                                className="text-[9px] px-1 h-4 uppercase tracking-tighter"
                                                            >
                                                                {assignment.group_id ? 'Group' : 'User'}
                                                            </Badge>
                                                            {assignment.due_date && (
                                                                <span className="text-[10px] text-amber-600 flex items-center gap-1 font-medium">
                                                                    <Calendar className="h-3 w-3" /> Due:{' '}
                                                                    {new Date(assignment.due_date).toLocaleDateString()}
                                                                </span>
                                                            )}
                                                            <span className="text-[10px] text-muted-foreground">
                                                                Assigned{' '}
                                                                {new Date(assignment.assigned_at).toLocaleDateString()}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-muted-foreground hover:text-destructive transition-colors opacity-0 group-hover:opacity-100"
                                                    onClick={() => handleDeleteAssignment(assignment.id)}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            </div>
                                            
                                            {/* Group Members Waterfall */}
                                            {assignment.group_id && expandedGroups.includes(assignment.group_id) && (
                                                <div className="px-3 pb-3 pt-1 border-t bg-muted/20">
                                                    <p className="text-[10px] font-medium text-muted-foreground mb-2 uppercase tracking-widest pl-12">
                                                        Group Members
                                                    </p>
                                                    <div className="space-y-1 pl-12">
                                                        {!groupMembers[assignment.group_id] ? (
                                                            <div className="flex items-center gap-2 py-1">
                                                                <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
                                                                <span className="text-xs text-muted-foreground">Loading members...</span>
                                                            </div>
                                                        ) : groupMembers[assignment.group_id].length === 0 ? (
                                                            <p className="text-xs text-muted-foreground py-1 italic">No members in this group.</p>
                                                        ) : (
                                                            groupMembers[assignment.group_id].map(member => (
                                                                <div key={member.id} className="flex flex-col py-1">
                                                                    <span className="text-xs font-medium">{member.full_name || member.email}</span>
                                                                    <span className="text-[10px] text-muted-foreground">{member.email}</span>
                                                                </div>
                                                            ))
                                                        )}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </ScrollArea>
                        )}
                    </TabsContent>
                </Tabs>
            </div>
        </div>
    );
};
