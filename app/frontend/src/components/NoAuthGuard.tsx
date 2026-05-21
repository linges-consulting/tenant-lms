import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../contexts/auth-context';

interface NoAuthGuardProps {
    children: React.ReactNode;
}

export const NoAuthGuard: React.FC<NoAuthGuardProps> = ({ children }) => {
    const { user, activeTenant, isLoading } = useAuth();

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="flex flex-col items-center gap-4">
                    <div className="h-12 w-12 animate-spin rounded-full border-4 border-primary/20 border-t-primary" />
                </div>
            </div>
        );
    }

    if (user) {
        if (user.is_sysadmin) {
            return <Navigate to="/admin" replace />;
        }

        if (activeTenant) {
            const membership = user.members?.find(m => m.tenant_id === activeTenant.id);
            if (membership?.is_business_manager || membership?.is_training_creator) {
                return <Navigate to="/manage" replace />;
            }
        }
        return <Navigate to="/dashboard" replace />;
    }

    return <>{children}</>;
};
