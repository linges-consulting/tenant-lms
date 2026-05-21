import React from 'react';
import {
    Bell,
    CheckCircle2,
    AlertCircle,
    Info,
    Clock,
    Search,
    Loader2,
    Award
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { notificationsApi, type Notification } from '@/api/notifications';
import { certificatesApi } from '@/api/certificates';
import { formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { useQueryClient } from '@tanstack/react-query';
import { notifKeys } from '@/queries/notifications';

import { useNotifications } from '@/contexts/notification-context';

export const NotificationPage: React.FC = () => {
    const { refreshUnreadCount } = useNotifications();
    const qc = useQueryClient();
    const [notifications, setNotifications] = React.useState<Notification[]>([]);
    const [loading, setLoading] = React.useState(true);
    const [searchQuery, setSearchQuery] = React.useState('');

    const invalidateBell = () => {
        qc.invalidateQueries({ queryKey: notifKeys.unreadCount() });
    };

    const loadNotifications = async () => {
        try {
            const data = await notificationsApi.getNotifications();
            setNotifications(data);
        } catch (error) {
            console.error('Failed to fetch notifications:', error);
            toast.error('Failed to load notifications');
        } finally {
            setLoading(false);
        }
    };

    React.useEffect(() => {
        loadNotifications();
    }, []);

    const handleMarkAsRead = async (id: string) => {
        try {
            await notificationsApi.markAsRead(id);
            setNotifications(notifications.map(n => n.id === id ? { ...n, is_read: true } : n));
            refreshUnreadCount();
            invalidateBell();
        } catch {
            toast.error('Failed to mark as read');
        }
    };

    const handleMarkAllRead = async () => {
        try {
            await notificationsApi.markAllAsRead();
            setNotifications(notifications.map(n => ({ ...n, is_read: true })));
            refreshUnreadCount();
            invalidateBell();
            toast.success('All notifications marked as read');
        } catch {
            toast.error('Failed to mark all as read');
        }
    };

    const handleDelete = async (id: string) => {
        try {
            await notificationsApi.deleteNotification(id);
            setNotifications(notifications.filter(n => n.id !== id));
            refreshUnreadCount();
            invalidateBell();
            toast.success('Notification deleted');
        } catch {
            toast.error('Failed to delete notification');
        }
    };

    const filteredNotifications = notifications.filter(n =>
        n.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.message.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const getIcon = (type: string) => {
        switch (type) {
            case 'success': return <CheckCircle2 className="h-5 w-5 text-primary" />;
            case 'warning': return <AlertCircle className="h-5 w-5 text-muted-foreground" />;
            case 'error': return <AlertCircle className="h-5 w-5 text-destructive" />;
            case 'info': return <Info className="h-5 w-5 text-primary" />;
            default: return <Bell className="h-5 w-5 text-muted-foreground" />;
        }
    };

    return (
        <div className="space-y-6 max-w-4xl">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                            <Bell className="w-6 h-6 text-primary" />
                        </div>
                        Notifications
                    </h1>
                    <p className="text-muted-foreground mt-1">Your recent alerts and updates.</p>
                </div>
                {notifications.some(n => !n.is_read) && (
                    <Button variant="outline" size="sm" onClick={handleMarkAllRead}>Mark all as read</Button>
                )}
            </div>

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                    placeholder="Search notifications..."
                    className="pl-10"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                />
            </div>

            <div className="space-y-4">
                {loading ? (
                    <div className="flex justify-center py-20">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    filteredNotifications.map((notif) => (
                        <Card
                            key={notif.id}
                            className={cn('cursor-pointer hover:bg-muted/50 transition-colors', notif.is_read ? 'bg-background' : 'bg-primary/5 border-primary/20')}
                            onClick={() => !notif.is_read && handleMarkAsRead(notif.id)}
                        >
                            <CardContent className="p-4">
                                <div className="flex items-start space-x-4">
                                    <div className="mt-1 flex-shrink-0">
                                        {getIcon(notif.notification_type)}
                                    </div>
                                    <div className="flex-1 space-y-1">
                                        <div className="flex items-center justify-between">
                                            <h3 className="font-semibold">{notif.title}</h3>
                                            <span className="text-xs text-muted-foreground flex items-center">
                                                <Clock className="h-3 w-3 mr-1" />
                                                {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
                                            </span>
                                        </div>
                                        <p className="text-sm text-muted-foreground">{notif.message}</p>
                                        <div className="pt-2 flex flex-wrap gap-2 items-center">
                                            {!notif.is_read && <Badge variant="default" className="text-[10px] h-4">New</Badge>}
                                            {notif.data?.certificate_id && (
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="h-6 text-xs px-2 gap-1"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        certificatesApi.viewCertificatePdf(notif.data!.certificate_id!);
                                                    }}
                                                >
                                                    <Award className="h-3 w-3" />
                                                    View Certificate
                                                </Button>
                                            )}
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-6 text-xs px-2 hover:bg-destructive hover:text-destructive-foreground"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleDelete(notif.id);
                                                }}
                                            >
                                                Delete
                                            </Button>
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    ))
                )}
            </div>

            {!loading && filteredNotifications.length === 0 && (
                <div className="text-center py-20 bg-muted/20 rounded-lg border-2 border-dashed">
                    <Bell className="mx-auto h-12 w-12 text-muted-foreground opacity-20" />
                    <p className="mt-4 text-muted-foreground">
                        {searchQuery ? 'No notifications match your search.' : 'No notifications yet.'}
                    </p>
                </div>
            )}
        </div>
    );
};
