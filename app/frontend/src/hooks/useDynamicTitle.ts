import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/auth-context';

const getPageName = (pathname: string): string | null => {
    // Auth routes have a static title handled outside this switch
    if (pathname === '/' || pathname === '/login' || pathname === '/register') {
        return null;
    }

    // Learner portal
    if (pathname.startsWith('/dashboard/my-courses')) return 'My Courses';
    if (pathname.startsWith('/dashboard/certificates')) return 'Certificates';
    if (pathname.startsWith('/dashboard/learn/')) return 'Course';
    if (pathname.startsWith('/dashboard/learn')) return 'Learn';
    if (pathname === '/dashboard') return 'Dashboard';

    // Manager portal
    if (pathname.startsWith('/manage/employees')) return 'Employees';
    if (pathname.startsWith('/manage/groups')) return 'Groups';
    if (pathname.match(/^\/manage\/courses\/[^/]+\/assignments/)) return 'Course Assignments';
    if (pathname.startsWith('/manage/courses/')) return 'Course Editor';
    if (pathname.startsWith('/manage/courses')) return 'Courses';
    if (pathname.startsWith('/manage/my-courses')) return 'My Courses';
    if (pathname.startsWith('/manage/certificates')) return 'Certificates';
    if (pathname.startsWith('/manage/learn/')) return 'Course';
    if (pathname.startsWith('/manage/reports')) return 'Reports';
    if (pathname === '/manage') return 'Dashboard';

    // Admin portal
    if (pathname.startsWith('/admin/tenants/new')) return 'Register Tenant';
    if (pathname.startsWith('/admin/tenants/')) return 'Tenant Settings';
    if (pathname.startsWith('/admin/tenants')) return 'Tenants';
    if (pathname.startsWith('/admin/users')) return 'Users';
    if (pathname.startsWith('/admin/check')) return 'System Check';
    if (pathname === '/admin') return 'Dashboard';

    // Global routes
    if (pathname.startsWith('/settings')) return 'Settings';
    if (pathname.startsWith('/profile')) return 'Profile';
    if (pathname.startsWith('/notifications')) return 'Notifications';

    return 'Page';
};

export const useDynamicTitle = () => {
    const { pathname } = useLocation();
    const { user, activeTenant } = useAuth();

    useEffect(() => {
        // Determine if on auth page
        if (['/', '/login', '/register'].includes(pathname)) {
            document.title = 'Enterprise Learning Platform';
            return;
        }

        const pageName = getPageName(pathname);
        const pageStr = pageName ? ` | ${pageName}` : '';

        if (user) {
            if (activeTenant) {
                // If logged in and has a tenant
                document.title = `${activeTenant.name} Training${pageStr}`;
            } else if (user.is_sysadmin) {
                // If user is admin with no tenant
                document.title = `Enterprise Learning Platform${pageStr}`;
            } else {
                // Fallback for user with no tenant and not admin
                document.title = `Enterprise Learning Platform${pageStr}`;
            }
        } else {
            // Fallback
            document.title = 'Enterprise Learning Platform';
        }
    }, [pathname, user, activeTenant]);
};

export function DynamicTitleUpdater() {
    useDynamicTitle();
    return null;
}
