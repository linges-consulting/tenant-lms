import { ENV } from '../config/env';

export class ApiError extends Error {
    status: number;
    data?: unknown;
    constructor(message: string, status: number, data?: unknown) {
        super(message);
        this.name = 'ApiError';
        this.status = status;
        this.data = data;
    }
}

interface RequestOptions extends RequestInit {
    params?: Record<string, string | string[]>;
    responseType?: 'json' | 'blob';
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, responseType = 'json', ...init } = options;

    let url = `${ENV.API_BASE_URL}${endpoint}`;
    if (params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (Array.isArray(value)) {
                value.forEach(v => searchParams.append(key, v));
            } else if (value !== undefined && value !== null) {
                searchParams.append(key, value);
            }
        });
        const queryString = searchParams.toString();
        if (queryString) {
            url += `?${queryString}`;
        }
    }

    const headers = new Headers(init.headers);
    const token = localStorage.getItem('token');
    
    // Retrieve active tenant ID from storage
    let activeTenantId: string | null = null;
    const activeTenantStr = localStorage.getItem('activeTenant');
    if (activeTenantStr) {
        try {
            const tenant = JSON.parse(activeTenantStr);
            activeTenantId = tenant.id;
        } catch (e) {
            console.error('Failed to parse activeTenant from localStorage', e);
        }
    }

    if (token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    if (activeTenantId && !headers.has('X-Tenant-ID')) {
        headers.set('X-Tenant-ID', activeTenantId);
    }

    if (!(init.body instanceof FormData) && !(init.body instanceof URLSearchParams) && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, {
        ...init,
        headers,
    });

    // Attempt token refresh for 401 responses (except on auth endpoints)
    const authExclusionList = [
        '/auth/login',
        '/auth/register',
        '/auth/check-username',
        '/auth/refresh',
        '/auth/select-tenant',
        '/auth/validate-invite',
        '/auth/register-invite',
        '/auth/tenants',
    ];
    
    const shouldAttemptRefresh = response.status === 401 && 
        !authExclusionList.some(excluded => endpoint.includes(excluded)) && 
        token;

    if (shouldAttemptRefresh) {
        try {
            const refreshRes = await fetch(`${ENV.API_BASE_URL}/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                },
            });

            if (refreshRes.ok) {
                const { access_token } = await refreshRes.json();
                localStorage.setItem('token', access_token);
                headers.set('Authorization', `Bearer ${access_token}`);
                const retryResponse = await fetch(url, { ...init, headers });
                if (retryResponse.ok) {
                    if (responseType === 'blob') return (await retryResponse.blob()) as unknown as T;
                    return await retryResponse.json() as T;
                }
            } else {
                localStorage.removeItem('token');
                window.location.href = '/';
                throw new ApiError('Session expired. Please log in again.', 401);
            }
        } catch (e) {
            console.error('Token refresh error:', e);
            localStorage.removeItem('token');
            if (!(e instanceof ApiError)) {
                window.location.href = '/';
            }
            throw e instanceof ApiError ? e : new ApiError('Session expired. Please log in again.', 401);
        }
    }

    if (!response.ok) {
        let errorData;
        try {
            errorData = await response.json();
        } catch {
            errorData = { detail: response.statusText };
        }
        throw new ApiError(errorData.detail || 'API request failed', response.status, errorData);
    }

    if (response.status === 204) return {} as T;
    if (responseType === 'blob') {
        return (await response.blob()) as unknown as T;
    }
    return await response.json() as T;
}

const isRawBody = (body: unknown) => body instanceof FormData || body instanceof URLSearchParams || typeof body === 'string';

export const client = {
    get: <T>(endpoint: string, options?: RequestOptions) => request<T>(endpoint, { ...options, method: 'GET' }),
    post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
        request<T>(endpoint, { ...options, method: 'POST', body: isRawBody(body) ? (body as BodyInit) : JSON.stringify(body) }),
    put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
        request<T>(endpoint, { ...options, method: 'PUT', body: isRawBody(body) ? (body as BodyInit) : JSON.stringify(body) }),
    patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
        request<T>(endpoint, { ...options, method: 'PATCH', body: isRawBody(body) ? (body as BodyInit) : JSON.stringify(body) }),
    delete: <T>(endpoint: string, options?: RequestOptions) => request<T>(endpoint, { ...options, method: 'DELETE' }),
    getBlob: (endpoint: string, options?: RequestOptions) => 
        request<Blob>(endpoint, { ...options, method: 'GET', responseType: 'blob' }),
};
