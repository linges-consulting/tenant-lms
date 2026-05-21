import { client } from './client';

export type ThemePreference = 'light' | 'dark' | 'system';

export interface SettingsResponse {
    theme_preference: string;
    avatar_url?: string;
}

/**
 * Settings Service - Handles user preference updates (theme, avatar, etc.)
 */
export const settingsService = {
    /**
     * Update user's theme preference and persist to database
     */
    updateTheme: (theme: ThemePreference): Promise<SettingsResponse> =>
        client.patch<SettingsResponse>('/users/me', { theme_preference: theme }),

    /**
     * Update arbitrary user settings (avatar_url, theme_preference, etc.)
     */
    updateSettings: (updates: Record<string, unknown>): Promise<SettingsResponse> =>
        client.patch<SettingsResponse>('/users/me', updates),

    /**
     * Get current user's settings
     */
    getMySettings: () =>
        client.get<SettingsResponse>('/users/me'),
};
