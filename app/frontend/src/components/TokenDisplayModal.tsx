import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Loader2, AlertCircle, Copy, Eye, EyeOff, CheckCircle2 } from 'lucide-react';
import { userService, type RegistrationTokenResponse } from '../api/users';
import { getApiError } from '../lib/utils';

interface TokenDisplayModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  userId: string;
  email?: string;
  onTokenRegenerated?: () => void;
}

export const TokenDisplayModal: React.FC<TokenDisplayModalProps> = ({
  open,
  onOpenChange,
  userId,
  email,
  onTokenRegenerated,
}) => {
  const [tokenData, setTokenData] = useState<RegistrationTokenResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [copiedField, setCopiedField] = useState<'token' | 'url' | null>(null);
  const [showRegenerateConfirm, setShowRegenerateConfirm] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);

  // Fetch token when dialog opens
  useEffect(() => {
    if (open && userId) {
      fetchToken();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, userId]);

  const fetchToken = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await userService.getRegistrationToken(userId);
      setTokenData(data);
    } catch (err: unknown) {
      setError(getApiError(err, 'Failed to fetch registration token'));
      setTokenData(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegenerateToken = async () => {
    setShowRegenerateConfirm(false);
    setIsRegenerating(true);
    setError('');
    try {
      const newTokenData = await userService.regenerateRegistrationToken(userId);
      setTokenData(newTokenData);
      setShowToken(true);
      onTokenRegenerated?.();
    } catch (err: unknown) {
      setError(getApiError(err, 'Failed to regenerate token'));
    } finally {
      setIsRegenerating(false);
    }
  };

  const copyToClipboard = async (text: string, field: 'token' | 'url') => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
    } catch {
      setError('Failed to copy to clipboard');
    }
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      setTokenData(null);
      setError('');
      setShowToken(false);
      setCopiedField(null);
    }
    onOpenChange(newOpen);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Registration Token Management</DialogTitle>
            <DialogDescription>
              {email ? `Manage registration token for ${email}` : 'Manage registration token for user'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6">
            {/* Loading State */}
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                <span className="ml-3 text-muted-foreground">Loading token information...</span>
              </div>
            )}

            {/* Error State */}
            {error && !isLoading && (
              <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
                <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-destructive">Error</p>
                  <p className="text-sm text-destructive/80 mt-1">{error}</p>
                </div>
              </div>
            )}

            {/* No Token State */}
            {!isLoading && !error && !tokenData && (
              <div className="flex items-center justify-center py-8 px-4 bg-muted rounded-lg border border-dashed border-border">
                <div className="text-center">
                  <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                  <p className="text-muted-foreground font-medium">No Active Token</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    This user does not have an active registration token yet.
                  </p>
                </div>
              </div>
            )}

            {/* Token Display State */}
            {!isLoading && tokenData && (
              <div className="space-y-4">
                {/* Token Field */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Registration Token
                  </label>
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <input
                        type={showToken ? 'text' : 'password'}
                        value={tokenData.token}
                        readOnly
                        className="w-full px-3 py-2 border border-border rounded-md bg-muted font-mono text-sm"
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
                      onClick={() => copyToClipboard(tokenData.token, 'token')}
                      className="gap-2"
                    >
                      <Copy className="h-4 w-4" />
                      {copiedField === 'token' ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                </div>

                {/* Registration URL Field */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Registration Link
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={tokenData.registration_url}
                      readOnly
                      className="flex-1 px-3 py-2 border border-border rounded-md bg-muted font-mono text-sm text-muted-foreground"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => copyToClipboard(tokenData.registration_url, 'url')}
                      className="gap-2 whitespace-nowrap"
                    >
                      <Copy className="h-4 w-4" />
                      {copiedField === 'url' ? 'Copied' : 'Copy'}
                    </Button>
                  </div>
                </div>

                {/* Token Expiration */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-foreground">
                    Expires
                  </label>
                  <div className="flex items-center gap-2 px-3 py-2 bg-primary/10 border border-primary/20 rounded-md">
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                    <span className="text-sm text-foreground">
                      {new Date(tokenData.expires_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Token will expire {getRelativeTime(tokenData.expires_at)}
                  </p>
                </div>

                {/* Instructions */}
                <div className="bg-muted border border-border rounded-lg p-4 text-sm">
                  <p className="font-medium text-foreground mb-2">How to share:</p>
                  <ol className="text-muted-foreground list-decimal list-inside space-y-1 text-xs">
                    <li>Copy the token or link above</li>
                    <li>Send it to the user via email or secure message</li>
                    <li>User can click the link or paste the token to register</li>
                  </ol>
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={isLoading || isRegenerating}
            >
              Close
            </Button>
            {tokenData && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowRegenerateConfirm(true)}
                disabled={isLoading || isRegenerating}
                className="gap-2"
              >
                {isRegenerating && <Loader2 className="h-4 w-4 animate-spin" />}
                {isRegenerating ? 'Regenerating...' : 'Regenerate Token'}
              </Button>
            )}
            {!tokenData && !isLoading && (
              <Button
                type="button"
                onClick={fetchToken}
                variant="secondary"
              >
                Retry
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Regenerate Confirmation Dialog */}
      <Dialog open={showRegenerateConfirm} onOpenChange={setShowRegenerateConfirm}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>Regenerate Token?</DialogTitle>
            <DialogDescription>
              This will invalidate the current token and create a new one. The user will need to use the new token to register.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowRegenerateConfirm(false)}
              disabled={isRegenerating}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleRegenerateToken}
              disabled={isRegenerating}
              className="bg-destructive hover:bg-destructive/90"
            >
              {isRegenerating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {isRegenerating ? 'Regenerating...' : 'Regenerate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

/**
 * Helper function to get relative time (e.g., "in 2 days")
 */
function getRelativeTime(dateString: string): string {
  const now = new Date();
  const date = new Date(dateString);
  const seconds = Math.floor((date.getTime() - now.getTime()) / 1000);

  if (seconds < 60) return 'in a few seconds';
  if (seconds < 3600) return `in ${Math.floor(seconds / 60)} minute${Math.floor(seconds / 60) !== 1 ? 's' : ''}`;
  if (seconds < 86400) return `in ${Math.floor(seconds / 3600)} hour${Math.floor(seconds / 3600) !== 1 ? 's' : ''}`;

  const days = Math.floor(seconds / 86400);
  return `in ${days} day${days !== 1 ? 's' : ''}`;
}

export default TokenDisplayModal;
