import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { ArrowLeft, PlusCircle, Save, Globe, RotateCcw, Video, FileText, Loader2, History, X, HelpCircle, Trash2, Check, AlertCircle, Upload, ChevronUp, ChevronDown, Eye } from 'lucide-react';
import { PageLoader } from '../components/ui/PageLoader';

import { managerTrainingsApi, trainingsApi } from '../api/trainings';
import type { TrainingStructure, TrainingHistorySnapshot, Chapter } from '../api/trainings';
import { certificatesApi } from '../api/certificates';
import type { CertificateTemplate } from '../api/certificates';
import { useAuth } from '../contexts/auth-context';
import { RichTextEditor } from '../components/RichTextEditor';
import { TrainingAuditTimeline } from '../components/TrainingAuditTimeline';
import { cn } from '../lib/utils';
import { toast } from 'sonner';

type QuizQuestionType = 'multiple_choice' | 'multiple_select' | 'true_false' | 'matching' | 'ordering';

interface QuizOption {
    id: string;
    text: string;
}

interface QuizQuestion {
    id: string;
    text: string;
    type: QuizQuestionType;
    options: QuizOption[];
    correct_option_ids: string[];
    left_items?: QuizOption[];
    right_items?: QuizOption[];
}

const TRUE_FALSE_OPTIONS: QuizOption[] = [
    { id: 'true', text: 'True' },
    { id: 'false', text: 'False' },
];

const QUIZ_TYPE_LABELS: Record<QuizQuestionType, string> = {
    multiple_choice: 'Multiple Choice',
    multiple_select: 'Multiple Select',
    true_false: 'True / False',
    matching: 'Matching',
    ordering: 'Ordering',
};

const isSingleAnswerType = (type: QuizQuestionType) => type === 'multiple_choice' || type === 'true_false';

