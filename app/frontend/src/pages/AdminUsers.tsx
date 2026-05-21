import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { UsersIcon, UserPlus } from 'lucide-react';
import { userService, type User } from '../api/users';
import { UserTable } from '../components/UserTable';
import { AddAdminDialog } from '../components/AddAdminDialog';

export const AdminUsers: React.FC = () => {
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [openAddAdminDialog, setOpenAddAdminDialog] = useState(false);

    const fetchUsers = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await userService.listGlobalUsers();
            setUsers(data);
        } catch (error) {
            console.error('Failed to fetch users:', error);
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => { fetchUsers(); }, [fetchUsers]);

    return (
        <div className="space-y-6 max-w-7xl mx-auto animate-in fade-in duration-500">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                        <UsersIcon className="w-6 h-6 text-violet-600 dark:text-violet-400" />
                    </div>
                    Global User Directory
                </h1>
                <p className="text-muted-foreground mt-1">Manage and audit all user accounts across the platform.</p>
            </div>

            <Card className="border-border/50 shadow-sm">
                <CardHeader className="pb-4 border-b border-border/50">
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle className="text-lg">All Platform Users</CardTitle>
                            <CardDescription>
                                {isLoading ? 'Loading...' : `${users.length} registered user${users.length !== 1 ? 's' : ''} across all tenants.`}
                            </CardDescription>
                        </div>
                        <Button onClick={() => setOpenAddAdminDialog(true)} className="gap-2">
                            <UserPlus className="h-4 w-4" />
                            Add Administrator
                        </Button>
                    </div>
                </CardHeader>
                <CardContent className="pt-4">
                    <UserTable
                        users={users}
                        isLoading={isLoading}
                        mode="sysadmin"
                        onRefresh={fetchUsers}
                    />
                </CardContent>
            </Card>

            <AddAdminDialog
                open={openAddAdminDialog}
                onOpenChange={setOpenAddAdminDialog}
                onAdminCreated={fetchUsers}
            />
        </div>
    );
};
