import { client as apiClient } from './client';

export interface CertificateTemplate {
    id: string;
    name: string;
    html_content: string;
    is_active: boolean;
    is_default: boolean;
    is_in_use: boolean;
    tenant_id: string;
    created_at: string;
    updated_at: string;
}

export interface CertificateTemplateCreate {
    name: string;
    html_content: string;
    is_active?: boolean;
    target_tenant_id?: string;  // SysAdmin only: specify which tenant to assign this template to
}

export interface CertificateTemplateUpdate {
    name?: string;
    html_content?: string;
    is_active?: boolean;
}

export interface Certificate {
    id: string;
    certificate_number: string;
    user_id: string;
    training_id: string;
    template_id: string;
    issued_at: string;
    data: Record<string, unknown>;
    // Joined fields
    training_title?: string;
    user_name?: string;
}

export const certificatesApi = {
    // Admin Template management
    listTemplates: (tenantIds?: string[]) => 
        apiClient.get<CertificateTemplate[]>('/certificates/templates', { 
            params: tenantIds ? { target_tenant_id: tenantIds } : undefined 
        }),
    
    getTemplate: (id: string) => 
        apiClient.get<CertificateTemplate>(`/certificates/templates/${id}`),
    
    createTemplate: (data: CertificateTemplateCreate) => 
        apiClient.post<CertificateTemplate>('/certificates/templates', data),
    
    updateTemplate: (id: string, data: CertificateTemplateUpdate) => 
        apiClient.put<CertificateTemplate>(`/certificates/templates/${id}`, data),
    
    deleteTemplate: (id: string) => 
        apiClient.delete(`/certificates/templates/${id}`),
    
    getTemplatePreviewUrl: (id: string) => {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1';
        return `${baseUrl}/certificates/templates/${id}/pdf`;
    },

    previewTemplatePdf: async (id: string) => {
        const blob = await apiClient.getBlob(`/certificates/templates/${id}/pdf`);
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        // Clean up URL object after a short delay to allow the tab to load
        setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    },
    
    downloadCertificatePdf: async (id: string) => {
        const blob = await apiClient.getBlob(`/certificates/${id}/pdf`);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `certificate_${id}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    },

    viewCertificatePdf: async (id: string) => {
        const blob = await apiClient.getBlob(`/certificates/${id}/pdf`);
        const url = window.URL.createObjectURL(blob);
        window.open(url, '_blank');
        setTimeout(() => window.URL.revokeObjectURL(url), 60000);
    },
    
    previewTemplate: (html_content: string, data: Record<string, unknown> = {}) =>
        apiClient.post<{ rendered_html: string }>('/certificates/templates/preview', { html_content, data }),

    // User Certificates
    listMyCertificates: () => 
        apiClient.get<Certificate[]>('/certificates/my'),
    
    getCertificate: (id: string) => 
        apiClient.get<Certificate>(`/certificates/${id}`),
    
    getCertificateView: (id: string) =>
        apiClient.get<{ rendered_html: string }>(`/certificates/${id}/view`),
    
    downloadCertificate: async (id: string, format: 'html' | 'pdf' = 'pdf') => {
        const token = localStorage.getItem('access_token') || '';
        const tenantId = localStorage.getItem('active_tenant_id') || '';
        
        // Match the backend: /{id}/pdf for PDF, or use /{id}/view for HTML if we want to download it
        const url_path = format === 'pdf' ? `/api/v1/certificates/${id}/pdf` : `/api/v1/certificates/${id}/view`;
        
        const resp = await fetch(url_path, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-Tenant-ID': tenantId,
            }
        });
        if (!resp.ok) throw new Error('Download failed');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `certificate_${id}.${format === 'pdf' ? 'pdf' : 'html'}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
};
