import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import { ScrollArea } from "./ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Search, Users, User, Calendar, Trash2, Loader2, Info } from "lucide-react";
import { managerTrainingsApi, type TrainingAssignment } from "../api/trainings";
import { userService, type User as UserType } from "../api/users";
import { groupService, type Group } from "../api/groups";
import { Badge } from "./ui/badge";

interface TrainingAssignmentModalProps {
    isOpen: boolean;
    onClose: () => void;
    trainingId: string;
    trainingTitle: string;
}

export const TrainingAssignmentModal: React.FC<TrainingAssignmentModalProps> = ({
    isOpen,
    onClose,
    trainingId,
    trainingTitle,
}) => {
    const [activeAssignments, setActiveAssignments] = useState<TrainingAssignment[]>([]);
    const [allUsers, setAllUsers] = useState<UserType[]>([]);
    const [allGroups, setAllGroups] = useState<Group[]>([]);
    const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);
    const [selectedGroupIds, setSelectedGroupIds] = useState<string[]>([]);
    const [searchQuery, setSearchQuery] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [dueDate, setDueDate] = useState<string>("");

    useEffect(() => {
        if (isOpen && trainingId) {
            loadData();
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, trainingId]);

    const loadData = async () => {
        setIsLoading(true);
        try {
            const [assignments, users, groups] = await Promise.all([
                managerTrainingsApi.listAssignments(trainingId),
                userService.listTenantUsers(),
                groupService.list(),
            ]);
            setActiveAssignments(assignments);
            setAllUsers(users);
            setAllGroups(groups);
        } catch (error) {
            console.error("Failed to load assignment data", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAssign = async () => {
        if (selectedUserIds.length === 0 && selectedGroupIds.length === 0) return;

        setIsSaving(true);
        try {
            await managerTrainingsApi.bulkAssign(trainingId, {
                user_ids: selectedUserIds,
                group_ids: selectedGroupIds,
                due_date: dueDate || undefined,
            });
            // Reset selection and reload
            setSelectedUserIds([]);
            setSelectedGroupIds([]);
            setDueDate("");
            loadData();
        } catch (error) {
            console.error("Failed to assign training", error);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteAssignment = async (assignmentId: string) => {
        try {
            await managerTrainingsApi.deleteAssignment(assignmentId);
            setActiveAssignments(prev => prev.filter(a => a.id !== assignmentId));
        } catch (error) {
            console.error("Failed to delete assignment", error);
        }
    };

    const filteredUsers = allUsers.filter(u =>
        (u.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.email.toLowerCase().includes(searchQuery.toLowerCase())) &&
        !activeAssignments.some(a => a.user_id === u.id)
    );

    const filteredGroups = allGroups.filter(g =>
        g.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !activeAssignments.some(a => a.group_id === g.id)
    );

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-3xl h-[80vh] flex flex-col p-0 overflow-hidden" style={{ minHeight: 0 }}>
                <DialogHeader className="p-6 pb-2">
                    <DialogTitle className="text-2xl font-bold flex items-center gap-2">
                        Assign Training: <span className="text-primary">{trainingTitle}</span>
                    </DialogTitle>
                    <DialogDescription>
                        Assign this training to individual employees or entire groups.
                    </DialogDescription>
                </DialogHeader>

                <div className="flex-1 min-h-0 flex flex-col">
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

                        <TabsContent value="assign" className="flex-1 min-h-0 flex flex-col m-0 p-6 gap-4
                            data-[state=inactive]:hidden">
                            <div className="flex flex-col sm:flex-row gap-4">
                                <div className="relative flex-1">
                                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                    <input
                                        className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all text-sm"
                                        placeholder="Search people or groups..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                    />
                                </div>
                                <div className="flex items-center gap-2 border rounded-lg px-3 py-1.5 bg-background">
                                    <Calendar className="h-4 w-4 text-muted-foreground" />
                                    <input
                                        type="date"
                                        className="outline-none bg-transparent text-sm h-7"
                                        value={dueDate}
                                        onChange={(e) => setDueDate(e.target.value)}
                                        placeholder="Due Date (Optional)"
                                    />
                                </div>
                            </div>

                            <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-2 gap-6 mt-2">
                                {/* Groups Section */}
                                <div className="flex flex-col min-h-0 border rounded-xl bg-muted/30" style={{ maxHeight: '100%', overflow: 'hidden' }}>
                                    <div className="p-3 border-b bg-background/50 flex items-center justify-between">
                                        <h4 className="text-sm font-semibold flex items-center gap-2">
                                            <Users className="h-4 w-4 text-primary" /> Groups
                                        </h4>
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Available: {filteredGroups.length}</span>
                                    </div>
                                    <ScrollArea className="flex-1">
                                        <div className="p-3 space-y-2">
                                            {filteredGroups.length === 0 ? (
                                                <p className="text-xs text-muted-foreground text-center py-8">No groups available to assign.</p>
                                            ) : (
                                                filteredGroups.map(group => (
                                                    <div
                                                        key={group.id}
                                                        className={cn('flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer hover:bg-background', selectedGroupIds.includes(group.id) && 'bg-background ring-1 ring-primary/20')}
                                                        onClick={() => {
                                                            setSelectedGroupIds(prev =>
                                                                prev.includes(group.id) ? prev.filter(id => id !== group.id) : [...prev, group.id]
                                                            )
                                                        }}
                                                    >
                                                        <Checkbox
                                                            checked={selectedGroupIds.includes(group.id)}
                                                            className="pointer-events-none"
                                                            tabIndex={-1}
                                                        />
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm font-medium truncate">{group.name}</p>
                                                            <p className="text-[10px] text-muted-foreground">{group.member_count} members</p>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </ScrollArea>
                                </div>

                                {/* Users Section */}
                                <div className="flex flex-col min-h-0 border rounded-xl bg-muted/30" style={{ maxHeight: '100%', overflow: 'hidden' }}>
                                    <div className="p-3 border-b bg-background/50 flex items-center justify-between">
                                        <h4 className="text-sm font-semibold flex items-center gap-2">
                                            <User className="h-4 w-4 text-muted-foreground" /> Individual Employees
                                        </h4>
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Available: {filteredUsers.length}</span>
                                    </div>
                                    <ScrollArea className="flex-1">
                                        <div className="p-3 space-y-2">
                                            {filteredUsers.length === 0 ? (
                                                <p className="text-xs text-muted-foreground text-center py-8">No employees available to assign.</p>
                                            ) : (
                                                filteredUsers.map(user => (
                                                    <div
                                                        key={user.id}
                                                        className={cn('flex items-center gap-3 p-2 rounded-lg transition-colors cursor-pointer hover:bg-background', selectedUserIds.includes(user.id) && 'bg-background ring-1 ring-primary/20')}
                                                        onClick={() => {
                                                            setSelectedUserIds(prev =>
                                                                prev.includes(user.id) ? prev.filter(id => id !== user.id) : [...prev, user.id]
                                                            )
                                                        }}
                                                    >
                                                        <Checkbox
                                                            checked={selectedUserIds.includes(user.id)}
                                                            className="pointer-events-none"
                                                            tabIndex={-1}
                                                        />
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm font-medium truncate">{user.full_name || user.email}</p>
                                                            <p className="text-[10px] text-muted-foreground truncate">{user.email}</p>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </ScrollArea>
                                </div>
                            </div>
                        </TabsContent>

                        <TabsContent value="active" className="flex-1 min-h-0 flex flex-col m-0 p-6
                            data-[state=inactive]:hidden">
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
                                    <div className="space-y-3 pr-4">
                                        {activeAssignments.map(assignment => (
                                            <div key={assignment.id} className="flex items-center justify-between p-3 rounded-lg border bg-background hover:border-primary/20 transition-all group">
                                                <div className="flex items-center gap-3">
                                                    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center', assignment.group_id ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground')}>
                                                        {assignment.group_id ? <Users className="h-4 w-4" /> : <User className="h-4 w-4" />}
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-bold">{assignment.group_name || assignment.user_name}</p>
                                                        <div className="flex items-center gap-2 mt-0.5">
                                                            <Badge variant="outline" className="text-[9px] px-1 h-4 uppercase tracking-tighter">
                                                                {assignment.group_id ? 'Group' : 'User'}
                                                            </Badge>
                                                            {assignment.due_date && (
                                                                <span className="text-[10px] text-muted-foreground flex items-center gap-1 font-medium">
                                                                    <Calendar className="h-3 w-3" /> Due: {new Date(assignment.due_date).toLocaleDateString()}
                                                                </span>
                                                            )}
                                                            <span className="text-[10px] text-muted-foreground">
                                                                Assigned {new Date(assignment.assigned_at).toLocaleDateString()}
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
                                        ))}
                                    </div>
                                </ScrollArea>
                            )}
                        </TabsContent>
                    </Tabs>
                </div>

                <DialogFooter className="p-6 border-t pt-4">
                    <Button variant="outline" onClick={onClose} disabled={isSaving}>Cancel</Button>
                    <Button
                        onClick={handleAssign}
                        disabled={isSaving || (selectedUserIds.length === 0 && selectedGroupIds.length === 0)}
                        className="min-w-[120px]"
                    >
                        {isSaving ? (
                            <>
                                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                Assigning...
                            </>
                        ) : (
                            <>Assign Selected ({selectedUserIds.length + selectedGroupIds.length})</>
                        )}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
