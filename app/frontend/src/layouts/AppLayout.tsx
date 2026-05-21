import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/auth-context';
import { ADMIN_NAV_LINKS, MANAGER_NAV_LINKS, LEARNER_NAV_LINKS } from '../data/mockData';
import { Sidebar } from '../components/layout/Sidebar';
import { Topbar } from '../components/layout/Topbar';
import { MobileHeader } from '../components/layout/MobileHeader';
import { MobileBottomNav } from '../components/layout/MobileBottomNav';
import { Sheet, SheetContent } from '../components/ui/sheet';

export function AppLayout() {
    const { user, activeTenant, activeMembership, logout } = useAuth();
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);

    // 1. Determine Portal Context (Role-Based Priority)
    const isSystemAdmin = user?.is_sysadmin === true;
    const isBusinessManager = activeMembership?.is_business_manager === true;
    const isTrainingCreator = activeMembership?.is_training_creator === true;
    const hasManagerRights = isBusinessManager || isTrainingCreator;

    // Determine the active portal context (Role-Based Priority)
    let activeContext: 'admin' | 'manage' | 'learner' = 'learner';

    if (isSystemAdmin) {
        activeContext = 'admin';
    } else if (hasManagerRights) {
        activeContext = 'manage';
    } else {
        activeContext = 'learner';
    }

    // 2. Resolve Branding
    const getAcronym = (name: string) => name ? name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() : 'L';
    let branding = {
        name: activeTenant?.name || 'Custom LMS',
        logo: activeTenant?.logo_url || getAcronym(activeTenant?.name || 'Custom LMS'),
        subLabel: 'Learner Portal',
        roleLabel: 'Learner',
        primaryColor: activeTenant?.primary_color || undefined as string | undefined,
    };

    if (activeContext === 'admin') {
        branding = {
            name: 'System Admin',
            logo: 'SA',
            subLabel: 'Master Control',
            roleLabel: 'Admin',
            primaryColor: undefined,
        };
    } else if (activeContext === 'manage') {
        branding.subLabel = 'Manager Portal';
        branding.roleLabel = 'Manager';
    }

    // 3. Resolve Navigation Links
    let rawLinks = LEARNER_NAV_LINKS;
    let basePath = '/dashboard';

    if (activeContext === 'admin') {
        rawLinks = ADMIN_NAV_LINKS;
        basePath = '/admin';
    } else if (activeContext === 'manage') {
        rawLinks = MANAGER_NAV_LINKS;
        basePath = '/manage';
    }

    // 4. Apply Role-Based Filtering
    const filteredLinks = rawLinks.filter(link => {
        if (activeContext === 'manage') {
            if (!isBusinessManager && ['Employees', 'Groups', 'Reports'].includes(link.label)) {
                return false;
            }
            if (link.label === 'Manage Trainings' && !isTrainingCreator) {
                return false;
            }
        }
        return true;
    });

    // 5. Mobile-specific filters (to keep bottom bar clean)
    const mobileBottomLinks = filteredLinks.filter(link => {
        if (activeContext === 'admin' && link.label === 'System Check') return false;
        if (activeContext === 'manage' && link.label === 'Reports') return false;
        return true;
    });

    return (
        <div className="flex h-screen w-full bg-background overflow-hidden relative selection:bg-primary/30">
            {/* Desktop Sidebar — hidden on mobile */}
            <div className="hidden md:flex">
                <Sidebar
                    user={user!}
                    activeMembership={activeMembership}
                    collapsed={sidebarCollapsed}
                    branding={branding}
                    logout={logout}
                />
            </div>

            {/* Mobile Sheet Drawer */}
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
                <SheetContent side="left" className="p-0 w-56">
                    <Sidebar
                        user={user!}
                        activeMembership={activeMembership}
                        collapsed={false}
                        branding={branding}
                        logout={logout}
                    />
                </SheetContent>
            </Sheet>

            <div className="flex-1 flex flex-col h-full min-w-0 transition-all duration-300">
                {/* Desktop Topbar — hidden on mobile */}
                <div className="hidden md:block">
                    <Topbar
                        onToggleSidebar={() => setSidebarCollapsed(!sidebarCollapsed)}
                        isSidebarVisible={!sidebarCollapsed}
                    />
                </div>

                {/* Mobile Header — visible only on mobile */}
                <div className="md:hidden">
                    <MobileHeader
                        branding={branding}
                        user={user}
                        logout={logout}
                        onMenuClick={() => setMobileOpen(true)}
                    />
                </div>

                {/* Main Content Area */}
                <main className="flex-1 overflow-x-hidden overflow-y-auto bg-background pb-16 lg:pb-0 scroll-smooth custom-scrollbar">
                    <div className="min-h-full max-w-7xl mx-auto p-4 md:p-8 animate-in slide-in-from-bottom-4 duration-700 fade-in">
                        <Outlet />
                    </div>
                </main>
            </div>

            {/* Mobile Bottom Navigation */}
            <MobileBottomNav
                links={mobileBottomLinks}
                primaryColor={branding.primaryColor}
                basePath={basePath}
            />
        </div>
    );
};
