import { Bell } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { Button } from './ui/button';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { ScrollArea } from './ui/scroll-area';
import { cn } from '@/lib/utils';
import { useUnreadCount, useNotifications, useMarkAllRead } from '../queries/notifications';
import type { Notification } from '../api/notifications';

export function NotificationBell() {
  const { data: unreadData } = useUnreadCount();
  const { data: notifData } = useNotifications(5, 0);
  const markAllRead = useMarkAllRead();

  const unreadCount = unreadData?.unread_count ?? 0;
  const items: Notification[] = notifData?.items ?? [];

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative text-muted-foreground hover:text-foreground hover:bg-muted transition-colors rounded-full"
          aria-label="Notifications"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-destructive-foreground text-xs font-bold leading-none">
              {unreadCount > 9 ? '9+' : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        <div className="flex items-center justify-between border-b px-4 py-2">
          <span className="text-sm font-semibold">Notifications</span>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-auto py-1 px-2"
              onClick={() => markAllRead.mutate()}
              disabled={markAllRead.isPending}
            >
              Mark all read
            </Button>
          )}
        </div>
        <ScrollArea className="h-72">
          {items.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-6">No notifications</p>
          ) : (
            items.map((n) => (
              <div
                key={n.id}
                className={cn(
                  'border-b px-4 py-3 text-sm',
                  !n.is_read && 'bg-accent/50',
                )}
              >
                <p className="font-medium">{n.title}</p>
                <p className="text-muted-foreground text-xs mt-0.5 line-clamp-2">{n.message}</p>
              </div>
            ))
          )}
        </ScrollArea>
        <div className="border-t px-4 py-2">
          <NavLink
            to="/notifications"
            className="text-xs text-primary hover:underline"
          >
            View all notifications
          </NavLink>
        </div>
      </PopoverContent>
    </Popover>
  );
}
