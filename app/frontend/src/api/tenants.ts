import { client } from './client';
import type { Tenant } from './auth';

export interface TenantCreate {
    name: string;
    admin_email: string;
    admin_name: string;
    logo_url?: string;
    primary_color?: string;
    secondary_color?: string;
}

export interface ServiceHealth {
    status: 'ok' | 'error';
    service: string;
}

export const tenantService = {
    list: () => client.get<Tenant[]>('/tenants'),
    getTenant: (id: string) => client.get<Tenant>(`/tenants/admin/${id}`),
    create: (data: TenantCreate) => client.post<Tenant>('/tenants', data),
    getMetrics: () => client.get<Record<string, unknown>[]>('/tenants/admin/metrics'),
    update: (id: string, data: Partial<TenantCreate> & { is_active?: boolean }) => client.patch<Tenant>(`/tenants/admin/${id}`, data),
    checkHealth: (service: 'auth' | 'core' | 'notification') =>
        client.get<ServiceHealth>(`/health/${service}`),
};
