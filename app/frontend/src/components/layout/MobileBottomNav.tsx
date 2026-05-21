import React from 'react';
import { NavLink } from 'react-router-dom';
import { Icon } from '../ui/Icon';

interface MobileBottomNavProps {
    links: { label: string; href: string; icon: string; activeMatch?: string }[];
    primaryColor?: string;
    basePath: string;
}

export const MobileBottomNav: React.FC<MobileBottomNavProps> = ({ 
    links, 
    primaryColor,
    basePath
}) => {
    // Filter some links if there are too many for mobile bottom nav
    const mobileLinks = links.length > 5 ? links.slice(0, 5) : links;

    return (
        <nav className="lg:hidden fixed bottom-0 left-0 right-0 h-16 bg-card border-t border-border z-40 flex items-center justify-around px-2 pb-safe shadow-[0_-4px_10px_rgba(0,0,0,0.05)] transition-all duration-300">
            {mobileLinks.map((link) => (
                <NavLink
                    key={link.label}
                    to={link.href}
                    end={link.href === basePath}
                    className={({ isActive }) =>
                        `flex flex-col items-center justify-center w-full h-full space-y-1 transition-all ${isActive 
                            ? 'text-primary scale-110' 
                            : 'text-muted-foreground hover:text-foreground'
                        }`
                    }
                    style={({ isActive }) =>
                        isActive && primaryColor
                            ? { color: primaryColor }
                            : {}
                    }
                >
                    <Icon name={link.icon} className="w-5 h-5" />
                    <span className="text-[10px] font-medium truncate max-w-full px-1">{link.label}</span>
                </NavLink>
            ))}
        </nav>
    );
};
