import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Award, Download, Eye, Calendar, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { 
    Card, 
    CardContent, 
    CardFooter, 
    CardHeader, 
    CardTitle 
} from '../components/ui/card';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from '../components/ui/dialog';
import { certificatesApi } from '../api/certificates';
import type { Certificate } from '../api/certificates';
import { toast } from 'sonner';
import { Badge } from '../components/ui/badge';

export const LearnerCertificates: React.FC = () => {
    const navigate = useNavigate();
    const [certificates, setCertificates] = useState<Certificate[]>([]);
    const [loading, setLoading] = useState(true);
    const [previewContent, setPreviewContent] = useState('');
    const [isPreviewOpen, setIsPreviewOpen] = useState(false);
    const [selectedCertId, setSelectedCertId] = useState<string | null>(null);

    useEffect(() => {
        fetchCertificates();
    }, []);

    const fetchCertificates = async () => {
        try {
            setLoading(true);
            const data = await certificatesApi.listMyCertificates();
            setCertificates(data);
        } catch (error) {
            console.error('Failed to fetch certificates:', error);
            toast.error('Failed to load certificates');
        } finally {
            setLoading(false);
        }
    };

    const handlePreview = async (id: string) => {
        try {
            setSelectedCertId(id);
            const certView = await certificatesApi.getCertificateView(id);
            setPreviewContent(certView.rendered_html || '<h1>Certificate</h1><p>Content not available</p>');
            setIsPreviewOpen(true);
        } catch {
            toast.error('Failed to load preview');
        }
    };

    const handleDownload = async (id: string, format: 'pdf' | 'html' = 'pdf') => {
        try {
            await certificatesApi.downloadCertificate(id, format);
        } catch (error) {
            console.error('Download error:', error);
            toast.error('Download failed');
        }
    };

    const location = useLocation();
    const basePath = location.pathname.startsWith('/manage') ? '/manage' : '/dashboard';

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <Award className="w-6 h-6 text-primary" />
                    </div>
                    My Certificates
                </h1>
                <p className="text-muted-foreground mt-1">View and download your earned certificates for completed trainings.</p>
            </div>

            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3].map((i) => (
                        <Card key={i} className="animate-pulse">
                            <CardHeader className="bg-muted h-32"></CardHeader>
                            <CardContent className="h-24"></CardContent>
                        </Card>
                    ))}
                </div>
            ) : certificates.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-20 bg-muted/30 rounded-xl border border-dashed text-center">
                    <Award className="w-16 h-16 text-muted-foreground mb-4 opacity-20" />
                    <h3 className="text-xl font-semibold mb-2">No certificates yet</h3>
                    <p className="text-muted-foreground max-w-sm">Complete courses that offer certificates to see them listed here.</p>
                    <Button variant="outline" className="mt-6" onClick={() => navigate(`${basePath}/my-courses`)}>
                        Browse Courses
                    </Button>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {certificates.map((cert) => (
                        <Card key={cert.id} className="group hover:shadow-lg transition-all duration-300 border-primary/10 hover:border-primary/30">
                            <CardHeader className="relative overflow-hidden p-0 rounded-t-xl h-40 bg-primary/5 flex items-center justify-center">
                                <Award className="w-20 h-20 text-primary/20 group-hover:scale-110 transition-transform duration-500" />
                                <div className="absolute top-4 right-4 group-hover:opacity-100 transition-opacity">
                                    <Badge variant="secondary" className="bg-background/90 backdrop-blur shadow-sm border-primary/10 text-primary">
                                        Verified
                                    </Badge>
                                </div>
                            </CardHeader>
                            <CardContent className="pt-6">
                                <CardTitle className="line-clamp-1 mb-2 text-lg">{cert.training_title || 'Training Program'}</CardTitle>
                                <div className="space-y-2 text-sm text-muted-foreground">
                                    <div className="flex items-center gap-2">
                                        <Calendar className="w-4 h-4" />
                                        <span>Issued on {new Date(cert.issued_at).toLocaleDateString()}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <CheckCircle className="w-4 h-4 text-primary" />
                                        <span className="font-mono text-[10px] uppercase tracking-wider">{cert.certificate_number}</span>
                                    </div>
                                </div>
                            </CardContent>
                            <CardFooter className="pt-0 flex gap-2">
                                <Button className="flex-1 gap-2" variant="outline" size="sm" onClick={() => handlePreview(cert.id)}>
                                    <Eye className="w-4 h-4" /> View
                                </Button>
                                <Button className="flex-1 gap-2" size="sm" onClick={() => handleDownload(cert.id)}>
                                    <Download className="w-4 h-4" /> PDF
                                </Button>
                            </CardFooter>
                        </Card>
                    ))}
                </div>
            )}

            {/* Preview Viewport */}
            <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
                <DialogContent className="sm:max-w-[800px] h-[85vh] flex flex-col p-0 overflow-hidden">
                    <DialogHeader className="p-6 pb-2 border-b">
                        <DialogTitle className="flex items-center gap-2">
                            <Award className="w-5 h-5 text-primary" />
                            Certificate Preview
                        </DialogTitle>
                    </DialogHeader>
                    <div className="flex-1 bg-muted p-4 md:p-8 overflow-y-auto">
                        <div className="bg-white shadow-2xl mx-auto min-h-full w-full max-w-[650px] aspect-[1/1.4] overflow-hidden rounded-sm ring-1 ring-black/5">
                             <iframe 
                                title="Certificate Document"
                                srcDoc={previewContent}
                                className="w-full h-full border-none"
                            />
                        </div>
                    </div>
                    <DialogFooter className="p-4 border-t bg-card gap-2 sm:justify-between">
                        <div className="hidden sm:flex items-center text-xs text-muted-foreground gap-2">
                            <CheckCircle className="w-4 h-4 text-primary" />
                            Secure Digitally Verified Certificate
                        </div>
                        <div className="flex items-center gap-2 w-full sm:w-auto">
                            <Button variant="ghost" onClick={() => setIsPreviewOpen(false)}>Close</Button>
                            <Button className="gap-2" onClick={() => selectedCertId && handleDownload(selectedCertId)}>
                                <Download className="w-4 h-4" /> Download PDF
                            </Button>
                        </div>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
