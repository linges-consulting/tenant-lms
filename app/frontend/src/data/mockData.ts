// src/data/mockData.ts

export const CURRENT_USER = {
    name: "Alex Johnson",
    email: "alex.j@company.com",
    role: "Learner",
    avatarUrl: "https://i.pravatar.cc/150?u=alex",
};

export const ADMIN_USER = {
    name: "Sarah Admin",
    email: "sarah.a@company.com",
    role: "Manager",
    avatarUrl: "https://i.pravatar.cc/150?u=sarah",
};

export const TENANT_INFO = {
    name: "Acme Corp",
    logoUrl: "https://ui-avatars.com/api/?name=AC&background=135BEC&color=fff&rounded=true&bold=true",
    primaryColor: "#135BEC",
};

export const LEARNER_NAV_LINKS = [
    { label: "Dashboard", href: "/dashboard", activeMatch: "/dashboard", icon: "LayoutDashboard" },
    { label: "My Trainings", href: "/dashboard/my-courses", activeMatch: "/dashboard/my-courses", icon: "BookOpen" },
    { label: "Certificates", href: "/dashboard/certificates", activeMatch: "/dashboard/certificates", icon: "Award" },
];

export const MANAGER_NAV_LINKS = [
    { label: "Dashboard", href: "/manage", activeMatch: "/manage", icon: "LayoutDashboard" },
    { label: "My Trainings", href: "/manage/my-courses", activeMatch: "/manage/my-courses", icon: "BookOpen" },
    { label: "Manage Trainings", href: "/manage/courses", activeMatch: "/manage/courses", icon: "FileText" },
    { label: "Employees", href: "/manage/employees", activeMatch: "/manage/employees", icon: "Users" },
    { label: "Groups", href: "/manage/groups", activeMatch: "/manage/groups", icon: "Users" },
    { label: "Reports", href: "/manage/reports", activeMatch: "/manage/reports", icon: "Activity" },
    { label: "Certificates", href: "/manage/certificates", activeMatch: "/manage/certificates", icon: "Award" },
    { label: "Categories", href: "/manage/categories", activeMatch: "/manage/categories", icon: "Tag" },
];

export const LEARNER_METRICS = [
    { label: "In Progress", value: "3", icon: "Clock" },
    { label: "Completed", value: "12", icon: "CheckCircle" },
    { label: "Certifications", value: "4", icon: "Award" },
];

export const ASSIGNED_COURSES = [
    {
        id: "c1",
        title: "Information Security Basics",
        category: "Compliance",
        duration: "45 min",
        progress: 100,
        status: "Completed",
        thumbnail: "https://images.unsplash.com/photo-1550751827-4bd374c3f58b",
    },
    {
        id: "c2",
        title: "Advanced React Patterns",
        category: "Engineering",
        duration: "2h 30m",
        progress: 40,
        status: "In Progress",
        thumbnail: "https://images.unsplash.com/photo-1633356122544-f134324a6cee",
    },
    {
        id: "c3",
        title: "Q3 Corporate Ethics",
        category: "Compliance",
        duration: "30 min",
        progress: 0,
        status: "Not Started",
        thumbnail: "https://images.unsplash.com/photo-1589829085413-56de8ae18c73",
    },
];

export const MANAGER_METRICS = [
    { label: "Global Compliance", value: "82%", trend: "+2.4%" },
    { label: "Total Employees", value: "154", trend: "+12" },
    { label: "Training Hours", value: "450h", trend: "+45h" },
    { label: "Overdue", value: "3", trend: "-2", isAlert: true },
];

export const URGENT_ACTIONS = [
    { id: 1, title: "3 Employees Overdue for Ethics Training", time: "2h ago" },
    { id: 2, title: "Review 'Q4 Sales Pitch' Course Draft", time: "5h ago" },
];

export const EMPLOYEE_LIST = [
    { id: 1, name: "Alice Smith", email: "alice@acme.com", role: "Developer", compliance: 100, joined: "2023-01-15", avatarUrl: "https://i.pravatar.cc/150?u=1" },
    { id: 2, name: "Bob Jones", email: "bob@acme.com", role: "Designer", compliance: 60, joined: "2023-03-22", avatarUrl: "https://i.pravatar.cc/150?u=2" },
    { id: 3, name: "Charlie Day", email: "charlie@acme.com", role: "Sales Rep", compliance: 100, joined: "2022-11-05", avatarUrl: "https://i.pravatar.cc/150?u=3" },
    { id: 4, name: "Diana Prince", email: "diana@acme.com", role: "Product Manager", compliance: 85, joined: "2024-01-10", avatarUrl: "https://i.pravatar.cc/150?u=4" },
];

export const SYS_ADMIN_USER = {
    name: "System Admin",
    email: "sysadmin@customlms.com",
    role: "Super Admin",
    avatarUrl: "https://i.pravatar.cc/150?u=sysadmin",
};

