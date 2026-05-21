import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Search, PlusCircle, MoreVertical, Building2, Loader2, ArrowUpDown } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { Link, useNavigate } from 'react-router-dom';
import { tenantService } from '../api/tenants';
import type { Tenant } from '../api/auth';


export const AdminTenants: React.FC = () => {
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [sortField, setSortField] = useState<'name' | 'users' | 'courses' | 'certs' | 'status'>('name');
    const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
    const navigate = useNavigate();

    const fetchTenants = async () => {
        try {
            const data = await tenantService.list();
            setTenants(data);
        } catch (error) {
            console.error('Failed to fetch tenants:', error);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchTenants();
    }, []);

    const handleSort = (field: typeof sortField) => {
        if (sortField === field) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortField(field);
            setSortDirection('asc');
        }
    };

    const sortedTenants = [...tenants].sort((a, b) => {
        let valA: string | number = '';
        let valB: string | number = '';

        switch (sortField) {
            case 'name':
                valA = a.name.toLowerCase();
                valB = b.name.toLowerCase();
                break;
            case 'users':
                valA = a.user_count || 0;
                valB = b.user_count || 0;
                break;
            case 'courses':
                valA = a.course_count || 0;
                valB = b.course_count || 0;
                break;
            case 'certs':
                valA = a.certificate_count || 0;
                valB = b.certificate_count || 0;
                break;
            case 'status':
                valA = a.is_active ? 1 : 0;
                valB = b.is_active ? 1 : 0;
                break;
        }

        if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
        if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
        return 0;
    });

    const filteredTenants = sortedTenants.filter(t =>
        t.name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="space-y-8 max-w-7xl mx-auto animate-in fade-in duration-500">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center shrink-0">
                            <Building2 className="w-6 h-6 text-violet-600 dark:text-violet-400" />
                        </div>
                        Tenant Management
                    </h1>
                    <p className="text-muted-foreground mt-1">Manage all organizations registered on the platform.</p>
                </div>
                <div className="flex gap-3">
                    <Link to="/admin/tenants/new">
                        <Button>
                            <PlusCircle className="mr-2 h-4 w-4" />
                            Register Tenant
                        </Button>
                    </Link>
                </div>
            </div>

            <Card className="border-border/50 shadow-sm">
                <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-border/50">
                    <div>
                        <CardTitle className="text-lg">Organizations</CardTitle>
                        <CardDescription>A list of all tenants across environments.</CardDescription>
                    </div>
                    <div className="relative w-full sm:w-72 mt-4 sm:mt-0">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <Input
                            placeholder="Search tenants..."
                            className="bg-muted/50 pl-9 w-full"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                        />
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    <Table>
                        <TableHeader className="bg-muted/50">
                            <TableRow>
                                <TableHead className="pl-4 w-[50px]"></TableHead>
                                <TableHead className="pl-6">
                                    <button onClick={() => handleSort('name')} className="flex items-center gap-1 hover:text-foreground transition-colors group">
                                        Tenant Name
                                        <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'name' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                                <TableHead className="text-right">
                                    <button onClick={() => handleSort('users')} className="flex items-center gap-1 ml-auto hover:text-foreground transition-colors group">
                                        Active Users
                                        <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'users' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                                <TableHead className="text-right">
                                    <button onClick={() => handleSort('courses')} className="flex items-center gap-1 ml-auto hover:text-foreground transition-colors group">
                                        Courses
                                        <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'courses' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                                <TableHead className="text-right">
                                    <button onClick={() => handleSort('certs')} className="flex items-center gap-1 ml-auto hover:text-foreground transition-colors group">
                                        Certificates
                                        <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'certs' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                                <TableHead className="text-right">
                                    <button onClick={() => handleSort('status')} className="flex items-center gap-1 ml-auto hover:text-foreground transition-colors group">
                                        Status
                                        <ArrowUpDown className={cn('w-3 h-3 transition-opacity', sortField === 'status' ? 'opacity-100' : 'opacity-0 group-hover:opacity-40')} />
                                    </button>
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {isLoading ? (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-32 text-center">
                                        <div className="flex flex-col items-center justify-center gap-2">
                                            <Loader2 className="h-6 w-6 animate-spin text-primary" />
                                            <p className="text-sm text-muted-foreground">Loading organizations...</p>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ) : filteredTenants.length === 0 ? (
                                <TableRow>
                                    <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                                        No organizations found.
                                    </TableCell>
                                </TableRow>
                            ) : (
                                filteredTenants.map((tenant) => (
                                    <TableRow key={tenant.id} className="hover:bg-muted/30">
                                        <TableCell className="pl-4 w-[50px]">
                                            <DropdownMenu>
                                                <DropdownMenuTrigger asChild>
                                                    <Button variant="ghost" size="icon" className="h-8 w-8">
                                                        <span className="sr-only">Open menu</span>
                                                        <MoreVertical className="h-4 w-4" />
                                                    </Button>
                                                </DropdownMenuTrigger>
                                                <DropdownMenuContent align="start">
                                                    <DropdownMenuLabel>Actions</DropdownMenuLabel>
                                                    <DropdownMenuSeparator />
                                                    <DropdownMenuItem
                                                        onClick={() => navigate(`/admin/tenants/${tenant.id}`)}
                                                        className="cursor-pointer"
                                                    >
                                                        View &amp; Edit Settings
                                                    </DropdownMenuItem>
                                                </DropdownMenuContent>
                                            </DropdownMenu>
                                        </TableCell>
                                        <TableCell className="pl-6">
                                            <div className="flex items-center gap-3">
                                                <div
                                                    className="w-10 h-10 rounded-md flex items-center justify-center text-white font-bold text-sm shrink-0"
                                                    style={{ backgroundColor: tenant.primary_color || '#6366f1' }}
                                                >
                                                    {tenant.logo_url ? (
                                                        <img src={tenant.logo_url} alt={tenant.name} className="w-8 h-8 rounded-sm object-contain" />
                                                    ) : (
                                                        tenant.name.substring(0, 2).toUpperCase()
                                                    )}
                                                </div>
                                                <span className="font-medium">{tenant.name}</span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-right text-muted-foreground">{tenant.user_count || 0}</TableCell>
                                        <TableCell className="text-right text-muted-foreground">{tenant.course_count || 0}</TableCell>
                                        <TableCell className="text-right font-medium">{tenant.certificate_count || 0}</TableCell>
                                        <TableCell className="text-right">
                                            {tenant.is_active ? (
                                                <Badge
                                                    variant="secondary"
                                                    className="bg-primary/10 text-primary hover:bg-primary/20 border-0"
                                                >
                                                    Active
                                                </Badge>
                                            ) : (
                                                <Badge
                                                    variant="secondary"
                                                    className="bg-destructive/10 text-destructive hover:bg-destructive/20 border-0"
                                                >
                                                    Deactivated
                                                </Badge>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                ))
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

        </div>
    );
};
