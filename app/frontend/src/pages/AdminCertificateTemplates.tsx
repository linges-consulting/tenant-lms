import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, MoreVertical, Trash2, Edit, CheckCircle, XCircle, Eye, Loader2, ToggleLeft, ToggleRight, ShieldCheck } from 'lucide-react';
import { getApiError } from '../lib/utils';
import { Button } from '../components/ui/button';
import { 
    Table, 
    TableBody, 
    TableCell, 
    TableHead, 
    TableHeader, 
    TableRow 
} from '../components/ui/table';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Badge } from '../components/ui/badge';
import { certificatesApi } from '../api/certificates';
import type { CertificateTemplate } from '../api/certificates';
import { tenantService } from '../api/tenants';
import type { Tenant } from '../api/auth';
import { useAuth } from '../contexts/auth-context';
import { toast } from 'sonner';
import { MultiSelect } from '../components/MultiSelect';
import type { Option } from '../components/MultiSelect';

export const AdminCertificateTemplates: React.FC = () => {
    const { user } = useAuth();
    const navigate = useNavigate();
    const isSysAdmin = user?.is_sysadmin === true;
    
    const [templates, setTemplates] = useState<CertificateTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [pdfLoadingId, setPdfLoadingId] = useState<string | null>(null);
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
    const [tenantOptions, setTenantOptions] = useState<Option[]>([]);

    useEffect(() => {
        const tenantFilter = selectedTenantIds.length > 0 ? selectedTenantIds : undefined;
        fetchTemplates(tenantFilter);
    }, [selectedTenantIds]);

    useEffect(() => {
        if (isSysAdmin) {
            tenantService.list().then(data => {
                setTenants(data);
                setTenantOptions(data.map(t => ({ label: t.name, value: t.id })));
            }).catch(console.error);
        }
    }, [isSysAdmin]);

    const fetchTemplates = async (tenantIds?: string[]) => {
        try {
            setLoading(true);
            const data = await certificatesApi.listTemplates(tenantIds);
            setTemplates(data);
        } catch (error) {
            console.error('Failed to fetch templates:', error);
            toast.error('Failed to load certificate templates');
        } finally {
            setLoading(false);
        }
    };

    const handleToggleActive = async (template: CertificateTemplate) => {
        try {
            await certificatesApi.updateTemplate(template.id, { is_active: !template.is_active });
            toast.success(`Template ${!template.is_active ? 'activated' : 'deactivated'}`);
            fetchTemplates();
        } catch (e) {
            toast.error(getApiError(e, 'Failed to update status'));
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Are you sure you want to delete this template?')) return;
        try {
            await certificatesApi.deleteTemplate(id);
            toast.success('Template deleted');
            fetchTemplates();
        } catch (e) {
            toast.error(getApiError(e, 'Failed to delete template'));
        }
    };

    const handlePreviewPdf = async (id: string) => {
        setPdfLoadingId(id);
        try {
            await certificatesApi.previewTemplatePdf(id);
        } catch {
            toast.error('Failed to generate PDF preview');
        } finally {
            setPdfLoadingId(null);
        }
    };

    const getTenantName = (tenantId: string) => {
        if (!tenantId) return 'N/A';
        const t = tenants.find(t => t.id === tenantId);
        return t ? t.name : tenantId.substring(0, 8) + '...';
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                            <ShieldCheck className="w-6 h-6 text-violet-600 dark:text-violet-400" />
                        </div>
                        Certificate Templates
                    </h1>
                    <p className="text-muted-foreground mt-1">Manage HTML templates for automatically issued certificates.</p>
                </div>
                <Button onClick={() => navigate('/admin/certificate-templates/new')} className="gap-2">
                    <Plus className="w-4 h-4" />
                    New Template
                </Button>
            </div>

            {isSysAdmin && (
                <div className="flex items-center gap-4 bg-muted/30 p-4 rounded-lg border border-dashed">
                    <span className="text-sm font-medium text-muted-foreground whitespace-nowrap flex items-center gap-1">
                        Filter by Tenant:
                    </span>
                    <div className="w-full max-w-sm">
                        <MultiSelect
                            options={tenantOptions}
                            selected={selectedTenantIds}
                            onChange={setSelectedTenantIds}
                            placeholder="All Tenants"
                        />
                    </div>
                    {selectedTenantIds.length > 0 && (
                        <Button 
                            variant="ghost" 
                            size="sm" 
                            onClick={() => setSelectedTenantIds([])}
                            className="h-8 text-xs underline underline-offset-4"
                        >
                            Reset
                        </Button>
                    )}
                </div>
            )}

            <div className="bg-card rounded-lg border shadow-sm overflow-hidden text-card-foreground">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-[50px] pl-4"></TableHead>
                            <TableHead>Name</TableHead>
                            {isSysAdmin && <TableHead>Tenant</TableHead>}
                            <TableHead>Status</TableHead>
                            <TableHead>Created At</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <TableCell colSpan={isSysAdmin ? 5 : 4} className="py-10">
                                    <div className="flex items-center justify-center gap-2 text-muted-foreground">
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        <span className="text-sm">Loading templates…</span>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ) : templates.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={isSysAdmin ? 5 : 4} className="text-center py-10 text-muted-foreground">No templates found. Create one to get started.</TableCell>
                            </TableRow>
                        ) : (
                            templates.map((template) => {
                                const isProtected = template.is_default || template.is_in_use;
                                return (
                                    <TableRow key={template.id}>
                                        <TableCell className="pl-4 w-[50px]">
                                            <div className="flex items-center gap-1">
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8"
                                                    disabled={pdfLoadingId === template.id}
                                                    onClick={() => handlePreviewPdf(template.id)}
                                                    title="Preview PDF"
                                                >
                                                    {pdfLoadingId === template.id
                                                        ? <Loader2 className="h-4 w-4 animate-spin" />
                                                        : <Eye className="h-4 w-4" />
                                                    }
                                                </Button>
                                                <DropdownMenu>
                                                    <DropdownMenuTrigger asChild>
                                                        <Button variant="ghost" size="icon" className="h-8 w-8">
                                                            <MoreVertical className="w-4 h-4" />
                                                        </Button>
                                                    </DropdownMenuTrigger>
                                                    <DropdownMenuContent align="end">
                                                        <DropdownMenuItem onClick={() => navigate(`/admin/certificate-templates/${template.id}`)}>
                                                            <Edit className="w-4 h-4 mr-2" /> Edit
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            onClick={() => handleToggleActive(template)}
                                                            disabled={isProtected && template.is_active}
                                                            className={isProtected && template.is_active ? 'opacity-40 cursor-not-allowed' : ''}
                                                        >
                                                            {template.is_active
                                                                ? <><ToggleLeft className="w-4 h-4 mr-2" /> Deactivate</>
                                                                : <><ToggleRight className="w-4 h-4 mr-2 text-primary" /> Activate</>
                                                            }
                                                        </DropdownMenuItem>
                                                        <DropdownMenuItem
                                                            onClick={() => handleDelete(template.id)}
                                                            disabled={isProtected}
                                                            className={isProtected ? 'opacity-40 cursor-not-allowed' : 'text-destructive'}
                                                        >
                                                            <Trash2 className="w-4 h-4 mr-2" /> Delete
                                                        </DropdownMenuItem>
                                                    </DropdownMenuContent>
                                                </DropdownMenu>
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium">{template.name}</span>
                                                {template.is_default && (
                                                    <Badge variant="outline" className="gap-1 text-[10px] px-1.5 py-0 border-primary/30 text-primary">
                                                        <ShieldCheck className="w-2.5 h-2.5" /> Default
                                                    </Badge>
                                                )}
                                                {template.is_in_use && !template.is_default && (
                                                    <Badge variant="outline" className="text-[10px] px-1.5 py-0 border-muted-foreground/30 text-muted-foreground">
                                                        In use
                                                    </Badge>
                                                )}
                                            </div>
                                        </TableCell>
                                        {isSysAdmin && <TableCell className="text-muted-foreground">{getTenantName(template.tenant_id)}</TableCell>}
                                        <TableCell>
                                            <Badge variant={template.is_active ? "outline" : "secondary"} className="gap-1 bg-background">
                                                {template.is_active ? (
                                                    <CheckCircle className="w-3 h-3 text-primary fill-primary/10" />
                                                ) : (
                                                    <XCircle className="w-3 h-3 text-muted-foreground" />
                                                )}
                                                {template.is_active ? "Active" : "Inactive"}
                                            </Badge>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">{new Date(template.created_at).toLocaleDateString()}</TableCell>
                                    </TableRow>
                                );
                            })
                        )}
                    </TableBody>
                </Table>
            </div>
        </div>
    );
};

