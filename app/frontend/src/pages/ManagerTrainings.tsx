import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import {
    BookOpen,
    Plus,
    Search,
    MoreVertical,
    Edit,
    CheckCircle,
    Clock,
    Loader2,
    FileText,
    LayoutGrid,
    List,
    Archive,
    Users,
    SendHorizonal,
    RotateCcw,
    Trash2,
} from 'lucide-react';
import { managerTrainingsApi } from '../api/trainings';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger
} from "../components/ui/dropdown-menu";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { ManageEditorsModal } from '../components/ManageEditorsModal';
import type { Training } from '../api/trainings';
import { useAuth } from '../contexts/auth-context';
import { toast } from 'sonner';

export const ManagerTrainings: React.FC = () => {
    const navigate = useNavigate();
    const { user, activeMembership } = useAuth();
    const [trainings, setTrainings] = useState<Training[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [viewMode, setViewMode] = useState<'grid' | 'table'>('table');
    const [filterMode, setFilterMode] = useState<'all' | 'my'>('all');

    // New Training Dialog State
    const [isNewTrainingDialogOpen, setIsNewTrainingDialogOpen] = useState(false);
    const [newTrainingTitle, setNewTrainingTitle] = useState('');
    const [newTrainingDescription, setNewTrainingDescription] = useState('');
    const [newTrainingTitleError, setNewTrainingTitleError] = useState('');

    // Discard confirmation (when closing dialog with unsaved content)
    const [isDiscardConfirmOpen, setIsDiscardConfirmOpen] = useState(false);

    // Archive Dialog State
    const [trainingToArchive, setTrainingToArchive] = useState<Training | null>(null);
    const [isArchiveDialogOpen, setIsArchiveDialogOpen] = useState(false);

    // Collaboration State
    const [trainingToManageEditors, setTrainingToManageEditors] = useState<Training | null>(null);
    const [isEditorsModalOpen, setIsEditorsModalOpen] = useState(false);

    const handleArchiveTraining = async () => {
        if (!trainingToArchive) return;
        try {
            await managerTrainingsApi.archiveTraining(trainingToArchive.id);
            setTrainings(prev => prev.map(t => t.id === trainingToArchive.id ? { ...t, is_archived: true } : t));
            setIsArchiveDialogOpen(false);
            setTrainingToArchive(null);
        } catch (error) {
            console.error('Failed to archive training', error);
            toast.error('Failed to archive training.');
        }
    };

    // Delete dialog state
    const [trainingToDelete, setTrainingToDelete] = useState<Training | null>(null);
    const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

    const handleDeleteTraining = async () => {
        if (!trainingToDelete) return;
        try {
            await managerTrainingsApi.deleteTraining(trainingToDelete.id);
            setTrainings(prev => prev.filter(t => t.id !== trainingToDelete.id));
            setIsDeleteDialogOpen(false);
            setTrainingToDelete(null);
        } catch (error) {
            console.error('Failed to delete training', error);
            toast.error('Failed to delete training.');
        }
    };

    const handleMarkReady = async (training: Training) => {
        try {
            const updated = await managerTrainingsApi.markReady(training.id);
            setTrainings(prev => prev.map(t => t.id === training.id ? { ...t, ...updated } : t));
        } catch (error: unknown) {
            const detail = (error as { message?: string })?.message;
            toast.error(detail || 'Failed to mark training as ready.');
        }
    };

    const handleSendToDraft = async (training: Training) => {
        try {
            const updated = await managerTrainingsApi.sendToDraft(training.id);
            setTrainings(prev => prev.map(t => t.id === training.id ? { ...t, ...updated } : t));
        } catch (error) {
            console.error('Failed to revert training to draft', error);
            toast.error('Failed to revert to draft.');
        }
    };

    const isCreator = activeMembership?.is_training_creator;
    const isManager = activeMembership?.is_business_manager;

    const [isCreating, setIsCreating] = useState(false);

    const hasNewTrainingContent = () => newTrainingTitle.trim() !== '' || newTrainingDescription.trim() !== '';

    const resetNewTrainingForm = () => {
        setNewTrainingTitle('');
        setNewTrainingDescription('');
        setNewTrainingTitleError('');
    };

    const handleOpenNewTrainingDialog = () => {
        resetNewTrainingForm();
        setIsNewTrainingDialogOpen(true);
    };

    const handleCloseNewTrainingDialog = () => {
        if (hasNewTrainingContent()) {
            setIsDiscardConfirmOpen(true);
        } else {
            setIsNewTrainingDialogOpen(false);
        }
    };

    const handleDiscardNewTraining = () => {
        setIsDiscardConfirmOpen(false);
        setIsNewTrainingDialogOpen(false);
        resetNewTrainingForm();
    };

    const fetchTrainings = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await managerTrainingsApi.getManagerTrainings();
            setTrainings(data);
        } catch (error) {
            console.error('Failed to fetch trainings', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTrainings();
    }, [fetchTrainings]);

    // Keep the active managed training in sync with the main list if it refreshes
    useEffect(() => {
        if (trainingToManageEditors) {
            const updated = trainings.find(t => t.id === trainingToManageEditors.id);
            if (updated) setTrainingToManageEditors(updated);
        }
    }, [trainings, trainingToManageEditors]);

    const handleSaveNewTraining = async () => {
        if (isCreating) return;
        if (!newTrainingTitle.trim()) {
            setNewTrainingTitleError('Training title is required.');
            return;
        }
        setNewTrainingTitleError('');
        setIsCreating(true);
        try {
            const newTraining = await managerTrainingsApi.createTraining({
                title: newTrainingTitle.trim(),
                category: 'general',
                description: newTrainingDescription.trim() || undefined,
                structure_type: 'flat',
                is_published: false,
                requires_certificate: false,
            });
            setIsNewTrainingDialogOpen(false);
            resetNewTrainingForm();
            navigate(`/manage/courses/${newTraining.id}`);
        } catch (error: unknown) {
            const status = (error as { status?: number })?.status;
            if (status === 409) {
                setNewTrainingTitleError('A training with this name already exists.');
            } else {
                toast.error('Failed to create training. Please try again.');
            }
        } finally {
            setIsCreating(false);
        }
    };

    const filteredTrainings = trainings.filter(t => {
        const matchesSearch = t.title.toLowerCase().includes(searchQuery.toLowerCase()) || t.category?.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesFilter = filterMode === 'all' || (filterMode === 'my' && t.created_by_id === user?.id);
        return matchesSearch && matchesFilter;
    });

    const publishedCount = trainings.filter(t => t.is_published).length;
    const draftCount = trainings.length - publishedCount;

    const canManageLifecycle = (training: Training) => {
        return user?.is_sysadmin || training.created_by_id === user?.id;
    };

    const isCollaboratorOnly = (training: Training) => {
        if (canManageLifecycle(training)) return false;
        return training.collaborators?.some(c => c.user_id === user?.id) ?? false;
    };

    const isDraft = (training: Training) => !training.is_ready && !training.is_published && !training.is_archived;

    const canEdit = (training: Training) => {
        const collab = isCollaboratorOnly(training);
        return isCreator && !training.is_published && !training.is_archived && (canManageLifecycle(training) || collab);
    };

    const canMarkReadyAction = (training: Training) =>
        isCreator && !isCollaboratorOnly(training) && isDraft(training) && canManageLifecycle(training);

    const canRevertAction = (training: Training) =>
        (isCreator && !isCollaboratorOnly(training) && canManageLifecycle(training)) || isManager;

    const canArchiveAction = (training: Training) =>
        isManager && !isCollaboratorOnly(training) && (training.is_ready || training.is_published) && !training.is_archived;

    const canDeleteAction = (training: Training) =>
        isCreator && !isCollaboratorOnly(training) && training.created_by_id === user?.id && isDraft(training);

    const hasDropdownActions = (training: Training) =>
        canEdit(training) || canMarkReadyAction(training) || (canRevertAction(training) && (training.is_ready || training.is_published)) ||
        canManageLifecycle(training) || canArchiveAction(training) || canDeleteAction(training);

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                            <BookOpen className="w-6 h-6 text-primary" />
                        </div>
                        Training Content
                    </h1>
                    <p className="text-muted-foreground mt-1">
                        Build and manage training courses for your organization.
                    </p>
                </div>
                {isCreator && (
                    <Button onClick={handleOpenNewTrainingDialog} disabled={isCreating} className="shadow-md h-11 px-6">
                        <Plus className="mr-2 h-5 w-5" /> Create Training
                    </Button>
                )}
            </div>

            {/* Metrics */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                <Card className="border-border/50 shadow-sm">
                    <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-muted-foreground">Total Trainings</p>
                                <p className="text-3xl font-bold mt-1">{isLoading ? '—' : trainings.length}</p>
                            </div>
                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                                <FileText className="w-6 h-6 text-primary" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm">
                    <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-muted-foreground">Published</p>
                                <p className="text-3xl font-bold mt-1 text-foreground">{isLoading ? '—' : publishedCount}</p>
                            </div>
                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                                <CheckCircle className="w-6 h-6 text-primary" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card className="border-border/50 shadow-sm">
                    <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm font-medium text-muted-foreground">Drafts</p>
                                <p className="text-3xl font-bold mt-1 text-muted-foreground">{isLoading ? '—' : draftCount}</p>
                            </div>
                            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                                <Clock className="w-6 h-6 text-muted-foreground" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Filters & View Toggle */}
            <div className="flex flex-col sm:row items-center justify-between gap-4">
                <div className="relative w-full sm:max-w-md">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                        className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                        placeholder="Search courses by title or category..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 bg-muted p-1 rounded-lg mr-2">
                        <Button
                            variant={filterMode === 'all' ? 'secondary' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setFilterMode('all')}
                        >
                            All Trainings
                        </Button>
                        <Button
                            variant={filterMode === 'my' ? 'secondary' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setFilterMode('my')}
                        >
                            My Trainings
                        </Button>
                    </div>
                    <div className="flex items-center gap-1 bg-muted p-1 rounded-lg">
                        <Button
                            variant={viewMode === 'table' ? 'secondary' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setViewMode('table')}
                        >
                            <List className="h-4 w-4 mr-2" /> Table
                        </Button>
                        <Button
                            variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                            size="sm"
                            className="h-8 px-3"
                            onClick={() => setViewMode('grid')}
                        >
                            <LayoutGrid className="h-4 w-4 mr-2" /> Grid
                        </Button>
                    </div>
                </div>
            </div>

            {/* Content Area */}
            {isLoading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4">
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                    <p className="text-muted-foreground animate-pulse">Loading training library...</p>
                </div>
            ) : filteredTrainings.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 border-2 border-dashed rounded-2xl bg-muted/30">
                    <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                        <BookOpen className="w-8 h-8 text-muted-foreground" />
                    </div>
                    <h3 className="text-xl font-semibold text-foreground">No trainings found</h3>
                    <p className="text-muted-foreground mt-2 max-w-sm text-center px-4">
                        {searchQuery ? "We couldn't find any courses matching your search criteria." :
                            isCreator ? "Your training library is currently empty. Get started by creating your first course." :
                                "No training courses have been created for your organization yet."}
                    </p>
                    {!searchQuery && isCreator ? (
                        <Button onClick={handleOpenNewTrainingDialog} disabled={isCreating} className="mt-6" variant="outline">
                            <Plus className="mr-2 h-4 w-4" /> Create First Training
                        </Button>
                    ) : !searchQuery && !isCreator && isManager && (
                        <p className="mt-4 text-sm text-muted-foreground bg-primary/5 px-4 py-2 rounded-lg border border-primary/10">
                            View-only access: Contact a Training Creator to build new courses.
                        </p>
                    )}
                </div>
            ) : viewMode === 'table' ? (
                <Card className="border-border/50 shadow-sm overflow-hidden">
                    <Table>
                        <TableHeader className="bg-muted/50">
                            <TableRow>
                                <TableHead className="pl-4 w-[50px]"></TableHead>
                                <TableHead className="w-[30%]">Training Title</TableHead>
                                <TableHead>Creator</TableHead>
                                <TableHead>Category</TableHead>
                                <TableHead>Version</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredTrainings.map((training) => (
                                <TableRow key={training.id} className="hover:bg-muted/30 transition-colors group">
                                    <TableCell className="pl-4 w-[50px]">
                                        {hasDropdownActions(training) && (
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-primary">
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="start" className="w-48">
                                                    <DropdownMenuLabel>Training Actions</DropdownMenuLabel>
                                                    <DropdownMenuSeparator />
                                                    {canEdit(training) && (
                                                        <DropdownMenuItem onClick={() => navigate(`/manage/courses/${training.id}`)}>
                                                            <Edit className="mr-2 h-4 w-4" /> Edit Training
                                                        </DropdownMenuItem>
                                                    )}
                                                    {canMarkReadyAction(training) && (
                                                        <DropdownMenuItem onClick={() => handleMarkReady(training)}>
                                                            <SendHorizonal className="mr-2 h-4 w-4" /> Mark as Ready
                                                        </DropdownMenuItem>
                                                    )}
                                                    {canRevertAction(training) && (training.is_ready || training.is_published) && (
                                                        <DropdownMenuItem onClick={() => handleSendToDraft(training)} className="text-muted-foreground">
                                                            <RotateCcw className="mr-2 h-4 w-4" /> Revert to Draft
                                                        </DropdownMenuItem>
                                                    )}
                                                    {canManageLifecycle(training) && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem onClick={() => {
                                                                setTrainingToManageEditors(training);
                                                                setIsEditorsModalOpen(true);
                                                            }}>
                                                                <Users className="mr-2 h-4 w-4" /> Manage Editors
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}
                                                    {canArchiveAction(training) && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                className="text-amber-600 focus:text-amber-600 focus:bg-amber-500/10"
                                                                onClick={() => {
                                                                    setTrainingToArchive(training);
                                                                    setIsArchiveDialogOpen(true);
                                                                }}
                                                            >
                                                                <Archive className="mr-2 h-4 w-4" /> Archive Training
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}
                                                    {canDeleteAction(training) && (
                                                        <>
                                                            <DropdownMenuSeparator />
                                                            <DropdownMenuItem
                                                                className="text-destructive focus:text-destructive focus:bg-destructive/10"
                                                                onClick={() => {
                                                                    setTrainingToDelete(training);
                                                                    setIsDeleteDialogOpen(true);
                                                                }}
                                                            >
                                                                <Trash2 className="mr-2 h-4 w-4" /> Delete Training
                                                            </DropdownMenuItem>
                                                        </>
                                                    )}
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        )}
                                    </TableCell>
                                    <TableCell className="font-medium">
                                        <div className="flex items-center gap-3">
                                            <div className="w-10 h-10 rounded bg-muted flex items-center justify-center text-muted-foreground">
                                                <FileText className="w-5 h-5" />
                                            </div>
                                            <span className="group-hover:text-primary transition-colors cursor-pointer" onClick={() => navigate(`/manage/courses/${training.id}`)}>
                                                {training.title}
                                            </span>
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-sm font-medium">{training.creator_name || 'System Generated'}</span>
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="capitalize">
                                            {training.category || 'General'}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>
                                        <span className="text-muted-foreground text-sm font-mono">v{training.version}</span>
                                    </TableCell>
                                    <TableCell>
                                        {training.is_archived ? (
                                            <Badge className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30 px-2 py-0.5">
                                                <Archive className="w-3 h-3 mr-1" /> Archived
                                            </Badge>
                                        ) : training.is_published ? (
                                            <Badge className="bg-primary/10 text-primary border-primary/20 px-2 py-0.5">
                                                <CheckCircle className="w-3 h-3 mr-1" /> Published
                                            </Badge>
                                        ) : training.is_ready ? (
                                            <Badge className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 px-2 py-0.5">
                                                <CheckCircle className="w-3 h-3 mr-1" /> Ready
                                            </Badge>
                                        ) : (
                                            <Badge variant="secondary" className="bg-muted text-muted-foreground border-border px-2 py-0.5">
                                                <Clock className="w-3 h-3 mr-1" /> Draft
                                            </Badge>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredTrainings.map((training) => (
                        <Card key={training.id} className="group overflow-hidden border-border/50 hover:border-primary/40 hover:shadow-lg transition-all duration-300">
                            <div className="h-32 bg-secondary relative">
                                <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-primary/10" />
                                <div className="absolute top-3 right-3">
                                    {training.is_published ? (
                                        <Badge className="bg-primary text-primary-foreground border-0">Published</Badge>
                                    ) : training.is_ready ? (
                                        <Badge className="bg-emerald-500 text-white border-0">Ready</Badge>
                                    ) : (
                                        <Badge className="bg-muted text-muted-foreground border-0">Draft</Badge>
                                    )}
                                </div>
                                {isCreator && (
                                    <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity bg-black/40">
                                        <Button size="sm" variant="secondary" onClick={() => navigate(`/manage/courses/${training.id}`)}>
                                            <Edit className="h-4 w-4 mr-2" /> Edit Training
                                        </Button>
                                    </div>
                                )}
                            </div>
                            <CardHeader className="p-5">
                                <div className="flex justify-between items-start gap-4">
                                    <div>
                                        <CardTitle className="text-lg line-clamp-1 group-hover:text-primary transition-colors">{training.title}</CardTitle>
                                        <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                                            <span>By {training.creator_name || 'System Generated'}</span>
                                        </div>
                                        <CardDescription className="line-clamp-2 mt-1.5 h-10 text-xs">
                                            {training.description || 'No description provided.'}
                                        </CardDescription>
                                    </div>
                                </div>
                            </CardHeader>
                            <CardContent className="px-5 pb-5 pt-0">
                                <div className="flex items-center justify-between text-xs text-muted-foreground border-t pt-4">
                                    <div className="flex items-center gap-1">
                                        <Badge variant="secondary" className="text-[10px] h-5">{training.category || 'General'}</Badge>
                                    </div>
                                    <span className="font-mono">v{training.version}</span>
                                </div>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
            <AlertDialog open={isArchiveDialogOpen} onOpenChange={setIsArchiveDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Archive Training?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will hide the course from all learner dashboards. The training stays visible to managers with an Archived badge.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel onClick={() => setTrainingToArchive(null)}>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleArchiveTraining} className="bg-amber-600 hover:bg-amber-700">
                            Archive Training
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Delete Training?</AlertDialogTitle>
                        <AlertDialogDescription>
                            This will permanently delete "<strong>{trainingToDelete?.title}</strong>" and all its content. This action cannot be undone.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel onClick={() => setTrainingToDelete(null)}>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDeleteTraining} className="bg-destructive hover:bg-destructive/90">
                            Delete Training
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
            {/* Manage Editors Modal */}
            {trainingToManageEditors && (
                <ManageEditorsModal
                    isOpen={isEditorsModalOpen}
                    onClose={() => {
                        setIsEditorsModalOpen(false);
                        setTrainingToManageEditors(null);
                    }}
                    trainingId={trainingToManageEditors.id}
                    trainingTitle={trainingToManageEditors.title}
                    currentCollaborators={trainingToManageEditors.collaborators || []}
                    onUpdate={fetchTrainings}
                />
            )}

            {/* New Training Dialog */}
            <Dialog open={isNewTrainingDialogOpen} onOpenChange={(open) => { if (!open) handleCloseNewTrainingDialog(); }}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Create New Training</DialogTitle>
                        <DialogDescription>
                            Fill in the details below. You can add content after saving.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="space-y-1.5">
                            <Label htmlFor="new-title">Title <span className="text-destructive">*</span></Label>
                            <Input
                                id="new-title"
                                placeholder="e.g. Workplace Safety Fundamentals"
                                value={newTrainingTitle}
                                onChange={(e) => {
                                    setNewTrainingTitle(e.target.value);
                                    if (newTrainingTitleError) setNewTrainingTitleError('');
                                }}
                                onKeyDown={(e) => { if (e.key === 'Enter') handleSaveNewTraining(); }}
                            />
                            {newTrainingTitleError && (
                                <p className="text-xs text-destructive">{newTrainingTitleError}</p>
                            )}
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="new-description">Description</Label>
                            <Input
                                id="new-description"
                                placeholder="Brief overview of this training..."
                                value={newTrainingDescription}
                                onChange={(e) => setNewTrainingDescription(e.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={handleCloseNewTrainingDialog} disabled={isCreating}>
                            Cancel
                        </Button>
                        <Button onClick={handleSaveNewTraining} disabled={isCreating}>
                            {isCreating ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Creating...</> : 'Create Training'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Discard Confirmation */}
            <AlertDialog open={isDiscardConfirmOpen} onOpenChange={setIsDiscardConfirmOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Discard unsaved training?</AlertDialogTitle>
                        <AlertDialogDescription>
                            You have unsaved content. If you close this dialog, your changes will be lost.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel onClick={() => setIsDiscardConfirmOpen(false)}>Keep Editing</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDiscardNewTraining} className="bg-destructive hover:bg-destructive/90">
                            Discard
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
};
