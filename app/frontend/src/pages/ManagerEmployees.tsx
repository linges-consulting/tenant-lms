import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Users as UsersIcon } from 'lucide-react';
import { userService, type User } from '../api/users';
import { useAuth } from '../contexts/auth-context';
import { UserTable } from '../components/UserTable';

export const ManagerEmployees: React.FC = () => {
    const { activeTenant, activeMembership } = useAuth();
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const fetchUsers = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await userService.listTenantUsers();
            setUsers(data);
        } catch (error) {
            console.error('Failed to fetch users:', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => { fetchUsers(); }, [fetchUsers]);

    // Must be a business manager to access this page
    if (!activeMembership?.is_business_manager) {
        return (
            <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
                <UsersIcon className="w-10 h-10 mb-3 opacity-30" />
                <p className="text-lg font-medium">Access Restricted</p>
                <p className="text-sm mt-1">You need Business Manager permissions to view this page.</p>
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto animate-in fade-in duration-500">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <UsersIcon className="w-6 h-6 text-primary" />
                    </div>
                    Employee Directory
                </h1>
                <p className="text-muted-foreground mt-1">
                    Manage team members for <span className="font-medium">{activeTenant?.name}</span>.
                </p>
            </div>

            <Card className="border-border/50 shadow-sm">
                <CardHeader className="pb-4 border-b border-border/50">
                    <CardTitle className="text-lg">Team Members</CardTitle>
                    <CardDescription>
                        {isLoading ? 'Loading...' : `${users.length} member${users.length !== 1 ? 's' : ''} in ${activeTenant?.name}.`}
                    </CardDescription>
                </CardHeader>
                <CardContent className="pt-4">
                    <UserTable
                        users={users}
                        isLoading={isLoading}
                        mode="manager"
                        activeTenantId={activeTenant?.id}
                        activeTenantName={activeTenant?.name}
                        onRefresh={fetchUsers}
                    />
                </CardContent>
            </Card>
        </div>
    );
};
