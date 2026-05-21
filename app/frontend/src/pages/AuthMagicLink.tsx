import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '../components/ui/card';
import { TENANT_INFO } from '../data/mockData';
import { ArrowLeft, Mail, Sparkles } from 'lucide-react';

export const AuthMagicLink: React.FC = () => {
    const navigate = useNavigate();
    const [isSent, setIsSent] = useState(false);

    return (
        <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
            <div className="absolute top-8 left-8">
                <button
                    onClick={() => navigate('/')}
                    className="flex items-center text-sm font-medium text-muted-foreground hover:text-foreground transition-colors group"
                >
                    <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
                    Back to Login
                </button>
            </div>

            <div className="w-full max-w-md space-y-8 animate-in slide-in-from-bottom-4 duration-500">
                <div className="flex flex-col items-center space-y-3 text-center">
                    <div className="w-16 h-16 bg-card border border-border shadow-sm rounded-2xl flex items-center justify-center">
                        <Sparkles className="w-8 h-8 text-amber-500" />
                    </div>
                    <h2 className="text-3xl font-bold tracking-tight text-foreground">Passwordless Login</h2>
                    <p className="text-muted-foreground">
                        We'll send a magic link directly to your inbox for instant access to {TENANT_INFO.name}.
                    </p>
                </div>

                <Card className="border-border shadow-sm">
                    {!isSent ? (
                        <>
                            <CardHeader>
                                <CardTitle className="text-xl">Email details</CardTitle>
                                <CardDescription>
                                    Enter the email address associated with your account.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="email">Work Email</Label>
                                    <div className="relative">
                                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <Input id="email" type="email" placeholder="name@company.com" className="pl-9 bg-background focus-visible:ring-primary" />
                                    </div>
                                </div>
                            </CardContent>
                            <CardFooter>
                                <Button className="w-full" size="lg" onClick={() => setIsSent(true)}>
                                    Send Magic Link <ArrowLeft className="w-4 h-4 ml-2 rotate-180" />
                                </Button>
                            </CardFooter>
                        </>
                    ) : (
                        <div className="p-8 text-center space-y-6">
                            <div className="w-16 h-16 bg-primary/10 text-primary rounded-full flex items-center justify-center mx-auto">
                                <Mail className="w-8 h-8" />
                            </div>
                            <div className="space-y-2">
                                <h3 className="text-xl font-bold">Check your inbox!</h3>
                                <p className="text-muted-foreground text-sm">
                                    We've sent a temporary login link. Please check your spam folder if you don't see it within 3 minutes.
                                </p>
                            </div>
                            <Button variant="outline" className="w-full" onClick={() => setIsSent(false)}>
                                Try another email
                            </Button>
                        </div>
                    )}
                </Card>
            </div>
        </div>
    );
};
