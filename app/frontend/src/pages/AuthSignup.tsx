import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { AlertCircle, Check, X, Eye, EyeOff, ArrowLeft, GraduationCap, MailCheck, KeyRound } from 'lucide-react';
import { PasswordStrengthIndicator } from '../components/PasswordStrengthIndicator';
import { validatePassword } from '../lib/password-validation';
import { authService } from '../api/auth';
import { ApiError } from '../api/client';

type SignupStep = 'invite' | 'credentials';

export const AuthSignup: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [step, setStep] = useState<SignupStep>('invite');
    const [isLoading, setIsLoading] = useState(false);

    // Invite step
    const [email, setEmail] = useState('');
    const [inviteToken, setInviteToken] = useState(searchParams.get('token') || '');
    const [error, setError] = useState('');

    // Credentials step
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [usernameError, setUsernameError] = useState('');
    const [checkingUsername, setCheckingUsername] = useState(false);
    const [isUsernameValid, setIsUsernameValid] = useState(false);

    useEffect(() => {
        if (searchParams.get('token')) {
            setInviteToken(searchParams.get('token') || '');
            setStep('invite');
        }
    }, [searchParams]);

    // Validate username with debounce
    useEffect(() => {
        const timer = setTimeout(async () => {
            if (!username.trim()) {
                setUsernameError('');
                setIsUsernameValid(false);
                return;
            }
            if (username.length < 3) {
                setUsernameError('Username must be at least 3 characters');
                setIsUsernameValid(false);
                return;
            }
            if (!/^[a-zA-Z0-9_-]+$/.test(username)) {
                setUsernameError('Username can only contain letters, numbers, underscores, and hyphens');
                setIsUsernameValid(false);
                return;
            }
            setCheckingUsername(true);
            try {
                const isAvailable = await authService.checkUsernameAvailability(username);
                if (isAvailable) {
                    setUsernameError('');
                    setIsUsernameValid(true);
                } else {
                    setUsernameError('This username is already taken');
                    setIsUsernameValid(false);
                }
            } catch {
                setUsernameError('Could not verify username availability');
                setIsUsernameValid(false);
            } finally {
                setCheckingUsername(false);
            }
        }, 500);
        return () => clearTimeout(timer);
    }, [username]);

    const handleUsernameChange = (value: string) => {
        setUsername(value);
        setUsernameError('');
        setIsUsernameValid(false);
    };

    const handleValidateInvite = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!email.trim()) { setError('Email is required'); return; }
        if (!inviteToken.trim()) { setError('Invitation link/token is required'); return; }
        setIsLoading(true);
        try {
            await authService.validateRegistrationToken(email, inviteToken);
            setStep('credentials');
        } catch (err) {
            if (err instanceof ApiError) {
                setError(err.message || 'Invalid invitation. Please check your email and link.');
            } else {
                setError('Failed to validate invitation. Please try again.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleSignup = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!username.trim() || !isUsernameValid) {
            setError('Please enter a valid, available username');
            return;
        }
        const passwordValidation = validatePassword(password);
        if (passwordValidation.score < 4) {
            setError('Password is not strong enough. Please follow the requirements.');
            return;
        }
        if (password !== confirmPassword) {
            setError('Passwords do not match. Please try again.');
            return;
        }
        setIsLoading(true);
        try {
            await authService.completeRegistration(email, inviteToken, username, password);
            navigate('/');
        } catch (err) {
            if (err instanceof ApiError) {
                if (err.status === 422 && (err.data as Record<string, unknown>)?.detail) {
                    const detail = (err.data as Record<string, unknown>).detail;
                    if (Array.isArray(detail)) {
                        setError(detail.map((d: { msg: string }) => d.msg).join(', '));
                    } else {
                        setError(String(detail));
                    }
                } else {
                    setError(err.message || 'Registration failed. Please try again.');
                }
            } else {
                setError('An unexpected error occurred during registration.');
            }
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen grid lg:grid-cols-2 bg-background">

            {/* Image / Branding Side */}
            <div className="hidden lg:block relative overflow-hidden">
                <img
                    src="https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1200&q=80"
                    alt=""
                    aria-hidden="true"
                    className="absolute inset-0 h-full w-full object-cover"
                />
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

                    <div className="space-y-3 max-w-sm">
                        <p className="text-white/50 text-xs font-semibold uppercase tracking-widest">
                            {step === 'invite' ? 'Account Activation' : 'Account Setup'}
                        </p>
                        <h2 className="text-3xl font-bold text-white leading-tight">
                            {step === 'invite'
                                ? 'Activate your invitation.'
                                : 'Secure your account.'}
                        </h2>
                        <p className="text-white/70 text-sm leading-relaxed">
                            {step === 'invite'
                                ? 'Your manager has invited you to the platform. Enter your invitation details to get started with your training.'
                                : 'Choose a username and strong password to protect your account and access your personalized training paths.'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Form Side */}
            <div className="flex items-center justify-center p-8 sm:p-12">
                <div className="w-full max-w-md space-y-8">

                    {/* Back link */}
                    <button
                        onClick={() => step === 'credentials' ? setStep('invite') : navigate('/')}
                        className="flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group"
                    >
                        <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
                        {step === 'credentials' ? 'Back to Invitation' : 'Back to Login'}
                    </button>

                    <div className="flex flex-col items-center lg:items-start space-y-2 text-center lg:text-left">
                        {/* Mobile-only logo */}
                        <div className="flex items-center gap-2 lg:hidden mb-2">
                            <GraduationCap className="h-7 w-7 text-primary" />
                            <span className="text-sm font-bold text-foreground">Enterprise Learning Platform</span>
                        </div>
                        <h2 className="text-3xl font-bold tracking-tight text-foreground">
                            {step === 'invite' ? 'Verify Invitation' : 'Create Your Account'}
                        </h2>
                        <p className="text-muted-foreground">
                            {step === 'invite'
                                ? 'Enter your email and invitation token to proceed'
                                : 'Set your username and password'}
                        </p>
                    </div>

                    {/* Step 1: Invite Validation */}
                    {step === 'invite' && (
                        <Card className="border-border shadow-sm">
                            <form onSubmit={handleValidateInvite}>
                                <CardHeader className="space-y-1">
                                    <CardTitle className="text-xl flex items-center gap-2">
                                        <MailCheck className="w-5 h-5 text-primary" />
                                        Invitation Verification
                                    </CardTitle>
                                    <CardDescription>
                                        Enter your invitation details to activate your account
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
                                        <p className="text-xs text-muted-foreground">
                                            Must match the email your invitation was sent to
                                        </p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="token">Invitation Link or Token</Label>
                                        <Input
                                            id="token"
                                            type="text"
                                            placeholder="Paste the invitation link or token here"
                                            className="bg-background font-mono text-xs"
                                            value={inviteToken}
                                            onChange={(e) => setInviteToken(e.target.value)}
                                            required
                                        />
                                        <p className="text-xs text-muted-foreground">
                                            Copy and paste the entire link from your invitation email
                                        </p>
                                    </div>
                                </CardContent>
                                <CardFooter className="flex flex-col space-y-3">
                                    <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
                                        {isLoading ? (
                                            <span className="flex items-center gap-2">
                                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/20 border-t-primary-foreground" />
                                                Verifying...
                                            </span>
                                        ) : (
                                            'Verify & Continue'
                                        )}
                                    </Button>
                                    <p className="text-center text-sm text-muted-foreground">
                                        Already have an account?{' '}
                                        <button
                                            type="button"
                                            onClick={() => navigate('/')}
                                            className="font-medium text-primary hover:underline underline-offset-2"
                                        >
                                            Sign in
                                        </button>
                                    </p>
                                </CardFooter>
                            </form>
                        </Card>
                    )}

                    {/* Step 2: Credentials Setup */}
                    {step === 'credentials' && (
                        <Card className="border-border shadow-sm">
                            <form onSubmit={handleSignup}>
                                <CardHeader className="space-y-1">
                                    <CardTitle className="text-xl flex items-center gap-2">
                                        <KeyRound className="w-5 h-5 text-primary" />
                                        Account Setup
                                    </CardTitle>
                                    <CardDescription>
                                        Choose your username and secure password
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {error && (
                                        <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm flex items-center gap-2">
                                            <AlertCircle className="w-4 h-4 shrink-0" />
                                            {error}
                                        </div>
                                    )}

                                    {/* Email (read-only) */}
                                    <div className="space-y-2">
                                        <Label className="text-xs text-muted-foreground">Email</Label>
                                        <div className="px-3 py-2 rounded-md bg-muted text-sm text-foreground">
                                            {email}
                                        </div>
                                    </div>

                                    {/* Username */}
                                    <div className="space-y-2">
                                        <Label htmlFor="username">
                                            Username <span className="text-destructive">*</span>
                                        </Label>
                                        <div className="relative">
                                            <Input
                                                id="username"
                                                type="text"
                                                placeholder="johndoe_01"
                                                className="bg-background pr-10"
                                                value={username}
                                                onChange={(e) => handleUsernameChange(e.target.value)}
                                                required
                                            />
                                            <div className="absolute right-3 top-1/2 -translate-y-1/2">
                                                {checkingUsername ? (
                                                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary/20 border-t-primary" />
                                                ) : isUsernameValid && username ? (
                                                    <Check className="w-4 h-4 text-primary" />
                                                ) : username && !isUsernameValid ? (
                                                    <X className="w-4 h-4 text-destructive" />
                                                ) : null}
                                            </div>
                                        </div>
                                        {usernameError && (
                                            <p className="text-xs text-destructive">{usernameError}</p>
                                        )}
                                        <p className="text-xs text-muted-foreground">
                                            Letters, numbers, underscores, and hyphens only. At least 3 characters.
                                        </p>
                                    </div>

                                    {/* Password */}
                                    <div className="space-y-2">
                                        <Label htmlFor="password">Password</Label>
                                        <div className="relative">
                                            <Input
                                                id="password"
                                                type={showPassword ? 'text' : 'password'}
                                                placeholder="At least 8 characters"
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
                                        <PasswordStrengthIndicator password={password} />
                                    </div>

                                    {/* Confirm Password */}
                                    <div className="space-y-2">
                                        <Label htmlFor="confirmPassword">
                                            Confirm Password <span className="text-destructive">*</span>
                                        </Label>
                                        <div className="relative">
                                            <Input
                                                id="confirmPassword"
                                                type={showConfirmPassword ? 'text' : 'password'}
                                                placeholder="Re-enter your password"
                                                className="bg-background pr-10"
                                                value={confirmPassword}
                                                onChange={(e) => setConfirmPassword(e.target.value)}
                                                required
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary transition-all p-1.5 rounded-md hover:bg-muted"
                                                title={showConfirmPassword ? 'Hide password' : 'Show password'}
                                            >
                                                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                            </button>
                                        </div>
                                        {password && confirmPassword && password !== confirmPassword && (
                                            <p className="text-xs text-destructive">Passwords do not match</p>
                                        )}
                                        {password && confirmPassword && password === confirmPassword && (
                                            <p className="text-xs text-primary flex items-center gap-1">
                                                <Check className="w-3 h-3" /> Passwords match
                                            </p>
                                        )}
                                    </div>
                                </CardContent>
                                <CardFooter className="flex flex-col space-y-3">
                                    <Button
                                        type="submit"
                                        className="w-full"
                                        size="lg"
                                        disabled={isLoading || !isUsernameValid || validatePassword(password).score < 4}
                                    >
                                        {isLoading ? (
                                            <span className="flex items-center gap-2">
                                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/20 border-t-primary-foreground" />
                                                Creating account...
                                            </span>
                                        ) : (
                                            'Complete Setup'
                                        )}
                                    </Button>
                                    <p className="text-center text-sm text-muted-foreground">
                                        Already have an account?{' '}
                                        <button
                                            type="button"
                                            onClick={() => navigate('/')}
                                            className="font-medium text-primary hover:underline underline-offset-2"
                                        >
                                            Sign in
                                        </button>
                                    </p>
                                </CardFooter>
                            </form>
                        </Card>
                    )}

                </div>
            </div>
        </div>
    );
};
