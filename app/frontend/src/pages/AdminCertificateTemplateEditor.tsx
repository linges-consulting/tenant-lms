import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    ArrowLeft,
    Save,
    Eye,
    Loader2,
    Code
} from 'lucide-react';
import { cn } from '../lib/utils';
import { PageLoader } from '../components/ui/PageLoader';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { 
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from '../components/ui/select';
import { certificatesApi } from '../api/certificates';
import { tenantService } from '../api/tenants';
import type { Tenant } from '../api/auth';
import { useAuth } from '../contexts/auth-context';
import { toast } from 'sonner';

export const AdminCertificateTemplateEditor: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { user } = useAuth();
    const isSysAdmin = user?.is_sysadmin === true;

    const [loading, setLoading] = useState(id ? true : false);
    const [saving, setSaving] = useState(false);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [pdfLoading, setPdfLoading] = useState(false);
    
    const [name, setName] = useState('');
    const [htmlContent, setHtmlContent] = useState('');
    const [isActive, setIsActive] = useState(true);
    const [targetTenantId, setTargetTenantId] = useState('');
    const [tenantName, setTenantName] = useState('');
    
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [previewHtml, setPreviewHtml] = useState('');
    const [errors, setErrors] = useState<{ [key: string]: string }>({});

    useEffect(() => {
        if (id) {
            fetchTemplate();
        } else {
            // Default content for new templates
            setHtmlContent('<div style="font-family: sans-serif; text-align: center; border: 10px solid #ccc; padding: 50px; background: white;">\n  <h1 style="font-size: 48px; color: #333;">Certificate of Completion</h1>\n  <p style="font-size: 24px;">This is to certify that</p>\n  <h2 style="font-size: 36px; color: #000; border-bottom: 2px solid #000; display: inline-block; padding: 0 20px;">{{user_name}}</h2>\n  <p style="font-size: 24px;">has successfully completed the course</p>\n  <h3 style="font-size: 28px; color: #1e40af;">{{training_title}}</h3>\n  <div style="margin-top: 50px; display: flex; justify-content: space-between;">\n    <div>\n      <p style="border-top: 1px solid #000; width: 200px; margin: 0 auto;">Date: {{completion_date}}</p>\n    </div>\n    <div>\n      <p style="border-top: 1px solid #000; width: 200px; margin: 0 auto;">ID: {{certificate_number}}</p>\n    </div>\n  </div>\n</div>');
        }

        if (isSysAdmin) {
            tenantService.list().then(setTenants).catch(console.error);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id, isSysAdmin]);

    const fetchTemplate = async () => {
        try {
            setLoading(true);
            const template = await certificatesApi.getTemplate(id!);
            setName(template.name);
            setHtmlContent(template.html_content);
            setIsActive(template.is_active);
            setTargetTenantId(template.tenant_id);
            
            // Set initial preview
            handlePreview(template.html_content);
        } catch (error) {
            console.error('Failed to fetch template:', error);
            toast.error('Failed to load template');
            navigate('/admin/certificate-templates');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isSysAdmin && tenants.length > 0 && targetTenantId) {
            const t = tenants.find(t => t.id === targetTenantId);
            if (t) setTenantName(t.name);
        }
    }, [isSysAdmin, tenants, targetTenantId]);

    const validate = () => {
        const newErrors: { [key: string]: string } = {};
        if (!name.trim()) newErrors.name = 'Name is required';
        if (name.length < 3) newErrors.name = 'Name must be at least 3 characters';
        if (!htmlContent.trim()) newErrors.html = 'HTML content is required';
        if (isSysAdmin && !id && !targetTenantId) newErrors.tenant = 'Target tenant is required';
        
        // Simple HTML validation
        if (htmlContent && !htmlContent.includes('{{')) {
            toast.warning('No variables (e.g., {{user_name}}) detected in the HTML content.');
        }

        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSave = async () => {
        if (!validate()) return;

        try {
            setSaving(true);
            if (id) {
                await certificatesApi.updateTemplate(id, {
                    name,
                    html_content: htmlContent,
                    is_active: isActive
                });
                toast.success('Template updated successfully');
            } else {
                await certificatesApi.createTemplate({
                    name,
                    html_content: htmlContent,
                    is_active: isActive,
                    ...(isSysAdmin && targetTenantId ? { target_tenant_id: targetTenantId } : {})
                });
                toast.success('Template created successfully');
            }
            navigate('/admin/certificate-templates');
        } catch (error) {
            console.error('Failed to save template:', error);
            toast.error('Failed to save certificate template');
        } finally {
            setSaving(false);
        }
    };

    const handlePreviewPdf = async () => {
        if (!id) return;
        setPdfLoading(true);
        try {
            await certificatesApi.previewTemplatePdf(id);
        } catch {
            toast.error('Failed to generate PDF preview');
        } finally {
            setPdfLoading(false);
        }
    };

    const handlePreview = async (currentHtml?: string) => {
        const htmlToPreview = currentHtml || htmlContent;
        if (!htmlToPreview.trim()) return;

        try {
            setPreviewLoading(true);
            const resp = await certificatesApi.previewTemplate(htmlToPreview, {
                user_name: 'John Doe',
                training_title: 'Introduction to Cloud Architecture',
                completion_date: new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }),
                certificate_number: 'CERT-DEMO-2024-X99'
            });
            setPreviewHtml(resp.rendered_html);
        } catch (error) {
            console.error('Preview failed:', error);
            toast.error('Failed to generate preview');
        } finally {
            setPreviewLoading(false);
        }
    };

    if (loading) {
        return <PageLoader label="Loading template data..." />;
    }

    return (
        <div className="flex flex-col h-[calc(100vh-120px)] space-y-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => navigate('/admin/certificate-templates')}>
                        <ArrowLeft className="w-5 h-5" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-foreground">
                            {id ? 'Edit Template' : 'Create New Template'}
                        </h1>
                        <p className="text-sm text-muted-foreground">
                            {id ? `Modifying template: ${name}` : 'Design a new certificate template using HTML'}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={() => navigate('/admin/certificate-templates')}>
                        Cancel
                    </Button>
                    {id && (
                        <Button
                            variant="outline"
                            onClick={handlePreviewPdf}
                            disabled={pdfLoading}
                            className="gap-2 border-primary/20 text-primary hover:bg-primary/5"
                        >
                            {pdfLoading
                                ? <Loader2 className="w-4 h-4 animate-spin" />
                                : <Eye className="w-4 h-4" />
                            }
                            Preview PDF
                        </Button>
                    )}
                    <Button onClick={handleSave} disabled={saving} className="gap-2">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Template
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
                {/* Editor Pane */}
                <div className="flex flex-col gap-4 min-h-0">
                    <Card className="flex flex-col flex-1 min-h-0 shadow-sm border-muted">
                        <CardHeader className="py-4">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Code className="w-4 h-4" />
                                Template Configuration
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4 flex-1 overflow-y-auto pr-4">
                            {isSysAdmin && !id && (
                                <div className="space-y-2">
                                    <Label htmlFor="tenant" className={errors.tenant ? "text-destructive" : ""}>
                                        Target Tenant <span className="text-destructive">*</span>
                                    </Label>
                                    <Select 
                                        value={targetTenantId} 
                                        onValueChange={setTargetTenantId}
                                    >
                                        <SelectTrigger id="tenant" className={errors.tenant ? "border-destructive" : ""}>
                                            <SelectValue placeholder="Select a tenant..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {tenants.map(t => (
                                                <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    {errors.tenant && <p className="text-xs text-destructive">{errors.tenant}</p>}
                                </div>
                            )}

                            {isSysAdmin && id && (
                                <div className="space-y-2">
                                    <Label>Tenant</Label>
                                    <Badge variant="outline" className="text-sm px-3 py-1 font-normal block w-fit">
                                        {tenantName || targetTenantId}
                                    </Badge>
                                </div>
                            )}

                            <div className="space-y-2">
                                <Label htmlFor="name" className={errors.name ? "text-destructive" : ""}>
                                    Template Name <span className="text-destructive">*</span>
                                </Label>
                                <Input 
                                    id="name"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    placeholder="e.g., Compliance Completion Certificate"
                                    className={errors.name ? "border-destructive" : ""}
                                />
                                {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
                            </div>

                            <div className="space-y-2 flex-1 flex flex-col min-h-0">
                                <div className="flex items-center justify-between">
                                    <Label htmlFor="html" className={errors.html ? "text-destructive" : ""}>
                                        HTML Content <span className="text-destructive">*</span>
                                    </Label>
                                    <Button 
                                        variant="ghost" 
                                        size="sm" 
                                        onClick={() => handlePreview()}
                                        className="h-7 text-xs gap-1"
                                    >
                                        <Eye className="w-3 h-3" />
                                        Update Preview
                                    </Button>
                                </div>
                                <Textarea 
                                    id="html"
                                    value={htmlContent}
                                    onChange={(e) => setHtmlContent(e.target.value)}
                                    className={cn('font-mono text-sm min-h-[300px] flex-1 resize-none', errors.html && 'border-destructive')}
                                    placeholder="<div style='...'>...</div>"
                                />
                                {errors.html && <p className="text-xs text-destructive">{errors.html}</p>}
                            </div>

                            <div className="flex items-center gap-2 pt-2">
                                <Switch 
                                    id="active" 
                                    checked={isActive}
                                    onCheckedChange={setIsActive}
                                />
                                <Label htmlFor="active" className="cursor-pointer">Active and available for courses</Label>
                            </div>

                            <div className="bg-muted/30 border border-muted-foreground/10 rounded-lg p-4">
                                <div className="flex items-center gap-2 mb-2">
                                    <Code className="h-4 w-4 text-primary" />
                                    <h4 className="text-sm font-semibold">Available Variables</h4>
                                </div>
                                <div className="text-xs space-y-1">
                                    <p className="text-muted-foreground mb-2">Insert these tags into your HTML for dynamic data:</p>
                                    <div className="flex flex-wrap gap-2">
                                        <Badge variant="secondary" className="font-mono text-[10px]">{"{{user_name}}"}</Badge>
                                        <Badge variant="secondary" className="font-mono text-[10px]">{"{{training_title}}"}</Badge>
                                        <Badge variant="secondary" className="font-mono text-[10px]">{"{{completion_date}}"}</Badge>
                                        <Badge variant="secondary" className="font-mono text-[10px]">{"{{certificate_number}}"}</Badge>
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Preview Pane */}
                <div className="flex flex-col min-h-0">
                    <Card className="flex flex-col flex-1 min-h-0 overflow-hidden shadow-sm border-muted">
                        <CardHeader className="py-4 border-b flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    <Eye className="w-4 h-4" />
                                    Live Preview
                                </CardTitle>
                                <CardDescription className="text-xs">Scaled view of certificate rendering</CardDescription>
                            </div>
                            {previewLoading && <Loader2 className="w-4 h-4 animate-spin text-primary" />}
                        </CardHeader>
                        <CardContent className="p-0 flex-1 bg-muted/20 relative">
                            {previewHtml ? (
                                <iframe 
                                    title="Certificate Preview"
                                    srcDoc={previewHtml}
                                    className="w-full h-full border-none"
                                />
                            ) : (
                                <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-8 text-center">
                                    <Eye className="w-10 h-10 mb-2 opacity-20" />
                                    <p className="text-sm">Click "Update Preview" or start typing to see the rendered certificate.</p>
                                </div>
                            )}
                        </CardContent>
                        <div className="p-4 border-t bg-muted/5 flex justify-between items-center text-xs text-muted-foreground">
                            <span>A4 Landscape Aspect Ratio</span>
                            <Button variant="ghost" size="sm" className="h-6 text-[10px]" onClick={() => handlePreview()}>
                                Re-render
                            </Button>
                        </div>
                    </Card>
                </div>
            </div>
        </div>
    );
};