export const ADMIN_NAV_LINKS = [
    { label: "Dashboard", href: "/admin", activeMatch: "/admin", icon: "LayoutDashboard" },
    { label: "Tenants", href: "/admin/tenants", activeMatch: "/admin/tenants", icon: "Building2" },
    { label: "Global Users", href: "/admin/users", activeMatch: "/admin/users", icon: "Users" },
    { label: "Certificate Templates", href: "/admin/certificate-templates", activeMatch: "/admin/certificate-templates", icon: "ShieldCheck" },
    { label: "System Check", href: "/admin/check", activeMatch: "/admin/check", icon: "Activity" },
];

export const ADMIN_METRICS = [
    { label: "Active Tenants", value: "24", trend: "+3" },
    { label: "Global Users", value: "12,450", trend: "+850" },
    { label: "Total Trainings", value: "842", trend: "+12" },
    { label: "System Status", value: "Healthy", isAlert: false, trend: "99.9% Uptime" },
];

export const TENANT_LIST = [
    { id: "t1", name: "Acme Corp", users: 154, status: "Active", courses: 14, certificates: 892 },
    { id: "t2", name: "Globex Inc", users: 89, status: "Active", courses: 8, certificates: 412 },
    { id: "t3", name: "Initech", users: 42, status: "Warning", courses: 3, certificates: 85 },
    { id: "t4", name: "Soylent Corp", users: 210, status: "Active", courses: 24, certificates: 1250 },
];

// --- Database Simulation ---
export type UserRole = 'Learner' | 'Manager' | 'SysAdmin';

export interface MockUserMembership {
    tenantId: string | 'system';
    tenantName: string;
    role: UserRole;
    branding?: {
        primaryColor: string;
        secondaryColor: string;
        logoUrl: string;
    };
}

export interface MockUser {
    id: string;
    email: string;
    passwordHash: string; // In UI we just compare plain 'password' for testing
    name: string;
    avatarUrl: string;
    themePreference: 'light' | 'dark' | 'system';
    memberships: MockUserMembership[];
}

export const MOCK_USERS: MockUser[] = [
    {
        id: "u1",
        email: "learner@acme.com",
        passwordHash: "password",
        name: "Alex Learner",
        avatarUrl: "https://i.pravatar.cc/150?u=alex",
        themePreference: "system",
        memberships: [
            {
                tenantId: "t1", tenantName: "Acme Corp", role: "Learner",
                branding: { primaryColor: "#135BEC", secondaryColor: "#0f45b3", logoUrl: "https://ui-avatars.com/api/?name=AC&background=135BEC&color=fff" }
            }
        ]
    },
    {
        id: "u2",
        email: "manager@acme.com",
        passwordHash: "password",
        name: "Sarah Admin",
        avatarUrl: "https://i.pravatar.cc/150?u=sarah",
        themePreference: "light",
        memberships: [
            {
                tenantId: "t1", tenantName: "Acme Corp", role: "Manager",
                branding: { primaryColor: "#135BEC", secondaryColor: "#0f45b3", logoUrl: "https://ui-avatars.com/api/?name=AC&background=135BEC&color=fff" }
            }
        ]
    },
    {
        id: "u3",
        email: "admin@acme.com",
        passwordHash: "password",
        name: "System Admin",
        avatarUrl: "https://i.pravatar.cc/150?u=sysadmin",
        themePreference: "dark",
        memberships: [
            {
                tenantId: "system", tenantName: "Global LMS Network", role: "SysAdmin",
                branding: { primaryColor: "#10b981", secondaryColor: "#059669", logoUrl: "https://ui-avatars.com/api/?name=GLN&background=10b981&color=fff" }
            }
        ]
    },
    {
        id: "u4",
        email: "multi@acme.com",
        passwordHash: "password",
        name: "Multi Workspace User",
        avatarUrl: "https://i.pravatar.cc/150?u=multi",
        themePreference: "dark",
        memberships: [
            {
                tenantId: "t1", tenantName: "Acme Corp", role: "Learner",
                branding: { primaryColor: "#135BEC", secondaryColor: "#0f45b3", logoUrl: "https://ui-avatars.com/api/?name=AC&background=135BEC&color=fff" }
            },
            {
                tenantId: "t2", tenantName: "Globex Inc", role: "Manager",
                branding: { primaryColor: "#8b5cf6", secondaryColor: "#6d28d9", logoUrl: "https://ui-avatars.com/api/?name=GL&background=8b5cf6&color=fff" }
            },
            {
                tenantId: "t4", tenantName: "Soylent Corp", role: "Manager",
                branding: { primaryColor: "#ef4444", secondaryColor: "#b91c1c", logoUrl: "https://ui-avatars.com/api/?name=SC&background=ef4444&color=fff" }
            }
        ]
    }
];
