import { client } from './client';

export interface Notification {
    id: string;
    event_id: string | null;
    tenant_id: string;
    user_id: string;
    title: string;
    message: string;
    notification_type: 'success' | 'warning' | 'info' | 'error';
    is_read: boolean;
    created_at: string;
    data?: { certificate_id?: string } | null;
}

export interface NotificationListResponse {
    items: Notification[];
    total: number;
    limit: number;
    offset: number;
}

export const notificationsApi = {
    getNotifications: async (): Promise<Notification[]> => {
        const data = await client.get<NotificationListResponse>('/notifications');
        return data.items;
    },

    list: (limit = 20, offset = 0): Promise<NotificationListResponse> =>
        client.get<NotificationListResponse>(`/notifications?limit=${limit}&offset=${offset}`),

    unreadCount: (): Promise<{ unread_count: number }> =>
        client.get<{ unread_count: number }>('/notifications/unread-count'),

    markAsRead: async (notificationId: string): Promise<{ status: string }> => {
        return await client.patch<{ status: string }>(`/notifications/${notificationId}/read`);
    },

    markRead: (id: string): Promise<{ status: string }> =>
        client.patch<{ status: string }>(`/notifications/${id}/read`),

    markAllRead: (): Promise<{ status: string }> =>
        client.patch<{ status: string }>('/notifications/mark-all-read'),

    markAllAsRead: async (): Promise<{ status: string }> => {
        return await client.patch<{ status: string }>('/notifications/mark-all-read');
    },

    deleteNotification: async (notificationId: string): Promise<{ status: string }> => {
        return await client.delete<{ status: string }>(`/notifications/${notificationId}`);
    }
};
