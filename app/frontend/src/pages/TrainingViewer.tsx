import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import ReactPlayer from 'react-player';

import { authStorage } from '../lib/auth-storage';

import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { ScrollArea } from '../components/ui/scroll-area';
import {
    ChevronLeft, ChevronRight, PlayCircle, CheckCircle2, Lock, HelpCircle,
    Loader2, Award, PanelRightClose, PanelRightOpen, Eye, BookOpen,
    AlertCircle, Trophy, XCircle, CheckCircle, Check, X,
    Video, File as FileIcon, Package, Clock
} from 'lucide-react';
import { Progress as UIProgress } from "../components/ui/progress";
import { AlertModal } from "../components/AlertModal";
import { Checkbox } from "../components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";

import { trainingsApi } from '../api/trainings';
import type { Training, TrainingStructure, Chapter, QuizAnswer, QuizResult } from '../api/trainings';
import { certificatesApi } from '../api/certificates';
import { cn } from '../lib/utils';
import { useAuth } from '../contexts/auth-context';
import DOMPurify from 'dompurify';

// ── Quiz question types ──────────────────────────────────────────────────────

interface QuizOption {
    id: string;
    text: string;
}

interface BaseQuestion {
    id: string;
    /** Display text — API may use `text` or `title` */
    text?: string;
    title?: string;
    description?: string;
    type: string;
    correct_option_id?: string;
    correct_option_ids?: string[];
}

interface MultipleChoiceQuestion extends BaseQuestion {
    type: 'multiple_choice' | 'multiple_select';
    options: QuizOption[];
}

interface TrueFalseQuestion extends BaseQuestion {
    type: 'true_false';
    options?: QuizOption[];
}

interface MatchingQuestion extends BaseQuestion {
    type: 'matching';
    left_items: QuizOption[];
    right_items: QuizOption[];
    options?: QuizOption[];
}

interface OrderingQuestion extends BaseQuestion {
    type: 'ordering';
    options: QuizOption[];
}

type Question =
    | MultipleChoiceQuestion
    | TrueFalseQuestion
    | MatchingQuestion
    | OrderingQuestion;

