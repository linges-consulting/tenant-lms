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
import { Search, UserPlus, UserMinus, Loader2, Info, ShieldCheck } from "lucide-react";
import { managerTrainingsApi, type TrainingCollaborator } from "../api/trainings";
import { userService, type User as UserType } from "../api/users";
import { useAuth } from "../contexts/auth-context";
import { Badge } from "./ui/badge";
import { cn } from "../lib/utils";

interface ManageEditorsModalProps {
    isOpen: boolean;
    onClose: () => void;
    trainingId: string;
    trainingTitle: string;
    currentCollaborators: TrainingCollaborator[];
    onUpdate: () => void;
}

export const ManageEditorsModal: React.FC<ManageEditorsModalProps> = ({
    isOpen,
    onClose,
    trainingId,
    trainingTitle,
    currentCollaborators,
    onUpdate,
}) => {
    const { user } = useAuth();
    const [allCreators, setAllCreators] = useState<UserType[]>([]);
    const [localCollaborators, setLocalCollaborators] = useState<TrainingCollaborator[]>(currentCollaborators);
    const [searchQuery, setSearchQuery] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [isProcessing, setIsProcessing] = useState<string | null>(null);

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
            const creators = users.filter(u => {
                const memberships = (u.members || ((u as unknown) as Record<string, unknown[]>)['memberships'] || []) as { is_training_creator?: boolean; isTrainingCreator?: boolean; role?: string }[];
                return memberships.some((m) =>
                    m.is_training_creator ||
                    m.isTrainingCreator ||
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

    const filteredCreators = allCreators.filter(u => {
        // Exclude current user and filter by search query
        const isSelf = u.id === user?.id;
        if (isSelf) return false;

        return (
            u.full_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            u.email.toLowerCase().includes(searchQuery.toLowerCase())
        );
    });

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="max-w-md h-[70vh] flex flex-col p-0 overflow-hidden">
                <DialogHeader className="p-6 pb-2">
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        Manage Editors: <span className="text-primary truncate max-w-[200px]">{trainingTitle}</span>
                    </DialogTitle>
                    <DialogDescription>
                        Assign other creators to help edit this training.
                    </DialogDescription>
                </DialogHeader>

                <div className="p-6 pt-2 flex-1 flex flex-col min-h-0 gap-4">
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
                            <Badge variant="outline" className="text-[10px]">{filteredCreators.length}</Badge>
                        </div>
                        <ScrollArea className="flex-1">
                            {isLoading ? (
                                <div className="flex flex-col items-center justify-center py-20 gap-2">
                                    <Loader2 className="h-6 w-6 animate-spin text-primary" />
                                    <p className="text-xs text-muted-foreground">Loading creators...</p>
                                </div>
                            ) : filteredCreators.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-20 gap-2 text-muted-foreground">
                                    <Info className="h-6 w-6 opacity-20" />
                                    <p className="text-xs italic">No creators found matching search.</p>
                                </div>
                            ) : (
                                <div className="p-2 space-y-1">
                                    {filteredCreators.map(user => {
                                        const active = isCollaborator(user.id);
                                        const processing = isProcessing === user.id;
                                        
                                        return (
                                            <div key={user.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-background transition-colors border border-transparent hover:border-border group">
                                                <div className="flex items-center gap-3 min-w-0">
                                                    <div className={cn('w-8 h-8 rounded-full flex items-center justify-center shrink-0', active ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground')}>
                                                        <ShieldCheck className="h-4 w-4" />
                                                    </div>
                                                    <div className="min-w-0">
                                                        <p className="text-sm font-semibold truncate leading-none mb-1">{user.full_name || user.email}</p>
                                                        <p className="text-[10px] text-muted-foreground truncate">{user.email}</p>
                                                    </div>
                                                </div>
                                                
                                                <Button
                                                    size="sm"
                                                    variant={active ? "ghost" : "outline"}
                                                    className={cn('h-8 w-8 p-0 rounded-full transition-all', active ? 'text-destructive hover:bg-destructive/10' : 'text-primary hover:bg-primary/10')}
                                                    onClick={() => active ? handleRemoveCollaborator(user.id) : handleAddCollaborator(user.id)}
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
