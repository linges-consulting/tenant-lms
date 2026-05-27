import React, { createContext, useContext, useState, useEffect } from 'react';
import { useTheme } from '../components/theme-provider';
import { userService } from '../api/users';
import { authService } from '../api/auth';
import type { User, TenantMembership } from '../api/users';
import type { Tenant } from '../api/auth';
import { authStorage } from '../lib/auth-storage';

// Helper function to convert hex to HSL for shadcn/ui
const hexToHSL = (hex: string): { h: number, s: number, l: number, formatted: string } => {
    // Remove the hash if it exists
    hex = hex.replace(/^#/, '');

    // Parse r, g, b
    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;

    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0, l = (max + min) / 2;

    if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h /= 6;
    }

    h = Math.round(h * 360);
    s = Math.round(s * 100);
    l = Math.round(l * 100);

    return { h, s, l, formatted: `${h} ${s}% ${l}%` };
};

interface AuthContextType {
    user: User | null;
    activeTenant: Tenant | null;
    activeMembership: TenantMembership | null;
    isLoading: boolean;
    isRefreshing?: boolean;
    login: (token: string) => Promise<void>;
    selectTenant: (tenant: Tenant, token: string) => Promise<void>;
    logout: () => void;
    updateThemePreference: (theme: 'light' | 'dark' | 'system') => void;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [activeTenant, setActiveTenant] = useState<Tenant | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const { setTheme } = useTheme();

    const initialize = async () => {
        const token = authStorage.getToken();
        const storedTenant = authStorage.getActiveTenant();

        if (token) {
            try {
                // Attempt to fetch current user with existing token
                // Note: We don't use AbortSignal here since initialization is short-lived
                // and React 18 protects against state updates after unmount
                const currentUser = await userService.getMe();
                setUser(currentUser);
                if (storedTenant) {
                    try {
                        setActiveTenant(JSON.parse(storedTenant));
                    } catch (e) {
                        console.error('Failed to parse stored tenant', e);
                    }
                }
            } catch (error) {
                // If getMe() failed with 401, attempt to refresh token before giving up
                const errorStatus = (error as { status?: number })?.status;
                if (errorStatus === 401) {
                    try {
                        // Refresh the token
                        const refreshResponse = await authService.refresh();
                        const newToken = refreshResponse.access_token;
                        authStorage.setToken(newToken);

                        // Retry getMe() with refreshed token
                        const currentUser = await userService.getMe();
                        setUser(currentUser);
                        if (storedTenant) {
                            try {
                                setActiveTenant(JSON.parse(storedTenant));
                            } catch (e) {
                                console.error('Failed to parse stored tenant', e);
                            }
                        }
                    } catch (refreshError) {
                        console.error('Token refresh failed during initialization, logging out', refreshError);
                        authStorage.removeToken();
                        authStorage.removeActiveTenant();
                    }
                } else {
                    // For non-401 errors, log and clear session
                    console.error('Failed to initialize auth', error);
                    authStorage.removeToken();
                    authStorage.removeActiveTenant();
                }
            } finally {
                setIsLoading(false);
            }
        } else {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        initialize();
    }, []);

    useEffect(() => {
        if (activeTenant?.primary_color) {
            try {
                const { h, s, l, formatted } = hexToHSL(activeTenant.primary_color);
                const root = document.documentElement;

                // Set primary colors
                root.style.setProperty('--primary', formatted);
                root.style.setProperty('--ring', formatted);

                // Calculate high-contrast foreground (accessible contrast)
                const foreground = l > 65 ? '222.2 47.4% 11.2%' : '210 40% 98%';
                root.style.setProperty('--primary-foreground', foreground);

                // Derived colors for UI accents
                root.style.setProperty('--accent', `${h} ${Math.max(0, s - 20)}% ${Math.min(100, l + 40)}%`);
                root.style.setProperty('--accent-foreground', formatted);

            } catch (e) {
                console.error("Failed to apply tenant color:", e);
            }
        } else {
            const root = document.documentElement;
            root.style.removeProperty('--primary');
            root.style.removeProperty('--ring');
            root.style.removeProperty('--primary-foreground');
            root.style.removeProperty('--accent');
            root.style.removeProperty('--accent-foreground');
        }
    }, [activeTenant]);

    const login = async (token: string) => {
        authStorage.setToken(token);
        setIsRefreshing(true);
        try {
            const currentUser = await userService.getMe();
            setUser(currentUser);
        } finally {
            setIsRefreshing(false);
        }
    };

    const selectTenant = async (tenant: Tenant, token: string) => {
        authStorage.setToken(token);
        authStorage.setActiveTenant(JSON.stringify(tenant));
        setActiveTenant(tenant);
        setIsRefreshing(true);
        try {
            const currentUser = await userService.getMe();
            setUser(currentUser);
        } catch (error) {
            console.error("Failed to fetch user during tenant selection:", error);
            setUser(null);
        } finally {
            setIsRefreshing(false);
        }
    };

    const logout = () => {
        setUser(null);
        setActiveTenant(null);
        authStorage.removeToken();
        authStorage.removeActiveTenant();
        setTheme('system');
    };

    const updateThemePreference = (theme: 'light' | 'dark' | 'system') => {
        // In a real app we would do a fetch/PUT request to save this setting
        setTheme(theme);
    };

    const refreshUser = async () => {
        setIsRefreshing(true);
        try {
            const currentUser = await userService.getMe();
            setUser(currentUser);
        } catch (error) {
            console.error('Failed to refresh user', error);
        } finally {
            setIsRefreshing(false);
        }
    };

    const activeMembership = React.useMemo(() => {
        if (!user || !activeTenant) return null;
        return user.members?.find(m => m.tenant_id === activeTenant.id) || null;
    }, [user, activeTenant]);

    return (
        <AuthContext.Provider value={{
            user,
            activeTenant,
            activeMembership,
            isLoading,
            isRefreshing,
            login,
            selectTenant,
            logout,
            updateThemePreference,
            refreshUser
        }}>
            {children}
        </AuthContext.Provider>
    );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within an AuthProvider");
    return context;
};
