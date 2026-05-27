import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/auth-context';

interface AuthGuardProps {
    children: React.ReactNode;
    requireSysAdmin?: boolean;
    requireNotSysAdmin?: boolean;
    requireTrainingCreator?: boolean;
    requireBusinessManager?: boolean;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({
    children,
    requireSysAdmin = false,
    requireNotSysAdmin = false,
    requireTrainingCreator = false,
    requireBusinessManager = false,
}) => {
    const { user, activeMembership, isLoading } = useAuth();
    const location = useLocation();

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
                    <p className="text-sm font-medium text-muted-foreground animate-pulse">
                        Waking up the LMS...
                    </p>
                </div>
            </div>
        );
    }

    if (!user) {
        return <Navigate to="/" state={{ from: location }} replace />;
    }

    if (requireSysAdmin && !user.is_sysadmin) {
        return <Navigate to="/dashboard" replace />;
    }

    // SysAdmins are global-only — they have no tenant membership and cannot use
    // the learner or manager portals. Redirect them to their admin portal.
    if (requireNotSysAdmin && user.is_sysadmin) {
        return <Navigate to="/admin" replace />;
    }

    if (requireTrainingCreator && !activeMembership?.is_training_creator) {
        return <Navigate to="/manage" replace />;
    }

    if (requireBusinessManager && !activeMembership?.is_business_manager) {
        return <Navigate to="/dashboard" replace />;
    }

    return <>{children}</>;
};