export const TrainingViewer: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { user, activeMembership } = useAuth();

    // Preview mode: honour ?preview=true only for sysadmins and business managers.
    // Training creators and learners cannot enable preview by manipulating the URL.
    const previewRequested = new URLSearchParams(location.search).get('preview') === 'true';
    const previewMode = new URLSearchParams(location.search).get('mode'); // 'content' | 'simulate'
    const canPreview = user?.is_sysadmin || activeMembership?.is_business_manager || activeMembership?.is_training_creator;
    const isPreview = previewRequested && !!canPreview;
    // Content view: read-only, all answers revealed, no completion UI
    const isContentView = isPreview && previewMode === 'content';

    const [training, setTraining] = useState<Training | null>(null);
    const [structure, setStructure] = useState<TrainingStructure | null>(null);
    const [activeChapter, setActiveChapter] = useState<Chapter | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isCompleting, setIsCompleting] = useState(false);
    const [trainingCompleted, setTrainingCompleted] = useState(false);
    const [certificateId, setCertificateId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    // Quiz State
    const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string[]>>({});
    const [quizSubmitting, setQuizSubmitting] = useState(false);
    const [quizResult, setQuizResult] = useState<QuizResult | null>(null);
    const [currentQuestionIndex, setCurrentQuestionIndex] = useState<number | null>(null);
    const [isReviewMode, setIsReviewMode] = useState(false);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);

    // Navigation Guard & Alert States
    const [alertConfig, setAlertConfig] = useState<{isOpen: boolean, title: string, description: string, confirmText?: string, cancelText?: string, onConfirm?: () => void} | null>(null);

    // Video player state
    const [resumePosition] = useState<number>(0);
    const playerRef = useRef<HTMLVideoElement>(null);
    const milestonesReported = useRef<Set<number>>(new Set());

    // SCORM player state
    const completeChapterRef = useRef<() => void>(() => {});
    const scormFiredRef = useRef(false);

    const closeAlert = () => setAlertConfig(null);

    const handleVideoProgress = useCallback((e: React.SyntheticEvent<HTMLVideoElement>) => {
        const video = e.currentTarget;
        if (!video.duration) return;
        const pct = (video.currentTime / video.duration) * 100;
        if (pct >= 25 && !milestonesReported.current.has(25)) {
            milestonesReported.current.add(25);
        }
        if (pct >= 50 && !milestonesReported.current.has(50)) {
            milestonesReported.current.add(50);
        }
        if (pct >= 75 && !milestonesReported.current.has(75)) {
            milestonesReported.current.add(75);
        }
    }, []);

    // Heartbeat: refresh JWT when remaining lifetime <= 10 min
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const token = authStorage.getToken();
                if (!token) return;
                const resp = await fetch('/api/v1/auth/heartbeat', {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token}` },
                });
                const newToken = resp.headers.get('new_token');
                if (newToken) {
                    authStorage.setToken(newToken);
                }
            } catch {
                // silent fail — user will be redirected on next 401
            }
        }, 60_000);

        return () => clearInterval(interval);
    }, []);

    const showAlert = (title: string, description: string, options?: {confirmText?: string, cancelText?: string, onConfirm?: () => void}) => {
        setAlertConfig({
            isOpen: true,
            title,
            description,
            ...options
        });
    };

    useEffect(() => {
        let active = true;
        if (id) {
            loadTraining(id, active);
        }
        return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id]);

    useEffect(() => {
        setSelectedAnswers({});
        setQuizResult(null);
    }, [activeChapter?.id]);

    const loadTraining = async (trainingId: string, active: boolean = true, silent: boolean = false) => {
        if (!silent) setIsLoading(true);
        setError(null);
        let sData: TrainingStructure | null = null;
        try {
            const tData = await trainingsApi.getTraining(trainingId);
            if (!active) return null;
            setTraining(tData);

            sData = await trainingsApi.getTrainingStructure(trainingId);
            if (!active) return null;
            setStructure(sData);
            setCertificateId(sData.certificate_id || null);

            // Use tData.status (progress_percentage >= 100) as the authoritative completed check.
            // sData.status uses enroll.is_completed which may lag if complete_training was never called.
            const isCompleted = tData.status === 'completed';
            if (isCompleted) {
                setTrainingCompleted(true);
                setIsSidebarOpen(false);
            }

            if (!isCompleted && (!silent || !activeChapter)) {
                if (sData.modules.length > 0) {
                    let foundActive = false;
                    for (const mod of sData.modules) {
                        const uncompleted = mod.chapters.find(c => !c.is_completed);
                        if (uncompleted) {
                            setActiveChapter(uncompleted);
                            foundActive = true;
                            break;
                        }
                    }

                    if (!foundActive) {
                        const firstChapter = sData.modules[0]?.chapters[0];
                        if (firstChapter) {
                            setActiveChapter(firstChapter);
                        } else {
                            setTrainingCompleted(true);
                        }

                        const certs = await trainingsApi.getCertificates();
                        if (!active) return sData;
                        if (certs.some(c => c.training_id === tData.id)) {
                            setTrainingCompleted(true);
                        }
                    }
                } else if (sData.orphan_chapters.length > 0) {
                    const uncompleted = sData.orphan_chapters.find(c => !c.is_completed);
                    if (uncompleted) {
                        setActiveChapter(uncompleted);
                    } else {
                        setActiveChapter(sData.orphan_chapters[0]);

                        const certs = await trainingsApi.getCertificates();
                        if (!active) return sData;
                        if (certs.some(c => c.training_id === tData.id)) {
                            setTrainingCompleted(true);
                        }
                    }
                }
            } else if (!isCompleted) {
                let updatedActive = null;
                for (const mod of sData.modules) {
                    const match = mod.chapters.find(c => c.id === activeChapter?.id);
                    if (match) {
                        updatedActive = match;
                        break;
                    }
                }
                if (!updatedActive) {
                    updatedActive = sData.orphan_chapters.find(c => c.id === activeChapter?.id);
                }
                if (updatedActive) {
                    setActiveChapter(updatedActive);
                }
            }

        } catch (err) {
            console.error("Failed to load training structure", err);
            if (!silent) setError("Failed to load training content.");
        } finally {
            if (active && !silent) setIsLoading(false);
        }
        return sData;
    };

    const findChapterById = (chapterId: string, currentStructure: TrainingStructure | null): Chapter | null => {
        if (!currentStructure) return null;
        for (const mod of currentStructure.modules) {
            const match = mod.chapters.find(c => c.id === chapterId);
            if (match) return match;
        }
        return currentStructure.orphan_chapters.find(c => c.id === chapterId) || null;
    };

    const findNextChapter = (currentId: string, currentStructure: TrainingStructure): Chapter | null => {
        const allChapters: Chapter[] = [];
        currentStructure.modules.forEach(m => allChapters.push(...m.chapters));
        allChapters.push(...currentStructure.orphan_chapters);
        
        const currentIndex = allChapters.findIndex(c => c.id === currentId);
        if (currentIndex !== -1 && currentIndex < allChapters.length - 1) {
            return allChapters[currentIndex + 1];
        }
        return null;
    };

    useEffect(() => {
        if (activeChapter?.content_type === 'QUIZ') {
            setSelectedAnswers({});
            setQuizResult(null);
            setCurrentQuestionIndex(0);
            setIsReviewMode(!!activeChapter.is_completed);
        } else {
            setCurrentQuestionIndex(null);
            setIsReviewMode(false);
        }
    }, [activeChapter?.id, activeChapter?.content_type, activeChapter?.is_completed]);

    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            if (activeChapter?.content_type === 'QUIZ' && !quizResult && !activeChapter.is_completed && Object.keys(selectedAnswers).length > 0) {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [activeChapter, quizResult, selectedAnswers]);

    const handleSyllabusChapterClick = (chapterId: string) => {
        if (chapterId === activeChapter?.id) return;

        if (activeChapter?.content_type === 'QUIZ' && !quizResult && !activeChapter.is_completed && Object.keys(selectedAnswers).length > 0) {
            showAlert(
                "Incomplete Quiz", 
                "You have an active quiz in progress. Leaving this chapter will restart your attempt. Are you sure you want to continue?",
                {
                    confirmText: "Yes, Leave Quiz",
                    cancelText: "Stay",
                    onConfirm: () => {
                        const chapter = findChapterById(chapterId, structure);
                        if (chapter) setActiveChapter(chapter);
                    }
                }
            );
            return;
        }

        const chapter = findChapterById(chapterId, structure);
        if (chapter) setActiveChapter(chapter);
    };

    const handleCompleteChapter = async () => {
        if (!id || !activeChapter || !structure) return;
        if (isPreview) {
            const next = findNextChapter(activeChapter.id, structure);
            if (next) {
                setActiveChapter(next);
            } else {
                setTrainingCompleted(true);
            }
            return;
        }

        setIsCompleting(true);
        try {
            await trainingsApi.completeChapter(id, activeChapter.id);
            const updatedStructure = await loadTraining(id, true, true);
            
            const next = updatedStructure ? findNextChapter(activeChapter.id, updatedStructure) : null;
            if (next) {
                setActiveChapter(next);
                window.scrollTo(0, 0);
            } else {
                await handleFinishCourse();
            }
        } catch (err) {
            console.error("Failed to complete chapter", err);
            alert("Failed to mark chapter as complete. You may need to complete previous chapters first.");
        } finally {
            setIsCompleting(false);
        }
    };

    // Keep ref in sync so SCORM API always calls the latest version
    useEffect(() => {
        completeChapterRef.current = handleCompleteChapter;
    });

    // SCORM 1.2 API — inject into window so the iframe's SCO can call window.parent.API
    useEffect(() => {
        if (activeChapter?.content_type !== 'SCORM') {
            delete (window as Window & { API?: unknown }).API;
            return;
        }
        scormFiredRef.current = false;

        (window as Window & { API?: unknown }).API = {
            LMSInitialize: () => 'true',
            LMSFinish: () => {
                if (!scormFiredRef.current) {
                    scormFiredRef.current = true;
                    setTimeout(() => completeChapterRef.current(), 0);
                }
                return 'true';
            },
            LMSSetValue: (element: string, value: string) => {
                if (element === 'cmi.core.lesson_status' &&
                    (value === 'passed' || value === 'completed') &&
                    !scormFiredRef.current) {
                    scormFiredRef.current = true;
                    setTimeout(() => completeChapterRef.current(), 0);
                }
                return 'true';
            },
            LMSGetValue: (element: string) => {
                if (element === 'cmi.core.student_name') return user?.full_name || '';
                if (element === 'cmi.core.student_id') return user?.id || '';
                if (element === 'cmi.core.lesson_status') return activeChapter.is_completed ? 'completed' : 'not attempted';
                if (element === 'cmi.core.entry') return activeChapter.is_completed ? 'resume' : 'ab-initio';
                return '';
            },
            LMSGetLastError: () => '0',
            LMSGetErrorString: () => '',
            LMSGetDiagnostic: () => '',
            LMSCommit: () => 'true',
        };

        return () => {
            delete (window as Window & { API?: unknown }).API;
        };
    }, [activeChapter?.id, activeChapter?.content_type, activeChapter?.is_completed, user?.full_name, user?.id]);

    const handleFinishCourse = async () => {
        if (!id) return;
        if (isPreview) {
            setTrainingCompleted(true);
            return;
        }
        setIsCompleting(true);
        try {
            const result = await trainingsApi.completeTraining(id);
            setCertificateId(result.certificate_id);
            setTrainingCompleted(true);
            setIsSidebarOpen(false);
        } catch (err) {
            console.error("Failed to finalize training", err);
            alert("Failed to finalize training. Please ensure all chapters are completed.");
        } finally {
            setIsCompleting(false);
        }
    };

    const handleSubmitQuiz = async () => {
        if (!id || !activeChapter || !activeChapter.content_data?.questions) return;

        if (isPreview) {
            setQuizResult({
                score: 100,
                passed: true,
                attempt_number: 1,
                max_attempts: 3,
                is_locked: false
            });
            return;
        }

        const submission: QuizAnswer[] = (activeChapter.content_data.questions as Question[]).map((q) => ({
            question_id: q.id,
            selected_option_ids: selectedAnswers[q.id] || []
        }));

        setQuizSubmitting(true);
        try {
            const result = await trainingsApi.submitQuiz(id, activeChapter.id, { answers: submission });
            setQuizResult(result);
            
            await loadTraining(id, true, true);
            setIsReviewMode(false);
            setCurrentQuestionIndex(null);
        } catch (err) {
            console.error("Failed to submit quiz", err);
            showAlert("Error", "Failed to submit quiz answers. Please try again.");
        } finally {
            setQuizSubmitting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex h-[calc(100vh-4rem)] items-center justify-center">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
        );
    }

    if (error || !training || !structure) {
        return (
            <div className="p-8 text-center max-w-md mx-auto mt-20">
                <div className="bg-destructive/10 text-destructive p-4 rounded-lg mb-4">
                    {error || "Training not found."}
                </div>
                <Button onClick={() => navigate(-1)} variant="outline">Back to Dashboard</Button>
            </div>
        );
    }

    const isExpired = training.status === 'expired';

    const getDueInfo = (): { label: string; isPast: boolean } | null => {
        if (!training.due_date || training.status === 'completed') return null;
        const now = Date.now();
        const due = new Date(training.due_date).getTime();
        const diffMs = due - now;
        if (diffMs <= 0) return { label: 'Past Due', isPast: true };
        const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
        if (diffHours < 24) return { label: `${diffHours}h left`, isPast: false };
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        return { label: `${diffDays}d left`, isPast: false };
    };
    const dueInfo = getDueInfo();

    const renderQuizResultSummary = () => {
        if (!quizResult) return null;

        const { score, passed, attempt_number, max_attempts, is_locked } = quizResult;
        const isUnlimited = max_attempts === 0;

        return (
            <div className="max-w-2xl mx-auto py-8 animate-in zoom-in-95 duration-500">
                <Card className="shadow-2xl border-border/50 overflow-hidden rounded-[2rem] bg-card/50 backdrop-blur-sm border-2">
                    <div className={cn('h-3 w-full', passed ? 'bg-primary shadow-[0_0_20px_rgba(16,185,129,0.4)]' : 'bg-destructive shadow-[0_0_20px_rgba(239,68,68,0.4)]')} />
                    
                    <div className="p-8 md:p-12 flex flex-col items-center gap-10">
                        {/* Status Icon & Animated Background */}
                        <div className="relative">
                            <div className={cn('absolute inset-0 rounded-full blur-3xl opacity-20 animate-pulse', passed ? 'bg-primary' : 'bg-destructive')} />
                            <div className={cn('relative w-32 h-32 rounded-full flex items-center justify-center border-4', passed ? 'bg-primary/10 border-primary/20 text-primary shadow-xl' : 'bg-destructive/10 border-destructive/20 text-destructive shadow-xl')}>
                                {passed ? <Trophy className="w-16 h-16" /> : <XCircle className="w-16 h-16" />}
                            </div>
                        </div>

                        <div className="space-y-4 text-center">
                            <Badge variant="outline" className={cn('px-4 py-1 rounded-full text-[10px] font-black uppercase tracking-[0.2em] border-2', passed ? 'border-primary/30 text-primary bg-primary/10' : 'border-destructive/30 text-destructive bg-destructive/10')}>
                                Assessment {passed ? "Passed" : "Failed"}
                            </Badge>
                            <h2 className="text-5xl font-black text-foreground tracking-tight leading-none">
                                {score}<span className="text-2xl text-muted-foreground ml-1">%</span>
                            </h2>
                            <p className="text-muted-foreground font-medium text-lg max-w-sm mx-auto leading-relaxed">
                                {passed 
                                    ? "Exceptional work! You've mastered all the key objectives for this assessment module." 
                                    : "You didn't reach the required passing threshold. Review the material and try again to improve."}
                            </p>
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-2 gap-4 w-full max-w-md">
                            <div className="p-5 bg-muted rounded-3xl border border-border flex flex-col items-center group hover:bg-background hover:shadow-md transition-all cursor-default">
                                <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-1.5">Attempt No.</span>
                                <span className="text-2xl font-black text-foreground">{attempt_number}</span>
                            </div>
                            <div className="p-5 bg-muted rounded-3xl border border-border flex flex-col items-center group hover:bg-background hover:shadow-md transition-all cursor-default">
                                <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest mb-1.5">Max Limit</span>
                                <span className="text-2xl font-black text-foreground">{isUnlimited ? '∞' : max_attempts}</span>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex flex-col gap-3 w-full max-w-md">
                            {passed ? (
                                <Button 
                                    size="lg" 
                                    onClick={handleCompleteChapter}
                                    className="w-full h-14 rounded-2xl font-black text-lg bg-foreground hover:bg-foreground/90 text-background shadow-xl group"
                                >
                                    Proceed to Next Lesson <ChevronRight className="ml-2 h-5 w-5 group-hover:translate-x-1 transition-transform" />
                                </Button>
                            ) : !is_locked ? (
                                <Button 
                                    size="lg" 
                                    onClick={() => {
                                        setSelectedAnswers({});
                                        setQuizResult(null);
                                        setCurrentQuestionIndex(0);
                                        setIsReviewMode(false);
                                    }}
                                    className="w-full h-14 rounded-2xl font-black text-lg bg-primary hover:bg-primary/90 text-white shadow-xl shadow-primary/20"
                                >
                                    Try Again
                                </Button>
                            ) : null}
                            
                            <Button 
                                variant="outline" 
                                size="lg" 
                                onClick={() => setIsReviewMode(true)}
                                className="w-full h-14 rounded-2xl font-bold text-lg border-2 border-border hover:bg-muted transition-colors"
                            >
                                Review Questions
                            </Button>
                        </div>

                        {is_locked && !passed && (
                            <div className="mt-4 flex items-center gap-3 p-4 bg-destructive/10 text-destructive rounded-2xl border-2 border-destructive/20 w-full max-w-md animate-in slide-in-from-top-4 duration-500">
                                <XCircle className="w-6 h-6 shrink-0" />
                                <div className="text-left">
                                    <p className="text-sm font-black uppercase tracking-tight">Attempts Locked</p>
                                    <p className="text-xs font-medium opacity-80">You've reached the maximum attempt limit. Contact support to request a reset.</p>
                                </div>
                            </div>
                        )}
                    </div>
                </Card>
            </div>
        );
    };

    const renderQuizContent = () => {
        if (!activeChapter || activeChapter.content_type !== 'QUIZ') return null;

        const content = activeChapter.content_data;
        const questions = (content?.questions || []) as Question[];
        const isCompleted = activeChapter.is_completed || !!quizResult;
        
        if (quizResult && !isReviewMode) {
            return renderQuizResultSummary();
        }

        if (isReviewMode) {
            return (
                <div className="space-y-6 max-w-3xl mx-auto animate-in fade-in duration-500">
                    <div className="flex items-center justify-between bg-white p-6 rounded-2xl border border-border/50 shadow-sm sticky top-0 z-10">
                        <div>
                            <h3 className="text-xl font-bold text-foreground">Assessment Review</h3>
                            <p className="text-sm text-muted-foreground font-medium">Reviewing {questions.length} total questions</p>
                        </div>
                        <div className="flex gap-3">
                            {quizResult && !quizResult.is_locked && (
                                <Button variant="outline" size="sm" className="h-10 px-4 font-bold border-2" onClick={() => {
                                    setSelectedAnswers({});
                                    setQuizResult(null);
                                    setCurrentQuestionIndex(0);
                                    setIsReviewMode(false);
                                }}>
                                    Retake Quiz
                                </Button>
                            )}
                            <Button size="sm" className="h-10 px-6 font-bold" onClick={() => setIsReviewMode(false)}>
                                Back to Score
                            </Button>
                        </div>
                    </div>

                    <div className="space-y-6">
                        {(questions as Question[]).map((q, idx) => {
                            const userAnswer = selectedAnswers[q.id] || [];
                            const correctIds = q.correct_option_ids || (q.correct_option_id ? [q.correct_option_id] : []);
                            const isUserCorrect = userAnswer.length === correctIds.length && 
                                               [...userAnswer].sort().every((val, i) => val === [...correctIds].sort()[i]);

                            return (
                                <Card key={q.id} className={cn('border border-border/50 shadow-sm transition-all overflow-hidden', isUserCorrect ? 'bg-primary/5' : 'bg-destructive/5')}>
                                    <CardHeader className="py-4 px-6 flex-row items-center justify-between border-b border-border/30">
                                        <div className="flex items-center gap-3">
                                            <div className={cn('h-8 w-8 rounded-lg flex items-center justify-center shrink-0', isUserCorrect ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive')}>
                                                {isUserCorrect ? <CheckCircle className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
                                            </div>
                                            <CardTitle className="text-base font-bold">Question {idx + 1}</CardTitle>
                                        </div>
                                        <Badge variant={isUserCorrect ? "default" : "destructive"} className={isUserCorrect ? "bg-primary hover:bg-primary" : ""}>
                                            {isUserCorrect ? "Correct" : "Incorrect"}
                                        </Badge>
                                    </CardHeader>
                                    <div className="p-6 space-y-4">
                                        <p className="text-lg font-semibold text-foreground">{q.text || q.title}</p>
                                        <div className="grid grid-cols-1 gap-2.5">
                                            {(q as MultipleChoiceQuestion | TrueFalseQuestion | OrderingQuestion).options?.map((opt: QuizOption, oIdx: number) => {
                                                const isCorrect = correctIds.includes(opt.id);
                                                const isSelected = userAnswer.includes(opt.id);
                                                
                                                let stateClasses = "border-border/50 bg-muted/20 opacity-70";
                                                if (isCorrect) stateClasses = "border-primary bg-primary/5 text-foreground shadow-[0_0_0_1px_rgba(16,185,129,0.2)] opacity-100 ring-1 ring-primary/20";
                                                else if (isSelected && !isCorrect) stateClasses = "border-destructive bg-destructive/5 text-foreground shadow-[0_0_0_1px_rgba(239,68,68,0.2)] opacity-100 ring-1 ring-destructive/20";

                                                return (
                                                    <div key={opt.id} className={cn('flex items-center gap-4 p-3 rounded-xl border transition-all', stateClasses)}>
                                                        <div className={cn('h-6 w-6 rounded-md flex items-center justify-center shrink-0 font-bold text-xs', isCorrect ? 'bg-primary text-primary-foreground' : isSelected ? 'bg-destructive text-destructive-foreground' : 'bg-muted-foreground/10 text-muted-foreground')}>
                                                            {isCorrect ? <Check className="h-3.5 w-3.5" /> : isSelected ? <X className="h-3.5 w-3.5" /> : String.fromCharCode(65 + oIdx)}
                                                        </div>
                                                        <span className="flex-1 font-medium">{opt.text}</span>
                                                        {isCorrect && <CheckCircle className="h-4 w-4 text-primary" />}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </Card>
                            );
                        })}
                    </div>
                </div>
            );
        }

        const qIndex = currentQuestionIndex ?? 0;
        const currentQ = questions[qIndex];
        const maxAttempts = (content?.max_attempts as number) || 0;
        const attemptsCount = activeChapter.attempts_count || 0;
        const isUnlimited = maxAttempts === 0;
        const isLocked = !isCompleted && !isUnlimited && attemptsCount >= maxAttempts;
        const allAnswered = questions.length > 0 && (questions as Question[]).every((q) => (selectedAnswers[q.id]?.length || 0) > 0);

        if (!currentQ) return <div className="p-8 text-center text-muted-foreground font-medium">No questions found.</div>;

        return (
            <div className="max-w-xl mx-auto space-y-8 animate-in slide-in-from-bottom-6 duration-700">
                <div className="space-y-3 bg-muted/20 p-5 rounded-2xl border border-border/50">
                    <div className="flex justify-between text-[10px] font-black text-muted-foreground uppercase tracking-widest">
                        <span className="flex items-center gap-2"><HelpCircle className="w-3.5 h-3.5 text-primary" /> Question {qIndex + 1} of {questions.length}</span>
                        <span>{Math.round(((qIndex + 1) / questions.length) * 100)}% Complete</span>
                    </div>
                    <UIProgress value={((qIndex + 1) / questions.length) * 100} className="h-2 rounded-full overflow-hidden bg-primary/5" />
                </div>

                <Card className="shadow-lg border-border/50 overflow-hidden rounded-3xl group transition-all">
                    <CardHeader className="pb-4 pt-10 px-8">
                        <Badge variant="outline" className="w-fit mx-auto mb-4 border-primary/20 text-primary bg-primary/5 uppercase tracking-tighter font-bold">
                            {currentQ.type === 'true_false' ? 'True / False'
                                : currentQ.type === 'matching' ? 'Matching'
                                : currentQ.type === 'ordering' ? 'Ordering'
                                : 'Multiple Choice'}
                        </Badge>
                        <CardTitle className="text-2xl font-black leading-tight text-center text-foreground">{currentQ.text || currentQ.title}</CardTitle>
                        {currentQ.description && <CardDescription className="text-center text-sm font-medium mt-3 text-muted-foreground">{currentQ.description}</CardDescription>}
                    </CardHeader>
                    <CardContent className="px-8 pb-10 mt-2">
                        {currentQ.type === 'true_false' ? (
                            <div className="flex gap-4">
                                {(['True', 'False'] as const).map(opt => (
                                    <button
                                        key={opt}
                                        onClick={() => {
                                            if (isLocked) return;
                                            setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: [opt.toLowerCase()] });
                                        }}
                                        className={cn(
                                            'flex-1 rounded-lg border px-4 py-3 text-sm font-medium transition-colors',
                                            selectedAnswers[currentQ.id]?.includes(opt.toLowerCase())
                                                ? 'border-primary bg-primary text-primary-foreground'
                                                : 'border-border hover:bg-accent',
                                            isLocked && 'opacity-50 cursor-not-allowed',
                                        )}
                                        disabled={isLocked}
                                    >
                                        {opt}
                                    </button>
                                ))}
                            </div>
                        ) : currentQ.type === 'matching' ? (
                            <div className="space-y-2">
                                {(currentQ.left_items as { id: string; text: string }[] | undefined)?.map(left => (
                                    <div key={left.id} className="flex items-center gap-4">
                                        <span className="w-1/2 text-sm">{left.text}</span>
                                        <select
                                            className="w-1/2 rounded border border-border px-2 py-1 text-sm bg-background"
                                            value={
                                                (selectedAnswers[currentQ.id] ?? [])
                                                    .find((p: string) => p.startsWith(left.id))
                                                    ?.split('::')[1] ?? ''
                                            }
                                            onChange={e => {
                                                if (isLocked) return;
                                                const pairs = (selectedAnswers[currentQ.id] ?? []).filter((p: string) => !p.startsWith(left.id));
                                                setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: [...pairs, `${left.id}::${e.target.value}`] });
                                            }}
                                            disabled={isLocked}
                                        >
                                            <option value="">Select...</option>
                                            {(currentQ.right_items as { id: string; text: string }[] | undefined)?.map(right => (
                                                <option key={right.id} value={right.id}>{right.text}</option>
                                            ))}
                                        </select>
                                    </div>
                                ))}
                            </div>
                        ) : currentQ.type === 'ordering' ? (
                            <div className="space-y-2">
                                {(
                                    selectedAnswers[currentQ.id] ??
                                    (currentQ.options as { id: string }[] | undefined)?.map(o => o.id) ??
                                    []
                                ).map((itemId: string, idx: number, arr: string[]) => {
                                    const item = (currentQ.options as { id: string; text: string }[] | undefined)?.find(o => o.id === itemId);
                                    return (
                                        <div key={itemId} className="flex items-center gap-2 rounded border border-border px-3 py-2 bg-card">
                                            <span className="flex-1 text-sm">{item?.text}</span>
                                            <button
                                                disabled={idx === 0 || isLocked}
                                                onClick={() => {
                                                    const next = [...arr];
                                                    [next[idx - 1], next[idx]] = [next[idx], next[idx - 1]];
                                                    setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: next });
                                                }}
                                                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                                                aria-label="Move up"
                                            >▲</button>
                                            <button
                                                disabled={idx === arr.length - 1 || isLocked}
                                                onClick={() => {
                                                    const next = [...arr];
                                                    [next[idx], next[idx + 1]] = [next[idx + 1], next[idx]];
                                                    setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: next });
                                                }}
                                                className="text-muted-foreground hover:text-foreground disabled:opacity-30"
                                                aria-label="Move down"
                                            >▼</button>
                                        </div>
                                    );
                                })}
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 gap-3">
                                {(currentQ.options as { id: string; text: string }[] | undefined)?.map((opt, oIdx) => {
                                    const isMultiple = (currentQ.correct_option_ids?.length || 0) > 1 || (currentQ.correct_option_id === undefined && currentQ.correct_option_ids === undefined);
                                    const isSelected = selectedAnswers[currentQ.id]?.includes(opt.id);

                                    return (
                                        <div
                                            key={opt.id}
                                            onClick={() => {
                                                if (isLocked) return;
                                                const current = selectedAnswers[currentQ.id] || [];
                                                if (isMultiple) {
                                                    const newVal = current.includes(opt.id)
                                                        ? current.filter(id => id !== opt.id)
                                                        : [...current, opt.id];
                                                    setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: newVal });
                                                } else {
                                                    setSelectedAnswers({ ...selectedAnswers, [currentQ.id]: [opt.id] });
                                                }
                                            }}
                                            className={cn(
                                                'flex items-center gap-4 p-4 rounded-2xl border-2 transition-all cursor-pointer select-none group/option',
                                                isSelected
                                                    ? 'border-primary bg-primary/5 shadow-md ring-1 ring-primary/20'
                                                    : 'border-border/60 bg-muted/10 hover:border-primary/40 hover:bg-muted/30',
                                                isLocked && 'opacity-50 cursor-not-allowed',
                                            )}
                                        >
                                            <div className={cn(
                                                'h-8 w-8 rounded-lg flex items-center justify-center shrink-0 font-black text-xs transition-all',
                                                isSelected ? 'bg-primary text-white scale-110' : 'bg-muted-foreground/10 text-muted-foreground group-hover/option:bg-primary/20 group-hover/option:text-primary',
                                            )}>
                                                {String.fromCharCode(65 + oIdx)}
                                            </div>
                                            <span className={cn('text-base font-bold transition-all', isSelected ? 'text-primary' : 'text-foreground')}>
                                                {opt.text}
                                            </span>
                                            <div className="ml-auto">
                                                {isMultiple ? (
                                                    <Checkbox checked={isSelected} className="h-5 w-5 rounded-md pointer-events-none data-[state=checked]:bg-primary data-[state=checked]:border-primary" />
                                                ) : (
                                                    <div className={cn('h-5 w-5 rounded-full border-2 flex items-center justify-center transition-all', isSelected ? 'border-primary bg-primary' : 'border-muted-foreground/30')}>
                                                        {isSelected && <div className="h-2 w-2 bg-white rounded-full" />}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <div className="flex justify-between items-center gap-4 px-2">
                    <Button
                        variant="ghost"
                        size="lg"
                        className="rounded-xl h-12 font-bold text-muted-foreground hover:bg-muted"
                        onClick={() => setCurrentQuestionIndex(Math.max(0, qIndex - 1))}
                        disabled={qIndex === 0 || quizSubmitting}
                    >
                        <ChevronLeft className="h-5 w-5 mr-1" /> Previous
                    </Button>

                    {qIndex < questions.length - 1 ? (
                        <Button
                            size="lg"
                            className="rounded-xl h-12 px-10 font-bold shadow-lg shadow-primary/20 group hover:translate-x-1 transition-transform"
                            onClick={() => setCurrentQuestionIndex(qIndex + 1)}
                            disabled={!selectedAnswers[currentQ.id]?.length || quizSubmitting}
                        >
                            Continue <ChevronRight className="h-5 w-5 ml-1 transition-transform group-hover:translate-x-1" />
                        </Button>
                    ) : (
                        <Button
                            size="lg"
                            onClick={handleSubmitQuiz}
                            disabled={!allAnswered || quizSubmitting || isLocked}
                            className="rounded-xl h-12 px-12 font-black shadow-lg shadow-primary/30"
                        >
                            {quizSubmitting ? <Loader2 className="h-5 w-5 mr-2 animate-spin" /> : <Check className="h-5 w-5 mr-2" />}
                            Process Results
                        </Button>
                    )}
                </div>

                {isLocked && (
                    <div className="p-6 bg-destructive/5 border border-destructive/20 rounded-2xl flex items-center gap-5 text-destructive animate-in bounce-in duration-500">
                        <div className="h-12 w-12 bg-destructive/10 rounded-full flex items-center justify-center shrink-0">
                            <AlertCircle className="h-6 w-6" />
                        </div>
                        <div className="flex-1">
                            <p className="font-black text-xl">Attempts Exhausted</p>
                            <p className="opacity-90 font-medium text-sm">You have reached the limit of {maxAttempts} attempts. Please contact your instructor for a reset.</p>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // Read-only quiz renderer for content view mode — shows all questions with correct answers highlighted
    const renderQuizContentView = () => {
        if (!activeChapter || activeChapter.content_type !== 'QUIZ') return null;
        const questions = (activeChapter.content_data?.questions || []) as Question[];
        return (
            <div className="space-y-6 max-w-3xl mx-auto animate-in fade-in duration-500">
                <div className="flex items-center gap-3 bg-amber-500/10 border border-amber-500/30 rounded-xl px-4 py-3">
                    <CheckCircle className="w-4 h-4 text-amber-600 shrink-0" />
                    <p className="text-sm font-medium text-amber-700 dark:text-amber-400">Correct answers are highlighted. This view does not record any responses.</p>
                </div>
                <div className="space-y-5">
                    {questions.map((q, idx) => {
                        const correctIds = q.correct_option_ids || (q.correct_option_id ? [q.correct_option_id] : []);
                        return (
                            <Card key={q.id} className="border-border/50 shadow-sm overflow-hidden">
                                <CardHeader className="py-4 px-6 border-b border-border/30">
                                    <div className="flex items-center gap-3">
                                        <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 text-xs font-bold text-primary">{idx + 1}</div>
                                        <CardTitle className="text-base font-semibold">{q.text || q.title}</CardTitle>
                                    </div>
                                </CardHeader>
                                <div className="p-5 space-y-2">
                                    {(q as MultipleChoiceQuestion | TrueFalseQuestion | OrderingQuestion).options?.map((opt: QuizOption, oIdx: number) => {
                                        const isCorrect = correctIds.includes(opt.id);
                                        return (
                                            <div key={opt.id} className={cn(
                                                'flex items-center gap-3 p-3 rounded-lg border transition-all',
                                                isCorrect
                                                    ? 'border-primary/40 bg-primary/5 text-foreground'
                                                    : 'border-border/40 bg-muted/20 text-muted-foreground',
                                            )}>
                                                <div className={cn('h-6 w-6 rounded-md flex items-center justify-center shrink-0 font-bold text-xs', isCorrect ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground')}>
                                                    {isCorrect ? <Check className="h-3.5 w-3.5" /> : String.fromCharCode(65 + oIdx)}
                                                </div>
                                                <span className={cn('flex-1 text-sm font-medium', isCorrect && 'text-foreground')}>{opt.text}</span>
                                                {isCorrect && <CheckCircle className="h-4 w-4 text-primary shrink-0" />}
                                            </div>
                                        );
                                    })}
                                </div>
                            </Card>
                        );
                    })}
                </div>
            </div>
        );
    };

    const totalCount = structure ? (structure.total_chapters || 0) : 0;
    const totalProgress = totalCount > 0 
        ? Math.round((structure.modules.reduce((acc, mod) => acc + mod.chapters.filter(c => c.is_completed).length, 0) + structure.orphan_chapters.filter(c => c.is_completed).length) / totalCount * 100)
        : 0;

    return (
        <div className="flex h-[calc(100vh-4rem)] bg-background overflow-hidden relative">
            {!isSidebarOpen && (
                <Button 
                    variant="outline" 
                    size="icon" 
                    className="absolute right-4 top-4 z-40 rounded-full shadow-lg bg-background"
                    onClick={() => setIsSidebarOpen(true)}
                >
                    <PanelRightOpen className="w-5 h-5" />
                </Button>
            )}

            <div className={cn('flex-1 flex flex-col overflow-hidden transition-all duration-300', isSidebarOpen ? 'mr-0' : '')}>
                {isContentView && (
                    <div className="bg-amber-500 text-white px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center justify-between gap-2 z-30">
                        <button onClick={() => navigate(-1)} className="flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity">
                            <ChevronLeft className="w-3.5 h-3.5" /> Back
                        </button>
                        <span className="flex items-center gap-2"><BookOpen className="w-4 h-4" />CONTENT REVIEW — All chapters unlocked. Correct answers shown. No progress recorded.</span>
                        <span className="w-14" />
                    </div>
                )}
                {isPreview && !isContentView && (
                    <div className="bg-primary/90 text-primary-foreground px-4 py-1.5 text-[10px] font-bold uppercase tracking-widest flex items-center justify-between gap-2 z-30">
                        <button onClick={() => navigate(-1)} className="flex items-center gap-1 opacity-80 hover:opacity-100 transition-opacity">
                            <ChevronLeft className="w-3.5 h-3.5" /> Back
                        </button>
                        <span className="flex items-center gap-2"><Eye className="w-4 h-4" />SIMULATION MODE — Experiencing training as a learner. No progress recorded.</span>
                        <span className="w-14" />
                    </div>
                )}
                
                <ScrollArea className="flex-1">
                    <div className="max-w-4xl mx-auto p-4 md:p-10 pb-32">
                        {trainingCompleted ? (
                            <div className="flex flex-col items-center py-16 animate-in zoom-in-95 duration-500 max-w-lg mx-auto text-center">
                                <div className="w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6">
                                    <Award className="w-12 h-12 text-primary" />
                                </div>
                                <h2 className="text-3xl font-bold mb-2">Training Completed!</h2>
                                <p className="text-muted-foreground mb-8 text-base">
                                    Congratulations on finishing <span className="font-semibold text-foreground">"{training.title}"</span>.
                                </p>

                                {/* Completion details */}
                                <div className="w-full grid grid-cols-2 gap-3 mb-8">
                                    <div className="rounded-xl border bg-card p-4 text-left">
                                        <p className="text-xs text-muted-foreground mb-1">Chapters Completed</p>
                                        <p className="text-xl font-bold text-foreground">
                                            {training.completed_chapters ?? structure?.total_chapters ?? '–'} / {training.total_chapters ?? structure?.total_chapters ?? '–'}
                                        </p>
                                    </div>
                                    <div className="rounded-xl border bg-card p-4 text-left">
                                        <p className="text-xs text-muted-foreground mb-1">Completion Date</p>
                                        <p className="text-xl font-bold text-foreground">
                                            {training.completed_at
                                                ? new Date(training.completed_at).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
                                                : 'Today'}
                                        </p>
                                    </div>
                                </div>

                                <div className="flex flex-col sm:flex-row gap-3 w-full">
                                    {certificateId && (
                                        <Button
                                            size="lg"
                                            variant="default"
                                            onClick={() => certificatesApi.viewCertificatePdf(certificateId)}
                                            className="h-11 px-8 shadow-md gap-2 flex-1"
                                        >
                                            <Award className="w-5 h-5" /> View Certificate
                                        </Button>
                                    )}
                                    <Button size="lg" variant="outline" onClick={() => navigate('/dashboard')} className="h-11 px-8 shadow-md flex-1">
                                        Back to Dashboard
                                    </Button>
                                </div>
                            </div>
                        ) : activeChapter ? (
                            <div className="space-y-6">
                                <div className="space-y-4">
                                    <div className="flex items-center gap-3">
                                        <Badge variant="secondary" className="px-2.5 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-widest text-primary bg-primary/10 border-transparent">
                                            {activeChapter.content_type === 'QUIZ' ? 'Module Assessment' : activeChapter.content_type === 'VIDEO' ? 'Video Lesson' : 'Learning Module'}
                                        </Badge>
                                        {activeChapter.is_completed && <Badge className="bg-primary text-primary-foreground border-0 text-[10px] uppercase font-bold">Completed</Badge>}
                                    </div>
                                    <h1 className="text-3xl font-bold tracking-tight">{activeChapter.title}</h1>
                                </div>

                                {activeChapter.content_type === 'QUIZ' ? (
                                    isContentView ? renderQuizContentView() : renderQuizContent()
                                ) : (
                                    <div className="space-y-8 animate-in fade-in duration-500">
                                        {activeChapter.content_type === 'VIDEO' && (activeChapter.content_data?.url || activeChapter.video_url) && (
                                            <div className="aspect-video w-full rounded-2xl overflow-hidden bg-black shadow-xl border border-border/50">
                                                <ReactPlayer
                                                    ref={playerRef}
                                                    src={(activeChapter.content_data?.url as string) ?? activeChapter.video_url ?? ''}
                                                    width="100%"
                                                    height="100%"
                                                    controls
                                                    onTimeUpdate={handleVideoProgress}
                                                    onLoadedData={() => {
                                                        if (resumePosition > 0 && playerRef.current) {
                                                            playerRef.current.currentTime = resumePosition;
                                                        }
                                                    }}
                                                />
                                            </div>
                                        )}

                                        {activeChapter.content_type === 'PDF' && (activeChapter.content_data?.url || activeChapter.video_url) && (
                                            <div className="w-full h-[70vh] rounded-lg overflow-hidden border border-border/50">
                                                <iframe
                                                    src={(activeChapter.content_data?.url as string) ?? activeChapter.video_url ?? ''}
                                                    title={activeChapter.title}
                                                    className="w-full h-full"
                                                    aria-label={`PDF: ${activeChapter.title}`}
                                                />
                                            </div>
                                        )}

                                        {activeChapter.content_type === 'SCORM' && !!activeChapter.content_data?.index_url && (
                                            <div className="w-full rounded-2xl overflow-hidden border border-border/50 shadow-xl">
                                                <iframe
                                                    src={activeChapter.content_data.index_url as string}
                                                    title={activeChapter.title}
                                                    className="w-full"
                                                    style={{ height: '70vh', border: 'none' }}
                                                    allow="fullscreen"
                                                    aria-label={`SCORM: ${activeChapter.title}`}
                                                />
                                            </div>
                                        )}

                                        <div className="py-6 space-y-6">
                                            {!!activeChapter.content_data?.description && (
                                                <div className="p-5 bg-muted/20 border border-border/50 rounded-2xl">
                                                    <h3 className="text-sm font-bold text-foreground mb-2 uppercase tracking-tight">Lesson Overview</h3>
                                                    <p className="text-muted-foreground text-sm leading-relaxed whitespace-pre-wrap">{activeChapter.content_data.description as React.ReactNode}</p>
                                                </div>
                                            )}

                                            <div className="prose max-w-none text-foreground font-medium leading-relaxed">
                                                <div dangerouslySetInnerHTML={{
                                                    __html: DOMPurify.sanitize(
                                                        ((activeChapter.content_data?.text as string) || activeChapter.content || (activeChapter.content_type === 'VIDEO' ? '' : 'No content provided for this lesson.'))?.replace(/\n/g, '<br/>') ?? '',
                                                        { USE_PROFILES: { html: true } }
                                                    )
                                                }} />
                                            </div>
                                        </div>

                                        <div className="bg-muted/30 p-4 rounded-xl border flex items-center justify-between gap-4">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-10 px-4"
                                                onClick={() => {
                                                    const allChapters: Chapter[] = [];
                                                    structure.modules.forEach(m => allChapters.push(...m.chapters));
                                                    allChapters.push(...structure.orphan_chapters);
                                                    const idx = allChapters.findIndex(c => c.id === activeChapter.id);
                                                    if (idx > 0) setActiveChapter(allChapters[idx - 1]);
                                                }}
                                                disabled={structure.modules[0]?.chapters[0]?.id === activeChapter.id}
                                            >
                                                <ChevronLeft className="w-4 h-4 mr-2" /> Previous
                                            </Button>

                                            {isContentView ? (
                                                // Content view: plain Next with no completion side-effect
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="h-10 px-6"
                                                    onClick={() => {
                                                        const next = findNextChapter(activeChapter.id, structure);
                                                        if (next) setActiveChapter(next);
                                                    }}
                                                    disabled={!findNextChapter(activeChapter.id, structure)}
                                                >
                                                    Next <ChevronRight className="w-4 h-4 ml-2" />
                                                </Button>
                                            ) : activeChapter.content_type === 'SCORM' && !activeChapter.is_completed ? (
                                                <Button
                                                    variant="default"
                                                    size="sm"
                                                    className="h-10 px-6 shadow-sm"
                                                    onClick={handleCompleteChapter}
                                                    disabled={isCompleting || isExpired}
                                                >
                                                    {isCompleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
                                                    Mark Complete
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant="default"
                                                    size="sm"
                                                    className="h-10 px-6 shadow-sm"
                                                    onClick={handleCompleteChapter}
                                                    disabled={isCompleting || isExpired}
                                                >
                                                    {isCompleting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                                                    {findNextChapter(activeChapter.id, structure) ? 'Next Lesson' : 'Finish Course'} <ChevronRight className="w-4 h-4 ml-2" />
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : null}
                    </div>
                </ScrollArea>
            </div>

            {!trainingCompleted && isSidebarOpen && (
                <div className="w-80 border-l bg-background flex flex-col animate-in slide-in-from-right duration-300">
                    <div className="p-3 border-b space-y-2">
                        <div className="flex items-center justify-between">
                            <h2 className="font-semibold text-sm">Course Content</h2>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-muted-foreground"
                                onClick={() => setIsSidebarOpen(false)}
                            >
                                <PanelRightClose className="w-4 h-4" />
                            </Button>
                        </div>
                        {isContentView ? (
                            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                                {totalCount} chapter{totalCount !== 1 ? 's' : ''} — content review
                            </p>
                        ) : (
                            <div className="space-y-1">
                                <div className="flex justify-between text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                                    <span>Progress</span>
                                    <span className="text-primary">{totalProgress}%</span>
                                </div>
                                <UIProgress value={totalProgress} className="h-1" />
                            </div>
                        )}
                        {dueInfo && (
                            <div className={cn(
                                'flex items-center gap-1.5 text-[10px] font-semibold mt-1',
                                dueInfo.isPast ? 'text-destructive' : 'text-muted-foreground'
                            )}>
                                <Clock className="w-3 h-3 shrink-0" />
                                {dueInfo.isPast
                                    ? `Past Due · ${new Date(training.due_date!).toLocaleDateString()}`
                                    : `Due ${new Date(training.due_date!).toLocaleDateString()} · ${dueInfo.label}`}
                            </div>
                        )}
                    </div>

                    <ScrollArea className="flex-1">
                        <Accordion type="multiple" defaultValue={structure.modules.map(m => m.id)} className="w-full">
                            {structure.modules.map((module) => {
                                const moduleChapters = module.chapters || [];
                                const completedInModule = moduleChapters.filter(c => c.is_completed).length;
                                const totalInModule = moduleChapters.length;
                                const moduleComplete = totalInModule > 0 && completedInModule === totalInModule;
                                return (
                                <AccordionItem key={module.id} value={module.id} className="border-b last:border-0">
                                    <AccordionTrigger className="px-3 py-2 hover:bg-muted/30 hover:no-underline font-semibold text-[11px] uppercase tracking-wider text-muted-foreground/80">
                                        <div className="flex items-center gap-2 flex-1 min-w-0">
                                            {moduleComplete ? (
                                                <CheckCircle2 className="w-3.5 h-3.5 text-primary shrink-0" />
                                            ) : (
                                                <span className="w-3.5 h-3.5 rounded-full border border-muted-foreground/40 shrink-0 flex items-center justify-center text-[8px] font-bold text-muted-foreground/60">
                                                    {completedInModule}
                                                </span>
                                            )}
                                            <span className="truncate flex-1 text-left">{module.title}</span>
                                            <span className={cn('text-[9px] font-bold normal-case tracking-normal shrink-0', moduleComplete ? 'text-primary' : 'text-muted-foreground/60')}>
                                                {completedInModule}/{totalInModule}
                                            </span>
                                        </div>
                                    </AccordionTrigger>
                                    <AccordionContent className="pb-0">
                                        {module.chapters.map((ch) => {
                                            const isActive = activeChapter?.id === ch.id;
                                            const allChapters: Chapter[] = [];
                                            structure.modules.forEach(m => allChapters.push(...m.chapters));
                                            if (structure.orphan_chapters) allChapters.push(...structure.orphan_chapters);
                                            const firstUncompleted = allChapters.find(c => !c.is_completed);
                                            const isLocked = !isPreview && !ch.is_completed && firstUncompleted?.id !== ch.id;

                                            return (
                                                <button
                                                    key={ch.id}
                                                    onClick={() => !isLocked && handleSyllabusChapterClick(ch.id)}
                                                    disabled={isLocked}
                                                    className={cn(
                                                        'w-full text-left px-3 py-2 flex items-start gap-2.5 transition-colors group relative',
                                                        isActive
                                                            ? 'bg-primary/5 text-primary'
                                                            : isLocked ? 'opacity-40 cursor-not-allowed' : 'hover:bg-muted/50'
                                                    )}
                                                >
                                                    {isActive && <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary" />}
                                                    <div className="mt-0.5 shrink-0">
                                                        {ch.is_completed ? (
                                                            <CheckCircle2 className="w-4 h-4 text-primary" />
                                                        ) : isLocked ? (
                                                            <Lock className="w-4 h-4 text-muted-foreground/40" />
                                                        ) : isActive ? (
                                                            <div className="w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                                                                <PlayCircle className="w-3 h-3 text-white" />
                                                            </div>
                                                        ) : (
                                                            <div className="w-4 h-4 rounded-full border-2 border-muted-foreground/30 group-hover:border-primary/50" />
                                                        )}
                                                    </div>
                                                    <div className="flex-1 overflow-hidden">
                                                        <p className={cn('text-[13px] font-medium leading-tight', isActive ? 'text-primary' : 'text-foreground')}>
                                                            {ch.title}
                                                        </p>
                                                        <div className="flex items-center gap-2 mt-0.5">
                                                            <span className="text-[10px] font-medium text-muted-foreground flex items-center gap-1">
                                                                {ch.content_type === 'QUIZ' ? <HelpCircle className="w-3 h-3" /> : ch.content_type === 'VIDEO' ? <Video className="w-3 h-3" /> : ch.content_type === 'SCORM' ? <Package className="w-3 h-3" /> : <FileIcon className="w-3 h-3" />}
                                                                {ch.content_type === 'QUIZ' ? 'Quiz' : ch.content_type === 'VIDEO' ? 'Video' : ch.content_type === 'SCORM' ? 'SCORM' : 'Article'}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </button>
                                            );
                                        })}
                                    </AccordionContent>
                                </AccordionItem>
                                );
                            })}
                        </Accordion>
                    </ScrollArea>
                </div>
            )}

            {alertConfig && (
                <AlertModal
                    isOpen={alertConfig.isOpen}
                    title={alertConfig.title}
                    description={alertConfig.description}
                    onClose={closeAlert}
                    onConfirm={alertConfig.onConfirm}
                    confirmText={alertConfig.confirmText}
                    cancelText={alertConfig.cancelText}
                />
            )}
        </div>
    );
};
