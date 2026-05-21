import React, { useState, useEffect } from 'react';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";
import { Badge } from "./ui/badge";
import { Search, UserPlus, UserMinus, Loader2, Info, ShieldCheck, Clock, CircleDot, CheckCircle, Archive, AlertTriangle } from "lucide-react";
import { managerTrainingsApi, type TrainingCollaborator, type Training } from "../api/trainings";
import { userService, type User as UserType, type TenantMembership } from "../api/users";
import { useAuth } from "../contexts/auth-context";
import { cn } from "../lib/utils";

interface ManageCollaboratorsModalProps {
    isOpen: boolean;
    onClose: () => void;
    trainingId: string;
    trainingTitle: string;
    trainingStatus: Training['lifecycle_status'];
    currentCollaborators: TrainingCollaborator[];
    onUpdate: () => void;
}

function StatusBadge({ status }: { status: Training['lifecycle_status'] }) {
    if (status === 'draft') {
        return (
            <Badge variant="secondary" className="bg-muted text-muted-foreground border-border px-2 py-0.5">
                <Clock className="w-3 h-3 mr-1" /> Draft
            </Badge>
        );
    }
    if (status === 'ready') {
        return (
            <Badge className="bg-blue-100 text-blue-700 border-blue-200 px-2 py-0.5">
                <CircleDot className="w-3 h-3 mr-1" /> Ready
            </Badge>
        );
    }
    if (status === 'published') {
        return (
            <Badge className="bg-green-100 text-green-700 border-green-200 px-2 py-0.5">
                <CheckCircle className="w-3 h-3 mr-1" /> Published
            </Badge>
        );
    }
    if (status === 'archived') {
        return (
            <Badge className="bg-orange-100 text-orange-700 border-orange-200 px-2 py-0.5">
                <Archive className="w-3 h-3 mr-1" /> Archived
            </Badge>
        );
    }
    return null;
}

