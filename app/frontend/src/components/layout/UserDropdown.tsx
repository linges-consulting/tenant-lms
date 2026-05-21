import React from 'react';
import { NavLink } from 'react-router-dom';
import { LogOut, Settings, User } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '../ui/dropdown-menu';
import { UserAvatar } from '../UserAvatar';

interface UserDropdownUser {
  id?: string;
  full_name?: string | null;
  email?: string;
  avatar_url?: string | null;
}

interface UserDropdownProps {
  user: UserDropdownUser;
  logout: () => void;
  primaryColor?: string;
  align?: 'start' | 'center' | 'end';
  side?: 'top' | 'right' | 'bottom' | 'left';
  showLabel?: boolean;
}

export const UserDropdown: React.FC<UserDropdownProps> = ({ 
  user, 
  logout, 
  primaryColor,
  align = 'end',
  side = 'bottom',
  showLabel = true
}) => {
  const displayName = user?.full_name || 'User';
  const displayEmail = user?.email || '';
  const initials = displayName.split(' ').map((n: string) => n[0]).join('').toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-3 w-full hover:bg-muted p-2 rounded-md transition-colors text-left group outline-none">
          <div className="group-hover:border-primary/50 transition-colors">
            <UserAvatar
              initials={initials}
              avatarUrl={user?.avatar_url}
              shapeId={user?.avatar_url}
              color={primaryColor}
              variant="rounded-square"
              className="w-8 h-8"
            />
          </div>
          {showLabel && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-medium text-foreground truncate">{displayName}</span>
              <span className="text-xs text-muted-foreground truncate">{displayEmail}</span>
            </div>
          )}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align={align} side={side} sideOffset={8}>
        <DropdownMenuLabel>
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-bold leading-none">{displayName}</p>
            <p className="text-[10px] leading-none text-muted-foreground font-medium">{displayEmail}</p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="cursor-pointer" asChild>
          <NavLink to={`/profile/${user?.username || user?.id}`} className="w-full flex items-center">
            <User className="mr-2 h-4 w-4" />
            <span>My Profile</span>
          </NavLink>
        </DropdownMenuItem>
        <DropdownMenuItem className="cursor-pointer" asChild>
          <NavLink to="/settings" className="w-full flex items-center">
            <Settings className="mr-2 h-4 w-4" />
            <span>Settings</span>
          </NavLink>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive cursor-pointer" onClick={logout}>
          <LogOut className="mr-2 h-4 w-4" />
          <span>Log out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
