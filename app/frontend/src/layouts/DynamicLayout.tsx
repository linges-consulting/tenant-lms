import React from 'react';
import { useAuth } from '../contexts/auth-context';
import { Navigate } from 'react-router-dom';
import { AppLayout } from './AppLayout';

export const DynamicLayout: React.FC = () => {
    const { activeTenant, user } = useAuth();

    if (!user) {
        return <Navigate to="/" replace />;
    }

    if (!activeTenant && !user.is_sysadmin) {
        // Multi-tenant user who hasn't selected a tenant yet for global dashboard area.
        // We'll still wrap them in AppLayout but it will use defaults/user-context.
        return <AppLayout />;
    }

    // In all other cases (SysAdmin, or user with activeTenant), 
    // AppLayout will handle the specific contextual rendering.
    return <AppLayout />;
};
