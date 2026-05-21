import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './auth-context';
import { settingsService } from '../api/settings';

export type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
    theme: Theme;
    setTheme: (theme: Theme) => Promise<void>;
    isLoading: boolean;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

/**
 * ThemeProvider Component - Manages theme persistence and DOM updates
 *
 * Features:
 * - Loads theme from user.theme_preference on mount
 * - Persists theme changes to backend
 * - Applies theme to DOM (dark class on document.documentElement)
 * - Respects system theme preferences
 * - Error handling without breaking UI
 */
export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { user } = useAuth();
    const [theme, setThemeState] = useState<Theme>('system');
    const [isLoading, setIsLoading] = useState(true);

    /**
     * Load theme from user profile on mount or when user changes
     */
    useEffect(() => {
        if (user) {
            // Load theme from user's stored preference
            const userTheme = (user.theme_preference || 'system') as Theme;
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setThemeState(userTheme);
        } else if (user === null) {
            // User is not authenticated
            setThemeState('system');
        }
        // While user is still being loaded (undefined), keep loading state
        setIsLoading(user !== undefined);
    }, [user]);

    /**
     * Apply theme to DOM
     * - For 'dark': add 'dark' class
     * - For 'light': remove 'dark' class
     * - For 'system': check system preference and apply accordingly
     */
    useEffect(() => {
        const applyTheme = (themeToApply: Theme) => {
            let shouldBeDark = false;

            if (themeToApply === 'dark') {
                shouldBeDark = true;
            } else if (themeToApply === 'light') {
                shouldBeDark = false;
            } else if (themeToApply === 'system') {
                shouldBeDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            }

            const html = document.documentElement;
            if (shouldBeDark) {
                html.classList.add('dark');
            } else {
                html.classList.remove('dark');
            }
        };

        applyTheme(theme);

        // Listen for system theme changes
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handleChange = () => {
            if (theme === 'system') {
                applyTheme('system');
            }
        };

        mediaQuery.addEventListener('change', handleChange);
        return () => mediaQuery.removeEventListener('change', handleChange);
    }, [theme]);

    /**
     * Set theme and persist to backend
     */
    const setTheme = async (newTheme: Theme) => {
        try {
            setThemeState(newTheme);
            // Persist to backend if user is authenticated
            if (user) {
                await settingsService.updateTheme(newTheme);
            }
        } catch (error) {
            console.error('Failed to update theme preference:', error);
            // UI state already updated, backend sync failed but don't crash
        }
    };

    return (
        <ThemeContext.Provider value={{ theme, setTheme, isLoading }}>
            {children}
        </ThemeContext.Provider>
    );
};

/**
 * Hook to use theme context
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useTheme(): ThemeContextType {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
}
