import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from './ui/select';
import { Loader2, AlertCircle, CheckCircle2, Copy, Eye, EyeOff } from 'lucide-react';
import { userService } from '../api/users';
import { authService, type Tenant } from '../api/auth';
import { getApiError } from '../lib/utils';

interface UserCreationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUserCreated?: () => void;
  tenantId?: string; // If provided, auto-select this tenant
}

interface CreatedUser {
  user_id: string;
  email: string;
  token: string;
  registration_url: string;
  expires_at: string;
}

type UserRole = 'MANAGER' | 'CREATOR' | 'EMPLOYEE';

const ROLE_LABELS: Record<UserRole, string> = {
  MANAGER: 'Business Manager',
  CREATOR: 'Training Creator',
  EMPLOYEE: 'Employee',
};

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  MANAGER: 'Can manage team members and view reports',
  CREATOR: 'Can create and manage training content',
  EMPLOYEE: 'Can take courses and view progress',
};

export const UserCreationDialog: React.FC<UserCreationDialogProps> = ({
  open,
  onOpenChange,
  onUserCreated,
  tenantId: initialTenantId,
}) => {
  const [step, setStep] = useState<'form' | 'token'>('form');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [selectedRole, setSelectedRole] = useState<UserRole>('EMPLOYEE');
  const [selectedTenant, setSelectedTenant] = useState<string>(initialTenantId || '');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [createdUser, setCreatedUser] = useState<CreatedUser | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [tenantLoading, setTenantLoading] = useState(false);
  const [error, setError] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [copiedField, setCopiedField] = useState<'token' | 'url' | null>(null);

  // Fetch available tenants on open
  useEffect(() => {
    if (open && !initialTenantId) {
      fetchTenants();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, initialTenantId]);

  const fetchTenants = async () => {
    setTenantLoading(true);
    try {
      const data = await authService.getAllTenants();
      setTenants(data);
      if (data.length > 0 && !selectedTenant) {
        setSelectedTenant(data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch tenants:', err);
    } finally {
      setTenantLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validation
    if (!email.trim()) {
      setError('Email is required');
      return;
    }

    if (!email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    if (!fullName.trim()) {
      setError('Full name is required');
      return;
    }

    if (!selectedTenant && !initialTenantId) {
      setError('Please select a tenant');
      return;
    }

    const tenantIdToUse = initialTenantId || selectedTenant;

    setIsLoading(true);
    try {
      // Map frontend role to backend role string
      const roleMap: Record<UserRole, string> = {
        MANAGER: 'MANAGER',
        CREATOR: 'CREATOR',
        EMPLOYEE: 'EMPLOYEE',
      };

      const response = await userService.createUser({
        email,
        full_name: fullName,
        tenant_id: tenantIdToUse,
        role: roleMap[selectedRole],
      });

      setCreatedUser(response);
      setStep('token');
    } catch (err: unknown) {
      setError(getApiError(err, 'Failed to create user account.'));
    } finally {
      setIsLoading(false);
    }
  };

  const copyToClipboard = async (text: string, field: 'token' | 'url') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      alert('Failed to copy to clipboard');
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      // Reset form when closing
      setEmail('');
      setFullName('');
      setSelectedRole('EMPLOYEE');
      if (!initialTenantId) {
        setSelectedTenant('');
      }
      setError('');
      setStep('form');
      setCreatedUser(null);
      setShowToken(false);
    }
    onOpenChange(newOpen);
  };

  // Token display step
  if (step === 'token' && createdUser) {
    return (
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-primary" />
              User Account Created
            </DialogTitle>
            <DialogDescription>
              Share the registration token with {createdUser.email}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* User Info */}
            <div className="space-y-3 text-sm">
              <div>
                <Label className="text-xs text-muted-foreground uppercase">Email</Label>
                <p className="text-base font-medium">{createdUser.email}</p>
              </div>
            </div>

            {/* Token Section */}
            <div className="space-y-3">
              <Label className="text-xs text-muted-foreground uppercase">Registration Token</Label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    type={showToken ? 'text' : 'password'}
                    value={createdUser.token}
                    readOnly
                    className="font-mono text-sm bg-muted pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken(!showToken)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(createdUser.token, 'token')}
                  className="gap-2"
                >
                  <Copy className="h-4 w-4" />
                  {copiedField === 'token' ? 'Copied' : 'Copy'}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Token expires on {new Date(createdUser.expires_at).toLocaleString()}
              </p>
            </div>

            {/* Registration URL Section */}
            <div className="space-y-3">
              <Label className="text-xs text-muted-foreground uppercase">Registration Link</Label>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={createdUser.registration_url}
                  readOnly
                  className="font-mono text-sm bg-muted"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => copyToClipboard(createdUser.registration_url, 'url')}
                  className="gap-2 whitespace-nowrap"
                >
                  <Copy className="h-4 w-4" />
                  {copiedField === 'url' ? 'Copied' : 'Copy'}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Share this link for one-click registration
              </p>
            </div>

            {/* Instructions */}
            <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 text-sm">
              <p className="font-medium text-foreground mb-2">How to share:</p>
              <ol className="text-muted-foreground list-decimal list-inside space-y-1">
                <li>Copy either the token or the registration link</li>
                <li>Send it to the user via email or message</li>
                <li>User can paste the token or click the link to register</li>
                <li>They'll set their username and password</li>
              </ol>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                handleOpenChange(false);
                onUserCreated?.();
              }}
            >
              Done
            </Button>
            <Button
              type="button"
              onClick={() => {
                setStep('form');
                setEmail('');
                setFullName('');
                setSelectedRole('EMPLOYEE');
                setCreatedUser(null);
              }}
            >
              Create Another User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  // Form step
  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create User Account</DialogTitle>
          <DialogDescription>
            Create a new user account and generate a registration token
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="create-email">
              Email Address <span className="text-destructive">*</span>
            </Label>
            <Input
              id="create-email"
              type="email"
              placeholder="user@example.com"
              value={email}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setEmail(e.target.value);
                setError('');
              }}
              disabled={isLoading}
              className={error && error.includes('email') ? 'border-destructive' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="create-fullname">
              Full Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="create-fullname"
              type="text"
              placeholder="John Doe"
              value={fullName}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                setFullName(e.target.value);
                setError('');
              }}
              disabled={isLoading}
              className={error && error.includes('name') ? 'border-destructive' : ''}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="create-role">
              Role <span className="text-destructive">*</span>
            </Label>
            <Select value={selectedRole} onValueChange={(value) => setSelectedRole(value as UserRole)} disabled={isLoading}>
              <SelectTrigger id="create-role">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(ROLE_LABELS) as UserRole[]).map((role) => (
                  <SelectItem key={role} value={role}>
                    <div>
                      <div className="font-medium">{ROLE_LABELS[role]}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {ROLE_DESCRIPTIONS[selectedRole]}
            </p>
          </div>

          {!initialTenantId && (
            <div className="space-y-2">
              <Label htmlFor="create-tenant">
                Tenant <span className="text-destructive">*</span>
              </Label>
              <Select 
                value={selectedTenant} 
                onValueChange={setSelectedTenant} 
                disabled={isLoading || tenantLoading}
              >
                <SelectTrigger id="create-tenant">
                  <SelectValue placeholder="Select a tenant..." />
                </SelectTrigger>
                <SelectContent>
                  {tenants.map((tenant) => (
                    <SelectItem key={tenant.id} value={tenant.id}>
                      {tenant.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {tenants.length === 0 && !tenantLoading && (
                <p className="text-xs text-muted-foreground">No tenants available</p>
              )}
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/30 px-3 py-2 rounded-md">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            A registration token will be generated that the user can use to complete their profile.
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
            <Button 
              type="submit" 
              disabled={isLoading || !email.trim() || !fullName.trim() || (!selectedTenant && !initialTenantId)}
            >
              {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isLoading ? 'Creating...' : 'Create User'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default UserCreationDialog;
