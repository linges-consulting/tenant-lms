import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Loader2, AlertCircle, Globe, Building2, CheckCircle2 } from 'lucide-react';
import { authService, type Tenant } from '../api/auth';
import { getApiError } from '../lib/utils';

interface OrganizationContextModalProps {
  open: boolean;
  onOpenChange?: (open: boolean) => void;
  onContextSelected?: () => void;
  isSysAdmin?: boolean; // Pass SysAdmin flag from parent
}

export const OrganizationContextModal: React.FC<OrganizationContextModalProps> = ({
  open,
  onOpenChange,
  onContextSelected,
  isSysAdmin = false,
}) => {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSelecting, setIsSelecting] = useState(false);
  const [error, setError] = useState('');
  const [selectedContext, setSelectedContext] = useState<'global' | string | null>(null);

  // Fetch available tenants on open
  useEffect(() => {
    if (open && isSysAdmin) {
      fetchTenants();
    }
  }, [open, isSysAdmin]);

  const fetchTenants = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await authService.getAllTenants();
      setTenants(data);
    } catch (err: unknown) {
      setError(getApiError(err, 'Failed to fetch tenants'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectGlobalMode = async () => {
    setIsSelecting(true);
    setError('');
    try {
      setSelectedContext('global');
      // Select with null for global admin mode
      const response = await authService.selectTenant(null);
      if (response?.access_token) {
        // Store the token (assuming client handles this)
        localStorage.setItem('org_context', 'global');
        onContextSelected?.();
        onOpenChange?.(false);
        // Route to dashboard
        setTimeout(() => {
          navigate('/admin');
        }, 500);
      }
    } catch (err: unknown) {
      setError(getApiError(err, 'Failed to select global mode'));
      setSelectedContext(null);
    } finally {
      setIsSelecting(false);
    }
  };

  const handleSelectTenant = async (tenantId: string, tenantName: string) => {
    setIsSelecting(true);
    setError('');
    try {
      setSelectedContext(tenantId);
      const response = await authService.selectTenant(tenantId);
      if (response?.access_token) {
        // Store the context (assuming client handles this)
        localStorage.setItem('org_context', tenantId);
        onContextSelected?.();
        onOpenChange?.(false);
        // Route to dashboard
        setTimeout(() => {
          navigate('/dashboard');
        }, 500);
      }
    } catch (err: unknown) {
      setError(getApiError(err, `Failed to select ${tenantName}`));
      setSelectedContext(null);
    } finally {
      setIsSelecting(false);
    }
  };

  // Don't render for non-SysAdmins
  if (!isSysAdmin && open) {
    onOpenChange?.(false);
    return null;
  }

  return (
    <Dialog open={open && isSysAdmin} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5 text-primary" />
            Select Your Workspace
          </DialogTitle>
          <DialogDescription>
            Choose whether to work in global admin mode or as a manager in a specific organization.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Error State */}
          {error && (
            <div className="flex items-start gap-3 p-4 bg-destructive/10 border border-destructive/30 rounded-lg">
              <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-destructive">Error</p>
                <p className="text-sm text-destructive/80 mt-1">{error}</p>
              </div>
            </div>
          )}

          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-3 text-muted-foreground">Loading available workspaces...</span>
            </div>
          )}

          {/* Global Admin Mode Option */}
          {!isLoading && (
            <>
              <div>
                <Card
                  className="p-6 cursor-pointer transition-all border-2 hover:border-primary hover:shadow-md"
                  onClick={() => !isSelecting && handleSelectGlobalMode()}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0">
                      <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-primary/10">
                        <Globe className="h-6 w-6 text-primary" />
                      </div>
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-semibold text-foreground">
                        Global Admin Mode
                      </h3>
                      <p className="text-sm text-muted-foreground mt-1">
                        Access all organizations and system settings without tenant restrictions
                      </p>
                      <div className="mt-4 flex items-center gap-3">
                        <Button
                          onClick={() => !isSelecting && handleSelectGlobalMode()}
                          disabled={isSelecting}
                          className="bg-primary hover:bg-primary/90"
                        >
                          {selectedContext === 'global' && isSelecting ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Selecting...
                            </>
                          ) : (
                            <>
                              {selectedContext === 'global' && !isSelecting && (
                                <CheckCircle2 className="mr-2 h-4 w-4" />
                              )}
                              Select
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              </div>

              {/* Organization List Divider */}
              {tenants.length > 0 && (
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-background text-muted-foreground">Or manage an organization</span>
                  </div>
                </div>
              )}

              {/* Tenant Cards */}
              {tenants.length > 0 ? (
                <div className="grid grid-cols-1 gap-3">
                  {tenants.map((tenant) => (
                    <Card
                      key={tenant.id}
                      className="p-4 cursor-pointer transition-all border hover:border-slate-400 hover:shadow-md"
                      onClick={() => !isSelecting && handleSelectTenant(tenant.id, tenant.name)}
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex-shrink-0">
                          {tenant.logo_url ? (
                            <img
                              src={tenant.logo_url}
                              alt={tenant.name}
                              className="h-10 w-10 rounded object-cover"
                            />
                          ) : (
                            <div className="flex items-center justify-center h-10 w-10 rounded bg-muted">
                              <Building2 className="h-5 w-5 text-muted-foreground" />
                            </div>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-base font-semibold text-foreground truncate">
                            {tenant.name}
                          </h4>
                          {(tenant.user_count || tenant.course_count) && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {tenant.user_count && `${tenant.user_count} user${tenant.user_count !== 1 ? 's' : ''}`}
                              {tenant.user_count && tenant.course_count && ' • '}
                              {tenant.course_count && `${tenant.course_count} course${tenant.course_count !== 1 ? 's' : ''}`}
                            </p>
                          )}
                        </div>
                        <div className="flex-shrink-0">
                          <Button
                            onClick={() => !isSelecting && handleSelectTenant(tenant.id, tenant.name)}
                            disabled={isSelecting}
                            variant="outline"
                            size="sm"
                          >
                            {selectedContext === tenant.id && isSelecting ? (
                              <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                              </>
                            ) : (
                              <>
                                {selectedContext === tenant.id && !isSelecting && (
                                  <CheckCircle2 className="mr-2 h-4 w-4" />
                                )}
                                Select
                              </>
                            )}
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : !isLoading && !error ? (
                <div className="flex items-center justify-center py-12 px-4 bg-muted rounded-lg border border-dashed border-border">
                  <div className="text-center">
                    <Building2 className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                    <p className="text-muted-foreground font-medium">No Organizations Available</p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Only the global admin mode is available
                    </p>
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default OrganizationContextModal;
