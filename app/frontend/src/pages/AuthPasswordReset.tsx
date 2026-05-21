import { useState } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { GraduationCap, ArrowLeft, Mail, CheckCircle2, AlertCircle, KeyRound, Eye, EyeOff } from 'lucide-react';
import { authService } from '../api/auth';

export function AuthPasswordReset() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<'idle' | 'sent' | 'done' | 'error'>('idle');
  const [error, setError] = useState('');

  async function handleForgot(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await authService.forgotPassword(email);
      setStatus('sent');
    } catch {
      setError('Something went wrong. Please try again.');
    }
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      await authService.resetPasswordByToken(token!, password);
      setStatus('done');
      setTimeout(() => navigate('/'), 2500);
    } catch {
      setError('Invalid or expired reset link. Please request a new one.');
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-background">

      {/* Image / Branding Side */}
      <div className="hidden lg:block relative overflow-hidden">
        <img
          src="https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80"
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
              Account Security
            </p>
            <h2 className="text-3xl font-bold text-white leading-tight">
              {token ? 'Set your new password.' : 'Recover your access.'}
            </h2>
            <p className="text-white/70 text-sm leading-relaxed">
              {token
                ? 'Choose a strong password to protect your account and continue your learning journey.'
                : "We'll send a secure reset link to your email so you can get back to your training."}
            </p>
          </div>
        </div>
      </div>

      {/* Form Side */}
      <div className="flex items-center justify-center p-8 sm:p-12">
        <div className="w-full max-w-md space-y-8">

          {/* Back link */}
          <button
            onClick={() => navigate('/')}
            className="flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group"
          >
            <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
            Back to Login
          </button>

          <div className="flex flex-col items-center lg:items-start space-y-2 text-center lg:text-left">
            {/* Mobile-only logo */}
            <div className="flex items-center gap-2 lg:hidden mb-2">
              <GraduationCap className="h-7 w-7 text-primary" />
              <span className="text-sm font-bold text-foreground">Enterprise Learning Platform</span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-foreground">
              {token ? 'Set New Password' : 'Forgot Password'}
            </h2>
            <p className="text-muted-foreground">
              {token
                ? 'Enter and confirm your new password below'
                : "Enter your email and we'll send you a reset link"}
            </p>
          </div>

          {/* Sent confirmation */}
          {status === 'sent' && (
            <Card className="border-border shadow-sm">
              <CardContent className="pt-8 pb-8 flex flex-col items-center text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                  <Mail className="h-7 w-7 text-primary" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold">Check your inbox</h3>
                  <p className="text-sm text-muted-foreground max-w-xs">
                    We've sent a password reset link to <strong>{email}</strong>. Check your spam folder if you don't see it within a few minutes.
                  </p>
                </div>
                <Button variant="outline" className="mt-2" onClick={() => setStatus('idle')}>
                  Try a different email
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Done confirmation */}
          {status === 'done' && (
            <Card className="border-border shadow-sm">
              <CardContent className="pt-8 pb-8 flex flex-col items-center text-center space-y-4">
                <div className="w-14 h-14 rounded-full bg-primary/10 flex items-center justify-center">
                  <CheckCircle2 className="h-7 w-7 text-primary" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-lg font-semibold">Password updated</h3>
                  <p className="text-sm text-muted-foreground">
                    Your password has been changed successfully. Redirecting you to login…
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Forgot password form */}
          {status === 'idle' && !token && (
            <Card className="border-border shadow-sm">
              <form onSubmit={handleForgot}>
                <CardHeader className="space-y-1">
                  <CardTitle className="text-xl flex items-center gap-2">
                    <Mail className="w-5 h-5 text-primary" />
                    Reset via Email
                  </CardTitle>
                  <CardDescription>
                    We'll send a secure link to reset your password
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
                    <Label htmlFor="email">Email Address</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="name@company.com"
                      className="bg-background"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </CardContent>
                <CardFooter className="flex flex-col space-y-3">
                  <Button type="submit" className="w-full" size="lg">
                    Send Reset Link
                  </Button>
                  <p className="text-center text-sm text-muted-foreground">
                    Remember your password?{' '}
                    <Link to="/" className="font-medium text-primary hover:underline underline-offset-2">
                      Sign in
                    </Link>
                  </p>
                </CardFooter>
              </form>
            </Card>
          )}

          {/* Reset password form (with token) */}
          {status === 'idle' && token && (
            <Card className="border-border shadow-sm">
              <form onSubmit={handleReset}>
                <CardHeader className="space-y-1">
                  <CardTitle className="text-xl flex items-center gap-2">
                    <KeyRound className="w-5 h-5 text-primary" />
                    Choose a New Password
                  </CardTitle>
                  <CardDescription>
                    Must be at least 8 characters
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
                    <Label htmlFor="password">New Password</Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        placeholder="At least 8 characters"
                        className="bg-background pr-10"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        required
                        minLength={8}
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
                <CardFooter className="flex flex-col space-y-3">
                  <Button type="submit" className="w-full" size="lg">
                    Update Password
                  </Button>
                </CardFooter>
              </form>
            </Card>
          )}

        </div>
      </div>
    </div>
  );
}
