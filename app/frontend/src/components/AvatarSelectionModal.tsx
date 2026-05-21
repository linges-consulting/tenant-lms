import React from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2 } from 'lucide-react';
import { AVATAR_SHAPES, getAvatarShapeById } from '../utils/avatar-shapes';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { cn } from '../lib/utils';

interface AvatarSelectionModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    selectedAvatarId: string | null;
    onSelectAvatar: (avatarId: string) => Promise<void>;
    onRemoveAvatar: () => Promise<void>;
    isLoading?: boolean;
    userInitials: string;
}

export const AvatarSelectionModal: React.FC<AvatarSelectionModalProps> = ({
    open,
    onOpenChange,
    selectedAvatarId,
    onSelectAvatar,
    onRemoveAvatar,
    isLoading = false,
    userInitials,
}) => {
    const [selecting, setSelecting] = React.useState<string | null>(null);
    const [isRemoving, setIsRemoving] = React.useState(false);

    const handleSelectAvatar = async (avatarId: string) => {
        setSelecting(avatarId);
        try {
            await onSelectAvatar(avatarId);
            onOpenChange(false);
        } catch (error) {
            console.error('Failed to select avatar:', error);
        } finally {
            setSelecting(null);
        }
    };

    const handleRemoveAvatar = async () => {
        setIsRemoving(true);
        try {
            await onRemoveAvatar();
            onOpenChange(false);
        } catch (error) {
            console.error('Failed to remove avatar:', error);
        } finally {
            setIsRemoving(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl max-h-[90vh] overflow-auto">
                <DialogHeader>
                    <DialogTitle>Choose Your Avatar</DialogTitle>
                    <DialogDescription>
                        Select one of our predefined avatars to represent you in the system.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-6">
                    {/* Current Avatar Preview */}
                    {selectedAvatarId && (
                        <div className="flex items-center gap-4 p-4 rounded-lg border border-border bg-muted/30">
                            <Avatar className="w-16 h-16 border border-border">
                                <AvatarImage src={getAvatarShapeById(selectedAvatarId)?.image} alt={selectedAvatarId} />
                                <AvatarFallback>{userInitials}</AvatarFallback>
                            </Avatar>
                            <div>
                                <p className="text-sm font-medium">Current Avatar</p>
                                <p className="text-xs text-muted-foreground">
                                    {AVATAR_SHAPES.find(s => s.id === selectedAvatarId)?.label}
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Avatar Grid */}
                    <div className="space-y-3">
                        <h3 className="text-sm font-medium">Available Avatars</h3>
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-4">
                            {AVATAR_SHAPES.map((avatar) => (
                                <button
                                    key={avatar.id}
                                    onClick={() => handleSelectAvatar(avatar.id)}
                                    disabled={isLoading || selecting !== null || isRemoving}
                                    className={cn(
                                        'flex flex-col items-center gap-3 p-3 rounded-lg border-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed',
                                        selectedAvatarId === avatar.id
                                            ? 'border-primary bg-primary/10 shadow-md'
                                            : 'border-border hover:border-primary/50 bg-card'
                                    )}
                                >
                                    <Avatar className="w-14 h-14 border border-border">
                                        <AvatarImage
                                            src={avatar.image}
                                            alt={avatar.label}
                                        />
                                        <AvatarFallback>{userInitials}</AvatarFallback>
                                    </Avatar>
                                    {selecting === avatar.id && (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    )}
                                    <span className="text-xs font-medium text-center line-clamp-2">
                                        {avatar.label}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <DialogFooter className="flex gap-2">
                    {selectedAvatarId && (
                        <Button
                            onClick={handleRemoveAvatar}
                            disabled={isLoading || selecting !== null || isRemoving}
                            variant="outline"
                            className="text-destructive hover:bg-destructive/10 flex-1 sm:flex-none"
                        >
                            {isRemoving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Use Initials Instead
                        </Button>
                    )}
                    <Button
                        onClick={() => onOpenChange(false)}
                        disabled={isLoading || selecting !== null || isRemoving}
                        variant="outline"
                    >
                        Close
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
