import React from 'react';
import { PanelLeft, PanelLeftClose } from 'lucide-react';
import { Button } from '../ui/button';
import { NotificationBell } from '../NotificationBell';

interface TopbarProps {
    onToggleSidebar: () => void;
    isSidebarVisible: boolean;
}

export const Topbar: React.FC<TopbarProps> = ({ onToggleSidebar, isSidebarVisible }) => {
    return (
        <header className="hidden lg:flex h-16 items-center justify-between px-8 bg-card border-b border-border shrink-0 z-20 shadow-sm transition-all duration-300">
            <div className="flex items-center gap-4">
                {onToggleSidebar && (
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={onToggleSidebar}
                        className="text-muted-foreground hover:text-foreground hover:bg-muted transition-colors rounded-lg"
                        title={isSidebarVisible ? "Hide Sidebar" : "Show Sidebar"}
                    >
                        {isSidebarVisible ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
                    </Button>
                )}
                <div className="flex-1 max-w-lg">
                </div>
            </div>
            <div className="flex items-center gap-6 pl-4">
                <NotificationBell />
            </div>
        </header>
    );
};
