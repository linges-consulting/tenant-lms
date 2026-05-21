import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { trainingsApi, managerTrainingsApi } from '../api/trainings';

export const trainingKeys = {
  all: ['trainings'] as const,
  list: (filters?: object) => [...trainingKeys.all, 'list', filters] as const,
  detail: (id: string) => [...trainingKeys.all, 'detail', id] as const,
};

export function useTrainings(filters?: { category?: string; status?: string }) {
  return useQuery({
    queryKey: trainingKeys.list(filters),
    queryFn: () => trainingsApi.getPublishedTrainings(filters),
  });
}

export function useTraining(id: string) {
  return useQuery({
    queryKey: trainingKeys.detail(id),
    queryFn: () => trainingsApi.getTraining(id),
    enabled: !!id,
  });
}

export function usePublishTraining() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => managerTrainingsApi.publishTraining(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: trainingKeys.all }),
  });
}
