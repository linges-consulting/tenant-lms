import { client } from './client';

export interface ManagerDashboard {
  total_trainings: number;
  active_assignments: number;
  completion_rate: number;
  overdue_count: number;
}

export interface CreatorDashboard {
  total_trainings: number;
  published_count: number;
  draft_count: number;
  total_enrollments: number;
}

export interface EmployeeDashboard {
  assigned_trainings: number;
  completed_trainings: number;
  in_progress_trainings: number;
  overdue_trainings: number;
}

export const dashboardsApi = {
  manager: (): Promise<ManagerDashboard> =>
    client.get<ManagerDashboard>('/dashboards/manager'),
  creator: (): Promise<CreatorDashboard> =>
    client.get<CreatorDashboard>('/dashboards/creator'),
  employee: (): Promise<EmployeeDashboard> =>
    client.get<EmployeeDashboard>('/dashboards/employee'),
};
