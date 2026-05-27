import React, { useState } from 'react';
import { cn } from '../lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Shield, Globe, Building2, ArrowRightLeft, ShieldCheck, CheckCircle2, AlertCircle, Loader2, Eye, EyeOff, Monitor, Sun, Moon } from 'lucide-react';
import { validatePassword } from '../lib/password-validation';
import { PasswordStrengthIndicator } from '../components/PasswordStrengthIndicator';
import { useAuth } from '../contexts/auth-context';
import { useTheme } from '../contexts/theme-context';
import { userService } from '../api/users';
import { settingsService } from '../api/settings';
import { authService } from '../api/auth';
import { useNavigate } from 'react-router-dom';
import { ProfileCard } from '../components/ProfileCard';

export const SettingsPage: React.FC = () => {
    const { user, activeTenant, selectTenant, refreshUser } = useAuth();
    const { theme, setTheme } = useTheme();
    const navigate = useNavigate();
    const [switchingId, setSwitchingId] = React.useState<string | null>(null);

    const handleSwitchTenant = async (tenantId: string) => {
        setSwitchingId(tenantId);
        try {
            const tokenResp = await authService.selectTenant(tenantId);
            const membership = user?.members.find((m) => m.tenant_id === tenantId);
            const tenant = membership?.tenant;
            if (!tenant) throw new Error('Tenant not found in memberships');
            await selectTenant(tenant, tokenResp.access_token);
            navigate('/dashboard');
        } catch (e) {
            console.error('Failed to switch tenant:', e);
        } finally {
            setSwitchingId(null);
        }
    };

    // --- Password form state ---
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [pwErrors, setPwErrors] = useState<Record<string, string>>({});
    const [isSavingPw, setIsSavingPw] = useState(false);
    const [pwSuccess, setPwSuccess] = useState<string | null>(null);
    const [pwApiError, setPwApiError] = useState<string | null>(null);

    const [showCurrentPassword, setShowCurrentPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

    const validatePwForm = (): boolean => {
        const errors: Record<string, string> = {};
        if (!currentPassword) errors.current = 'Current password is required.';
        if (!newPassword) errors.new = 'New password is required.';
        else {
            const result = validatePassword(newPassword);
            if (result.score < 3) {
                errors.new = 'Password is not strong enough.';
            }
        }

        if (newPassword === currentPassword) errors.new = 'New password must differ from your current password.';
        if (!confirmPassword) errors.confirm = 'Please confirm your new password.';
        else if (confirmPassword !== newPassword) errors.confirm = 'Passwords do not match.';
        setPwErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handlePasswordUpdate = async () => {
        setPwSuccess(null);
        setPwApiError(null);
        if (!validatePwForm()) return;
        setIsSavingPw(true);
        try {
            await userService.updatePassword(currentPassword, newPassword);
            setPwSuccess('Password updated successfully!');
            setCurrentPassword('');
            setNewPassword('');
            setConfirmPassword('');
            setPwErrors({});
        } catch (e: unknown) {
            const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
            const msg = typeof detail === 'string' ? detail : ((e as { message?: string })?.message || 'Failed to update password.');
            setPwApiError(typeof msg === 'string' ? msg : JSON.stringify(msg));
        } finally {
            setIsSavingPw(false);
        }
    };

    const handleThemeChange = async (newTheme: string) => {
        try {
            setTheme(newTheme as 'light' | 'dark' | 'system');
            await settingsService.updateTheme(newTheme as 'light' | 'dark' | 'system');
        } catch (e) {
            console.error('Failed to update theme preference:', e);
            // Revert on error
            setTheme(theme);
        }
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <Shield className="w-6 h-6 text-primary" />
                    </div>
                    Settings
                </h1>
                <p className="text-muted-foreground mt-1">Manage your account preferences and security.</p>
            </div>

            <Tabs defaultValue="profile" className="w-full">
                <TabsList className={cn('grid w-full lg:w-[480px]', user?.is_sysadmin ? 'grid-cols-3' : 'grid-cols-4')}>
                    <TabsTrigger value="profile">Profile</TabsTrigger>
                    {!user?.is_sysadmin && <TabsTrigger value="memberships">Memberships</TabsTrigger>}
                    <TabsTrigger value="security">Security</TabsTrigger>
                    <TabsTrigger value="appearance">Appearance</TabsTrigger>
                </TabsList>

                {/* Profile tab — Refined 2-column layout */}
                <TabsContent value="profile" className="mt-6 space-y-6">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                        {/* Left Column: Avatar & Overview */}
                        <div className="md:col-span-1 space-y-6">
                            <ProfileCard
                                user={user!}
                                activeTenantId={activeTenant?.id}
                                onRefresh={refreshUser}
                            />
                        </div>

                        {/* Right Column: Account & Preferences (Placeholder for future expandable settings) */}
                        <div className="md:col-span-2 space-y-6">
                            <Card className="border-border/50 shadow-sm overflow-hidden">
                                <CardHeader className="pb-4">
                                    <CardTitle className="text-xl flex items-center gap-3">
                                        <div className="p-2 rounded-lg bg-primary/10">
                                            <Building2 className="w-5 h-5 text-primary" />
                                        </div>
                                        Identity & Organization
                                    </CardTitle>
                                    <CardDescription>
                                        Your official identity within the platform.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                                        <div className="space-y-2">
                                            <Label className="text-sm font-semibold">Full Name</Label>
                                            <Input
                                                value={user?.full_name || ''}
                                                readOnly
                                                className="bg-muted/30 border-border/50 font-medium cursor-default"
                                            />
                                            <p className="text-[10px] text-muted-foreground/80 px-1">Managed by system administrator.</p>
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-sm font-semibold">Primary Email</Label>
                                            <Input
                                                value={user?.email || ''}
                                                readOnly
                                                className="bg-muted/30 border-border/50 font-medium cursor-default"
                                            />
                                            <p className="text-[10px] text-muted-foreground/80 px-1">Used for login and notifications.</p>
                                        </div>
                                    </div>
                                    <div className="pt-6 border-t border-border/50">
                                        <h4 className="text-sm font-bold mb-4">Account Status</h4>
                                        <div className="flex items-center gap-4">
                                            <div className="flex-1 p-4 rounded-xl bg-primary/5 border border-primary/10 flex items-center gap-4 shadow-sm transition-all hover:shadow-md">
                                                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                                    <CheckCircle2 className="h-6 w-6 text-primary" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-bold text-foreground">Verified Account</p>
                                                    <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">Your identity has been confirmed by the tenant manager.</p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                                <CardFooter className="bg-muted/10 border-t border-border/50 py-3">
                                    <p className="text-xs text-muted-foreground italic">If you need to change your legal name or email, please submit a request to your HR department.</p>
                                </CardFooter>
                            </Card>

                            {/* Any other profile settings can go here */}
                        </div>
                    </div>

                </TabsContent>

                {/* Memberships tab */}
                <TabsContent value="memberships" className="mt-6 space-y-6">
                    <Card className="border-border/50 shadow-sm">
                        <CardHeader>
                            <CardTitle className="text-xl flex items-center">
                                <Building2 className="w-5 h-5 mr-2 text-primary" /> Active Memberships
                            </CardTitle>
                            <CardDescription>
                                Organizations you belong to. Click "Switch" to change your active session.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {user?.members?.length === 0 && (
                                <p className="text-sm text-muted-foreground py-4 text-center">No active tenant memberships found.</p>
                            )}
                            {user?.members?.filter((m) => (m.tenant as { is_active?: boolean } | undefined)?.is_active !== false).map((membership, idx: number) => (
                                <div
                                    key={idx}
                                    className={cn(
                                    'flex items-center justify-between p-4 rounded-lg border transition-all',
                                    activeTenant?.id === membership.tenant_id
                                        ? 'border-primary bg-primary/5'
                                        : 'border-border bg-card'
                                )}
                                >
                                    <div className="flex items-center gap-4">
                                        <div
                                            className="w-10 h-10 rounded-md flex items-center justify-center text-white font-bold uppercase shadow-sm"
                                            style={{ backgroundColor: membership.tenant?.primary_color || 'var(--primary)' }}
                                        >
                                            {membership.tenant?.logo_url ? (
                                                <img src={membership.tenant.logo_url} alt={membership.tenant.name} className="w-8 h-8 object-contain" />
                                            ) : (
                                                membership.tenant?.name.substring(0, 2)
                                            )}
                                        </div>
                                        <div>
                                            <p className="font-semibold text-foreground text-lg">{membership.tenant?.name || 'Unknown Tenant'}</p>
                                            <p className="text-sm text-muted-foreground flex items-center gap-1.5 mt-0.5">
                                                <ShieldCheck className="w-4 h-4 text-primary" />
                                                Role: {membership.role}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {activeTenant?.id === membership.tenant_id ? (
                                            <span className="px-3 py-1 bg-primary text-primary-foreground text-xs font-semibold rounded-full">
                                                Active
                                            </span>
                                        ) : (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                className="gap-1.5"
                                                onClick={() => handleSwitchTenant(membership.tenant_id)}
                                                disabled={switchingId === membership.tenant_id || membership.is_active === false}
                                            >
                                                {switchingId === membership.tenant_id
                                                    ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                    : <ArrowRightLeft className="h-3.5 w-3.5" />
                                                }
                                                {membership.is_active === false ? 'Inactive' : 'Switch'}
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Security tab — Functional password form with enhanced UX */}
                <TabsContent value="security" className="mt-6 space-y-6">
                    <Card className="border-border/50 shadow-sm overflow-hidden">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-xl flex items-center gap-2">
                                <div className="p-2 rounded-lg bg-primary/10">
                                    <Shield className="w-5 h-5 text-primary" />
                                </div>
                                Password & Security
                            </CardTitle>
                            <CardDescription>
                                Secure your account by updating your password regularly.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {pwSuccess && (
                                <div className="flex items-center gap-2 text-sm text-foreground bg-muted border border-border px-3 py-2.5 rounded-lg">
                                    <CheckCircle2 className="h-4 w-4 shrink-0" />
                                    {pwSuccess}
                                </div>
                            )}
                            {pwApiError && (
                                <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/30 px-3 py-2.5 rounded-lg">
                                    <AlertCircle className="h-4 w-4 shrink-0" />
                                    {pwApiError}
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-5">
                                    <div className="space-y-2">
                                        <Label htmlFor="current" className="text-sm font-semibold">Current Password</Label>
                                        <div className="relative">
                                            <Input
                                                id="current"
                                                type={showCurrentPassword ? "text" : "password"}
                                                value={currentPassword}
                                                onChange={e => setCurrentPassword(e.target.value)}
                                                className={cn('pr-10', pwErrors.current ? 'border-destructive ring-destructive/20' : '')}
                                                placeholder="Enter current password"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                            >
                                                {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                        {pwErrors.current && <p className="text-[11px] text-destructive font-medium">{pwErrors.current}</p>}
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="new" className="text-sm font-semibold">New Password</Label>
                                        <div className="relative">
                                            <Input
                                                id="new"
                                                type={showNewPassword ? "text" : "password"}
                                                value={newPassword}
                                                onChange={e => setNewPassword(e.target.value)}
                                                className={cn('pr-10', pwErrors.new ? 'border-destructive ring-destructive/20' : '')}
                                                placeholder="Minimum 8 characters"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowNewPassword(!showNewPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                            >
                                                {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                        {pwErrors.new && <p className="text-[11px] text-destructive font-medium">{pwErrors.new}</p>}
                                        <PasswordStrengthIndicator password={newPassword} />
                                    </div>

                                    <div className="space-y-2">
                                        <Label htmlFor="confirm" className="text-sm font-semibold">Confirm New Password</Label>
                                        <div className="relative">
                                            <Input
                                                id="confirm"
                                                type={showConfirmPassword ? "text" : "password"}
                                                value={confirmPassword}
                                                onChange={e => setConfirmPassword(e.target.value)}
                                                className={cn('pr-10', pwErrors.confirm ? 'border-destructive ring-destructive/20' : '')}
                                                placeholder="Repeat new password"
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                                            >
                                                {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                            </button>
                                        </div>
                                        {pwErrors.confirm && <p className="text-[11px] text-destructive font-medium">{pwErrors.confirm}</p>}
                                    </div>
                                </div>

                                <div className="bg-muted/30 rounded-xl p-6 border border-border/50 flex flex-col justify-center">
                                    <div className="mb-4 w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                                        <ShieldCheck className="w-6 h-6 text-primary" />
                                    </div>
                                    <h4 className="text-base font-bold mb-2">Security Guidance</h4>
                                    <ul className="text-sm text-muted-foreground space-y-3">
                                        <li className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <span>Use a password manager to generate and store unique credentials.</span>
                                        </li>
                                        <li className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <span>Avoid reusing passwords from other social media or financial accounts.</span>
                                        </li>
                                        <li className="flex items-start gap-2">
                                            <div className="w-1.5 h-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                                            <span>After updating, you will remain logged in on this device.</span>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </CardContent>
                        <CardFooter className="border-t border-border/50 py-4 bg-muted/10 flex justify-end">
                            <Button onClick={handlePasswordUpdate} disabled={isSavingPw} className="px-8 shadow-sm">
                                {isSavingPw ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                                Save Changes
                            </Button>
                        </CardFooter>
                    </Card>
                </TabsContent>

                <TabsContent value="appearance" className="mt-6 space-y-6">
                    <Card className="border-border/50 shadow-sm overflow-hidden text-center sm:text-left">
                        <CardHeader className="pb-4">
                            <CardTitle className="text-xl flex items-center gap-2 justify-center sm:justify-start">
                                <div className="p-2 rounded-lg bg-primary/10">
                                    <Globe className="w-5 h-5 text-primary" />
                                </div>
                                System Theme
                            </CardTitle>
                            <CardDescription>
                                Personalize your workspace appearance. Choose between light, dark, or system defaults.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-8 pt-2">
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                                {/* Light Theme Card */}
                                <div
                                    onClick={() => handleThemeChange('light')}
                                    className={cn(
                                        'relative cursor-pointer group transition-all duration-300',
                                        (theme || 'system') === 'light' ? 'ring-2 ring-primary ring-offset-2 ring-offset-background scale-[1.02]' : 'hover:scale-[1.01]'
                                    )}
                                >
                                    <div className="aspect-[4/3] rounded-xl border border-border bg-background overflow-hidden shadow-sm group-hover:shadow-md transition-shadow">
                                        <div className="p-4 space-y-3">
                                            <div className="flex items-center gap-2">
                                                <div className="w-3 h-3 rounded-full bg-muted" />
                                                <div className="h-2 w-16 bg-muted rounded" />
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-2 w-full bg-muted/50 rounded" />
                                                <div className="h-2 w-[80%] bg-muted/50 rounded" />
                                            </div>
                                            <div className="h-8 w-full bg-muted rounded-md" />
                                        </div>
                                    </div>
                                    <div className="mt-3 flex items-center justify-between px-1">
                                        <div className="flex items-center gap-2">
                                            <Sun className={cn('w-4 h-4', (theme || 'system') === 'light' ? 'text-primary' : 'text-muted-foreground')} />
                                            <span className={cn('text-sm font-semibold', (theme || 'system') === 'light' ? 'text-foreground' : 'text-muted-foreground')}>Light Mode</span>
                                        </div>
                                        {(theme || 'system') === 'light' && <CheckCircle2 className="w-4 h-4 text-primary fill-primary/10" />}
                                    </div>
                                </div>

                                {/* Dark Theme Card */}
                                <div
                                    onClick={() => handleThemeChange('dark')}
                                    className={cn(
                                        'relative cursor-pointer group transition-all duration-300',
                                        (theme || 'system') === 'dark' ? 'ring-2 ring-primary ring-offset-2 ring-offset-background scale-[1.02]' : 'hover:scale-[1.01]'
                                    )}
                                >
                                    <div className="aspect-[4/3] rounded-xl border border-border bg-secondary overflow-hidden shadow-sm group-hover:shadow-md transition-shadow">
                                        <div className="p-4 space-y-3">
                                            <div className="flex items-center gap-2">
                                                <div className="w-3 h-3 rounded-full bg-secondary-foreground/20" />
                                                <div className="h-2 w-16 bg-secondary-foreground/20 rounded" />
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-2 w-full bg-secondary-foreground/10 rounded" />
                                                <div className="h-2 w-[80%] bg-secondary-foreground/10 rounded" />
                                            </div>
                                            <div className="h-8 w-full bg-secondary-foreground/20 rounded-md" />
                                        </div>
                                    </div>
                                    <div className="mt-3 flex items-center justify-between px-1">
                                        <div className="flex items-center gap-2">
                                            <Moon className={cn('w-4 h-4', (theme || 'system') === 'dark' ? 'text-primary' : 'text-muted-foreground')} />
                                            <span className={cn('text-sm font-semibold', (theme || 'system') === 'dark' ? 'text-foreground' : 'text-muted-foreground')}>Dark Mode</span>
                                        </div>
                                        {(theme || 'system') === 'dark' && <CheckCircle2 className="w-4 h-4 text-primary fill-primary/10" />}
                                    </div>
                                </div>

                                {/* System Theme Card */}
                                <div
                                    onClick={() => handleThemeChange('system')}
                                    className={cn(
                                        'relative cursor-pointer group transition-all duration-300',
                                        (theme || 'system') === 'system' ? 'ring-2 ring-primary ring-offset-2 ring-offset-background scale-[1.02]' : 'hover:scale-[1.01]'
                                    )}
                                >
                                    <div className="aspect-[4/3] rounded-xl border border-border/50 overflow-hidden shadow-sm group-hover:shadow-md transition-shadow relative">
                                        <div className="absolute inset-0 grid grid-cols-2">
                                            <div className="bg-background border-r border-border" />
                                            <div className="bg-secondary" />
                                        </div>
                                        <div className="absolute inset-0 p-4 space-y-3 pointer-events-none">
                                            <div className="flex items-center gap-2">
                                                <div className="w-3 h-3 rounded-full bg-muted-foreground/30" />
                                                <div className="h-2 w-16 bg-muted-foreground/30 rounded" />
                                            </div>
                                            <div className="space-y-2">
                                                <div className="h-2 w-full bg-muted rounded" />
                                                <div className="h-2 w-[80%] bg-muted rounded" />
                                            </div>
                                            <div className="h-8 w-full bg-muted-foreground/30 rounded-md" />
                                        </div>
                                    </div>
                                    <div className="mt-3 flex items-center justify-between px-1">
                                        <div className="flex items-center gap-2">
                                            <Monitor className={cn('w-4 h-4', (theme || 'system') === 'system' ? 'text-primary' : 'text-muted-foreground')} />
                                            <span className={cn('text-sm font-semibold', (theme || 'system') === 'system' ? 'text-foreground' : 'text-muted-foreground')}>System Default</span>
                                        </div>
                                        {(theme || 'system') === 'system' && <CheckCircle2 className="w-4 h-4 text-primary fill-primary/10" />}
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
};
