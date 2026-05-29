import { client } from './client';

export interface TrainingListItem {
  id: string;
  title: string;
  category: string;
  is_published: boolean;
  creator_id: string | null;
  creator_name: string;
  updated_at: string | null;
  enrolled_count: number;
  completed_count: number;
  completion_pct: number;
  overdue_count: number;
  lockout_count: number;
}

export interface QuizChapterStat {
  chapter_id: string;
  chapter_title: string;
  max_attempts: number;
  attempted_count: number;
  pass_count: number;
  pass_rate: number;
  avg_score: number;
  avg_attempts_to_pass: number;
  locked_count: number;
}

export interface EmployeeQuizAttempt {
  chapter_id: string;
  attempt_count: number;
  max_attempts: number;
  passed: boolean;
}

export interface EmployeeSummary {
  user_id: string;
  username: string;
  full_name: string;
  email: string;
  status: 'completed' | 'in_progress' | 'overdue' | 'not_started' | 'locked';
  due_date: string | null;
  completed_at: string | null;
  locked_quiz_count: number;
  quiz_attempts: EmployeeQuizAttempt[];
}

export interface TrainingDetailAnalytics {
  training_id: string;
  title: string;
  category: string;
  is_published: boolean;
  creator_name: string;
  enrolled_count: number;
  completed_count: number;
  completion_pct: number;
  overdue_count: number;
  lockout_count: number;
  due_soon_7d: number;
  due_soon_14d: number;
  due_soon_30d: number;
  quiz_chapters: QuizChapterStat[];
  employees: EmployeeSummary[];
}

export interface EmployeeAttemptDetail {
  chapter_id: string;
  chapter_title: string;
  max_attempts: number;
  attempts: { attempt_number: number; score: number; passed: boolean; created_at: string | null }[];
  is_locked: boolean;
}

export interface ProfileTrainingItem {
  training_id: string;
  title: string;
  category: string;
  status: 'completed' | 'in_progress' | 'overdue' | 'not_started';
  due_date: string | null;
  completed_at: string | null;
  quiz_total: number;
  quiz_passed: number;
  certificate_id: string | null;
}

export const analyticsApi = {
  getTrainingList: () =>
    client.get<TrainingListItem[]>('/analytics/trainings'),

  getTrainingDetail: (trainingId: string) =>
    client.get<TrainingDetailAnalytics>(`/analytics/trainings/${trainingId}`),

  getEmployeeDetail: (trainingId: string, userId: string) =>
    client.get<EmployeeAttemptDetail[]>(`/analytics/trainings/${trainingId}/employees/${userId}`),

  sendReminder: (trainingId: string, userIds: string[]) =>
    client.post<{ sent: number }>(`/analytics/trainings/${trainingId}/send-reminder`, { user_ids: userIds }),

  getProfileHistory: (userId: string) =>
    client.get<ProfileTrainingItem[]>(`/analytics/profile/${userId}`),

  getListReportUrl: (format: 'pdf' | 'csv') =>
    `/api/v1/analytics/report?format=${format}`,

  getDetailReportUrl: (trainingId: string, format: 'pdf' | 'csv') =>
    `/api/v1/analytics/trainings/${trainingId}/report?format=${format}`,
};
