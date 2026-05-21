import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { Shield, Building2, ChevronRight, UserCircle, AlertCircle, Eye, EyeOff, GraduationCap } from 'lucide-react';
import { useAuth } from '../contexts/auth-context';
import { authService } from '../api/auth';
import { userService } from '../api/users';
import { ScrollArea } from '../components/ui/scroll-area';
import { authStorage } from '../lib/auth-storage';
import type { Tenant } from '../api/auth';
import { ApiError } from '../api/client';

const TEST_ACCOUNTS = [
    { label: 'Global Admin', email: 'admin@cpvmtraining.com', org: 'Global' },
    { label: 'L Krishanthan', email: 'lkrishanthan@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +1', email: 'lkrishanthan+1@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +2', email: 'lkrishanthan+2@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +3', email: 'lkrishanthan+3@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +4', email: 'lkrishanthan+4@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +5', email: 'lkrishanthan+5@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +6', email: 'lkrishanthan+6@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +7', email: 'lkrishanthan+7@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +8', email: 'lkrishanthan+8@gmail.com', org: 'Testing' },
    { label: 'L Krishanthan +9', email: 'lkrishanthan+9@gmail.com', org: 'Testing' },
];
const TEST_PASSWORD = 'Password123!';

export const AuthLogin: React.FC = () => {
    const navigate = useNavigate();
    const [step, setStep] = useState<'login' | 'select-tenant'>('login');
    const [isLoading, setIsLoading] = useState(false);
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [availableTenants, setAvailableTenants] = useState<Tenant[]>([]);
    const [isSysAdmin, setIsSysAdmin] = useState(false);

    const { login, selectTenant } = useAuth();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const { session_token } = await authService.login(email, password);
            authStorage.setToken(session_token);

            const [memberTenants, me] = await Promise.all([
                authService.getAvailableTenants(),
                userService.getMe(),
            ]);

            const userIsSysAdmin = me.is_sysadmin ?? false;
            setIsSysAdmin(userIsSysAdmin);

            if (userIsSysAdmin) {
                await login(session_token);
                navigate('/admin');
            } else {
                const activeTenants = memberTenants.filter(t => {
                    const membership = me.members?.find(m => m.tenant_id === t.id);
                    return t.is_active !== false && membership?.is_active !== false;
                });

                if (activeTenants.length > 1) {
                    setAvailableTenants(activeTenants);
                    setStep('select-tenant');
                } else if (activeTenants.length === 1) {
                    await handleSelectTenant(activeTenants[0]);
                } else {
                    setError('Your account is not associated with any active organization. Please contact your administrator.');
                    authStorage.removeToken();
                }
            }
        } catch (err) {
            if (err instanceof ApiError) {
                setError(err.message || 'Invalid credentials.');
            } else {
                setError('An unexpected error occurred.');
            }
            authStorage.removeToken();
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelectTenant = async (tenant: Tenant) => {
        setIsLoading(true);
        setError('');
        try {
            const { access_token } = await authService.selectTenant(tenant.id);
            await selectTenant(tenant, access_token);

            const updatedUser = await userService.getMe();
            const membership = updatedUser.members?.find(m => m.tenant_id === tenant.id);

            if (isSysAdmin || membership?.is_business_manager || membership?.is_training_creator) {
                navigate('/manage');
            } else {
                navigate('/dashboard');
            }
        } catch {
            setError('Failed to select organization.');
        } finally {
            setIsLoading(false);
        }
    };

    const fillTestAccount = (testEmail: string) => {
        setEmail(testEmail);
        setPassword(TEST_PASSWORD);
        setStep('login');
    };

    return (
        <div className="min-h-screen grid lg:grid-cols-2 bg-background">

            {/* Image / Branding Side */}
            <div className="hidden lg:block relative overflow-hidden">
                <img
                    src="https://images.unsplash.com/photo-1522071820081-009f0129c71c?auto=format&fit=crop&w=1200&q=80"
                    alt=""
                    aria-hidden="true"
                    className="absolute inset-0 h-full w-full object-cover"
                />
                {/* Gradient overlay: light at top, dark at bottom */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/50 to-black/20" />

                <div className="relative z-10 flex flex-col h-full p-12">
                    {/* Logo */}
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-white/20 backdrop-blur-sm flex items-center justify-center">
                            <GraduationCap className="h-5 w-5 text-white" />
                        </div>
                        <span className="text-sm font-bold text-white tracking-tight">Enterprise Learning Platform</span>
                    </div>

                    <div className="flex-1" />

                    {/* Bottom content */}
                    <div className="space-y-6">
                        <div className="space-y-3 max-w-sm">
                            <p className="text-white/50 text-xs font-semibold uppercase tracking-widest">
                                Employee Training & Compliance
                            </p>
                            <h2 className="text-3xl font-bold text-white leading-tight">
                                Train smarter.<br />Comply faster.<br />Grow together.
                            </h2>
                            <p className="text-white/70 text-sm leading-relaxed">
                                A unified portal for compliance training, certification management, and workforce development — purpose-built for modern organizations.
                            </p>
                        </div>

                        {/* Test Credentials — dev only */}
                        {(!import.meta.env.PROD || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') && (
                            <div className="rounded-xl border border-white/10 bg-black/30 backdrop-blur-sm p-4 flex flex-col max-h-[280px]">
                                <div className="flex items-center justify-between mb-3 shrink-0">
                                    <p className="text-xs font-semibold text-white/50 uppercase tracking-widest">🧪 Test Accounts</p>
                                    <p className="text-[10px] text-white/30 italic">Click row to fill →</p>
                                </div>
                                <ScrollArea className="flex-1 -mx-2 px-2 min-h-0">
                                    <div className="space-y-4 text-xs pb-2 pr-3">
                                        {Object.entries(
                                            TEST_ACCOUNTS.reduce((acc, curr) => {
                                                if (!acc[curr.org]) acc[curr.org] = [];
                                                acc[curr.org].push(curr);
                                                return acc;
                                            }, {} as Record<string, typeof TEST_ACCOUNTS>)
                                        ).map(([org, accounts]) => (
                                            <div key={org} className="space-y-1">
                                                <p className="px-2 text-[10px] font-bold text-white/40 uppercase tracking-tighter mb-1">{org}</p>
                                                <div className="space-y-0.5">
                                                    {accounts.map(({ label, email: testEmail }) => (
                                                        <button
                                                            key={testEmail}
                                                            type="button"
                                                            onClick={() => fillTestAccount(testEmail)}
                                                            className="w-full flex items-center justify-between px-2 py-1.5 rounded-md text-left hover:bg-white/10 active:bg-white/15 transition-colors group cursor-pointer border border-transparent hover:border-white/10"
                                                        >
                                                            <span className="text-white/60 group-hover:text-white transition-colors w-32 shrink-0 font-medium">{label}</span>
                                                            <span className="text-white/50 group-hover:text-white transition-colors truncate font-mono">{testEmail}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </ScrollArea>
                                <div className="mt-2 pt-2 border-t border-white/10 text-white/40 px-2 text-[11px] shrink-0 flex items-center justify-between">
                                    <span>Password: <span className="text-white/70 font-mono">{TEST_PASSWORD}</span></span>
                                    <span className="text-[9px] text-white/20 font-sans">v1.2.0</span>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Form Side */}
            <div className="flex items-center justify-center p-8 sm:p-12 relative">
                <div className="w-full max-w-md space-y-8">
                    <div className="flex flex-col items-center lg:items-start space-y-2 text-center lg:text-left">
                        {/* Mobile-only logo */}
                        <div className="flex items-center gap-2 lg:hidden mb-2">
                            <GraduationCap className="h-7 w-7 text-primary" />
                            <span className="text-sm font-bold text-foreground">Enterprise Learning Platform</span>
                        </div>
                        <h2 className="text-3xl font-bold tracking-tight text-foreground">Sign in to your account</h2>
                        <p className="text-muted-foreground">Enter your portal credentials below</p>
                    </div>

                    <Card className="border-border shadow-sm">
                        {step === 'login' && (
                            <form onSubmit={handleLogin}>
                                <CardHeader className="space-y-1">
                                    <CardTitle className="text-xl">Authentication</CardTitle>
                                    <CardDescription>
                                        Enter your email and password to continue
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {error && (
                                        <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm flex items-center gap-2">
                                            <AlertCircle className="w-4 h-4 shrink-0" />
                                            {error}
                                        </div>
                                    )}
                                    <div className="space-y-2">
                                        <Label htmlFor="email">Email address</Label>
                                        <Input
                                            id="email"
                                            type="email"
                                            placeholder="name@company.com"
                                            className="bg-background"
                                            value={email}
                                            onChange={(e) => setEmail(e.target.value)}
                                            required
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <div className="flex items-center justify-between">
                                            <Label htmlFor="password">Password</Label>
                                            <Link to="/forgot-password" className="text-sm font-medium text-primary hover:underline">
                                                Forgot password?
                                            </Link>
                                        </div>
                                        <div className="relative">
                                            <Input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                className="bg-background pr-10"
                                                value={password}
                                                onChange={(e) => setPassword(e.target.value)}
                                                required
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowPassword(!showPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary transition-all p-1.5 rounded-md hover:bg-muted"
                                                title={showPassword ? 'Hide password' : 'Show password'}
                                            >
                                                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                            </button>
                                        </div>
                                    </div>
                                </CardContent>
                                <CardFooter className="flex flex-col space-y-4">
                                    <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                                        {isLoading ? (
                                            <span className="flex items-center gap-2">
                                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/20 border-t-primary-foreground" />
                                                Authenticating...
                                            </span>
                                        ) : (
                                            <><Shield className="mr-2 h-4 w-4" /> Sign In Securely</>
                                        )}
                                    </Button>
                                    <div className="text-center text-sm space-y-1">
                                        <p className="text-muted-foreground">
                                            Got an invite?{' '}
                                            <button
                                                type="button"
                                                onClick={() => navigate('/register')}
                                                className="font-medium text-primary hover:underline underline-offset-2"
                                            >
                                                Register now →
                                            </button>
                                        </p>
                                        <p className="text-xs text-muted-foreground/70">
                                            No invite? Reach out to your manager or administrator.
                                        </p>
                                    </div>
                                </CardFooter>
                            </form>
                        )}

                        {step === 'select-tenant' && (
                            <div>
                                <CardHeader className="space-y-1 border-b border-border/50 pb-4">
                                    <CardTitle className="text-xl flex items-center gap-2">
                                        <Building2 className="w-5 h-5 text-primary" />
                                        Select Organization
                                    </CardTitle>
                                    <CardDescription>
                                        Your account is associated with multiple organizations. Please select one to continue.
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-2 pt-4">
                                    {error && (
                                        <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm flex items-center gap-2 mb-2">
                                            <AlertCircle className="w-4 h-4 shrink-0" />
                                            {error}
                                        </div>
                                    )}
                                    <p className="text-sm font-medium mb-3">Available Organizations</p>
                                    <div className="flex flex-col gap-2 max-h-72 overflow-y-auto pr-0.5">
                                        {availableTenants.map((t) => (
                                            <button
                                                key={t.id}
                                                onClick={() => handleSelectTenant(t)}
                                                disabled={isLoading}
                                                className="w-full flex items-center justify-between p-3 rounded-md border border-border hover:border-primary/50 hover:bg-muted/50 transition-all text-left group"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div
                                                        className="w-10 h-10 rounded-md flex items-center justify-center text-white font-bold uppercase shrink-0"
                                                        style={{ backgroundColor: t.primary_color || 'var(--primary)' }}
                                                    >
                                                        {t.logo_url ? (
                                                            <img src={t.logo_url} alt={t.name} className="w-8 h-8 rounded-sm object-contain" />
                                                        ) : (
                                                            t.name.substring(0, 2)
                                                        )}
                                                    </div>
                                                    <div className="flex flex-col min-w-0">
                                                        <span className="font-semibold text-foreground truncate">{t.name}</span>
                                                        <span className="text-xs text-muted-foreground flex items-center gap-1 font-medium group-hover:text-foreground transition-colors">
                                                            <UserCircle className="w-3 h-3 shrink-0" />
                                                            Click to Enter
                                                        </span>
                                                    </div>
                                                </div>
                                                <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors shrink-0" />
                                            </button>
                                        ))}
                                        {availableTenants.length === 0 && (
                                            <p className="text-sm text-muted-foreground text-center py-4">No active organizations found.</p>
                                        )}
                                    </div>
                                </CardContent>
                                <CardFooter className="pt-2 border-t border-border/50 bg-muted/10 flex flex-col gap-2">
                                    <Button variant="ghost" className="w-full text-muted-foreground" onClick={() => setStep('login')}>
                                        Back to Login
                                    </Button>
                                </CardFooter>
                            </div>
                        )}
                    </Card>

                    <p className="text-center text-sm text-muted-foreground">
                        By signing in, you agree to our{' '}
                        <Link to="/terms" className="underline underline-offset-4 hover:text-primary">Terms of Service</Link>
                        {' '}and{' '}
                        <Link to="/privacy" className="underline underline-offset-4 hover:text-primary">Privacy Policy</Link>.
                    </p>
                </div>
            </div>
        </div>
    );
};
