import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { notificationsApi } from '@/api/notifications';
import { useAuth } from './auth-context';

interface NotificationContextType {
    unreadCount: number;
    refreshUnreadCount: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const NotificationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [unreadCount, setUnreadCount] = useState(0);
    const { user } = useAuth();

    const refreshUnreadCount = useCallback(async () => {
        if (!user) {
            setUnreadCount(0);
            return;
        }
        try {
            const data = await notificationsApi.unreadCount();
            setUnreadCount(data.unread_count);
        } catch (error) {
            console.error('Failed to fetch unread notification count:', error);
        }
    }, [user]);

    // Initial fetch and poll
    useEffect(() => {
        if (user) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            refreshUnreadCount();
            
            // Poll every 60 seconds
            const interval = setInterval(refreshUnreadCount, 60000);
            return () => clearInterval(interval);
        } else {
            setUnreadCount(0);
        }
    }, [user, refreshUnreadCount]);

    return (
        <NotificationContext.Provider value={{ unreadCount, refreshUnreadCount }}>
            {children}
        </NotificationContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useNotifications = () => {
    const context = useContext(NotificationContext);
    if (context === undefined) {
        throw new Error('useNotifications must be used within a NotificationProvider');
    }
    return context;
};
