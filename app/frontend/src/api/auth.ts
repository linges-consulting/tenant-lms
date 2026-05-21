import { client } from './client';

export interface SessionTokenResponse {
    session_token: string;
}

export interface Tenant {
    id: string;
    name: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
    is_active: boolean;
    user_count?: number;
    course_count?: number;
    certificate_count?: number;
    manager_invite_url?: string;
    is_admin_new?: boolean;
}

export interface TokenResponse {
    access_token: string;
    token_type: string;
}

export const authService = {
    login: (email: string, password: string) => {
        return client.post<SessionTokenResponse>('/auth/login', { email, password });
    },

    getAvailableTenants: () => client.get<Tenant[]>('/auth/tenants'),

    // For sysadmin: returns all tenants from the admin endpoint (not membership-based)
    getAllTenants: () => client.get<Tenant[]>('/tenants'),

    selectTenant: (tenantId?: string | null) => client.post<TokenResponse>('/auth/select-tenant', { tenant_id: tenantId || null }),

    refresh: () => client.post<TokenResponse>('/auth/refresh'),

    register: (email: string, username: string, password: string, fullName?: string) => {
        return client.post<{ id: string; email: string; username: string }>('/auth/register', {
            email,
            username,
            password,
            full_name: fullName,
        });
    },

    checkUsernameAvailability: async (username: string) => {
        try {
            const response = await client.get<{ available: boolean }>(`/auth/check-username?username=${encodeURIComponent(username)}`);
            return response.available;
        } catch {
            // If we get a 400/409, username is taken
            return false;
        }
    },

    validateRegistrationToken: (email: string, token: string) => {
        return client.post<{ valid: boolean }>('/auth/register/validate-token', {
            email,
            token,
        });
    },

    completeRegistration: (email: string, token: string, username: string, password: string) => {
        return client.post<{ id: string; email: string; username: string }>('/auth/register/complete', {
            email,
            token,
            username,
            password,
        });
    },

    forgotPassword: (email: string) =>
        client.post<{ message: string }>('/auth/forgot-password', { email }),

    resetPasswordByToken: (token: string, new_password: string) =>
        client.post<{ message: string }>('/auth/reset-password', { token, new_password }),
};
