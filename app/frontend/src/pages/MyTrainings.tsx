import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
    BookOpen,
    CheckCircle,
    Award,
    Clock,
    Loader2,
    Play,
    ChevronRight,
    GraduationCap,
} from 'lucide-react';
import { trainingsApi } from '../api/trainings';
import { certificatesApi } from '../api/certificates';
import type { Training, Certificate } from '../api/trainings';
import { useAuth } from '../contexts/auth-context';

function formatDueCountdown(expiresAt: string): { label: string; isPast: boolean } {
    const now = Date.now();
    const due = new Date(expiresAt).getTime();
    const diffMs = due - now;
    if (diffMs <= 0) return { label: 'Past Due', isPast: true };
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    if (diffHours < 24) return { label: `${diffHours}h left`, isPast: false };
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    return { label: `${diffDays}d left`, isPast: false };
}

const PRESET_GRADIENTS: Record<string, string> = {
    ocean:  'linear-gradient(135deg, #3b82f6 0%, #4338ca 100%)',
    sunset: 'linear-gradient(135deg, #f97316 0%, #e11d48 100%)',
    forest: 'linear-gradient(135deg, #10b981 0%, #0369a1 100%)',
    ember:  'linear-gradient(135deg, #f59e0b 0%, #dc2626 100%)',
};

interface MyTrainingsProps {
    basePath?: string; // e.g., "/dashboard" or "/manage"
}

type Filter = 'active' | 'completed' | 'expired' | 'all';

const filterLabels: Record<Filter, string> = {
    active: 'Active',
    completed: 'Completed',
    expired: 'Overdue',
    all: 'All',
};

const CategoryColors: Record<string, string> = {
    compliance: 'bg-destructive/10 text-destructive border-destructive/20',
    safety: 'bg-muted text-foreground border-border',
    leadership: 'bg-primary/10 text-primary border-primary/20',
    technical: 'bg-secondary text-secondary-foreground border-border',
    onboarding: 'bg-muted text-muted-foreground border-border',
};

