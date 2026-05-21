import { client } from './client';

export interface Assignment {
    id: string;
    training_id: string;
    tenant_id: string;
    group_id: string | null;
    user_id: string | null;
    assigned_at: string;
    group_name: string | null;
    user_name: string | null;
    training_title: string | null;
}

export interface CreateAssignmentPayload {
    training_id: string;
    group_id?: string;
    user_id?: string;
}

export const assignmentService = {
    list: () => client.get<Assignment[]>('/assignments'),
    create: (payload: CreateAssignmentPayload) =>
        client.post<Assignment>('/assignments', payload),
    delete: (assignmentId: string) => client.delete<void>(`/assignments/${assignmentId}`),
};
