import { useQuery } from '@tanstack/react-query';
import { dashboardsApi } from '../api/dashboards';

export const dashboardKeys = {
  all: ['dashboard'] as const,
  manager: () => [...dashboardKeys.all, 'manager'] as const,
  creator: () => [...dashboardKeys.all, 'creator'] as const,
  employee: () => [...dashboardKeys.all, 'employee'] as const,
};

export function useManagerDashboard() {
  return useQuery({
    queryKey: dashboardKeys.manager(),
    queryFn: () => dashboardsApi.manager(),
  });
}

export function useCreatorDashboard() {
  return useQuery({
    queryKey: dashboardKeys.creator(),
    queryFn: () => dashboardsApi.creator(),
  });
}

export function useEmployeeDashboard() {
  return useQuery({
    queryKey: dashboardKeys.employee(),
    queryFn: () => dashboardsApi.employee(),
  });
}
