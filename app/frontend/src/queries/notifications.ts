import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../api/notifications';
export type { NotificationListResponse } from '../api/notifications';

export const notifKeys = {
  all: ['notifications'] as const,
  list: (page?: number) => [...notifKeys.all, 'list', page] as const,
  unreadCount: () => [...notifKeys.all, 'unread-count'] as const,
};

export function useNotifications(limit = 20, offset = 0) {
  return useQuery({
    queryKey: notifKeys.list(offset),
    queryFn: () => notificationsApi.list(limit, offset),
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: notifKeys.unreadCount(),
    queryFn: () => notificationsApi.unreadCount(),
    refetchInterval: 30_000,
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => qc.invalidateQueries({ queryKey: notifKeys.all }),
  });
}
