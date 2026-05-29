import type { ElementType } from 'react';
import { useState, useEffect, useCallback } from 'react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Users, LayoutDashboard, Award,
  BarChart3, TrendingUp, UserCheck, BookOpen,
  GraduationCap, Layers, ClipboardList,
  FileText, Activity, RefreshCw, Globe, Tag,
} from 'lucide-react';
import { UserDropdown } from './UserDropdown';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Badge } from '../ui/badge';
import { tenantService } from '../../api/tenants';

interface User {
  id: string;
  full_name: string | null;
  email: string;
  avatar_url: string | null;
  username: string | null;
  is_sysadmin: boolean;
}

interface ActiveMembership {
  is_business_manager: boolean;
  is_training_creator: boolean;
}

interface Branding {
  name: string;
  logo: string;
  subLabel: string;
  primaryColor?: string;
}

export interface SidebarProps {
  user: User;
  activeMembership: ActiveMembership | null;
  collapsed: boolean;
  branding: Branding;
  logout: () => void;
}

interface NavItem {
  to: string;
  icon: ElementType;
  label: string;
}

// Learner portal
const LEARNING_NAV: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/dashboard/my-courses', icon: BookOpen, label: 'My Trainings' },
  { to: '/dashboard/certificates', icon: Award, label: 'Certificates' },
];

// Visible to all manager-context users (both roles)
const MANAGER_COMMON_NAV: NavItem[] = [
  { to: '/manage', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/manage/my-courses', icon: BookOpen, label: 'My Trainings' },
  { to: '/manage/certificates', icon: Award, label: 'Certificates' },
];

// Business Manager only
const MANAGEMENT_NAV: NavItem[] = [
  { to: '/manage/employees', icon: Users, label: 'Employees' },
  { to: '/manage/groups', icon: UserCheck, label: 'Groups' },
  { to: '/manage/reports', icon: BarChart3, label: 'Reports' },
  { to: '/manage/analytics', icon: TrendingUp, label: 'Analytics' },
  { to: '/manage/publish', icon: Globe, label: 'Review & Publish' },
  { to: '/manage/categories', icon: Tag, label: 'Categories' },
];

// Training Creator only
const STUDIO_NAV: NavItem[] = [
  { to: '/manage/courses', icon: FileText, label: 'Course Studio' },
];

const ADMIN_NAV: NavItem[] = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/admin/tenants', icon: Layers, label: 'Tenants' },
  { to: '/admin/users', icon: Users, label: 'Global Users' },
  { to: '/admin/certificate-templates', icon: GraduationCap, label: 'Certificate Templates' },
  { to: '/admin/check', icon: Activity, label: 'System Check' },
  { to: '/admin/bulk-import', icon: ClipboardList, label: 'Bulk Import' },
];

interface NavSectionProps {
  title: string;
  items: NavItem[];
  collapsed: boolean;
}

function NavSection({ title, items, collapsed }: NavSectionProps) {
  return (
    <div className="mb-4">
      {!collapsed && (
        <p className="px-3 mb-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </p>
      )}
      <div className="space-y-0.5">
        {items.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to.split('/').length <= 2}
            aria-label={label}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
                'hover:bg-accent hover:text-accent-foreground',
                isActive ? 'bg-primary text-primary-foreground font-medium' : 'text-foreground',
                collapsed && 'justify-center px-2',
              )
            }
            title={collapsed ? label : undefined}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </div>
    </div>
  );
}