export const MyTrainings: React.FC<MyTrainingsProps> = ({ basePath = "/dashboard" }) => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const [trainings, setTrainings] = useState<Training[]>([]);
    const [certificates, setCertificates] = useState<Certificate[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [activeFilter, setActiveFilter] = useState<Filter>('active');

    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true);
            try {
                const [trainingsData, certsData] = await Promise.all([
                    trainingsApi.getPublishedTrainings(),
                    trainingsApi.getCertificates(),
                ]);
                setTrainings(trainingsData);
                setCertificates(certsData);
            } catch (error) {
                console.error('Failed to load courses', error);
            } finally {
                setIsLoading(false);
            }
        };
        loadData();
    }, []);

    const completedIds = new Set(certificates.map((c) => c.training_id));
    const activeTrainings = trainings.filter((t) => t.status === 'not_started' || t.status === 'in_progress');
    const completedTrainings = trainings.filter((t) => t.status === 'completed');
    const expiredTrainings = trainings.filter((t) => t.status === 'expired');

    const filterCounts: Record<Filter, number> = {
        active: activeTrainings.length,
        completed: completedTrainings.length,
        expired: expiredTrainings.length,
        all: trainings.length,
    };

    const displayedTrainings = (() => {
        if (activeFilter === 'active') return activeTrainings;
        if (activeFilter === 'completed') return completedTrainings;
        if (activeFilter === 'expired') return expiredTrainings;
        return trainings;
    })();

    const handleCourseClick = (courseId: string) => {
        navigate(`${basePath}/learn/${courseId}`);
    };

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <GraduationCap className="w-6 h-6 text-primary" />
                        </div>
                        My Trainings
                    </h1>
                    <p className="text-muted-foreground mt-2">
                        Trainings assigned to you, {user?.full_name?.split(' ')[0] || 'there'}.
                    </p>
                </div>
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-2">
                {(Object.keys(filterLabels) as Filter[]).map((filter) => {
                    const isActive = activeFilter === filter;
                    return (
                        <button
                            key={filter}
                            onClick={() => setActiveFilter(filter)}
                            className={cn(
                                'inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-all border',
                                isActive
                                    ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                                    : 'bg-background text-muted-foreground border-border hover:bg-muted hover:text-foreground'
                            )}
                        >
                            {filterLabels[filter]}
                            {!isLoading && (
                                <span className={cn(
                                    'text-xs px-1.5 py-0.5 rounded-full font-semibold min-w-[1.25rem] text-center',
                                    isActive ? 'bg-primary-foreground/20 text-primary-foreground' : 'bg-muted text-muted-foreground'
                                )}>
                                    {filterCounts[filter]}
                                </span>
                            )}
                        </button>
                    );
                })}
            </div>

            {/* Course Grid */}
            {isLoading ? (
                <div className="flex justify-center py-16">
                    <Loader2 className="w-8 h-8 animate-spin text-primary" />
                </div>
            ) : displayedTrainings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center border rounded-xl bg-muted/10">
                    <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                        <BookOpen className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h3 className="font-semibold text-foreground mb-1">No courses here</h3>
                    <p className="text-sm text-muted-foreground max-w-xs">
                        {activeFilter === 'completed'
                            ? "You haven't completed any trainings yet. Keep going!"
                            : activeFilter === 'expired'
                                ? 'No overdue trainings.'
                                : activeFilter === 'all'
                                    ? 'No trainings assigned yet.'
                                    : 'No active trainings. Check the Completed tab to review past work.'}
                    </p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                    {displayedTrainings.map((course) => {
                        const isCompleted = completedIds.has(course.id);
                        const cert = certificates.find((c) => c.training_id === course.id);
                        const categoryColor =
                            CategoryColors[course.category?.toLowerCase() ?? ''] ||
                            'bg-muted text-muted-foreground border-border';

                        return (
                            <Card
                                key={course.id}
                                className="overflow-hidden flex flex-col group cursor-pointer border-border/50 hover:border-primary/40 hover:shadow-md transition-all duration-200"
                                onClick={() => handleCourseClick(course.id)}
                            >
                                {/* Thumbnail area */}
                                <div className="relative h-36 w-full overflow-hidden bg-gradient-to-br from-secondary to-background">
                                    {course.thumbnail?.startsWith('/storage/banners/') ? (
                                        <img
                                            src={course.thumbnail}
                                            className="absolute inset-0 w-full h-full object-cover"
                                            alt=""
                                        />
                                    ) : course.thumbnail?.startsWith('preset:') ? (
                                        <div
                                            className="absolute inset-0"
                                            style={{ background: PRESET_GRADIENTS[course.thumbnail.replace('preset:', '')] ?? 'linear-gradient(135deg, #3b82f6 0%, #4338ca 100%)' }}
                                        />
                                    ) : (
                                        <div
                                            className="absolute inset-0 opacity-30"
                                            style={{
                                                backgroundImage:
                                                    'radial-gradient(circle at 20% 50%, var(--primary) 0%, transparent 50%), radial-gradient(circle at 80% 20%, var(--primary) 0%, transparent 50%)',
                                            }}
                                        />
                                    )}
                                    {isCompleted && (
                                        <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                                            <div className="w-12 h-12 rounded-full bg-primary/10 border-2 border-primary/30 flex items-center justify-center">
                                                <CheckCircle className="w-6 h-6 text-primary" />
                                            </div>
                                        </div>
                                    )}
                                    {!isCompleted && (
                                        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                            <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-sm border border-white/20 flex items-center justify-center">
                                                <Play className="w-5 h-5 text-white ml-1" />
                                            </div>
                                        </div>
                                    )}
                                    <div className="absolute top-3 left-3 flex gap-2 flex-wrap">
                                        {course.category && (
                                            <span className={cn('text-[10px] font-semibold px-2 py-0.5 rounded-full border', categoryColor)}>
                                                {course.category}
                                            </span>
                                        )}
                                        {course.requires_certificate && (
                                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full border bg-muted text-foreground border-border">
                                                Certificate
                                            </span>
                                        )}
                                    </div>
                                    {course.status === 'completed' && (
                                        <Badge className="absolute top-3 right-3 bg-primary text-primary-foreground border-0 text-xs shadow-sm">
                                            Completed
                                        </Badge>
                                    )}
                                    {course.status === 'expired' && (
                                        <Badge className="absolute top-3 right-3 bg-destructive text-destructive-foreground border-0 text-xs shadow-sm">
                                            Overdue
                                        </Badge>
                                    )}
                                    {(course.status === 'in_progress' || course.status === 'not_started') && (
                                        <Badge className={cn('absolute top-3 right-3 text-primary-foreground border-0 text-xs shadow-sm', course.status === 'not_started' ? 'bg-secondary text-secondary-foreground' : 'bg-primary')}>
                                            {course.status === 'not_started' ? 'Not Started' : `${course.progress_percentage}% Done`}
                                        </Badge>
                                    )}
                                </div>

                                {/* Content */}
                                <CardContent className="p-5 flex-1 flex flex-col">
                                    <h3 className="font-bold text-base mb-1.5 line-clamp-2 group-hover:text-primary transition-colors">
                                        {course.title}
                                    </h3>
                                    {course.description && (
                                        <p className="text-xs text-muted-foreground line-clamp-2 mb-3 leading-relaxed">
                                            {course.description}
                                        </p>
                                    )}

                                    {/* Progress Bar */}
                                    {course.status !== 'completed' && (
                                        <div className="mb-3">
                                            <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
                                                <span>Progress</span>
                                                <span>{course.progress_percentage}%</span>
                                            </div>
                                            <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                                                <div
                                                    className={cn('h-full transition-all duration-500', course.status === 'expired' ? 'bg-destructive' : 'bg-primary')}
                                                    style={{ width: `${course.progress_percentage}%` }}
                                                />
                                            </div>
                                        </div>
                                    )}

                                    {/* Due date (per-user assignment deadline) */}
                                    {course.due_date && course.status !== 'completed' && (() => {
                                        const { label, isPast } = formatDueCountdown(course.due_date);
                                        return (
                                            <p className={cn(
                                                'text-[10px] mb-3 flex items-center gap-1',
                                                isPast ? 'text-destructive font-semibold' : 'text-muted-foreground'
                                            )}>
                                                <Clock className="w-3 h-3 shrink-0" />
                                                {isPast
                                                    ? `Past Due · ${new Date(course.due_date).toLocaleDateString()}`
                                                    : `Due ${new Date(course.due_date).toLocaleDateString()} · ${label}`}
                                            </p>
                                        );
                                    })()}

                                    <div className="mt-auto pt-3 flex items-center justify-between">
                                        {course.status === 'completed' ? (
                                            <div className="flex items-center gap-2 w-full">
                                                {cert?.certificate_id ? (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="text-xs border-border text-foreground hover:bg-muted flex-1"
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            certificatesApi.viewCertificatePdf(cert.certificate_id!);
                                                        }}
                                                    >
                                                        <Award className="w-3.5 h-3.5 mr-1.5" />
                                                        View Certificate
                                                    </Button>
                                                ) : (
                                                    <span className="text-xs text-primary font-medium flex items-center gap-1 flex-1">
                                                        <CheckCircle className="w-3.5 h-3.5" />
                                                        Completed
                                                    </span>
                                                )}
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="text-xs text-muted-foreground"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleCourseClick(course.id);
                                                    }}
                                                >
                                                    Review
                                                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                                                </Button>
                                            </div>
                                        ) : (
                                            <Button
                                                size="sm"
                                                className="w-full"
                                                disabled={course.status === 'expired'}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleCourseClick(course.id);
                                                }}
                                            >
                                                {course.status === 'expired' ? (
                                                    <>
                                                        <Clock className="w-3.5 h-3.5 mr-2" />
                                                        Overdue
                                                    </>
                                                ) : (
                                                    <>
                                                        <Play className="w-3.5 h-3.5 mr-2" />
                                                        {course.status === 'in_progress' ? 'Continue' : 'Start'}
                                                    </>
                                                )}
                                            </Button>
                                        )}
                                    </div>
                                </CardContent>
                            </Card>
                        );
                    })}
                </div>
            )}

            {/* Certificates earned section */}
            {!isLoading && certificates.filter((c) => c.certificate_id).length > 0 && (
                <div className="space-y-4 pt-6">
                    <h2 className="text-xl font-bold tracking-tight flex items-center gap-2">
                        <Award className="w-5 h-5 text-foreground" />
                        Recent Certificates
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {certificates
                            .filter((c) => c.certificate_id)
                            .map((cert) => (
                                <Card
                                    key={cert.id}
                                    className="border-amber-200/60 bg-gradient-to-r from-amber-50/40 to-yellow-50/30 shadow-sm cursor-pointer hover:shadow-md hover:border-amber-300 transition-all"
                                    onClick={() => certificatesApi.viewCertificatePdf(cert.certificate_id!)}
                                >
                                    <CardContent className="p-4 flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center shrink-0">
                                            <Award className="w-5 h-5 text-foreground" />
                                        </div>
                                        <div className="overflow-hidden">
                                            <p className="font-semibold text-sm text-foreground truncate">
                                                {cert.training_title}
                                            </p>
                                            <p className="text-xs text-muted-foreground mt-0.5">
                                                Earned{' '}
                                                {cert.completed_at
                                                    ? new Date(cert.completed_at).toLocaleDateString()
                                                    : 'Recently'}
                                            </p>
                                        </div>
                                        <ChevronRight className="w-4 h-4 text-muted-foreground ml-auto shrink-0" />
                                    </CardContent>
                                </Card>
                            ))}
                    </div>
                </div>
            )}
        </div>
    );
};
