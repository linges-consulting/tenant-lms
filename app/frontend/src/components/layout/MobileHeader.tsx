import React from 'react';
import { NavLink } from 'react-router-dom';
import { Bell, Menu } from 'lucide-react';
import { UserDropdown } from './UserDropdown';
import { useNotifications } from '../../contexts/notification-context';
import { Button } from '../ui/button';
import type { User } from '../../api/users';

interface MobileHeaderProps {
    branding: {
        name: string;
        logo: string;
        roleLabel: string;
        primaryColor?: string;
    };
    user: User | null;
    logout: () => void;
    onMenuClick: () => void;
}

export const MobileHeader: React.FC<MobileHeaderProps> = ({
    branding,
    user,
    logout,
    onMenuClick,
}) => {
    const { unreadCount } = useNotifications();

    return (
        <header className="flex lg:hidden h-14 items-center justify-between px-4 bg-card border-b border-border shrink-0 z-40 sticky top-0 shadow-sm transition-all duration-300">
            <div className="flex items-center gap-2">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={onMenuClick}
                    aria-label="Open menu"
                    className="text-muted-foreground hover:text-foreground"
                >
                    <Menu className="h-5 w-5" />
                </Button>
                {branding.logo.startsWith('http') ? (
                    <img src={branding.logo} alt="Logo" className="w-7 h-7 rounded-lg shadow-sm" />
                ) : (
                    <div
                        className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-primary-foreground bg-primary shadow-sm"
                        style={branding.primaryColor ? { backgroundColor: branding.primaryColor } : undefined}
                    >
                        {branding.logo}
                    </div>
                )}
                <div className="flex flex-col">
                    <span className="font-semibold text-foreground text-sm tracking-tight truncate line-clamp-1 max-w-[120px]">
                        {branding.name}
                    </span>
                    <span className="text-[9px] text-muted-foreground uppercase font-semibold">
                        {branding.roleLabel}
                    </span>
                </div>
            </div>
            <div className="flex items-center gap-4">
                <NavLink to="/notifications" className="relative text-muted-foreground hover:text-foreground group p-1 rounded-full hover:bg-muted">
                    <Bell className="w-5 h-5 transition-colors" />
                    {unreadCount > 0 && (
                        <span className="absolute top-0.5 right-0.5 w-2 h-2 bg-destructive rounded-full border border-card animate-pulsate"></span>
                    )}
                </NavLink>

                <UserDropdown
                    user={user ?? {}}
                    logout={logout}
                    primaryColor={branding.primaryColor}
                    showLabel={false}
                    align="end"
                />
            </div>
        </header>
    );
};
