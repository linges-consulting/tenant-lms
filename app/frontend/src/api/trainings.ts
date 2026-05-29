import { client as apiClient } from './client';

export interface Chapter {
    id: string;
    title: string;
    content_type: string;
    content_data: Record<string, unknown>;
    sequence_order: number;
    module_id?: string;
    is_completed?: boolean;
    video_url?: string;
    content?: string;
    attempts_count?: number;
}

export interface TrainingCollaborator {
    user_id: string;
}

export interface TrainingAuditLog {
    id: string;
    user_id: string;
    action: string;
    entity_type: string;
    entity_id: string;
    metadata_json: Record<string, unknown>;
    created_at: string;
    user_name?: string;
}

export interface Module {
    id: string;
    title: string;
    sequence_order: number;
    chapters: Chapter[];
}

export interface Training {
    id: string;
    title: string;
    description?: string;
    category?: string;
    duration?: string;
    thumbnail?: string | null;
    version: number;
    is_published: boolean;
    is_ready: boolean;
    is_archived: boolean;
    lifecycle_status?: 'draft' | 'ready' | 'published' | 'archived';
    requires_certificate: boolean;
    template_id?: string;
    tenant_id: string;
    created_by_id?: string;
    creator_name?: string;
    // Progress fields
    progress_percentage?: number;
    completed_chapters?: number;
    total_chapters?: number;
    status?: 'not_started' | 'in_progress' | 'completed' | 'expired';
    certificate_id?: string;
    completed_at?: string;
    collaborators: TrainingCollaborator[];
    structure_type?: 'flat' | 'modular';
    content_expires_at?: string | null;  // creator-set content expiry (auto-archive trigger)
    due_date?: string | null;             // per-user assignment due date (manager-set)
}

export interface TrainingHistorySnapshot {
    id: string;
    tenant_id: string;
    training_id: string;
    version: number;
    snapshot: TrainingStructure;
    created_at: string;
}

export interface TrainingStructure extends Training {
    modules: Module[];
    orphan_chapters: Chapter[]; // standalone
    total_chapters?: number;
}

export interface TrainingAssignment {
    id: string;
    training_id: string;
    user_id?: string;
    group_id?: string;
    user_name?: string;
    group_name?: string;
    due_date?: string;
    assigned_at: string;
}

export interface BulkAssignmentCreate {
    user_ids?: string[];
    group_ids?: string[];
    due_date?: string;
}

export interface Certificate {
    id: string;
    training_id: string;
    training_title?: string;
    is_completed: boolean;
    completed_at?: string;
    certificate_url?: string;
    certificate_id?: string;
    enrolled_at: string;
}

export interface QuizAnswer {
    question_id: string;
    selected_option_ids: string[];
}

export interface QuizSubmission {
    answers: QuizAnswer[];
}

export interface QuizResult {
    score: number;
    passed: boolean;
    attempt_number: number;
    max_attempts: number;
    is_locked: boolean;
    correct_answers?: Record<string, string[]>;
}

export interface QuizAttemptsSummaryUser {
    user_id: string;
    name: string;
    email: string;
    attempts: number;
}

export interface QuizAttemptsSummaryChapter {
    chapter_id: string;
    chapter_title: string;
    max_attempts: number;
    users_at_limit: QuizAttemptsSummaryUser[];
}

// Learner endpoints
export const trainingsApi = {
    getPublishedTrainings: (filters?: { category?: string; status?: string }) =>
        apiClient.get<Training[]>('/trainings', { params: filters as Record<string, string> | undefined }),

    getTraining: (id: string) =>
        apiClient.get<Training>(`/trainings/${id}`),

    getTrainingStructure: (id: string) =>
        apiClient.get<TrainingStructure>(`/trainings/${id}/structure`),

    completeChapter: (trainingId: string, chapterId: string) =>
        apiClient.post<{ status: string, chapter_id: string }>(`/trainings/${trainingId}/chapters/${chapterId}/complete`),

    completeTraining: (trainingId: string) =>
        apiClient.post<{ status: string, certificate_id: string, requires_certificate: boolean }>(`/trainings/${trainingId}/complete-training`),

    submitQuiz: (trainingId: string, chapterId: string, submission: QuizSubmission) =>
        apiClient.post<QuizResult>(`/trainings/${trainingId}/chapters/${chapterId}/submit-quiz`, submission),

    getCertificates: () =>
        apiClient.get<Certificate[]>('/user-report/me/certificates'),
};

