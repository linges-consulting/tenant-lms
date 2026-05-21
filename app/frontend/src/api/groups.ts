import { client } from './client';

export interface Group {
    id: string;
    tenant_id: string;
    name: string;
    description: string | null;
    created_at: string;
    member_count: number;
}

export interface GroupMember {
    user_id: string;
    added_at: string;
    user_email: string | null;
    user_name: string | null;
    user_avatar_url: string | null;
}

export interface CreateGroupPayload {
    name: string;
    description?: string;
}

export interface UpdateGroupPayload {
    name?: string;
    description?: string;
}

export const groupService = {
    list: () => client.get<Group[]>('/groups'),
    create: (payload: CreateGroupPayload) => client.post<Group>('/groups', payload),
    update: (groupId: string, payload: UpdateGroupPayload) => client.put<Group>(`/groups/${groupId}`, payload),
    delete: (groupId: string) => client.delete<void>(`/groups/${groupId}`),
    listMembers: (groupId: string) => client.get<GroupMember[]>(`/groups/${groupId}/members`),
    addMembers: (groupId: string, user_ids: string[]) =>
        client.post<{ added: number; message: string }>(`/groups/${groupId}/members`, { user_ids }),
    removeMember: (groupId: string, userId: string) =>
        client.delete<void>(`/groups/${groupId}/members/${userId}`),
};
