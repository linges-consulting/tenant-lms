import { client } from './client';
import type { Tenant } from './auth';

export interface TenantMembership {
    tenant_id: string;
    role: string;
    is_business_manager: boolean;
    is_training_creator: boolean;
    is_employee: boolean;
    is_active: boolean;
    status: string;
    tenant?: Tenant;
}

export interface User {
    id: string;
    email: string;
    full_name: string | null;
    avatar_url: string | null;
    username: string | null;
    role: string | null;
    global_role: string | null;
    is_sysadmin: boolean;
    is_active: boolean;
    status?: 'pending' | 'active' | 'deactivated';  // User account status
    theme_preference?: string; // 'light' | 'dark' | 'system'
    members: TenantMembership[];
    created_at: string;
    // groups are loaded separately via groupService
    groups?: string[]; // group names for display
}

export interface InviteUserPayload {
    email: string;
    full_name?: string;
    is_business_manager?: boolean;
    is_training_creator?: boolean;
}

export interface CreateUserPayload {
    email: string;
    full_name: string;
    tenant_id?: string;
    role?: string;
}

export interface CreateUserResponse {
    user_id: string;
    email: string;
    token: string;
    registration_url: string;
    expires_at: string;
}

export interface RegistrationTokenResponse {
    user_id: string;
    token: string;
    registration_url: string;
    expires_at: string;
}

export interface UserStats {
    completed_courses: number;
    in_progress_courses: number;
    total_enrollments: number;
    certificates_earned: number;
}

export interface UserCertificate {
    id: string;
    training_id: string;
    training_title: string;
    completed_at: string;
    certificate_url?: string;
}

export const userService = {
    getMe: (options?: { signal?: AbortSignal }) => client.get<User>('/users/me', options),

    getUser: (userId: string) => client.get<User>(`/users/${userId}`),

    getUserByUsername: (username: string) => client.get<User>(`/users/profile/${username}`),

    updatePassword: (oldPassword: string, newPassword: string) =>
        client.patch('/users/me/password', { old_password: oldPassword, new_password: newPassword }),

    listGlobalUsers: () => client.get<User[]>('/users/admin/list'),

    listTenantUsers: () => client.get<User[]>('/users'),

    inviteUser: (payload: InviteUserPayload) =>
        client.post<{ invite_url: string; message: string }>('/users/invite', payload),

    inviteSysAdmin: (email: string, full_name: string) => client.post<CreateUserResponse>('/users/invite-sysadmin', { email, full_name }),

    createUser: (payload: CreateUserPayload) =>
        client.post<CreateUserResponse>('/users/create', payload),

    getRegistrationToken: (userId: string) =>
        client.get<RegistrationTokenResponse>(`/users/${userId}/token`),

    regenerateRegistrationToken: (userId: string) =>
        client.post<RegistrationTokenResponse>(`/users/${userId}/regenerate-token`, {}),

    deactivateUser: (userId: string, tenantId?: string) => client.post<User>(`/users/${userId}/deactivate${tenantId ? `?tenant_id=${tenantId}` : ''}`),

    reactivateUser: (userId: string, tenantId?: string) => client.post<User>(`/users/${userId}/reactivate${tenantId ? `?tenant_id=${tenantId}` : ''}`),

    resetPassword: (userId: string) => client.post<{ message: string }>(`/users/${userId}/reset-password`),

    deleteUser: (userId: string, tenantId?: string) => client.delete<{ message: string }>(`/users/${userId}${tenantId ? `?tenant_id=${tenantId}` : ''}`),

    modifyUserRole: (userId: string, payload: { tenant_id: string; is_business_manager: boolean; is_training_creator: boolean }) =>
        client.patch<{ message: string }>(`/users/${userId}/role`, payload),

    adminInviteToTenant: (payload: {
        email: string;
        full_name?: string;
        tenant_id: string;
        is_business_manager: boolean;
        is_training_creator: boolean;
    }) => client.post<{ invite_url: string; message: string }>('/users/admin/invite-to-tenant', payload),

    lookupUserByEmail: (email: string) =>
        client.get<{
            id?: string;
            email: string;
            full_name?: string;
            existing_tenant_ids: string[];
            is_active: boolean;
        }>(`/users/admin/lookup/${email}`),

    updateMe: (payload: { username?: string; full_name?: string; avatar_url?: string }) =>
        client.patch<User>('/users/me', payload),

    getMyStats: () => client.get<UserStats>('/user-report/me/stats'),

    getUserStats: (userId: string, tenantId?: string) => 
        client.get<UserStats>(`/user-report/${userId}/stats${tenantId ? `?tenant_id=${tenantId}` : ''}`),

    getMyCertificates: () => client.get<UserCertificate[]>('/user-report/me/certificates'),

    getUserCertificates: (userId: string, tenantId?: string) => 
        client.get<UserCertificate[]>(`/user-report/${userId}/certificates${tenantId ? `?tenant_id=${tenantId}` : ''}`),

    updateUserNameAdmin: (userId: string, fullName: string, reason: string) =>
        client.post<User>(`/users/${userId}/update-name`, { full_name: fullName, reason: reason }),

    bulkImport: (tenantId: string, formData: FormData) =>
        client.post<{
            successes: Array<{ row: number; email: string }>;
            failures: Array<{ row: number; email: string; reason: string }>;
            total_rows: number;
        }>(`/users/bulk-import?tenant_id=${tenantId}`, formData),
};

