import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { userService, type CreateUserResponse } from '../api/users';
import { useFormDialog, extractErrorMessage } from '../hooks/useFormDialog';

interface AddAdminDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onAdminCreated?: () => void;
}

export const AddAdminDialog: React.FC<AddAdminDialogProps> = ({
    open,
    onOpenChange,
    onAdminCreated,
}) => {
    const [email, setEmail] = useState('');
    const [fullName, setFullName] = useState('');
    const [registrationToken, setRegistrationToken] = useState<CreateUserResponse | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Use custom hook for form state management
    const { isLoading, setIsLoading, error, setError, resetForm } = useFormDialog();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        // Prevent double submission
        if (isSubmitting || isLoading) {
            return;
        }

        setError('');

        if (!email.trim()) {
            setError('Email is required');
            return;
        }

        // Basic email validation
        if (!email.includes('@')) {
            setError('Please enter a valid email address');
            return;
        }

        if (!fullName.trim()) {
            setError('Full name is required');
            return;
        }

        setIsSubmitting(true);
        setIsLoading(true);
        try {
            const result = await userService.inviteSysAdmin(email, fullName);
            // Show token display inline
            setRegistrationToken(result);

            // Reset form
            setEmail('');
            setFullName('');
        } catch (e: unknown) {
            setError(extractErrorMessage(e));
        } finally {
            setIsLoading(false);
            setIsSubmitting(false);
        }
    };

    const handleOpenChange = (newOpen: boolean) => {
        if (!newOpen) {
            // Reset form when closing
            setEmail('');
            setFullName('');
            resetForm();
            setRegistrationToken(null);
        }
        onOpenChange(newOpen);
    };

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>{registrationToken ? 'Administrator Created Successfully!' : 'Add Administrator'}</DialogTitle>
                    <DialogDescription>
                        {registrationToken
                            ? 'Share the registration link below with the new administrator.'
                            : 'Create a new system administrator account. The user can complete their profile after first login.'}
                    </DialogDescription>
                </DialogHeader>

                {registrationToken ? (
                    <div className="space-y-4 py-4">
                        <div className="flex items-center gap-3 p-4 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
                            <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                            <p className="text-sm text-emerald-800 dark:text-emerald-300">
                                Administrator created. They will also receive an email invitation.
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>Registration Link</Label>
                            <div className="flex gap-2">
                                <Input value={registrationToken.registration_url} readOnly className="font-mono text-sm" />
                                <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(registrationToken.registration_url)}>Copy</Button>
                            </div>
                        </div>
                        <DialogFooter className="mt-6">
                            <Button onClick={() => { handleOpenChange(false); onAdminCreated?.(); }}>Done</Button>
                        </DialogFooter>
                    </div>
                ) : (
                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="admin-email">
                                Email Address <span className="text-destructive">*</span>
                            </Label>
                            <Input
                                id="admin-email"
                                type="email"
                                placeholder="admin@example.com"
                                value={email}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                                disabled={isLoading}
                                className={error && error.includes('email') ? 'border-destructive' : ''}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="admin-name">Full Name <span className="text-destructive">*</span></Label>
                            <Input
                                id="admin-name"
                                type="text"
                                placeholder="John Doe"
                                value={fullName}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFullName(e.target.value)}
                                disabled={isLoading}
                            />
                        </div>

                        {error && (
                            <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/30 px-3 py-2 rounded-md">
                                <AlertCircle className="h-4 w-4 shrink-0" />
                                {error}
                            </div>
                        )}

                        <p className="text-xs text-muted-foreground">
                            The admin will receive a welcome email with instructions to set their password and complete their profile.
                        </p>

                        <DialogFooter className="gap-2">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => handleOpenChange(false)}
                                disabled={isLoading}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" disabled={isLoading}>
                                {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                                {isLoading ? 'Creating...' : 'Create Admin'}
                            </Button>
                        </DialogFooter>
                    </form>
                )}
            </DialogContent>
        </Dialog>
    );
};
