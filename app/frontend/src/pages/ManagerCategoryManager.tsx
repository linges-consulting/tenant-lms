import React, { useState, useEffect } from 'react';
import { getCategories, createCategory, updateCategory, deleteCategory } from '../api/categories';
import type { Category } from '../api/categories';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { PageLoader } from '../components/ui/PageLoader';
import { Tag, Plus, Pencil, Trash2, Check, X } from 'lucide-react';
import { toast } from 'sonner';

export const ManagerCategoryManager: React.FC = () => {
    const [categories, setCategories] = useState<Category[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [newName, setNewName] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editingName, setEditingName] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<Category | null>(null);
    const [isDeleting, setIsDeleting] = useState(false);

    useEffect(() => {
        load();
    }, []);

    const load = async () => {
        setIsLoading(true);
        try {
            const data = await getCategories();
            setCategories(data);
        } catch {
            toast.error('Failed to load categories');
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreate = async () => {
        const name = newName.trim();
        if (!name) return;
        setIsCreating(true);
        try {
            const created = await createCategory({ name });
            setCategories(prev => [...prev, created]);
            setNewName('');
            toast.success(`Category "${name}" created`);
        } catch (e: unknown) {
            const msg = (e as { message?: string })?.message;
            toast.error(msg?.includes('409') ? `"${name}" already exists` : 'Failed to create category');
        } finally {
            setIsCreating(false);
        }
    };

    const handleStartEdit = (cat: Category) => {
        setEditingId(cat.id);
        setEditingName(cat.name);
    };

    const handleSaveEdit = async () => {
        if (!editingId) return;
        const name = editingName.trim();
        if (!name) return;
        setIsSaving(true);
        try {
            const updated = await updateCategory(editingId, { name });
            setCategories(prev => prev.map(c => c.id === editingId ? updated : c));
            setEditingId(null);
            toast.success('Category updated');
        } catch {
            toast.error('Failed to update category');
        } finally {
            setIsSaving(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setIsDeleting(true);
        try {
            await deleteCategory(deleteTarget.id);
            setCategories(prev => prev.filter(c => c.id !== deleteTarget.id));
            toast.success(`"${deleteTarget.name}" removed`);
        } catch {
            toast.error('Failed to delete category');
        } finally {
            setIsDeleting(false);
            setDeleteTarget(null);
        }
    };

    return (
        <>
        <div className="space-y-6">
            <div>
                <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                        <Tag className="w-6 h-6 text-primary" />
                    </div>
                    Categories
                </h1>
                <p className="text-muted-foreground mt-1">
                    Manage training categories for your organisation.
                </p>
            </div>

            <Card>
                <CardHeader className="border-b border-border/50 pb-4">
                    <CardTitle className="text-base">Add Category</CardTitle>
                </CardHeader>
                <CardContent className="pt-4">
                    <div className="flex items-center gap-2 max-w-sm">
                        <input
                            type="text"
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && handleCreate()}
                            placeholder="Category name…"
                            className="flex-1 h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <Button size="sm" onClick={handleCreate} disabled={isCreating || !newName.trim()}>
                            <Plus className="h-3.5 w-3.5 mr-1" />
                            {isCreating ? 'Adding…' : 'Add'}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardContent className="p-0">
                    {isLoading ? (
                        <PageLoader label="Loading categories…" />
                    ) : categories.length === 0 ? (
                        <div className="py-10 text-center text-muted-foreground text-sm">
                            No categories yet. Add one above.
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="pl-6">Name</TableHead>
                                    <TableHead className="text-right pr-6 w-[120px]">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {categories.map(cat => (
                                    <TableRow key={cat.id}>
                                        <TableCell className="pl-6">
                                            {editingId === cat.id ? (
                                                <input
                                                    autoFocus
                                                    type="text"
                                                    value={editingName}
                                                    onChange={e => setEditingName(e.target.value)}
                                                    onKeyDown={e => {
                                                        if (e.key === 'Enter') handleSaveEdit();
                                                        if (e.key === 'Escape') setEditingId(null);
                                                    }}
                                                    className="h-8 w-full max-w-xs rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                                                />
                                            ) : (
                                                <span className="text-sm font-medium">{cat.name}</span>
                                            )}
                                        </TableCell>
                                        <TableCell className="pr-6 text-right">
                                            <div className="flex items-center justify-end gap-1">
                                                {editingId === cat.id ? (
                                                    <>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7 text-primary" onClick={handleSaveEdit} disabled={isSaving}>
                                                            <Check className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground" onClick={() => setEditingId(null)}>
                                                            <X className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground hover:text-foreground" onClick={() => handleStartEdit(cat)}>
                                                            <Pencil className="h-3.5 w-3.5" />
                                                        </Button>
                                                        <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground hover:text-destructive" onClick={() => setDeleteTarget(cat)}>
                                                            <Trash2 className="h-3.5 w-3.5" />
                                                        </Button>
                                                    </>
                                                )}
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>
        </div>

        <AlertDialog open={!!deleteTarget} onOpenChange={open => { if (!open) setDeleteTarget(null); }}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>Delete category?</AlertDialogTitle>
                    <AlertDialogDescription>
                        <strong>"{deleteTarget?.name}"</strong> will be removed. Existing trainings that use this category will keep the category label but it won't appear in the category list going forward.
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={handleDelete}
                        disabled={isDeleting}
                    >
                        {isDeleting ? 'Deleting…' : 'Delete'}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
        </>
    );
};