// Manager endpoints
export const managerTrainingsApi = {
    getManagerTrainings: () =>
        apiClient.get<Training[]>('/trainings/manager'),

    createTraining: (data: Partial<Training>) =>
        apiClient.post<Training>('/trainings', data),

    updateTraining: (id: string, data: Partial<Training>) =>
        apiClient.put<Training>(`/trainings/${id}`, data),

    publishTraining: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/publish`),

    unpublishTraining: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/unpublish`),

    getTrainingCompletionCount: (id: string) =>
        apiClient.get<{ completed_count: number; assigned_count: number }>(`/trainings/${id}/completion-count`),

    getTrainingHistory: (id: string) =>
        apiClient.get<TrainingHistorySnapshot[]>(`/trainings/${id}/history`),

    createModule: (trainingId: string, data: { title: string, sequence_order: number }) =>
        apiClient.post<Module>(`/trainings/${trainingId}/modules`, data),

    createChapter: (trainingId: string, data: { title: string, content_type: string, content_data: Record<string, unknown>, sequence_order: number, module_id?: string }) =>
        apiClient.post<Chapter>(`/trainings/${trainingId}/chapters`, data),

    uploadChapterContent: (trainingId: string, chapterId: string, file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        return apiClient.post<Chapter>(`/trainings/${trainingId}/chapters/${chapterId}/upload`, formData);
    },

    uploadBanner: (trainingId: string, file: File) => {
        const formData = new FormData();
        formData.append('file', file);
        return apiClient.post<Training>(`/trainings/${trainingId}/banner`, formData);
    },

    deleteTraining: (id: string) =>
        apiClient.delete(`/trainings/${id}`),

    bulkAssign: (trainingId: string, data: BulkAssignmentCreate) =>
        apiClient.post<{ message: string, count: number }>(`/trainings/${trainingId}/assignments/bulk`, data),

    listAssignments: (trainingId: string) =>
        apiClient.get<TrainingAssignment[]>(`/trainings/${trainingId}/assignments`),

    deleteAssignment: (assignmentId: string) =>
        apiClient.delete(`/trainings/assignments/${assignmentId}`),

    updateAssignment: (assignmentId: string, data: { due_date: string | null }) =>
        apiClient.patch<TrainingAssignment>(`/trainings/assignments/${assignmentId}`, data),

    reorderModules: (trainingId: string, items: { id: string, sequence_order: number }[]) =>
        apiClient.post(`/trainings/${trainingId}/modules/reorder`, { items }),

    reorderChapters: (trainingId: string, moduleId: string | undefined, items: { id: string, sequence_order: number }[]) =>
        apiClient.post(`/trainings/${trainingId}/modules/${moduleId || 'orphan'}/chapters/reorder`, { items }),

    updateChapter: (trainingId: string, chapterId: string, data: Partial<{ title: string; content_type: string; content_data: Record<string, unknown> }>) =>
        apiClient.patch<Chapter>(`/trainings/${trainingId}/chapters/${chapterId}`, data),

    deleteChapter: (trainingId: string, chapterId: string) =>
        apiClient.delete(`/trainings/${trainingId}/chapters/${chapterId}`),

    deleteModule: (trainingId: string, moduleId: string) =>
        apiClient.delete(`/trainings/${trainingId}/modules/${moduleId}`),

    markReady: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/mark-ready`),

    sendToDraft: (id: string) =>
        apiClient.post<Training>(`/trainings/${id}/send-to-draft`),

    managerRevertToDraft: (id: string, comment: string) =>
        apiClient.post<Training>(`/trainings/${id}/manager-revert-to-draft`, { comment }),

    archiveTraining: (id: string) =>
        apiClient.post<{ status: string, message: string }>(`/trainings/${id}/archive`),

    getTrainingAudit: (id: string) =>
        apiClient.get<TrainingAuditLog[]>(`/trainings/${id}/audit`),

    addCollaborators: (id: string, userIds: string[]) =>
        apiClient.post<TrainingCollaborator[]>(`/trainings/${id}/collaborators`, userIds),

    removeCollaborator: (id: string, userId: string) =>
        apiClient.delete(`/trainings/${id}/collaborators/${userId}`),

    cloneTraining: (trainingId: string) =>
        apiClient.post<Training>(`/trainings/${trainingId}/clone`),

    getQuizAttemptsSummary: (trainingId: string) =>
        apiClient.get<QuizAttemptsSummaryChapter[]>(`/trainings/${trainingId}/quiz-attempts-summary`),

    resetUserQuizAttempts: (trainingId: string, chapterId: string, userId: string) =>
        apiClient.post<{ message: string }>(`/trainings/${trainingId}/chapters/${chapterId}/quiz/reset/${userId}`),

    exportScorm: async (trainingId: string, title: string) => {
        const blob = await apiClient.getBlob(`/trainings/${trainingId}/export-scorm`);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title.replace(/[^a-zA-Z0-9-_]/g, '_')}_scorm.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },
};