function BrandingHeader({ branding, collapsed, isAdmin }: { branding: Branding; collapsed: boolean; isAdmin: boolean }) {
  const isLogoUrl = branding.logo.startsWith('http') || branding.logo.startsWith('/');
  return (
    <div className={cn('h-16 flex items-center border-b shrink-0 px-3', (collapsed || isAdmin) && 'justify-center')}>
      <div className={cn('flex items-center gap-2 min-w-0', isAdmin && 'justify-center')}>
        {!isAdmin && (
          isLogoUrl ? (
            <img
              src={branding.logo}
              alt={branding.name}
              className="w-8 h-8 rounded-lg object-cover shrink-0"
            />
          ) : (
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-xs shrink-0"
              style={{ backgroundColor: branding.primaryColor || 'hsl(var(--primary))' }}
            >
              {branding.logo.slice(0, 2)}
            </div>
          )
        )}
        {!collapsed && (
          <div className={cn('flex flex-col min-w-0', isAdmin && 'items-center')}>
            <span className="text-sm font-bold text-foreground truncate">{branding.name}</span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
              {branding.subLabel}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

type HealthStatus = 'checking' | 'ok' | 'error';

const SERVICES: { key: 'auth' | 'core' | 'notification'; label: string; description: string }[] = [
  { key: 'auth', label: 'Auth Service', description: 'Authentication, users, tenants & groups' },
  { key: 'core', label: 'Core Service', description: 'Trainings, progress, certificates & media' },
  { key: 'notification', label: 'Notification', description: 'In-app notifications & email delivery' },
];

function dotColor(status: HealthStatus): string {
  if (status === 'ok') return 'bg-green-500';
  if (status === 'error') return 'bg-destructive';
  return 'bg-muted-foreground/40';
}

function healthBadgeVariant(): 'outline' {
  return 'outline';
}

function healthBadgeClass(status: HealthStatus): string {
  if (status === 'ok') return 'border-green-500/30 text-green-600 dark:text-green-400 bg-green-500/10';
  if (status === 'error') return 'border-destructive/30 text-destructive bg-destructive/10';
  return 'border-border text-muted-foreground bg-muted';
}

function healthLabel(status: HealthStatus): string {
  if (status === 'ok') return 'Operational';
  if (status === 'error') return 'Degraded';
  return 'Checking…';
}

interface ServiceHealthPanelProps {
  healthStatus: Record<string, HealthStatus>;
  onRefresh: () => void;
}

function ServiceHealthPanel({ healthStatus, onRefresh }: ServiceHealthPanelProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="System health"
        aria-label="System health status"
        className="flex flex-col items-center justify-center gap-[3px] p-2 rounded-md hover:bg-accent transition-colors shrink-0"
      >
        {SERVICES.map(s => (
          <span
            key={s.key}
            className={cn('h-1.5 w-1.5 rounded-full shrink-0', dotColor(healthStatus[s.key] as HealthStatus))}
          />
        ))}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Activity className="w-4 h-4" />
              System Health
              <button
                onClick={onRefresh}
                className="p-1 rounded hover:bg-accent transition-colors ml-1"
                title="Refresh health status"
                aria-label="Refresh health status"
              >
                <RefreshCw className="w-3.5 h-3.5 text-muted-foreground" />
              </button>
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 pt-1">
            {SERVICES.map(({ key, label, description }) => {
              const status = healthStatus[key] as HealthStatus;
              return (
                <div key={key} className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <span className={cn('h-2 w-2 rounded-full shrink-0 mt-0.5', dotColor(status))} />
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-none">{label}</p>
                      <p className="text-xs text-muted-foreground mt-0.5 truncate">{description}</p>
                    </div>
                  </div>
                  <Badge variant={healthBadgeVariant()} className={cn('shrink-0 text-[10px] px-1.5', healthBadgeClass(status))}>
                    {healthLabel(status)}
                  </Badge>
                </div>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function Sidebar({ user, activeMembership, collapsed, branding, logout }: SidebarProps) {
  const isManager = activeMembership?.is_business_manager ?? false;
  const isCreator = activeMembership?.is_training_creator ?? false;
  const isAdmin = user.is_sysadmin;
  const hasManagerAccess = isManager || isCreator;

  const [healthStatus, setHealthStatus] = useState<Record<string, HealthStatus>>(
    isAdmin ? { auth: 'checking', core: 'checking', notification: 'checking' } : {}
  );

  const pollHealth = useCallback(() => {
    if (!isAdmin) return;
    SERVICES.forEach(({ key }) => {
      tenantService.checkHealth(key)
        .then(() => setHealthStatus(prev => ({ ...prev, [key]: 'ok' })))
        .catch(() => setHealthStatus(prev => ({ ...prev, [key]: 'error' })));
    });
  }, [isAdmin]);

  const checkHealth = useCallback(() => {
    if (!isAdmin) return;
    setHealthStatus({ auth: 'checking', core: 'checking', notification: 'checking' });
    pollHealth();
  }, [isAdmin, pollHealth]);

  useEffect(() => {
    if (!isAdmin) return;
    pollHealth();
    const interval = setInterval(pollHealth, 60_000);
    return () => clearInterval(interval);
  }, [pollHealth, isAdmin]);

  return (
    <aside
      aria-label="Main navigation"
      className={cn(
        'flex flex-col h-full border-r bg-card transition-all duration-200',
        collapsed ? 'w-14' : 'w-56',
      )}
    >
      <BrandingHeader branding={branding} collapsed={collapsed} isAdmin={isAdmin} />

      <div className="flex-1 overflow-y-auto py-4 px-2">
        {isAdmin ? (
          <NavSection title="Admin" items={ADMIN_NAV} collapsed={collapsed} />
        ) : hasManagerAccess ? (
          <>
            <NavSection title="My Learning" items={MANAGER_COMMON_NAV} collapsed={collapsed} />
            {isManager && (
              <NavSection title="Management" items={MANAGEMENT_NAV} collapsed={collapsed} />
            )}
            {isCreator && (
              <NavSection title="Studio" items={STUDIO_NAV} collapsed={collapsed} />
            )}
          </>
        ) : (
          <NavSection title="Learning" items={LEARNING_NAV} collapsed={collapsed} />
        )}
      </div>

      <div className="border-t p-2">
        <div className="flex items-center gap-1.5">
          {isAdmin && (
            <ServiceHealthPanel
              healthStatus={healthStatus}
              onRefresh={checkHealth}
            />
          )}
          <div className="flex-1 min-w-0">
            <UserDropdown
              user={user}
              logout={logout}
              primaryColor={branding.primaryColor}
              align="end"
              side="top"
              showLabel={!collapsed}
            />
          </div>
        </div>
      </div>
    </aside>
  );
}
