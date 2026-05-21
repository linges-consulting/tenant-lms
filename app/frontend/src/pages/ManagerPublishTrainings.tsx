import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../components/ui/dialog';
import {
    Globe,
    EyeOff,
    Search,
    BookOpen,
    CheckCircle,
    Clock,
    Archive,
    FileText,
    ExternalLink,
    UserPlus,
    PlayCircle,
} from 'lucide-react';
import { managerTrainingsApi } from '../api/trainings';
import type { Training } from '../api/trainings';
import { PageLoader } from '../components/ui/PageLoader';
import { cn } from '../lib/utils';

type StatusFilter = 'all' | 'draft' | 'ready' | 'published' | 'archived';

const STATUS_FILTERS: { value: StatusFilter; label: string }[] = [
    { value: 'ready', label: 'Ready to Publish' },
    { value: 'all', label: 'All' },
    { value: 'draft', label: 'Draft' },
    { value: 'published', label: 'Published' },
    { value: 'archived', label: 'Archived' },
];

function lifecycleStatus(t: Training): 'draft' | 'ready' | 'published' | 'archived' {
    if (t.lifecycle_status) return t.lifecycle_status;
    if (t.is_archived) return 'archived';
    if (t.is_published) return 'published';
    if (t.is_ready) return 'ready';
    return 'draft';
}

function StatusBadge({ status }: { status: ReturnType<typeof lifecycleStatus> }) {
    const config = {
        draft: { label: 'Draft', icon: FileText, className: 'border-border text-muted-foreground bg-muted' },
        ready: { label: 'Ready', icon: CheckCircle, className: 'border-emerald-500/30 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10' },
        published: { label: 'Published', icon: Globe, className: 'border-primary/30 text-primary bg-primary/10' },
        archived: { label: 'Archived', icon: Archive, className: 'border-amber-500/30 text-amber-600 dark:text-amber-400 bg-amber-500/10' },
    }[status];
    const Icon = config.icon;
    return (
        <Badge variant="outline" className={cn('gap-1 text-xs', config.className)}>
            <Icon className="h-3 w-3" />
            {config.label}
        </Badge>
    );
}

