import React, { useState, useEffect, useCallback } from 'react';
import { managerTrainingsApi, type TrainingAuditLog } from "../api/trainings";
import {
    Clock,
    PlusCircle,
    Edit,
    CheckCircle,
    XCircle,
    Trash2,
    FileText,
    UserMinus,
    UserPlus,
    Archive,
    RotateCcw,
    Layout,
    ChevronDown
} from "lucide-react";
import { ScrollArea } from "./ui/scroll-area";
import { Loader2 } from "lucide-react";
import { cn } from "../lib/utils";

interface TrainingAuditTimelineProps {
    trainingId: string;
    refreshTrigger?: number;
}

export const TrainingAuditTimeline: React.FC<TrainingAuditTimelineProps> = ({
    trainingId,
    refreshTrigger = 0
}) => {
    const [logs, setLogs] = useState<TrainingAuditLog[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

    const loadAudit = useCallback(async () => {
        setIsLoading(true);
        try {
            const data = await managerTrainingsApi.getTrainingAudit(trainingId);
            setLogs(data);
            setExpandedIds(new Set());
        } catch (error) {
            console.error("Failed to load audit logs", error);
        } finally {
            setIsLoading(false);
        }
    }, [trainingId]);

    useEffect(() => {
        if (trainingId) {
            loadAudit();
        }
    }, [trainingId, refreshTrigger, loadAudit]);

    const toggleExpanded = useCallback((id: string) => {
        setExpandedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    }, []);

    const getActionIcon = (action: string) => {
        switch (action) {
            case 'CREATE_TRAINING':
            case 'CREATE_MODULE':
            case 'CREATE_CHAPTER':
                return <PlusCircle className="h-4 w-4 text-primary" />;
            case 'UPDATE_TRAINING':
            case 'UPDATE_MODULE':
            case 'UPDATE_CHAPTER':
                return <Edit className="h-4 w-4 text-muted-foreground" />;
            case 'PUBLISH_TRAINING':
                return <CheckCircle className="h-4 w-4 text-primary" />;
            case 'UNPUBLISH_TRAINING':
                return <XCircle className="h-4 w-4 text-amber-500" />;
            case 'DELETE_TRAINING':
            case 'DELETE_MODULE':
            case 'DELETE_CHAPTER':
                return <Trash2 className="h-4 w-4 text-destructive" />;
            case 'ADD_COLLABORATOR':
            case 'COLLABORATOR_ADDED':
                return <UserPlus className="h-4 w-4 text-primary" />;
            case 'REMOVE_COLLABORATOR':
            case 'COLLABORATOR_REMOVED':
                return <UserMinus className="h-4 w-4 text-destructive" />;
            case 'ARCHIVE_TRAINING':
                return <Archive className="h-4 w-4 text-muted-foreground" />;
            case 'RESTORE_TRAINING':
                return <RotateCcw className="h-4 w-4 text-primary" />;
            case 'REORDER_MODULES':
            case 'REORDER_CHAPTERS':
                return <Layout className="h-4 w-4 text-primary" />;
            default:
                return <FileText className="h-4 w-4 text-muted-foreground" />;
        }
    };

    const formatActionName = (action: string) => {
        return action.replace(/_/g, ' ').toLowerCase()
            .replace(/\b\w/g, c => c.toUpperCase());
    };

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center py-12 gap-2">
                <Loader2 className="h-6 w-6 animate-spin text-primary opacity-50" />
                <p className="text-xs text-muted-foreground">Loading history...</p>
            </div>
        );
    }

    if (logs.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 gap-2 text-muted-foreground border-2 border-dashed rounded-xl m-4">
                <Clock className="h-8 w-8 opacity-10" />
                <p className="text-xs italic">No activity history found.</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center gap-2 px-6 py-3 border-b bg-muted/30 shrink-0">
                <Clock className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Audit History</h3>
            </div>
            <ScrollArea className="flex-1">
                <div className="relative p-6 ml-4">
                    {/* Vertical Line */}
                    <div className="absolute left-[1.35rem] top-8 bottom-8 w-[2px] bg-border/50" />

                    <div className="space-y-8 relative">
                        {logs.map((log) => {
                            const hasDetails = log.metadata_json &&
                                Object.keys(log.metadata_json).filter(
                                    k => k !== 'training_id' && k !== 'user_id'
                                ).length > 0;
                            const isExpanded = expandedIds.has(log.id);

                            return (
                                <div key={log.id} className="relative pl-10 group">
                                    {/* Dot Icon */}
                                    <div className="absolute left-[-0.65rem] top-0 w-8 h-8 rounded-full border-4 border-background bg-muted flex items-center justify-center shadow-sm z-10 group-hover:bg-background transition-colors">
                                        {getActionIcon(log.action)}
                                    </div>

                                    <div className="flex flex-col">
                                        {/* Header row — clickable when details exist */}
                                        <button
                                            type="button"
                                            onClick={() => hasDetails && toggleExpanded(log.id)}
                                            className={cn(
                                                "flex items-center justify-between gap-4 mb-2 w-full text-left",
                                                hasDetails && "cursor-pointer"
                                            )}
                                            disabled={!hasDetails}
                                        >
                                            <div className="flex items-center gap-1.5 min-w-0">
                                                <h4 className="text-sm font-bold leading-none">
                                                    {formatActionName(log.action)}
                                                </h4>
                                                {hasDetails && (
                                                    <ChevronDown
                                                        className={cn(
                                                            "h-3 w-3 text-muted-foreground shrink-0 transition-transform duration-200",
                                                            isExpanded && "rotate-180"
                                                        )}
                                                    />
                                                )}
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                <span className="font-semibold text-foreground uppercase tracking-tighter text-[10px] bg-muted px-1.5 py-0.5 rounded-sm whitespace-nowrap">
                                                    {log.user_name || "Unknown"}
                                                </span>
                                                <span className="text-[10px] tabular-nums text-muted-foreground whitespace-nowrap">
                                                    {new Date(log.created_at).toLocaleString([], {
                                                        month: 'short',
                                                        day: 'numeric',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    })}
                                                </span>
                                            </div>
                                        </button>

                                        {hasDetails && isExpanded && (
                                            <div className="rounded-lg bg-muted/50 p-2 border border-border/50">
                                                <div className="text-[10px] space-y-1.5">
                                                    {Object.entries(log.metadata_json!)
                                                        .filter(([key]) => key !== 'training_id' && key !== 'user_id')
                                                        .map(([key, value]) => (
                                                            <div key={key} className="flex flex-col gap-0.5">
                                                                <span className="font-bold text-muted-foreground lowercase">{key}:</span>
                                                                <span className="italic break-words whitespace-pre-wrap">
                                                                    {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                                                                </span>
                                                            </div>
                                                        ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
};
