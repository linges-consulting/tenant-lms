import { client as apiClient } from './client';

export interface Category {
    id: string;
    tenant_id: string;
    name: string;
    is_active: boolean;
    created_at: string;
}

export interface CategoryCreate {
    name: string;
    is_active?: boolean;
}

export interface CategoryUpdate {
    name?: string;
    is_active?: boolean;
}

export const getCategories = (): Promise<Category[]> =>
    apiClient.get<Category[]>('/categories/');

export const createCategory = (data: CategoryCreate): Promise<Category> =>
    apiClient.post<Category>('/categories/', data);

export const updateCategory = (id: string, data: CategoryUpdate): Promise<Category> =>
    apiClient.put<Category>(`/categories/${id}`, data);

export const deleteCategory = (id: string): Promise<void> =>
    apiClient.delete<void>(`/categories/${id}`);