export const ManagerPublishTrainings: React.FC = () => {
    const navigate = useNavigate();
    const [trainings, setTrainings] = useState<Training[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState<StatusFilter>('ready');
    const [actionInProgress, setActionInProgress] = useState<string | null>(null);
    const [previewTraining, setPreviewTraining] = useState<Training | null>(null);

    useEffect(() => {
        const fetchTrainings = async () => {
            setIsLoading(true);
            try {
                const data = await managerTrainingsApi.getManagerTrainings();
                setTrainings(data);
            } catch (error) {
                console.error('Failed to fetch trainings', error);
            } finally {
                setIsLoading(false);
            }
        };
        fetchTrainings();
    }, []);

    const handlePublish = async (training: Training) => {
        setActionInProgress(training.id);
        try {
            const updated = await managerTrainingsApi.publishTraining(training.id);
            setTrainings(prev => prev.map(t => t.id === training.id ? { ...t, ...updated } : t));
        } catch (error) {
            console.error('Failed to publish training', error);
        } finally {
            setActionInProgress(null);
        }
    };

    const handleUnpublish = async (training: Training) => {
        setActionInProgress(training.id);
        try {
            const updated = await managerTrainingsApi.unpublishTraining(training.id);
            setTrainings(prev => prev.map(t => t.id === training.id ? { ...t, ...updated } : t));
        } catch (error) {
            console.error('Failed to unpublish training', error);
        } finally {
            setActionInProgress(null);
        }
    };

    const filtered = trainings.filter(t => {
        const status = lifecycleStatus(t);
        const matchesStatus = statusFilter === 'all' || status === statusFilter;
        const matchesSearch =
            t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (t.category ?? '').toLowerCase().includes(searchQuery.toLowerCase()) ||
            (t.creator_name ?? '').toLowerCase().includes(searchQuery.toLowerCase());
        return matchesStatus && matchesSearch;
    });

    const counts: Record<StatusFilter, number> = {
        all: trainings.length,
        draft: trainings.filter(t => lifecycleStatus(t) === 'draft').length,
        ready: trainings.filter(t => lifecycleStatus(t) === 'ready').length,
        published: trainings.filter(t => lifecycleStatus(t) === 'published').length,
        archived: trainings.filter(t => lifecycleStatus(t) === 'archived').length,
    };

    return (
        <>
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                        <Globe className="w-6 h-6 text-primary" />
                    </div>
                    Publish Trainings
                </h1>
                <p className="text-muted-foreground mt-1">
                    Review and publish trainings that are ready for learners.
                </p>
            </div>

            <Card>
                <CardContent className="pt-5 space-y-4">
                    {/* Filter tabs */}
                    <div className="flex flex-wrap gap-1.5">
                        {STATUS_FILTERS.map(f => (
                            <button
                                key={f.value}
                                onClick={() => setStatusFilter(f.value)}
                                className={cn(
                                    'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                                    statusFilter === f.value
                                        ? 'bg-primary text-primary-foreground'
                                        : 'bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                                )}
                            >
                                {f.label}
                                <span className={cn(
                                    'rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none',
                                    statusFilter === f.value ? 'bg-primary-foreground/20' : 'bg-background',
                                )}>
                                    {counts[f.value]}
                                </span>
                            </button>
                        ))}
                    </div>

                    {/* Search */}
                    <div className="relative max-w-xs">
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
                        <input
                            type="text"
                            placeholder="Search trainings…"
                            value={searchQuery}
                            onChange={e => setSearchQuery(e.target.value)}
                            className="w-full h-8 rounded-md border border-input bg-background pl-8 pr-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                        />
                    </div>

                    {/* Table */}
                    {isLoading ? (
                        <PageLoader label="Loading trainings…" />
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="pl-4 w-[160px]">Actions</TableHead>
                                    <TableHead>Training</TableHead>
                                    <TableHead>Category</TableHead>
                                    <TableHead>Creator</TableHead>
                                    <TableHead>Status</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filtered.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5} className="py-10 text-center">
                                            <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                                <BookOpen className="h-8 w-8 opacity-40" />
                                                <p className="text-sm">
                                                    {statusFilter === 'ready'
                                                        ? 'No trainings are ready to publish yet.'
                                                        : 'No trainings match your search.'}
                                                </p>
                                                {statusFilter === 'ready' && (
                                                    <p className="text-xs">Training creators need to mark their content as ready first.</p>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    filtered.map(training => {
                                        const status = lifecycleStatus(training);
                                        const isActing = actionInProgress === training.id;
                                        return (
                                            <TableRow key={training.id}>
                                                <TableCell className="pl-4">
                                                    <div className="flex items-center gap-2">
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-7 px-2 text-muted-foreground"
                                                            onClick={() => navigate(`/manage/publish/${training.id}/assignments`)}
                                                            title="Manage assignments"
                                                        >
                                                            <UserPlus className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="h-7 px-2 text-muted-foreground"
                                                            onClick={() => setPreviewTraining(training)}
                                                            title="Preview training"
                                                        >
                                                            <ExternalLink className="h-3.5 w-3.5" />
                                                        </Button>
                                                        {status === 'published' ? (
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                disabled={isActing}
                                                                onClick={() => handleUnpublish(training)}
                                                                className="h-7 text-xs text-muted-foreground hover:text-foreground border-border"
                                                            >
                                                                <EyeOff className="h-3.5 w-3.5 mr-1" />
                                                                {isActing ? 'Updating…' : 'Unpublish'}
                                                            </Button>
                                                        ) : status === 'ready' ? (
                                                            <Button
                                                                size="sm"
                                                                disabled={isActing}
                                                                onClick={() => handlePublish(training)}
                                                                className="h-7 text-xs"
                                                            >
                                                                <Globe className="h-3.5 w-3.5 mr-1" />
                                                                {isActing ? 'Publishing…' : 'Publish'}
                                                            </Button>
                                                        ) : (
                                                            <span className="text-xs text-muted-foreground px-2">
                                                                {status === 'archived' ? 'Archived' : 'Not ready'}
                                                            </span>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2">
                                                        <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
                                                            <BookOpen className="w-3.5 h-3.5 text-primary" />
                                                        </div>
                                                        <span className="font-medium text-sm">{training.title}</span>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <span className="text-sm text-muted-foreground capitalize">
                                                        {training.category ?? '—'}
                                                    </span>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-1.5">
                                                        <Clock className="h-3 w-3 text-muted-foreground" />
                                                        <span className="text-sm text-muted-foreground">
                                                            {training.creator_name ?? '—'}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <StatusBadge status={status} />
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>

        {/* Training preview mode picker */}
        <Dialog open={!!previewTraining} onOpenChange={(open) => { if (!open) setPreviewTraining(null); }}>
            <DialogContent className="max-w-sm">
                <DialogHeader>
                    <DialogTitle>Preview Training</DialogTitle>
                    <DialogDescription className="line-clamp-1">{previewTraining?.title}</DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-3 pt-2">
                    <button
                        onClick={() => { navigate(`/manage/learn/${previewTraining?.id}?preview=true&mode=content`); setPreviewTraining(null); }}
                        className="flex flex-col items-center gap-3 p-5 rounded-xl border border-border bg-muted/30 hover:bg-muted/60 hover:border-primary/40 transition-all text-left group"
                    >
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                            <BookOpen className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <p className="font-semibold text-sm text-foreground">View Content</p>
                            <p className="text-xs text-muted-foreground mt-0.5 leading-snug">Browse all chapters with answers revealed</p>
                        </div>
                    </button>
                    <button
                        onClick={() => { navigate(`/manage/learn/${previewTraining?.id}?preview=true&mode=simulate`); setPreviewTraining(null); }}
                        className="flex flex-col items-center gap-3 p-5 rounded-xl border border-border bg-muted/30 hover:bg-muted/60 hover:border-primary/40 transition-all text-left group"
                    >
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                            <PlayCircle className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <p className="font-semibold text-sm text-foreground">Simulate Training</p>
                            <p className="text-xs text-muted-foreground mt-0.5 leading-snug">Experience training as a learner would</p>
                        </div>
                    </button>
                </div>
            </DialogContent>
        </Dialog>
        </>
    );
};
