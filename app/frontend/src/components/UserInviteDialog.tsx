import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Loader2, Info, CheckCircle2, UserPlus, Copy, AlertCircle } from 'lucide-react';
import { userService } from '../api/users';
import { authService } from '../api/auth';
import type { Tenant } from '../api/auth';

interface UserInviteDialogProps {
    mode: 'admin' | 'manager';
    tenantId?: string; // Optional for manager mode, required context
    tenantName?: string;
    onClose: () => void;
    onSaved: () => void;
}

export const UserInviteDialog: React.FC<UserInviteDialogProps> = ({ mode, tenantId: initialTenantId, tenantName, onClose, onSaved }) => {
    const [email, setEmail] = useState('');
    const [fullName, setFullName] = useState('');
    const [selectedTenantId, setSelectedTenantId] = useState(initialTenantId || '');
    const [isManager, setIsManager] = useState(false);
    const [isCreator, setIsCreator] = useState(false);

    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState('');
    const [inviteUrl, setInviteUrl] = useState('');
    const [isCopied, setIsCopied] = useState(false);
    const [step, setStep] = useState<'form' | 'success'>('form');

    const [existingUser, setExistingUser] = useState<{
        id?: string;
        full_name?: string;
        existing_tenant_ids: string[];
        is_active: boolean;
    } | null>(null);

    // Load tenants for admin mode
    useEffect(() => {
        if (mode === 'admin') {
            authService.getAllTenants().then(setTenants).catch(console.error);
        }
    }, [mode]);

    // Lookup user when email changes (debounced)
    useEffect(() => {
        if (!email || !email.includes('@') || !email.includes('.')) {
            setExistingUser(null);
            setFullName('');
            setIsManager(false);
            setIsCreator(false);
            return;
        }

        const timer = setTimeout(async () => {
            setIsSearching(true);
            try {
                const resp = await userService.lookupUserByEmail(email);
                if (resp.id) {
                    setExistingUser(resp);
                    setFullName(resp.full_name || '');
                } else {
                    setExistingUser(null);
                    setFullName('');
                    setIsManager(false);
                    setIsCreator(false);
                }
            } catch (e) {
                console.error('Lookup failed', e);
                setExistingUser(null);
            } finally {
                setIsSearching(false);
            }
        }, 500);

        return () => clearTimeout(timer);
    }, [email]);

    const handleInvite = async () => {
        if (!email) { setError('Email is required.'); return; }
        if (!fullName.trim() && !existingUser) { setError('Full Name is required for new users.'); return; }
        if (mode === 'admin' && !selectedTenantId) { setError('Please select a tenant.'); return; }

        setIsSaving(true);
        setError('');

        try {
            let resp;
            if (mode === 'admin') {
                resp = await userService.adminInviteToTenant({
                    email,
                    full_name: fullName || undefined,
                    tenant_id: selectedTenantId,
                    is_business_manager: isManager,
                    is_training_creator: isCreator,
                });
            } else {
                resp = await userService.inviteUser({
                    email,
                    full_name: fullName || '',
                    is_business_manager: isManager,
                    is_training_creator: isCreator,
                });
            }
            
            if (resp.invite_url) {
                setInviteUrl(resp.invite_url);
                setStep('success');
            } else {
                // Fallback for cases where no URL is returned (unlikely)
                setTimeout(() => {
                    onSaved();
                    onClose();
                }, 2000);
            }
        } catch (e: unknown) {
            const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
            const msg = (e as { message?: string })?.message;
            setError(typeof detail === 'string' ? detail : (msg || 'Failed to send invitation.'));
        } finally {
            setIsSaving(false);
        }
    };

    const copyToClipboard = async () => {
        try {
            await navigator.clipboard.writeText(inviteUrl);
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy', err);
        }
    };

    const isUserInAllTenants = Boolean(mode === 'admin' && existingUser && tenants.length > 0 && existingUser.existing_tenant_ids.length >= tenants.length);
    const isAlreadyInCurrentTenant = Boolean(mode === 'manager' && existingUser && initialTenantId && existingUser.existing_tenant_ids.includes(initialTenantId));

    return (
        <Dialog open onOpenChange={onClose}>
            <DialogContent className="sm:max-w-[480px]">
                {step === 'form' ? (
                    <>
                        <DialogHeader>
                            <div className="flex items-center gap-2 mb-1">
                                <div className="p-2 bg-primary/10 rounded-lg">
                                    <UserPlus className="w-5 h-5 text-primary" />
                                </div>
                                <DialogTitle>{mode === 'admin' ? 'Add User to Tenant' : 'Invite Employee'}</DialogTitle>
                            </div>
                            <DialogDescription>
                                {mode === 'admin'
                                    ? 'Search for a user by email to add them to a tenant or invite them to the system.'
                                    : `Invite a new member to ${tenantName || 'your organization'}.`}
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-5 py-4">
                            {/* Email Input */}
                            <div className="space-y-2">
                                <Label htmlFor="invite-email" className="text-sm font-semibold">Email Address <span className="text-destructive">*</span></Label>
                                <div className="relative">
                                    <Input
                                        id="invite-email"
                                        placeholder="name@company.com"
                                        value={email}
                                        onChange={e => {
                                            setEmail(e.target.value);
                                            setError('');
                                        }}
                                        className={isSearching ? 'pr-10' : ''}
                                        autoComplete="off"
                                    />
                                    {isSearching && (
                                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                                        </div>
                                    )}
                                </div>
                                {existingUser && !isAlreadyInCurrentTenant && (
                                    <div className="flex items-center gap-2 px-2 text-[11px] text-primary font-medium">
                                        <CheckCircle2 className="w-3 h-3" />
                                        <span>Existing user found</span>
                                        {existingUser.is_active && <span className="bg-primary/10 px-1.5 py-0.5 rounded text-[10px]">Active</span>}
                                    </div>
                                )}
                                {isAlreadyInCurrentTenant && (
                                    <div className="flex items-center gap-2 px-2 text-[11px] text-destructive font-medium">
                                        <AlertCircle className="w-3 h-3" />
                                        <span>This user is already a member of your organization.</span>
                                    </div>
                                )}
                            </div>

                            {/* Name Input */}
                            <div className="space-y-2">
                                <Label htmlFor="invite-name" className="text-sm font-semibold">Full Name <span className="text-destructive">*</span></Label>
                                <Input
                                    id="invite-name"
                                    placeholder="Jane Doe"
                                    value={fullName}
                                    onChange={e => {
                                        setFullName(e.target.value);
                                        setError('');
                                    }}
                                    readOnly={!!existingUser}
                                    className={existingUser ? 'bg-muted/50 cursor-not-allowed border-dashed' : ''}
                                />
                                {existingUser && (
                                    <p className="text-[10px] text-muted-foreground px-1 italic">
                                        Name is derived from existing user profile and cannot be edited.
                                    </p>
                                )}
                            </div>

                            {/* ... (Role Selection and other inputs remain same, skipping for brevity in chunking if possible or including full) */}
                            {/* Tenant Selection (Admin Mode Only) */}
                            {mode === 'admin' && (
                                <div className="space-y-2">
                                    <Label className="text-sm font-semibold">Target Tenant</Label>
                                    <Select onValueChange={setSelectedTenantId} value={selectedTenantId}>
                                        <SelectTrigger className="w-full">
                                            <SelectValue placeholder="Select a tenant..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {tenants.map(t => (
                                                <SelectItem key={t.id} value={t.id}>
                                                    <div className="flex items-center gap-2">
                                                        <span>{t.name}</span>
                                                        {existingUser?.existing_tenant_ids.includes(t.id) && (
                                                            <span className="text-[10px] bg-muted px-1 rounded text-muted-foreground">Already Member</span>
                                                        )}
                                                    </div>
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            )}

                            {/* Role Selection */}
                            <div className="space-y-3">
                                <Label className="text-sm font-semibold block">Member Roles</Label>
                                <div className="grid grid-cols-1 gap-2">
                                    <label className={cn('flex items-start gap-3 p-3 rounded-lg border transition-all cursor-pointer', isManager ? 'bg-primary/5 border-primary/30 ring-1 ring-primary/20' : 'bg-card border-border hover:bg-muted/30')}>
                                        <input
                                            type="checkbox"
                                            checked={isManager}
                                            onChange={e => setIsManager(e.target.checked)}
                                            className="h-4 w-4 mt-1 accent-primary"
                                        />
                                        <div className="space-y-0.5">
                                            <p className="text-sm font-bold">Business Manager</p>
                                            <p className="text-xs text-muted-foreground">Admin access. Can manage users and view reports.</p>
                                        </div>
                                    </label>

                                    <label className={cn('flex items-start gap-3 p-3 rounded-lg border transition-all cursor-pointer', isCreator ? 'bg-primary/5 border-primary/30 ring-1 ring-primary/20' : 'bg-card border-border hover:bg-muted/30')}>
                                        <input
                                            type="checkbox"
                                            checked={isCreator}
                                            onChange={e => setIsCreator(e.target.checked)}
                                            className="h-4 w-4 mt-1 accent-primary"
                                        />
                                        <div className="space-y-0.5">
                                            <p className="text-sm font-bold">Training Creator</p>
                                            <p className="text-xs text-muted-foreground">Content access. Can create and manage courses.</p>
                                        </div>
                                    </label>
                                </div>
                                {!isManager && !isCreator && (
                                    <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 rounded-md">
                                        <p className="text-[11px] text-muted-foreground">
                                            User will have base <strong>Employee</strong> access.
                                        </p>
                                    </div>
                                )}
                            </div>

                            {error && <p className="text-sm text-destructive font-medium px-1 flex items-center gap-2"><AlertCircle className="w-4 h-4" /> {error}</p>}
                        </div>

                        <DialogFooter className="bg-muted/20 px-6 py-4 -mx-6 -mb-6 mt-2 border-t border-border/40">
                            <Button variant="ghost" onClick={onClose} disabled={isSaving}>Cancel</Button>
                            <Button
                                onClick={handleInvite}
                                disabled={isSaving || !email || !fullName || (mode === 'admin' && !selectedTenantId) || isUserInAllTenants || isAlreadyInCurrentTenant}
                                className="min-w-[120px]"
                            >
                                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                                {isSaving ? 'Processing...' : (mode === 'admin' ? 'Add to Tenant' : 'Send Invitation')}
                            </Button>
                        </DialogFooter>
                    </>
                ) : (
                    <>
                        <DialogHeader>
                            <div className="flex items-center gap-2 mb-1">
                                <div className="p-2 bg-primary/10 rounded-lg">
                                    <CheckCircle2 className="w-5 h-5 text-primary" />
                                </div>
                                <DialogTitle>Invitation Successful!</DialogTitle>
                            </div>
                            <DialogDescription>
                                An invitation email has been queued for {email}.
                            </DialogDescription>
                        </DialogHeader>

                        <div className="space-y-6 py-6">
                            <div className="space-y-3">
                                <Label className="text-xs text-muted-foreground uppercase font-bold tracking-wider">Direct Invite Link</Label>
                                <div className="flex gap-2">
                                    <Input
                                        value={inviteUrl}
                                        readOnly
                                        className="font-mono text-xs bg-muted/50 border-input"
                                    />
                                    <Button
                                        variant="outline"
                                        onClick={copyToClipboard}
                                        className="shrink-0 gap-2"
                                    >
                                        {isCopied ? <CheckCircle2 className="h-4 w-4 text-primary" /> : <Copy className="h-4 w-4" />}
                                        {isCopied ? 'Copied' : 'Copy'}
                                    </Button>
                                </div>
                                <p className="text-[11px] text-muted-foreground">
                                    You can copy this link and share it directly with the employee if they don't receive the email.
                                </p>
                            </div>

                            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 flex gap-3">
                                <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                                <div className="space-y-1">
                                    <p className="text-sm font-semibold text-foreground">What's next?</p>
                                    <p className="text-xs text-muted-foreground leading-relaxed">
                                        The user will appear as <strong>Pending</strong> in your directory until they complete their registration using the link above.
                                    </p>
                                </div>
                            </div>
                        </div>

                        <DialogFooter className="bg-muted/20 px-6 py-4 -mx-6 -mb-6 mt-2 border-t border-border/40">
                            <Button 
                                className="w-full sm:w-auto"
                                onClick={() => {
                                    onSaved();
                                    onClose();
                                }}
                            >
                                Done
                            </Button>
                        </DialogFooter>
                    </>
                )}
            </DialogContent>
        </Dialog>
    );
};