export const ManageCollaboratorsModal: React.FC<ManageCollaboratorsModalProps> = ({
    isOpen,
    onClose,
    trainingId,
    trainingTitle,
    trainingStatus,
    currentCollaborators,
    onUpdate,
}) => {
    const { user } = useAuth();
    const [allCreators, setAllCreators] = useState<UserType[]>([]);
    const [localCollaborators, setLocalCollaborators] = useState<TrainingCollaborator[]>(currentCollaborators);
    const [searchQuery, setSearchQuery] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isProcessing, setIsProcessing] = useState<string | null>(null);

    const isNotDraft = trainingStatus !== 'draft';

    // Sync local state when props change (initial load or parent refresh)
    useEffect(() => {
        setLocalCollaborators(currentCollaborators);
    }, [currentCollaborators]);

    useEffect(() => {
        if (isOpen && trainingId) {
            loadCreators();
        }
    }, [isOpen, trainingId]);

    const loadCreators = async () => {
        setIsLoading(true);
        try {
            const users = await userService.listTenantUsers();

            // Filter users who have the Training Creator role in this tenant
            const creators = users.filter(u => {
                const memberships: TenantMembership[] = u.members || [];
                return memberships.some((m: TenantMembership) =>
                    m.is_training_creator ||
                    m.role === 'Training Creator' ||
                    m.role === 'Creator'
                );
            });
            setAllCreators(creators);
        } catch (error) {
            console.error("Failed to load creators", error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleAddCollaborator = async (userId: string) => {
        setIsProcessing(userId);
        try {
            await managerTrainingsApi.addCollaborators(trainingId, [userId]);
            // Optimistic update
            setLocalCollaborators(prev => [...prev, { user_id: userId, training_id: trainingId } as TrainingCollaborator]);
            onUpdate();
        } catch (error) {
            console.error("Failed to add collaborator", error);
        } finally {
            setIsProcessing(null);
        }
    };

    const handleRemoveCollaborator = async (userId: string) => {
        setIsProcessing(userId);
        try {
            await managerTrainingsApi.removeCollaborator(trainingId, userId);
            // Optimistic update
            setLocalCollaborators(prev => prev.filter(c => c.user_id !== userId));
            onUpdate();
        } catch (error) {
            console.error("Failed to remove collaborator", error);
        } finally {
            setIsProcessing(null);
        }
    };

    const isCollaborator = (userId: string) =>
        localCollaborators.some(c => c.user_id === userId);

    // Look up a collaborator's display name from the loaded creators list
    const getCollaboratorName = (userId: string): string => {
        const found = allCreators.find(u => u.id === userId);
        if (found) return found.full_name || found.email || userId;
        return userId;
    };

    const filteredCreators = allCreators.filter(u => {
        // Exclude current user and filter by search query
        const isSelf = u.id === user?.id;
        if (isSelf) return false;

        return (
            u.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.email.toLowerCase().includes(searchQuery.toLowerCase())
        );
    });

    // Sort: collaborators first, then non-collaborators
    const sortedCreators = [...filteredCreators].sort((a, b) => {
        const aIsCollab = isCollaborator(a.id) ? 0 : 1;
        const bIsCollab = isCollaborator(b.id) ? 0 : 1;
        return aIsCollab - bIsCollab;
    });

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-md h-[75vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-6 pb-2">
                    <DialogTitle className="text-xl font-bold flex items-center gap-2 flex-wrap">
                        Manage Collaborators
                        <StatusBadge status={trainingStatus} />
                    </DialogTitle>
                    <DialogDescription className="truncate">
                        {trainingTitle}
                    </DialogDescription>
                </DialogHeader>

                <div className="p-6 pt-2 flex-1 flex flex-col min-h-0 gap-4">
                    {/* Edit-lock notice when not in Draft */}
                    {isNotDraft && (
                        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-amber-800">
                            <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-500" />
                            <p className="text-xs leading-snug">
                                Collaborators can view but not edit — training must be in <strong>Draft</strong> state to edit content.
                            </p>
                        </div>
                    )}

                    {/* Current collaborators summary strip */}
                    {localCollaborators.length > 0 && (
                        <div className="rounded-lg border bg-muted/30 px-3 py-2">
                            <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1.5">
                                Current Collaborators ({localCollaborators.length})
                            </p>
                            <div className="flex flex-wrap gap-1">
                                {localCollaborators.map(c => (
                                    <Badge key={c.user_id} variant="outline" className="text-[10px] py-0">
                                        {isLoading ? c.user_id : getCollaboratorName(c.user_id)}
                                    </Badge>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <input
                            className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all text-sm"
                            placeholder="Find creators by name or email..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    <div className="flex-1 min-h-0 border rounded-xl bg-muted/20 overflow-hidden flex flex-col">
                        <div className="p-2 px-3 border-b bg-background/50 flex items-center justify-between">
                            <h4 className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Available Creators</h4>
                            <Badge variant="outline" className="text-[10px]">{sortedCreators.length}</Badge>
                        </div>
                        <ScrollArea className="flex-1">
                            {isLoading ? (
                                <div className="flex flex-col items-center justify-center py-20 gap-2">
                                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                                    <p className="text-xs text-muted-foreground">Loading creators...</p>
                                </div>
                            ) : sortedCreators.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-20 gap-2 text-muted-foreground">
                                    <Info className="h-6 w-6 opacity-20" />
                                    <p className="text-xs italic">No creators found matching search.</p>
                                </div>
                            ) : (
                                <div className="p-2 space-y-1">
                                    {sortedCreators.map(creator => {
                                        const active = isCollaborator(creator.id);
                                        const processing = isProcessing === creator.id;

                                        return (
                                            <div key={creator.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-background transition-colors border border-transparent hover:border-border group">
                                                <div className="flex items-center gap-3 min-w-0">
                                                    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center shrink-0', active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground')}>
                                                        <ShieldCheck className="h-4 w-4" />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-semibold truncate leading-none mb-1">
                                                            {creator.full_name || creator.email}
                                                        </p>
                                                        <p className="text-[10px] text-muted-foreground truncate">{creator.email}</p>
                                                    </div>
                                                </div>

                                                <Button
                                                    size="sm"
                                                    variant={active ? "ghost" : "outline"}
                                                    className={cn('h-8 w-8 p-0 rounded-full transition-all', active ? 'text-destructive hover:bg-destructive/10' : 'text-primary hover:bg-primary/10')}
                                                    onClick={() => active ? handleRemoveCollaborator(creator.id) : handleAddCollaborator(creator.id)}
                                                    disabled={processing || !!isProcessing}
                                                >
                                                    {processing ? (
                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                    ) : active ? (
                                                        <UserMinus className="h-4 w-4" />
                                                    ) : (
                                                        <UserPlus className="h-4 w-4" />
                                                    )}
                                                </Button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </ScrollArea>
                    </div>
                </div>

                <DialogFooter className="p-4 border-t bg-muted/10">
                    <Button variant="ghost" onClick={onClose} className="w-full">Done</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
