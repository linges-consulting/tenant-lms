import React, { useState } from 'react';
import { cn } from '../lib/utils';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { Pencil, Check, X, Edit2, Mail, Calendar, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { UserAvatar } from './UserAvatar';
import { AvatarSelectionModal } from './AvatarSelectionModal';
import { userService } from '../api/users';
import { settingsService } from '../api/settings';
import { getApiError } from '../lib/utils';

interface ProfileCardProps {
    user: Record<string, unknown>;
    activeTenantId?: string | null;
    isViewOnly?: boolean;
    onRefresh?: () => Promise<void>;
}

export const ProfileCard: React.FC<ProfileCardProps> = ({
    user,
    activeTenantId,
    isViewOnly = false,
    onRefresh
}) => {
    // Editing state
    const [username, setUsername] = useState(user?.username || '');
    const [isEditingUsername, setIsEditingUsername] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [errorMessage, setErrorMessage] = useState('');

    // Avatar state
    const [avatarModalOpen, setAvatarModalOpen] = useState(false);
    const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);

    const handleUsernameUpdate = async () => {
        if (username === user?.username) {
            setIsEditingUsername(false);
            return;
        }

        setIsSaving(true);
        setSuccessMessage('');
        setErrorMessage('');

        try {
            await userService.updateMe({ username });
            setSuccessMessage('Username updated successfully!');
            if (onRefresh) await onRefresh();
            setIsEditingUsername(false);
        } catch (e: unknown) {
            setErrorMessage(getApiError(e, 'Failed to update username.'));
        } finally {
            setIsSaving(false);
        }
    };

    const handleAvatarShapeSelect = async (shapeId: string | null) => {
        setErrorMessage('');
        setSuccessMessage('');
        setIsUploadingAvatar(true);

        try {
            await settingsService.updateSettings({ avatar_url: shapeId });
            setSuccessMessage(shapeId ? 'Avatar updated successfully!' : 'Avatar removed.');
            if (onRefresh) await onRefresh();
        } catch (e: unknown) {
            setErrorMessage(getApiError(e, 'Failed to update avatar.'));
        } finally {
            setIsUploadingAvatar(false);
        }
    };

    const getActiveRoles = () => {
        // SysAdmin exclusivity: if the user is a sysadmin, we don't show tenant roles
        if (user?.is_sysadmin) return [];
        if (!user?.members) return [];

        // Find membership for active tenant context - dash-agnostic matching
        type Membership = { tenant_id?: string; is_business_manager?: boolean; isBusinessManager?: boolean; is_training_creator?: boolean; isTrainingCreator?: boolean; is_employee?: boolean; isEmployee?: boolean; role?: string };
        const members = user.members as Membership[];
        const targetId = String(activeTenantId || '').replace(/-/g, '').toLowerCase().trim();
        const membership = members.find((m) =>
            String(m.tenant_id || '').replace(/-/g, '').toLowerCase().trim() === targetId
        );

        const m = membership || (members.length > 0 ? members[0] : null);
        if (!m) return ['Employee'];

        const roles = [];
        const isManager = m.is_business_manager || m.isBusinessManager || m.role === 'Business Manager' || m.role === 'Manager';
        const isCreator = m.is_training_creator || m.isTrainingCreator || m.role === 'Training Creator' || m.role === 'Creator';
        const isEmployee = m.is_employee || m.isEmployee || m.role === 'Employee';

        if (isManager) roles.push('Manager');
        if (isCreator) roles.push('Creator');
        if (roles.length === 0 || isEmployee) roles.push('Employee');

        return roles;
    };

    const roles = getActiveRoles();
    const initials = (user?.full_name || user?.username || 'U')
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase();

    return (
        <Card className="border-border/50 shadow-sm overflow-hidden bg-card/50 backdrop-blur-sm">
            <CardContent className="pt-8 pb-6">
                <div className="flex flex-col items-center text-center">
                    <div className="relative group">
                        <div className="h-32 w-32 border-4 border-background rounded-xl shadow-xl overflow-hidden bg-muted/30">
                            <UserAvatar
                                initials={initials}
                                shapeId={user?.avatar_url || null}
                                className="w-full h-full"
                                variant="rounded-square"
                            />
                        </div>
                        {!isViewOnly && (
                            <button
                                onClick={() => setAvatarModalOpen(true)}
                                disabled={isUploadingAvatar}
                                className="absolute bottom-1 right-1 p-2 bg-primary text-primary-foreground rounded-full shadow-lg hover:bg-primary/90 transition-all transform hover:scale-110 disabled:opacity-50 disabled:cursor-not-allowed group-hover:scale-110"
                                title="Change Avatar"
                            >
                                {isUploadingAvatar ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pencil className="h-4 w-4" />}
                            </button>
                        )}
                    </div>

                    <h1 className="mt-4 text-2xl font-bold text-foreground tracking-tight">{user?.full_name}</h1>

                    {/* Username Display/Editor */}
                    <div className="mt-1 flex items-center justify-center min-h-[32px]">
                        {isEditingUsername && !isViewOnly ? (
                            <div className="flex items-center gap-2">
                                <Input
                                    value={username}
                                    onChange={(e) => setUsername(e.target.value)}
                                    className="h-8 text-sm w-36 text-center shadow-sm"
                                    autoFocus
                                    disabled={isSaving}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') handleUsernameUpdate();
                                        if (e.key === 'Escape') {
                                            setUsername(user?.username || '');
                                            setIsEditingUsername(false);
                                        }
                                    }}
                                />
                                <button
                                    onClick={handleUsernameUpdate}
                                    className="p-1.5 bg-primary/5 text-primary hover:bg-primary/10 rounded-md transition-colors"
                                    title="Save"
                                    disabled={isSaving}
                                >
                                    {isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                                </button>
                                <button
                                    onClick={() => {
                                        setUsername(user?.username || '');
                                        setIsEditingUsername(false);
                                    }}
                                    className="p-1.5 bg-destructive/5 text-destructive hover:bg-destructive/10 rounded-md transition-colors"
                                    title="Cancel"
                                    disabled={isSaving}
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            </div>
                        ) : (
                            <div
                                className={cn('flex items-center gap-1.5 px-3 py-1 rounded-full transition-all border border-transparent', !isViewOnly && 'cursor-pointer hover:bg-muted/80 hover:border-border/50 hover:shadow-sm group/username')}
                                onClick={() => !isViewOnly && setIsEditingUsername(true)}
                            >
                                <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">@{user?.username || 'user'}</span>
                                {!isViewOnly && <Edit2 className="h-3 w-3 text-muted-foreground opacity-0 group-hover/username:opacity-100 transition-opacity" />}
                            </div>
                        )}
                    </div>

                    {/* Role Badges - Filtered for Current Tenant */}
                    <div className="mt-4 flex flex-wrap justify-center gap-2">
                        {user?.is_sysadmin && (
                            <Badge className="bg-primary/10 text-primary border-primary/20 shadow-sm">
                                SYSADMIN
                            </Badge>
                        )}
                        {roles.map((role, idx) => (
                            <Badge key={idx} variant="outline" className="text-xs font-medium bg-background/50 backdrop-blur-sm border-border/50">
                                {role}
                            </Badge>
                        ))}
                    </div>
                </div>

                {/* Meta Information */}
                <div className="mt-8 pt-6 border-t border-border/50 space-y-4 text-sm">
                    <div className="flex items-center text-muted-foreground group/info">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center mr-4 transition-colors group-hover/info:bg-primary/20">
                            <Mail className="h-4.5 w-4.5 text-primary" />
                        </div>
                        <div className="flex flex-col min-w-0">
                            <span className="text-[10px] font-bold tracking-wider text-muted-foreground/60 uppercase">Email Address</span>
                            <span className="text-foreground font-semibold truncate">{user?.email}</span>
                        </div>
                    </div>
                    <div className="flex items-center text-muted-foreground group/info">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center mr-4 transition-colors group-hover/info:bg-primary/20">
                            <Calendar className="h-4.5 w-4.5 text-primary" />
                        </div>
                        <div className="flex flex-col">
                            <span className="text-[10px] font-bold tracking-wider text-muted-foreground/60 uppercase">Joined Date</span>
                            <span className="text-foreground font-semibold">
                                {user?.created_at ? new Date(user.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }) : 'N/A'}
                            </span>
                        </div>
                    </div>
                </div>

                {/* Feedback Messages */}
                {successMessage && (
                    <div className="mt-6 flex items-center gap-2 text-xs text-primary bg-primary/5 border border-primary/20 px-3 py-2 rounded-lg">
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                        {successMessage}
                    </div>
                )}
                {errorMessage && (
                    <div className="mt-6 flex items-center gap-2 text-xs text-destructive bg-destructive/10 border border-destructive/30 px-3 py-2 rounded-lg">
                        <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                        {errorMessage}
                    </div>
                )}
            </CardContent>

            {/* Avatar Modal Integration */}
            {!isViewOnly && (
                <AvatarSelectionModal
                    open={avatarModalOpen}
                    onOpenChange={setAvatarModalOpen}
                    selectedAvatarId={user?.avatar_url || null}
                    onSelectAvatar={handleAvatarShapeSelect}
                    onRemoveAvatar={() => handleAvatarShapeSelect(null)}
                    isLoading={isUploadingAvatar}
                    userInitials={initials}
                />
            )}
        </Card>
    );
};
