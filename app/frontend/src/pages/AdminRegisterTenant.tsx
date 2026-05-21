import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter
} from '../components/ui/dialog';
import { Building2, ArrowLeft, Mail, User, Globe, ShieldCheck, Copy, Check } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { tenantService } from '../api/tenants';

interface FormData {
    name: string;
    logo_url: string;
    primary_color: string;
    secondary_color: string;
    admin_name: string;
    admin_email: string;
}

export const AdminRegisterTenant: React.FC = () => {
    const navigate = useNavigate();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [inviteLink, setInviteLink] = useState('');
    const [isAdminNew, setIsAdminNew] = useState<boolean | undefined>(false);
    const [copied, setCopied] = useState(false);

    const [formData, setFormData] = useState<FormData>({
        name: '',
        logo_url: '',
        primary_color: '#4f46e5',
        secondary_color: '#10b981',
        admin_name: '',
        admin_email: ''
    });

    const handleInputChange = (field: keyof FormData, value: string) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleCopyLink = () => {
        if (!inviteLink) return;
        navigator.clipboard.writeText(inviteLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSubmitting(true);
        try {
            const response = await tenantService.create(formData);
            if (response.manager_invite_url) {
                setInviteLink(response.manager_invite_url);
            }
            setIsAdminNew(response.is_admin_new);
            setShowSuccessModal(true);
        } catch (error) {
            console.error('Failed to register tenant:', error);
            alert('Failed to register tenant. Please check console for details.');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCloseModal = () => {
        setShowSuccessModal(false);
        navigate('/admin/tenants');
    };

    return (
        <div className="space-y-6 max-w-3xl mx-auto animate-in fade-in duration-500">
            <div className="flex items-center gap-4 mb-8">
                <Link to="/admin/tenants">
                    <Button variant="ghost" size="icon" className="h-9 w-9 border border-border bg-card hover:bg-muted">
                        <ArrowLeft className="h-4 w-4 text-muted-foreground" />
                    </Button>
                </Link>
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">
                        Register New Tenant
                    </h1>
                    <p className="text-muted-foreground text-sm mt-1">Onboard a new organization and initialize its primary administrator.</p>
                </div>
            </div>

            <form onSubmit={handleSubmit}>
                <div className="grid grid-cols-1 gap-6">
                    <Card className="border-border/50 shadow-sm">
                        <CardHeader className="border-b border-border/50 bg-muted/20 pb-4">
                            <CardTitle className="text-lg flex items-center">
                                <Building2 className="w-5 h-5 mr-2 text-primary" />
                                Organization Details
                            </CardTitle>
                            <CardDescription>Basic information about the tenant entity.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-6">
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div className="space-y-2">
                                    <Label htmlFor="tenant-name">Organization Name</Label>
                                    <Input
                                        id="tenant-name"
                                        placeholder="e.g. Acme Corporation"
                                        required
                                        value={formData.name}
                                        onChange={(e) => handleInputChange('name', e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="tenant-logo">Logo URL <span className="text-muted-foreground font-normal">(Optional)</span></Label>
                                    <div className="relative">
                                        <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <Input
                                            id="tenant-logo"
                                            placeholder="https://example.com/logo.png"
                                            className="pl-9"
                                            value={formData.logo_url}
                                            onChange={(e) => handleInputChange('logo_url', e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div className="space-y-2">
                                    <Label htmlFor="primary-color">Primary Color</Label>
                                    <div className="flex gap-2 items-center">
                                        <Input
                                            id="primary-color"
                                            type="color"
                                            value={formData.primary_color}
                                            onChange={(e) => handleInputChange('primary_color', e.target.value)}
                                            className="w-12 h-10 p-1 cursor-pointer"
                                        />
                                        <Input
                                            type="text"
                                            value={formData.primary_color}
                                            onChange={(e) => handleInputChange('primary_color', e.target.value)}
                                            className="font-mono"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="secondary-color">Secondary Color</Label>
                                    <div className="flex gap-2 items-center">
                                        <Input
                                            id="secondary-color"
                                            type="color"
                                            value={formData.secondary_color}
                                            onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                                            className="w-12 h-10 p-1 cursor-pointer"
                                        />
                                        <Input
                                            type="text"
                                            value={formData.secondary_color}
                                            onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                                            className="font-mono"
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    <Card className="border-border/50 shadow-sm">
                        <CardHeader className="border-b border-border/50 bg-muted/20 pb-4">
                            <CardTitle className="text-lg flex items-center">
                                <ShieldCheck className="w-5 h-5 mr-2 text-primary" />
                                Primary Administrator
                            </CardTitle>
                            <CardDescription>This user will be granted the master 'Manager' role for this tenant.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6 pt-6">
                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div className="space-y-2">
                                    <Label htmlFor="admin-name">Full Name</Label>
                                    <div className="relative">
                                        <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <Input
                                            id="admin-name"
                                            placeholder="e.g. Jane Doe"
                                            className="pl-9"
                                            required
                                            value={formData.admin_name}
                                            onChange={(e) => handleInputChange('admin_name', e.target.value)}
                                        />
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label htmlFor="admin-email">Business Email</Label>
                                    <div className="relative">
                                        <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                                        <Input
                                            id="admin-email"
                                            type="email"
                                            placeholder="jane@acme.com"
                                            className="pl-9"
                                            required
                                            value={formData.admin_email}
                                            onChange={(e) => handleInputChange('admin_email', e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>
                            <div className="bg-primary/5 p-4 rounded-md border border-primary/10 flex items-start gap-3">
                                <div className="mt-0.5">
                                    <Mail className="w-5 h-5 text-primary" />
                                </div>
                                <div>
                                    <h4 className="text-sm font-medium text-foreground">Registration Invitation</h4>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        Upon creation, an invitation email containing a secure setup link will be dispatched to the address above. They will configure their password upon accepting the invitation.
                                    </p>
                                </div>
                            </div>
                        </CardContent>
                        <CardFooter className="border-t border-border/50 bg-muted/10 py-4 flex justify-end gap-3">
                            <Link to="/admin/tenants">
                                <Button type="button" variant="outline" className="bg-background">Cancel</Button>
                            </Link>
                            <Button type="submit" className="bg-primary hover:bg-primary/90 text-primary-foreground min-w-[140px]" disabled={isSubmitting}>
                                {isSubmitting ? (
                                    <span className="flex items-center gap-2">
                                        <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                                        Provisioning...
                                    </span>
                                ) : 'Register Tenant'}
                            </Button>
                        </CardFooter>
                    </Card>
                </div>
            </form>

            {/* Success Modal */}
            <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
                <DialogContent className="sm:max-w-md border-border/50 shadow-2xl">
                    <DialogHeader>
                        <div className="h-12 w-12 bg-primary/10 rounded-full flex items-center justify-center mb-4 mx-auto">
                            <ShieldCheck className="h-6 w-6 text-primary" />
                        </div>
                        <DialogTitle className="text-center text-xl">Tenant Registered Successfully!</DialogTitle>
                        <DialogDescription className="text-center pt-2">
                            The organization <span className="font-semibold text-foreground">{formData.name}</span> has been provisioned.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        {isAdminNew ? (
                            <div className="p-4 bg-muted/50 rounded-lg border border-border/50 space-y-3 animate-in slide-in-from-bottom-2">
                                <div className="flex items-center justify-between">
                                    <Label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Manager Invite Link</Label>
                                </div>
                                <div className="flex gap-2">
                                    <Input
                                        readOnly
                                        value={inviteLink || "Generating link..."}
                                        className="bg-background font-mono text-xs border-border/50 focus-visible:ring-primary"
                                    />
                                    <Button
                                        size="icon"
                                        variant="outline"
                                        onClick={handleCopyLink}
                                        className="shrink-0 border-border/50 hover:bg-muted hover:text-primary transition-colors"
                                        disabled={!inviteLink}
                                    >
                                        {copied ? <Check className="h-4 w-4 text-primary" /> : <Copy className="h-4 w-4" />}
                                    </Button>
                                </div>
                                <p className="text-[10px] text-muted-foreground leading-relaxed italic">
                                    Share this link with <span className="font-medium text-foreground">{formData.admin_name}</span> to complete their registration. An invitation email was also sent to <span className="font-medium text-foreground">{formData.admin_email}</span>.
                                </p>
                            </div>
                        ) : (
                            <div className="p-4 bg-primary/5 rounded-lg border border-primary/10 space-y-3 animate-in zoom-in-95 duration-300">
                                <div className="flex items-center gap-3">
                                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                        <User className="h-4 w-4 text-primary" />
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-semibold text-foreground text-left">Active User Assigned</h4>
                                        <p className="text-xs text-muted-foreground text-left">
                                            {formData.admin_email} is already an active user.
                                        </p>
                                    </div>
                                </div>
                                <p className="text-xs text-muted-foreground leading-relaxed">
                                    No invitation link is required. The user can now access this tenant using their existing credentials.
                                </p>
                            </div>
                        )}
                    </div>

                    <DialogFooter>
                        <Button
                            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium py-6"
                            onClick={handleCloseModal}
                        >
                            Done & Return to List
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