export const ManagerTrainingEditor: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const { user, activeMembership } = useAuth();
    const isCreator = activeMembership?.is_training_creator;
    const [training, setTraining] = useState<TrainingStructure | null>(null);
    // Computed after training loads (owner check)
    const isOwner = training ? training.created_by_id === user?.id || user?.is_sysadmin : false;
    const isCollaborator = training ? (training.collaborators?.some(c => c.user_id === user?.id) && !isOwner) : false;
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [category, setCategory] = useState('general');
    const [templateId, setTemplateId] = useState<string | undefined>(undefined);
    const [templates, setTemplates] = useState<CertificateTemplate[]>([]);

    const [history, setHistory] = useState<TrainingHistorySnapshot[]>([]);
    const [showHistory, setShowHistory] = useState(false);

    // Certificate preview state
    const [previewModalOpen, setPreviewModalOpen] = useState(false);
    const [selectedTemplate, setSelectedTemplate] = useState<CertificateTemplate | null>(null);
    const previewContainerRef = useRef<HTMLDivElement>(null);
    const [previewScale, setPreviewScale] = useState(1);

    // Inline forms: 'module' | 'standalone' | string (module ID)
    const [activeInlineForm, setActiveInlineForm] = useState<'module' | 'standalone' | string | null>(null);

    // Module form state
    const [newModuleTitle, setNewModuleTitle] = useState('');

    // Chapter form state
    const [newChapterTitle, setNewChapterTitle] = useState('');
    const [newChapterType, setNewChapterType] = useState('VIDEO');
    const [newChapterContent, setNewChapterContent] = useState('');
    const [newChapterDescription, setNewChapterDescription] = useState('');
    const [scormFile, setScormFile] = useState<File | null>(null);
    const [isUploadingScorm, setIsUploadingScorm] = useState(false);

    // Quiz Builder State
    const [quizQuestions, setQuizQuestions] = useState<QuizQuestion[]>([]);
    const [passingScore, setPassingScore] = useState(80);
    const [maxAttempts, setMaxAttempts] = useState(0);

    // Editing chapter state (inline)
    const [editingChapterId, setEditingChapterId] = useState<string | null>(null);
    const [isSavingChapter, setIsSavingChapter] = useState(false);

    // Delete chapter modal
    const [deleteChapterId, setDeleteChapterId] = useState<string | null>(null);
    const [isDeletingChapter, setIsDeletingChapter] = useState(false);

    // Delete module modal
    const [deleteModuleId, setDeleteModuleId] = useState<string | null>(null);
    const [isDeletingModule, setIsDeletingModule] = useState(false);

    // Publish validation errors
    const [publishErrors, setPublishErrors] = useState<string[]>([]);
    const [publishErrorOpen, setPublishErrorOpen] = useState(false);
    const [saveAttempted, setSaveAttempted] = useState(false);
    const [chapterSaveAttempted, setChapterSaveAttempted] = useState(false);

    // Banner image state
    const [thumbnail, setThumbnail] = useState<string | null>(null);
    const [isUploadingBanner, setIsUploadingBanner] = useState(false);
    const bannerInputRef = useRef<HTMLInputElement>(null);


    const fetchStructure = useCallback(async () => {
        setIsLoading(true);
        try {
            if (id) {
                const data = await trainingsApi.getTrainingStructure(id);
                setTraining(data);
                setTitle(data.title);
                setDescription(data.description || '');
                setCategory(data.category || 'general');
                setTemplateId(data.requires_certificate ? data.template_id : undefined);
                const presets = ['ocean', 'sunset', 'forest', 'ember'];
                setThumbnail(data.thumbnail || `preset:${presets[Math.floor(Math.random() * presets.length)]}`);

                const historyData = await managerTrainingsApi.getTrainingHistory(id);
                setHistory(historyData);
            }
        } catch (error: unknown) {
            console.error('Failed to fetch training structure:', error);
            // If unauthorized to view/edit, redirect to list
            if ((error as { response?: { status?: number } })?.response?.status === 403) {
                navigate('/manage/courses');
            }
        } finally {
            setIsLoading(false);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id]);

    useEffect(() => {
        fetchStructure();
    }, [fetchStructure]);

    useEffect(() => {
        const fetchTemplates = async () => {
            try {
                const data = await certificatesApi.listTemplates();
                const active = data.filter(t => t.is_active);
                setTemplates(active);
            } catch (error) {
                console.error('Failed to fetch templates:', error);
                toast.error('Failed to load certificate templates. You can still save other settings.');
            }
        };
        fetchTemplates();
    }, []);

    const handleSaveMetadata = async () => {
        if (!id || !training) return;

        setSaveAttempted(true);
        const errors: string[] = [];

        if (!title.trim()) {
            errors.push('Title is required.');
        }

        // Require at least 1 chapter total
        const totalChapters = calculateTotalChapters(training);
        if (totalChapters === 0) {
            errors.push('Training must have at least 1 chapter before saving.');
        }

        // No module may have zero chapters
        training.modules?.forEach(mod => {
            if (!mod.chapters || mod.chapters.length === 0) {
                errors.push(`Module "${mod.title}" has no chapters.`);
            }
        });

        if (errors.length > 0) {
            setPublishErrors(errors);
            setPublishErrorOpen(true);
            return;
        }

        setIsSaving(true);
        try {
            await managerTrainingsApi.updateTraining(id, {
                title,
                description,
                category,
                requires_certificate: !!templateId,
                template_id: templateId,
                thumbnail: thumbnail,
            });
            await fetchStructure();
        } catch (error: unknown) {
            const status = (error as { status?: number })?.status;
            if (status === 409) {
                toast.error('A training with this name already exists.');
            } else {
                console.error(error);
                toast.error('Failed to save training.');
            }
        } finally {
            setIsSaving(false);
        }
    };

    const handleMarkReady = async () => {
        if (!id) return;
        try {
            await managerTrainingsApi.markReady(id);
            toast.success('Training marked as ready.');
            await fetchStructure();
        } catch (error: unknown) {
            const detail = (error as { message?: string })?.message;
            toast.error(detail || 'Failed to mark as ready.');
        }
    };

    const handleSendToDraft = async () => {
        if (!id) return;
        try {
            await managerTrainingsApi.sendToDraft(id);
            toast.success('Reverted to draft.');
            await fetchStructure();
        } catch (error) {
            console.error(error);
            toast.error('Failed to revert to draft.');
        }
    };

    const handleCreateModule = async () => {
        if (!id) return;
        if (!newModuleTitle.trim()) {
            toast.error('Module title is required.');
            return;
        }
        try {
            const nextOrder = training?.modules.length ? training.modules.length + 1 : 1;
            await managerTrainingsApi.createModule(id, {
                title: newModuleTitle,
                sequence_order: nextOrder
            });
            setActiveInlineForm(null);
            setNewModuleTitle('');
            await fetchStructure();
            toast.success('Module added.');
        } catch (error: unknown) {
            console.error(error);
            const message = (error as { message?: string })?.message;
            toast.error(message || 'Failed to add module.');
        }
    };

    const handleSaveChapter = async (moduleId?: string) => {
        if (!id) return;
        setChapterSaveAttempted(true);

        // Validation — surface the FIRST missing field as a toast so the user
        // doesn't have to hunt for the inline error.
        if (!newChapterTitle.trim()) {
            toast.error('Chapter title is required.');
            return;
        }
        if (newChapterType !== 'QUIZ' && newChapterType !== 'SCORM' && !newChapterContent.trim()) {
            toast.error(
                newChapterType === 'VIDEO'
                    ? 'Video URL is required.'
                    : 'Chapter content is required.',
            );
            return;
        }
        if (newChapterType === 'VIDEO' && newChapterContent.trim() && !isValidUrl(newChapterContent.trim())) {
            toast.error('Please enter a valid URL (must start with http:// or https://).');
            return;
        }
        if (newChapterType === 'SCORM' && !scormFile && !editingChapterId) {
            toast.error('Please choose a SCORM ZIP package to upload.');
            return;
        }
        if (newChapterType === 'QUIZ') {
            if (quizQuestions.length === 0) {
                toast.error('Add at least one question to the quiz.');
                return;
            }
            const incompleteQuestion = quizQuestions.find(q => {
                if (!q.text.trim()) return true;
                if (q.type === 'matching') {
                    const hasPairs = (q.correct_option_ids || []).length > 0;
                    return !hasPairs;
                }
                if (q.type === 'ordering') {
                    return (q.options || []).length < 2 || q.options.some(o => !o.text.trim());
                }
                // multiple_choice / multiple_select / true_false
                const hasCorrect = (q.correct_option_ids || []).length > 0;
                const allOptionsHaveText = (q.options || []).every(o => o.text.trim());
                return !hasCorrect || !allOptionsHaveText;
            });
            if (incompleteQuestion) {
                toast.error('Each question needs text, options, and a correct answer.');
                return;
            }
        }

        setIsSavingChapter(true);
        try {
            let nextOrder = 1;
            if (!editingChapterId) {
                if (moduleId) {
                    const mod = training?.modules.find(m => m.id === moduleId);
                    if (mod) nextOrder = (mod.chapters?.length || 0) + 1;
                } else {
                    nextOrder = (training?.orphan_chapters?.length || 0) + 1;
                }
            }

            const normalizedQuestions = quizQuestions.map(q => {
                if (q.type === 'ordering') {
                    return { ...q, correct_option_ids: q.options.map(o => o.id) };
                }
                return q;
            });

            const chapterData: Record<string, unknown> = {
                title: newChapterTitle,
                content_type: newChapterType,
                content_data:
                    newChapterType === 'QUIZ'
                        ? {
                            questions: normalizedQuestions,
                            passing_score: passingScore,
                            max_attempts: maxAttempts
                        }
                        : {
                            [newChapterType === 'VIDEO' ? 'url' : 'text']: newChapterContent,
                            description: newChapterDescription
                        }
            };

            if (!editingChapterId) {
                chapterData.sequence_order = nextOrder;
                if (moduleId) chapterData.module_id = moduleId;
            }

            let savedChapter;
            if (editingChapterId) {
                savedChapter = await managerTrainingsApi.updateChapter(id, editingChapterId, chapterData);
            } else {
                savedChapter = await managerTrainingsApi.createChapter(id, chapterData);
            }

            if (newChapterType === 'SCORM' && scormFile) {
                setIsUploadingScorm(true);
                try {
                    await managerTrainingsApi.uploadChapterContent(id, savedChapter.id, scormFile);
                } finally {
                    setIsUploadingScorm(false);
                }
            }

            // Reset state
            setNewChapterTitle('');
            setNewChapterContent('');
            setNewChapterDescription('');
            setScormFile(null);
            setQuizQuestions([]);
            setMaxAttempts(0);
            setPassingScore(80);
            setActiveInlineForm(null);
            setEditingChapterId(null);
            setChapterSaveAttempted(false);
            await fetchStructure();
            toast.success(editingChapterId ? 'Chapter updated.' : 'Chapter added.');
        } catch (error: unknown) {
            console.error(error);
            const message = (error as { message?: string })?.message;
            toast.error(message || 'Failed to save chapter.');
        } finally {
            setIsSavingChapter(false);
        }
    };

    const handleReorderModules = async (moduleId: string, direction: 'up' | 'down') => {
        if (!training || !id) return;
        const modules = [...training.modules].sort((a, b) => a.sequence_order - b.sequence_order);
        const index = modules.findIndex(m => m.id === moduleId);
        if (index === -1) return;
        if (direction === 'up' && index === 0) return;
        if (direction === 'down' && index === modules.length - 1) return;

        const newIndex = direction === 'up' ? index - 1 : index + 1;
        const currentMod = modules[index];
        const otherMod = modules[newIndex];
        
        const tempOrder = currentMod.sequence_order;
        currentMod.sequence_order = otherMod.sequence_order;
        otherMod.sequence_order = tempOrder;

        try {
            await managerTrainingsApi.reorderModules(id, modules.map(m => ({ id: m.id, sequence_order: m.sequence_order })));
            await fetchStructure();
        } catch (error) {
            console.error('Failed to reorder modules:', error);
        }
    };

    const handleReorderChapters = async (moduleId: string | undefined, chapterId: string, direction: 'up' | 'down') => {
        if (!training || !id) return;
        
        // Find the collection to reorder (module chapters or orphan chapters)
        let chapters: Chapter[] = [];
        if (moduleId) {
            const mod = training.modules.find(m => m.id === moduleId);
            if (!mod) return;
            chapters = [...mod.chapters];
        } else {
            chapters = [...(training.orphan_chapters || [])];
        }

        chapters.sort((a, b) => a.sequence_order - b.sequence_order);
        const index = chapters.findIndex(c => c.id === chapterId);
        if (index === -1) return;
        if (direction === 'up' && index === 0) return;
        if (direction === 'down' && index === chapters.length - 1) return;

        const newIndex = direction === 'up' ? index - 1 : index + 1;
        const currentChap = chapters[index];
        const otherChap = chapters[newIndex];
        
        const tempOrder = currentChap.sequence_order;
        currentChap.sequence_order = otherChap.sequence_order;
        otherChap.sequence_order = tempOrder;

        try {
            await managerTrainingsApi.reorderChapters(id, moduleId, chapters.map(c => ({ id: c.id, sequence_order: c.sequence_order })));
            await fetchStructure();
        } catch (error) {
            console.error('Failed to reorder chapters:', error);
        }
    };

    const handleDeleteChapter = (chapterId: string) => {
        setDeleteChapterId(chapterId);
    };

    const handleConfirmDeleteChapter = async () => {
        if (!id || !deleteChapterId) return;
        setIsDeletingChapter(true);
        try {
            await managerTrainingsApi.deleteChapter(id, deleteChapterId);
            setDeleteChapterId(null);
            await fetchStructure();
        } catch (error) {
            console.error('Failed to delete chapter:', error);
        } finally {
            setIsDeletingChapter(false);
        }
    };

    const handleConfirmDeleteModule = async () => {
        if (!id || !deleteModuleId) return;
        setIsDeletingModule(true);
        try {
            await managerTrainingsApi.deleteModule(id, deleteModuleId);
            setDeleteModuleId(null);
            await fetchStructure();
        } catch (error) {
            console.error('Failed to delete module:', error);
            toast.error('Failed to delete module.');
        } finally {
            setIsDeletingModule(false);
        }
    };

    const handleEditChapter = (chapter: Chapter) => {
        setEditingChapterId(chapter.id);
        setNewChapterTitle(chapter.title);
        setNewChapterType(chapter.content_type);
        
        if (chapter.content_type === 'QUIZ') {
            const rawQuestions = (chapter.content_data?.questions || []) as Partial<QuizQuestion>[];
            const normalized: QuizQuestion[] = rawQuestions.map((q) => {
                const type = (q.type as QuizQuestionType) || 'multiple_choice';
                return {
                    id: q.id || crypto.randomUUID(),
                    text: q.text || '',
                    type,
                    options: q.options || (type === 'true_false' ? TRUE_FALSE_OPTIONS.map(o => ({ ...o })) : []),
                    correct_option_ids: q.correct_option_ids || [],
                    left_items: q.left_items,
                    right_items: q.right_items,
                };
            });
            setQuizQuestions(normalized);
            setPassingScore(chapter.content_data?.passing_score || 80);
            setMaxAttempts(chapter.content_data?.max_attempts || 0);
        } else {
            const text = chapter.content_data?.text || chapter.content_data?.url || '';
            setNewChapterContent(text);
            setNewChapterDescription(chapter.content_data?.description || '');
        }
        
        setActiveInlineForm(null); // Close any open "Add" forms
    };

    const handleCancelEdit = () => {
        setEditingChapterId(null);
        setNewChapterTitle('');
        setNewChapterContent('');
        setNewChapterDescription('');
        setQuizQuestions([]);
        setNewChapterType('VIDEO');
        setChapterSaveAttempted(false);
    };

    const buildDefaultOptions = (count = 2): QuizOption[] =>
        Array.from({ length: count }, () => ({ id: crypto.randomUUID(), text: '' }));

    const buildDefaultQuestion = (type: QuizQuestionType): QuizQuestion => {
        const base = { id: crypto.randomUUID(), text: '', type };
        if (type === 'true_false') {
            return { ...base, options: TRUE_FALSE_OPTIONS.map(o => ({ ...o })), correct_option_ids: [] };
        }
        if (type === 'matching') {
            return {
                ...base,
                options: [],
                correct_option_ids: [],
                left_items: buildDefaultOptions(2),
                right_items: buildDefaultOptions(2),
            };
        }
        return { ...base, options: buildDefaultOptions(2), correct_option_ids: [] };
    };

    const handleAddQuestion = (type: QuizQuestionType = 'multiple_choice') => {
        setQuizQuestions([...quizQuestions, buildDefaultQuestion(type)]);
    };

    const handleRemoveQuestion = (qId: string) => {
        setQuizQuestions(quizQuestions.filter(q => q.id !== qId));
    };

    const handleUpdateQuestion = (qId: string, text: string) => {
        setQuizQuestions(quizQuestions.map(q => q.id === qId ? { ...q, text } : q));
    };

    const handleChangeQuestionType = (qId: string, newType: QuizQuestionType) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId) return q;
            if (q.type === newType) return q;
            const carry = { id: q.id, text: q.text };
            if (newType === 'true_false') {
                return { ...carry, type: newType, options: TRUE_FALSE_OPTIONS.map(o => ({ ...o })), correct_option_ids: [] };
            }
            if (newType === 'matching') {
                return {
                    ...carry,
                    type: newType,
                    options: [],
                    correct_option_ids: [],
                    left_items: q.left_items?.length ? q.left_items : buildDefaultOptions(2),
                    right_items: q.right_items?.length ? q.right_items : buildDefaultOptions(2),
                };
            }
            // multiple_choice / multiple_select / ordering
            const reusable = q.options?.length ? q.options : buildDefaultOptions(2);
            return { ...carry, type: newType, options: reusable, correct_option_ids: [] };
        }));
    };

    const handleAddOption = (qId: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId) return q;
            if (q.type === 'true_false') return q;
            return {
                ...q,
                options: [...q.options, { id: crypto.randomUUID(), text: '' }],
            };
        }));
    };

    const handleUpdateOption = (qId: string, oId: string, text: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id === qId) {
                return {
                    ...q,
                    options: q.options.map(o => o.id === oId ? { ...o, text } : o)
                };
            }
            return q;
        }));
    };

    const handleRemoveOption = (qId: string, oId: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId) return q;
            if (q.type === 'true_false') return q;
            return {
                ...q,
                options: q.options.filter(o => o.id !== oId),
                correct_option_ids: q.type === 'ordering'
                    ? q.correct_option_ids.filter(id => id !== oId)
                    : q.correct_option_ids.filter(id => id !== oId),
            };
        }));
    };

    const handleSetCorrectOption = (qId: string, oId: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId) return q;
            if (isSingleAnswerType(q.type)) {
                return { ...q, correct_option_ids: [oId] };
            }
            const already = q.correct_option_ids.includes(oId);
            return {
                ...q,
                correct_option_ids: already
                    ? q.correct_option_ids.filter(id => id !== oId)
                    : [...q.correct_option_ids, oId],
            };
        }));
    };

    const handleMoveOption = (qId: string, oId: string, direction: -1 | 1) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId) return q;
            const idx = q.options.findIndex(o => o.id === oId);
            const target = idx + direction;
            if (idx < 0 || target < 0 || target >= q.options.length) return q;
            const next = [...q.options];
            [next[idx], next[target]] = [next[target], next[idx]];
            return { ...q, options: next };
        }));
    };

    const handleMatchAddItem = (qId: string, side: 'left' | 'right') => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId || q.type !== 'matching') return q;
            const key = side === 'left' ? 'left_items' : 'right_items';
            const list = q[key] || [];
            return { ...q, [key]: [...list, { id: crypto.randomUUID(), text: '' }] };
        }));
    };

    const handleMatchUpdateItem = (qId: string, side: 'left' | 'right', itemId: string, text: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId || q.type !== 'matching') return q;
            const key = side === 'left' ? 'left_items' : 'right_items';
            const list = (q[key] || []).map(it => it.id === itemId ? { ...it, text } : it);
            return { ...q, [key]: list };
        }));
    };

    const handleMatchRemoveItem = (qId: string, side: 'left' | 'right', itemId: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId || q.type !== 'matching') return q;
            const key = side === 'left' ? 'left_items' : 'right_items';
            const list = (q[key] || []).filter(it => it.id !== itemId);
            const filteredPairs = q.correct_option_ids.filter(p => {
                const [l, r] = p.split('::');
                return l !== itemId && r !== itemId;
            });
            return { ...q, [key]: list, correct_option_ids: filteredPairs };
        }));
    };

    const handleMatchSetPair = (qId: string, leftId: string, rightId: string) => {
        setQuizQuestions(quizQuestions.map(q => {
            if (q.id !== qId || q.type !== 'matching') return q;
            const others = q.correct_option_ids.filter(p => !p.startsWith(`${leftId}::`));
            return { ...q, correct_option_ids: rightId ? [...others, `${leftId}::${rightId}`] : others };
        }));
    };


    const isValidUrl = (url: string) => {
        try { new URL(url); return true; } catch { return false; }
    };

    const calculateTotalChapters = (structure: TrainingStructure) => {
        let count = structure.orphan_chapters?.length || 0;
        structure.modules?.forEach(mod => {
            count += mod.chapters?.length || 0;
        });
        return count;
    };

    useEffect(() => {
        if (!previewModalOpen || !previewContainerRef.current) return;
        const el = previewContainerRef.current;
        const updateScale = () => setPreviewScale(el.clientWidth / 800);
        updateScale();
        const observer = new ResizeObserver(updateScale);
        observer.observe(el);
        return () => observer.disconnect();
    }, [previewModalOpen]);

    const openPreview = () => {
        const template = templates.find(t => t.id === templateId);
        if (template) {
            setSelectedTemplate(template);
            setPreviewModalOpen(true);
        } else {
            alert('Please select a certificate template first.');
        }
    };

    const handleBannerUpload = async (file: File) => {
        if (!id) return;
        setIsUploadingBanner(true);
        try {
            const updated = await managerTrainingsApi.uploadBanner(id, file);
            setThumbnail(updated.thumbnail || null);
            toast.success('Banner image uploaded.');
        } catch {
            toast.error('Failed to upload banner image.');
        } finally {
            setIsUploadingBanner(false);
        }
    };

    const chapterTypeIcon = (type: string) => {
        if (type === 'VIDEO') return <Video className="w-3.5 h-3.5 text-primary" />;
        if (type === 'QUIZ') return <HelpCircle className="w-3.5 h-3.5 text-primary" />;
        if (type === 'SCORM') return <Upload className="w-3.5 h-3.5 text-muted-foreground" />;
        return <FileText className="w-3.5 h-3.5 text-muted-foreground" />;
    };

    const renderChapterForm = (moduleId?: string) => (
        <Card className="border-primary/50 bg-primary/5 shadow-inner mt-4 mb-4 overflow-hidden border">
            <CardHeader className="py-3 px-4 border-b border-primary/10 flex flex-row items-center justify-between bg-primary/10">
                <CardTitle className="text-sm font-semibold text-primary">
                    {editingChapterId ? 'Edit Chapter' : moduleId ? 'Add Chapter to Module' : 'Add Standalone Chapter'}
                </CardTitle>
                <Button variant="ghost" size="sm" onClick={() => { if (editingChapterId) handleCancelEdit(); else setActiveInlineForm(null); setChapterSaveAttempted(false); }} className="h-6 w-6 p-0 hover:bg-primary/20 hover:text-primary">
                    <X className="w-4 h-4" />
                </Button>
            </CardHeader>
            <CardContent className="p-5 space-y-5">
                <div className="space-y-1">
                    <Label className="text-secondary-foreground">Chapter Title</Label>
                    <Input value={newChapterTitle} onChange={e => setNewChapterTitle(e.target.value)} placeholder="e.g. Fundamental Concepts" className="bg-background" />
                    {chapterSaveAttempted && !newChapterTitle.trim() && <p className="text-xs text-destructive">Chapter title is required.</p>}
                </div>
                <div className="space-y-2">
                    <Label className="text-secondary-foreground">Content Type</Label>
                    <div className="flex flex-wrap gap-2">
                        <Button
                            variant={newChapterType === 'VIDEO' ? 'default' : 'outline'}
                            className="flex-1 min-w-[120px]"
                            onClick={() => setNewChapterType('VIDEO')}
                        >
                            <Video className="w-4 h-4 mr-2" /> Video
                        </Button>
                        <Button
                            variant={newChapterType === 'RICH_TEXT' ? 'default' : 'outline'}
                            className="flex-1 min-w-[120px]"
                            onClick={() => setNewChapterType('RICH_TEXT')}
                        >
                            <FileText className="w-4 h-4 mr-2" /> Text
                        </Button>
                        <Button
                            variant={newChapterType === 'QUIZ' ? 'default' : 'outline'}
                            className="flex-1 min-w-[120px]"
                            onClick={() => setNewChapterType('QUIZ')}
                        >
                            <HelpCircle className="w-4 h-4 mr-2" /> Quiz
                        </Button>
                        <Button
                            variant={newChapterType === 'SCORM' ? 'default' : 'outline'}
                            className="flex-1 min-w-[120px]"
                            onClick={() => setNewChapterType('SCORM')}
                        >
                            <Upload className="w-4 h-4 mr-2" /> SCORM
                        </Button>
                    </div>
                </div>

                {newChapterType !== 'QUIZ' && newChapterType !== 'SCORM' && (
                    <div className="space-y-4">
                        <div className="space-y-2">
                            <Label className="text-secondary-foreground">{newChapterType === 'VIDEO' ? 'Video URL' : 'Content'}</Label>
                            {newChapterType === 'VIDEO' ? (
                                <div className="space-y-1">
                                    <Input value={newChapterContent} onChange={e => setNewChapterContent(e.target.value)} placeholder="YouTube, Vimeo, or MP4 URL" className="bg-background" />
                                    {chapterSaveAttempted && !newChapterContent.trim() && <p className="text-xs text-destructive">Video URL is required.</p>}
                                    {newChapterContent.trim() && !isValidUrl(newChapterContent.trim()) && (
                                        <p className="text-xs text-destructive">Please enter a valid URL (must start with http:// or https://).</p>
                                    )}
                                </div>
                            ) : (
                                <div className="space-y-1">
                                    <RichTextEditor content={newChapterContent} onChange={setNewChapterContent} />
                                    {chapterSaveAttempted && !newChapterContent.trim() && <p className="text-xs text-destructive">Content is required.</p>}
                                </div>
                            )}
                        </div>
                        <div className="space-y-2">
                            <Label className="text-secondary-foreground">Description / Instructions</Label>
                            <textarea
                                value={newChapterDescription}
                                onChange={e => setNewChapterDescription(e.target.value)}
                                placeholder="Add a description or instructions for this chapter..."
                                className="w-full min-h-[100px] p-3 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                            />
                        </div>
                    </div>
                )}

                {newChapterType === 'SCORM' && (
                    <div className="space-y-2">
                        <Label className="text-secondary-foreground">SCORM Package (ZIP)</Label>
                        <div className={cn('flex flex-col items-center justify-center w-full h-32 border-2 border-dashed rounded-lg cursor-pointer transition-colors', scormFile ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50 hover:bg-muted/30')}>
                            <label className="flex flex-col items-center justify-center w-full h-full cursor-pointer">
                                <Upload className="w-8 h-8 mb-2 text-muted-foreground" />
                                {scormFile ? (
                                    <span className="text-sm font-medium text-primary">{scormFile.name}</span>
                                ) : (
                                    <span className="text-sm text-muted-foreground">Click to upload SCORM zip</span>
                                )}
                                <input type="file" accept=".zip" className="hidden" onChange={e => setScormFile(e.target.files?.[0] ?? null)} />
                            </label>
                        </div>
                    </div>
                )}

                {newChapterType === 'QUIZ' && (
                    <div className="space-y-6 pt-4 border-t border-primary/10">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Passing Score (%)</Label>
                                <Input type="number" min="0" max="100" value={passingScore} onChange={e => setPassingScore(Number(e.target.value))} />
                            </div>
                            <div className="space-y-2">
                                <Label>Max Attempts (0 for unlimited)</Label>
                                <Input type="number" min="0" value={maxAttempts} onChange={e => setMaxAttempts(Number(e.target.value))} />
                            </div>
                        </div>

                        <div className="space-y-6">
                            <div className="flex items-center justify-between">
                                <h4 className="text-md font-semibold text-primary">Questions</h4>
                                <Button size="sm" variant="outline" onClick={() => handleAddQuestion('multiple_choice')}>
                                    <PlusCircle className="mr-2 h-4 w-4" /> Add Question
                                </Button>
                            </div>

                            {quizQuestions.length === 0 ? (
                                <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-lg bg-background/50">
                                    No questions added yet. Click 'Add Question' to start building your quiz.
                                </div>
                            ) : (
                                <div className="space-y-6">
                                    {quizQuestions.map((q, qIndex) => {
                                        const isOrdering = q.type === 'ordering';
                                        const isMatching = q.type === 'matching';
                                        const isTF = q.type === 'true_false';
                                        const isSingle = isSingleAnswerType(q.type);
                                        const answerHint = isMatching
                                            ? 'Pair each left item with the correct right item'
                                            : isOrdering
                                                ? 'Arrange options in the correct order — top is first'
                                                : isSingle
                                                    ? 'Select the single correct answer'
                                                    : 'Select all correct answers';
                                        return (
                                        <Card key={q.id} className="border-border shadow-sm">
                                            <CardHeader className="p-4 pb-2 flex flex-row items-center justify-between space-y-0">
                                                <CardTitle className="text-sm font-medium">Question {qIndex + 1}</CardTitle>
                                                <div className="flex items-center gap-2">
                                                    <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10" onClick={() => handleRemoveQuestion(q.id)}>
                                                        <Trash2 className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="p-4 space-y-4 pt-0">
                                                <Input value={q.text} onChange={(e) => handleUpdateQuestion(q.id, e.target.value)} placeholder="Enter your question here..." />

                                                <div className="space-y-2">
                                                    <Label className="text-xs text-muted-foreground uppercase font-semibold">Question Type</Label>
                                                    <div className="flex flex-wrap gap-1.5">
                                                        {(Object.keys(QUIZ_TYPE_LABELS) as QuizQuestionType[]).map(t => (
                                                            <Button
                                                                key={t}
                                                                size="sm"
                                                                variant={q.type === t ? 'default' : 'outline'}
                                                                className="h-7 text-xs"
                                                                onClick={() => handleChangeQuestionType(q.id, t)}
                                                            >
                                                                {QUIZ_TYPE_LABELS[t]}
                                                            </Button>
                                                        ))}
                                                    </div>
                                                </div>

                                                {!isMatching && (
                                                    <div className="space-y-2">
                                                        <div className="flex items-center justify-between text-xs text-muted-foreground uppercase font-semibold">
                                                            <span>{isOrdering ? 'Options (in correct order)' : 'Answers'}</span>
                                                            <span>{answerHint}</span>
                                                        </div>
                                                        {q.options.map((o, oIndex) => (
                                                            <div key={o.id} className="flex items-center gap-3 bg-muted/30 p-2 rounded-lg border border-border/50">
                                                                <div className="text-muted-foreground select-none w-6 text-center font-medium">{String.fromCharCode(65 + oIndex)}</div>
                                                                <Input
                                                                    className="flex-1 bg-background"
                                                                    value={o.text}
                                                                    onChange={(e) => handleUpdateOption(q.id, o.id, e.target.value)}
                                                                    placeholder={isTF ? o.text : `Option ${oIndex + 1}`}
                                                                    disabled={isTF}
                                                                />
                                                                {isOrdering ? (
                                                                    <>
                                                                        <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0" onClick={() => handleMoveOption(q.id, o.id, -1)} disabled={oIndex === 0} title="Move up">
                                                                            <ChevronUp className="h-4 w-4" />
                                                                        </Button>
                                                                        <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0" onClick={() => handleMoveOption(q.id, o.id, 1)} disabled={oIndex === q.options.length - 1} title="Move down">
                                                                            <ChevronDown className="h-4 w-4" />
                                                                        </Button>
                                                                    </>
                                                                ) : (
                                                                    <Button size="icon" variant={q.correct_option_ids.includes(o.id) ? "default" : "outline"} className={cn('h-9 w-9 shrink-0', q.correct_option_ids.includes(o.id) && 'bg-primary hover:bg-primary/90 text-primary-foreground border-0')} onClick={() => handleSetCorrectOption(q.id, o.id)} title="Mark correct">
                                                                        <Check className="h-4 w-4" />
                                                                    </Button>
                                                                )}
                                                                <Button size="icon" variant="ghost" className="h-9 w-9 shrink-0 text-muted-foreground hover:text-destructive" onClick={() => handleRemoveOption(q.id, o.id)} disabled={isTF || q.options.length <= 2}>
                                                                    <X className="h-4 w-4" />
                                                                </Button>
                                                            </div>
                                                        ))}
                                                        {!isTF && (
                                                            <Button size="sm" variant="ghost" className="w-full mt-2 border border-dashed border-border" onClick={() => handleAddOption(q.id)}>
                                                                <PlusCircle className="mr-2 h-4 w-4" /> Add Option
                                                            </Button>
                                                        )}
                                                    </div>
                                                )}

                                                {isMatching && (
                                                    <div className="space-y-3">
                                                        <div className="text-xs text-muted-foreground uppercase font-semibold">{answerHint}</div>
                                                        <div className="grid grid-cols-2 gap-3">
                                                            <div className="space-y-2">
                                                                <Label className="text-xs">Left Items</Label>
                                                                {(q.left_items || []).map((it, idx) => (
                                                                    <div key={it.id} className="flex items-center gap-2 bg-muted/30 p-2 rounded-lg border border-border/50">
                                                                        <div className="text-muted-foreground w-6 text-center text-xs font-medium">{idx + 1}</div>
                                                                        <Input className="flex-1 bg-background" value={it.text} onChange={(e) => handleMatchUpdateItem(q.id, 'left', it.id, e.target.value)} placeholder={`Left ${idx + 1}`} />
                                                                        <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => handleMatchRemoveItem(q.id, 'left', it.id)} disabled={(q.left_items?.length || 0) <= 2}>
                                                                            <X className="h-3.5 w-3.5" />
                                                                        </Button>
                                                                    </div>
                                                                ))}
                                                                <Button size="sm" variant="ghost" className="w-full border border-dashed border-border" onClick={() => handleMatchAddItem(q.id, 'left')}>
                                                                    <PlusCircle className="mr-2 h-3.5 w-3.5" /> Add Left
                                                                </Button>
                                                            </div>
                                                            <div className="space-y-2">
                                                                <Label className="text-xs">Right Items</Label>
                                                                {(q.right_items || []).map((it, idx) => (
                                                                    <div key={it.id} className="flex items-center gap-2 bg-muted/30 p-2 rounded-lg border border-border/50">
                                                                        <div className="text-muted-foreground w-6 text-center text-xs font-medium">{String.fromCharCode(65 + idx)}</div>
                                                                        <Input className="flex-1 bg-background" value={it.text} onChange={(e) => handleMatchUpdateItem(q.id, 'right', it.id, e.target.value)} placeholder={`Right ${idx + 1}`} />
                                                                        <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-destructive" onClick={() => handleMatchRemoveItem(q.id, 'right', it.id)} disabled={(q.right_items?.length || 0) <= 2}>
                                                                            <X className="h-3.5 w-3.5" />
                                                                        </Button>
                                                                    </div>
                                                                ))}
                                                                <Button size="sm" variant="ghost" className="w-full border border-dashed border-border" onClick={() => handleMatchAddItem(q.id, 'right')}>
                                                                    <PlusCircle className="mr-2 h-3.5 w-3.5" /> Add Right
                                                                </Button>
                                                            </div>
                                                        </div>
                                                        <div className="space-y-2 pt-2 border-t border-border/50">
                                                            <Label className="text-xs text-muted-foreground uppercase font-semibold">Correct Pairs</Label>
                                                            {(q.left_items || []).map((left, idx) => {
                                                                const pair = q.correct_option_ids.find(p => p.startsWith(`${left.id}::`));
                                                                const currentRight = pair?.split('::')[1] || '';
                                                                return (
                                                                    <div key={left.id} className="flex items-center gap-2">
                                                                        <span className="text-xs flex-1 truncate">{left.text || `Left ${idx + 1}`}</span>
                                                                        <span className="text-xs text-muted-foreground">→</span>
                                                                        <select
                                                                            className="flex-1 h-9 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                                                                            value={currentRight}
                                                                            onChange={(e) => handleMatchSetPair(q.id, left.id, e.target.value)}
                                                                        >
                                                                            <option value="">— Select —</option>
                                                                            {(q.right_items || []).map((right, rIdx) => (
                                                                                <option key={right.id} value={right.id}>{right.text || `Right ${rIdx + 1}`}</option>
                                                                            ))}
                                                                        </select>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                )}
                                            </CardContent>
                                        </Card>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                )}
                <div className="flex justify-end pt-4 border-t border-primary/10 gap-3">
                    {editingChapterId && (
                        <Button variant="outline" onClick={handleCancelEdit} disabled={isSavingChapter}>
                            Cancel
                        </Button>
                    )}
                    <Button
                        onClick={() => handleSaveChapter(moduleId)}
                        disabled={isUploadingScorm || isSavingChapter}
                        className="w-full sm:w-auto shadow-md"
                    >
                        {isUploadingScorm || isSavingChapter ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...</> : <><Save className="w-4 h-4 mr-2" /> {editingChapterId ? 'Update Chapter' : 'Save Chapter'}</>}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );

    const renderModuleForm = () => (
        <Card className="border-primary/50 bg-primary/5 shadow-inner mt-4 mb-4 overflow-hidden border">
            <CardHeader className="py-3 px-4 border-b border-primary/10 flex flex-row items-center justify-between bg-primary/10">
                <CardTitle className="text-sm font-semibold text-primary">Add New Module</CardTitle>
                <Button variant="ghost" size="sm" onClick={() => setActiveInlineForm(null)} className="h-6 w-6 p-0 hover:bg-primary/20 hover:text-primary">
                    <X className="w-4 h-4" />
                </Button>
            </CardHeader>
            <CardContent className="p-5 space-y-5">
                <div className="space-y-2">
                    <Label className="text-secondary-foreground">Module Title</Label>
                    <Input value={newModuleTitle} onChange={e => setNewModuleTitle(e.target.value)} placeholder="e.g. Introduction & Basics" className="bg-background" />
                </div>
                <div className="flex justify-end pt-4 border-t border-primary/10">
                    <Button onClick={handleCreateModule} disabled={!newModuleTitle.trim()} className="w-full sm:w-auto shadow-md">
                        <Save className="w-4 h-4 mr-2" /> Save Module
                    </Button>
                </div>
            </CardContent>
        </Card>
    );

    if (!isCreator && !isLoading) {
        return (
            <div className="flex flex-col items-center justify-center h-[60vh]">
                <AlertCircle className="w-12 h-12 text-destructive mb-4" />
                <h2 className="text-2xl font-bold mb-2">Access Denied</h2>
                <Button onClick={() => navigate('/manage/courses')}><ArrowLeft className="w-4 h-4 mr-2" /> Back</Button>
            </div>
        );
    }

    if (isLoading || !training) return <PageLoader label="Loading training..." />;

    const sortedModules = [...training.modules].sort((a, b) => a.sequence_order - b.sequence_order);

    return (
        <div className="space-y-6 animate-in fade-in duration-300">

                    {/* ── Header ── */}
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3 border-b pb-4">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            <Button variant="outline" size="icon" className="shrink-0" onClick={() => navigate('/manage/courses')}>
                                <ArrowLeft className="w-4 h-4" />
                            </Button>
                            <div className="min-w-0">
                                <h1 className="text-xl font-bold text-foreground truncate">{training.title}</h1>
                                <div className="flex items-center gap-2 mt-0.5">
                                    <Badge variant="outline" className="text-[10px] h-4 px-1.5">v{training.version}</Badge>
                                    <span className={cn('text-xs font-medium',
                                        training.is_archived ? 'text-amber-500' :
                                        training.is_published ? 'text-primary' :
                                        training.is_ready ? 'text-emerald-500' :
                                        'text-muted-foreground'
                                    )}>
                                        {training.is_archived ? 'Archived' : training.is_published ? 'Published' : training.is_ready ? 'Ready' : 'Draft'}
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                            <Button variant="outline" size="sm" onClick={() => setShowHistory(!showHistory)}>
                                <History className="w-3.5 h-3.5 mr-1.5" />{showHistory ? 'Editor' : 'History'}
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => navigate(`/manage/learn/${training.id}?preview=true`)}>
                                <Eye className="w-3.5 h-3.5 mr-1.5" />Preview
                            </Button>
                            {!showHistory && isCreator && (
                                <Button size="sm" variant="secondary" onClick={handleSaveMetadata} disabled={isSaving}>
                                    {isSaving ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                                    Save
                                </Button>
                            )}
                            {isCreator && !isCollaborator && (
                                training.is_ready && !training.is_published ? (
                                    <Button size="sm" onClick={handleSendToDraft} variant="outline" className="text-muted-foreground border-border">
                                        <RotateCcw className="w-3.5 h-3.5 mr-1.5" />Revert to Draft
                                    </Button>
                                ) : !training.is_published && !training.is_archived && (
                                    <Button size="sm" onClick={handleMarkReady} variant="default" className="bg-emerald-600 hover:bg-emerald-700 text-white border-0">
                                        <Globe className="w-3.5 h-3.5 mr-1.5" />Mark Ready
                                    </Button>
                                )
                            )}
                        </div>
                    </div>

                    {showHistory ? (
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in slide-in-from-right-4 duration-300">
                            <div className="lg:col-span-2 space-y-4">
                                <h3 className="text-lg font-bold px-1 flex items-center gap-2">
                                    <History className="h-5 w-5 text-primary" /> Version Snapshots
                                </h3>
                                <div className="space-y-3">
                                    {history.length === 0
                                        ? <Card className="p-10 text-center text-muted-foreground border-dashed text-sm">No version history snapshots found.</Card>
                                        : history.map(snapshot => (
                                            <Card key={snapshot.id} className="p-4 flex items-center justify-between hover:border-primary/30 transition-colors">
                                                <div className="flex flex-col">
                                                    <span className="font-bold">Version {snapshot.version}</span>
                                                    <span className="text-xs text-muted-foreground">{new Date(snapshot.created_at).toLocaleString()}</span>
                                                </div>
                                                <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/learn/${training.id}?version=${snapshot.version}`)}>
                                                    View Snapshot
                                                </Button>
                                            </Card>
                                        ))
                                    }
                                </div>
                            </div>
                            <div className="lg:col-span-1 h-[calc(100vh-200px)] min-h-[500px]">
                                <Card className="h-full overflow-hidden shadow-sm flex flex-col">
                                    <TrainingAuditTimeline trainingId={id!} />
                                </Card>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-5">

                            {/* ── Training Info Card ── */}
                            <Card>
                                <CardHeader className="pb-2 pt-4 px-4">
                                    <CardTitle className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Training Settings</CardTitle>
                                </CardHeader>
                                <CardContent className="px-4 pb-4">
                                    {/*
                                        3-col grid, banner spans both rows:
                                        | Title       | Category    | Banner (row-span-2) |
                                        | Description | Certificate |                     |
                                    */}
                                    <div className="grid grid-cols-3 gap-4 items-start">
                                        {/* Title */}
                                        <div className="space-y-1">
                                            <Label className="text-xs">Title</Label>
                                            <Input value={title} onChange={e => setTitle(e.target.value)} className="h-9" />
                                            {saveAttempted && !title.trim() && <p className="text-xs text-destructive">Title is required.</p>}
                                        </div>

                                        {/* Category */}
                                        <div className="space-y-1">
                                            <Label className="text-xs">Category</Label>
                                            <select
                                                className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                                                value={category}
                                                onChange={e => setCategory(e.target.value)}
                                            >
                                                <option value="general">General</option>
                                                <option value="compliance">Compliance</option>
                                                <option value="safety">Safety</option>
                                                <option value="technical">Technical</option>
                                                <option value="soft_skills">Soft Skills</option>
                                                <option value="onboarding">Onboarding</option>
                                            </select>
                                        </div>

                                        {/* Banner Image — spans rows 1 & 2.
                                            Color is auto-assigned at training creation; the picker has been removed.
                                            Custom image upload is still optional. */}
                                        <div className="row-span-2 space-y-2">
                                            <Label className="text-xs">Banner Image</Label>
                                            <input
                                                ref={bannerInputRef}
                                                type="file"
                                                accept="image/jpeg,image/png,image/webp"
                                                className="hidden"
                                                onChange={e => {
                                                    const file = e.target.files?.[0];
                                                    if (file) handleBannerUpload(file);
                                                    e.target.value = '';
                                                }}
                                            />
                                            {/* Always render a preview of the current banner (preset gradient or uploaded image) */}
                                            <div className="relative h-20 rounded-md overflow-hidden border border-border group">
                                                {thumbnail?.startsWith('/storage/banners/') ? (
                                                    <img src={thumbnail} className="w-full h-full object-cover" alt="Banner preview" />
                                                ) : (
                                                    <div
                                                        className="absolute inset-0"
                                                        style={{
                                                            background:
                                                                thumbnail === 'preset:sunset' ? 'linear-gradient(135deg, #f97316 0%, #e11d48 100%)' :
                                                                thumbnail === 'preset:forest' ? 'linear-gradient(135deg, #10b981 0%, #0369a1 100%)' :
                                                                thumbnail === 'preset:ember'  ? 'linear-gradient(135deg, #f59e0b 0%, #dc2626 100%)' :
                                                                'linear-gradient(135deg, #3b82f6 0%, #4338ca 100%)',
                                                        }}
                                                    />
                                                )}
                                                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1.5">
                                                    <Button variant="secondary" size="sm" className="h-6 text-[10px] px-2" onClick={() => bannerInputRef.current?.click()} disabled={isUploadingBanner}>
                                                        {isUploadingBanner ? <Loader2 className="w-2.5 h-2.5 animate-spin mr-1" /> : <Upload className="w-2.5 h-2.5 mr-1" />}
                                                        {thumbnail?.startsWith('/storage/banners/') ? 'Change' : 'Upload image'}
                                                    </Button>
                                                    {thumbnail?.startsWith('/storage/banners/') && (
                                                        <Button
                                                            variant="destructive"
                                                            size="sm"
                                                            className="h-6 text-[10px] px-2"
                                                            onClick={() => {
                                                                const presets = ['ocean', 'sunset', 'forest', 'ember'];
                                                                setThumbnail(`preset:${presets[Math.floor(Math.random() * presets.length)]}`);
                                                            }}
                                                        >
                                                            Remove
                                                        </Button>
                                                    )}
                                                </div>
                                            </div>
                                            <p className="text-[10px] text-muted-foreground leading-tight">
                                                Image upload is optional. Color is auto-assigned.
                                            </p>
                                        </div>

                                        {/* Description — row 2, col 1 */}
                                        <div className="space-y-1">
                                            <Label className="text-xs">Description</Label>
                                            <Textarea
                                                value={description}
                                                onChange={e => setDescription(e.target.value)}
                                                placeholder="Describe what learners will gain from this training..."
                                                className="min-h-[96px] resize-none"
                                            />
                                        </div>

                                        {/* Certificate — row 2, col 2 */}
                                        <div className="space-y-1">
                                            <Label className="text-xs">Certificate on completion</Label>
                                            <div className="flex gap-1">
                                                <select
                                                    className="flex-1 h-9 rounded-md border border-input bg-background px-2 text-sm min-w-0"
                                                    value={templateId || ''}
                                                    onChange={e => setTemplateId(e.target.value || undefined)}
                                                >
                                                    <option value="">None</option>
                                                    {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                                                </select>
                                                <Button variant="outline" size="icon" className="h-9 w-9 shrink-0" onClick={openPreview} disabled={!templateId} title="Preview certificate">
                                                    <Eye className="w-3.5 h-3.5" />
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>

                            {/* ── Curriculum ── */}
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <h2 className="text-base font-semibold">
                                        Curriculum
                                        <span className="ml-2 text-xs font-normal text-muted-foreground">
                                            <span>{sortedModules.length} module{sortedModules.length !== 1 ? 's' : ''} · </span>{calculateTotalChapters(training)} chapter{calculateTotalChapters(training) !== 1 ? 's' : ''}
                                        </span>
                                    </h2>
                                    <div className="flex gap-2">
                                        <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setActiveInlineForm('module')}>
                                            <PlusCircle className="w-3.5 h-3.5 mr-1.5" />Module
                                        </Button>
                                        <Button size="sm" variant="outline" className="h-8 text-xs" onClick={() => setActiveInlineForm('standalone')}>
                                            <PlusCircle className="w-3.5 h-3.5 mr-1.5" />Chapter
                                        </Button>
                                    </div>
                                </div>

                                {activeInlineForm === 'module' && renderModuleForm()}
                                {activeInlineForm === 'standalone' && renderChapterForm()}

                                {/* Module list */}
                                <div className="space-y-2">
                                    {sortedModules.map((module, mIdx) => (
                                        <div key={module.id} className="rounded-lg border border-border overflow-hidden bg-card">

                                            {/* Module header row */}
                                            <div className="flex items-center gap-2 px-3 py-2 bg-muted/30 border-b border-border/50">
                                                {/* Reorder */}
                                                <div className="flex flex-col shrink-0">
                                                    <button
                                                        className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                        onClick={() => handleReorderModules(module.id, 'up')}
                                                        disabled={mIdx === 0}
                                                    ><ChevronUp className="w-3.5 h-3.5" /></button>
                                                    <button
                                                        className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                        onClick={() => handleReorderModules(module.id, 'down')}
                                                        disabled={mIdx === sortedModules.length - 1}
                                                    ><ChevronDown className="w-3.5 h-3.5" /></button>
                                                </div>

                                                {/* Number badge */}
                                                <span className="shrink-0 w-5 h-5 rounded bg-primary/15 text-primary text-[10px] font-bold flex items-center justify-center">
                                                    {module.sequence_order}
                                                </span>

                                                {/* Title */}
                                                <span className="flex-1 text-sm font-semibold truncate">{module.title}</span>

                                                {/* Chapter count pill */}
                                                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground shrink-0">
                                                    {module.chapters.length} ch
                                                </span>

                                                {/* Add chapter */}
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 px-2 text-xs shrink-0"
                                                    onClick={() => setActiveInlineForm(activeInlineForm === module.id ? null : module.id)}
                                                >
                                                    <PlusCircle className="w-3.5 h-3.5 mr-1" />Add
                                                </Button>

                                                {/* Delete module */}
                                                {isCreator && !isCollaborator && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive shrink-0"
                                                        onClick={() => setDeleteModuleId(module.id)}
                                                        title="Delete module"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </Button>
                                                )}
                                            </div>

                                            {/* Chapters */}
                                            {module.chapters.length > 0 && (
                                                <div className="divide-y divide-border/40">
                                                    {[...module.chapters]
                                                        .sort((a, b) => a.sequence_order - b.sequence_order)
                                                        .map((chapter, cIdx) => (
                                                            <React.Fragment key={chapter.id}>
                                                                {editingChapterId === chapter.id ? (
                                                                    <div className="px-2">
                                                                        {renderChapterForm(module.id)}
                                                                    </div>
                                                                ) : (
                                                                    <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/20 group">
                                                                        {/* Chapter reorder */}
                                                                        <div className="flex flex-col shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                                                            <button
                                                                                className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                                                onClick={() => handleReorderChapters(module.id, chapter.id, 'up')}
                                                                                disabled={cIdx === 0}
                                                                            ><ChevronUp className="w-3 h-3" /></button>
                                                                            <button
                                                                                className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                                                onClick={() => handleReorderChapters(module.id, chapter.id, 'down')}
                                                                                disabled={cIdx === module.chapters.length - 1}
                                                                            ><ChevronDown className="w-3 h-3" /></button>
                                                                        </div>

                                                                        {/* Index */}
                                                                        <span className="text-[10px] font-mono text-muted-foreground/50 w-6 shrink-0 text-right">
                                                                            {module.sequence_order}.{chapter.sequence_order}
                                                                        </span>

                                                                        {/* Type icon */}
                                                                        <span className="shrink-0">{chapterTypeIcon(chapter.content_type)}</span>

                                                                        {/* Title */}
                                                                        <span className="flex-1 text-sm truncate">{chapter.title}</span>

                                                                        {/* Actions — show on hover */}
                                                                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                                                            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => handleEditChapter(chapter)}>Edit</Button>
                                                                            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-destructive hover:bg-destructive/10"
                                                                                onClick={() => handleDeleteChapter(chapter.id)}>
                                                                                <Trash2 className="w-3 h-3" />
                                                                            </Button>
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </React.Fragment>
                                                        ))
                                                    }
                                                </div>
                                            )}

                                            {/* Empty state */}
                                            {module.chapters.length === 0 && (
                                                <div className="px-4 py-3 text-xs text-muted-foreground text-center bg-background/50">
                                                    No chapters — click <strong>Add</strong> to create one.
                                                </div>
                                            )}

                                            {/* Inline chapter form */}
                                            {activeInlineForm === module.id && (
                                                <div className="border-t border-primary/20 bg-primary/5 p-4">
                                                    {renderChapterForm(module.id)}
                                                </div>
                                            )}
                                        </div>
                                    ))}

                                    {/* Standalone Chapters */}
                                    {training.orphan_chapters?.length > 0 && (
                                        <div className="rounded-lg border border-border overflow-hidden bg-card/50">
                                            <div className="flex items-center gap-2 px-3 py-1.5 bg-muted/20 border-b border-border/40">
                                                <h4 className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground flex-1">Standalone Chapters</h4>
                                            </div>
                                            <div className="divide-y divide-border/40">
                                                {[...training.orphan_chapters]
                                                    .sort((a, b) => a.sequence_order - b.sequence_order)
                                                    .map((chapter, cIdx) => (
                                                        <React.Fragment key={chapter.id}>
                                                            {editingChapterId === chapter.id ? (
                                                                <div className="px-2">
                                                                    {renderChapterForm()}
                                                                </div>
                                                            ) : (
                                                                <div className="flex items-center gap-2 px-3 py-1.5 hover:bg-muted/20 group">
                                                                    <div className="flex flex-col shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                                                                        <button
                                                                            className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                                            onClick={() => handleReorderChapters(undefined, chapter.id, 'up')}
                                                                            disabled={cIdx === 0}
                                                                        ><ChevronUp className="w-3 h-3" /></button>
                                                                        <button
                                                                            className="disabled:opacity-30 text-muted-foreground hover:text-foreground"
                                                                            onClick={() => handleReorderChapters(undefined, chapter.id, 'down')}
                                                                            disabled={cIdx === training.orphan_chapters.length - 1}
                                                                        ><ChevronDown className="w-3 h-3" /></button>
                                                                    </div>
                                                                    <span className="text-[10px] font-mono text-muted-foreground/50 w-6 shrink-0 text-right">{chapter.sequence_order}</span>
                                                                    <span className="shrink-0">{chapterTypeIcon(chapter.content_type)}</span>
                                                                    <span className="flex-1 text-sm truncate">{chapter.title}</span>
                                                                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                                                                        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => handleEditChapter(chapter)}>Edit</Button>
                                                                        <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-destructive hover:bg-destructive/10"
                                                                            onClick={() => handleDeleteChapter(chapter.id)}>
                                                                            <Trash2 className="w-3 h-3" />
                                                                        </Button>
                                                                    </div>
                                                                </div>
                                                            )}
                                                        </React.Fragment>
                                                    ))
                                                }
                                            </div>
                                        </div>
                                    )}

                                    {sortedModules.length === 0 && activeInlineForm !== 'module' && (
                                        <div className="py-12 text-center text-sm text-muted-foreground border-2 border-dashed rounded-lg">
                                            No modules yet. Click <strong>+ Module</strong> to start building your curriculum.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}

            {/* Certificate Preview Modal */}
            {previewModalOpen && selectedTemplate && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
                        <CardHeader className="flex flex-row items-center justify-between p-4 border-b bg-muted/30">
                            <div>
                                <CardTitle className="text-lg">Certificate Preview</CardTitle>
                                <CardDescription>Previewing: {selectedTemplate.name}</CardDescription>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => setPreviewModalOpen(false)}><X className="h-5 w-5" /></Button>
                        </CardHeader>
                        <CardContent className="flex-1 overflow-hidden p-4 bg-muted flex items-center justify-center min-h-0">
                            <div
                                ref={previewContainerRef}
                                className="w-full relative overflow-hidden bg-white shadow-lg"
                                style={{ aspectRatio: '4/3', border: '12px solid var(--muted)', outline: '2px solid var(--border)' }}
                            >
                                <iframe
                                    srcDoc={selectedTemplate?.html_content
                                        ?.replace(/\{\{user_name\}\}/g, 'Jane Doe')
                                        ?.replace(/\{\{full_name\}\}/g, 'Jane Doe')
                                        ?.replace(/\{\{training_title\}\}/g, training.title)
                                        ?.replace(/\{\{completion_date\}\}/g, new Date().toLocaleDateString())
                                        ?.replace(/\{\{issued_date\}\}/g, new Date().toLocaleDateString())
                                        ?.replace(/\{\{certificate_number\}\}/g, 'LMS-PREVIEW-001')
                                        ?? ''}
                                    title="Certificate Preview"
                                    style={{
                                        position: 'absolute',
                                        top: 0,
                                        left: 0,
                                        width: '800px',
                                        height: '600px',
                                        transformOrigin: 'top left',
                                        transform: `scale(${previewScale})`,
                                        border: 'none',
                                        pointerEvents: 'none',
                                    }}
                                />
                            </div>
                        </CardContent>
                        <CardFooter className="p-4 border-t bg-muted/30 flex justify-end">
                            <Button onClick={() => setPreviewModalOpen(false)}>Close Preview</Button>
                        </CardFooter>
                    </Card>
                </div>
            )}


            {/* Delete Chapter Confirm Modal */}
            <Dialog open={!!deleteChapterId} onOpenChange={(open) => { if (!open) setDeleteChapterId(null); }}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Delete Chapter</DialogTitle>
                        <DialogDescription>Are you sure you want to delete this chapter? This action cannot be undone.</DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteChapterId(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={handleConfirmDeleteChapter} disabled={isDeletingChapter}>
                            {isDeletingChapter ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Deleting...</> : 'Delete'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Delete Module Confirm Modal */}
            <Dialog open={!!deleteModuleId} onOpenChange={(open) => { if (!open) setDeleteModuleId(null); }}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Delete Module</DialogTitle>
                        <DialogDescription>Are you sure you want to delete this module and all its chapters? This action cannot be undone.</DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setDeleteModuleId(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={handleConfirmDeleteModule} disabled={isDeletingModule}>
                            {isDeletingModule ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Deleting...</> : 'Delete'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Save Validation Error Modal */}
            <Dialog open={publishErrorOpen} onOpenChange={setPublishErrorOpen}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2 text-destructive">
                            <AlertCircle className="w-5 h-5" /> Cannot Save
                        </DialogTitle>
                        <DialogDescription>Please fix the following issues before saving:</DialogDescription>
                    </DialogHeader>
                    <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                        {publishErrors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                    <DialogFooter>
                        <Button onClick={() => setPublishErrorOpen(false)}>Got it</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

