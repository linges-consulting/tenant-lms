import React, { useState, useEffect } from 'react';
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
    Layout
} from "lucide-react";
import { ScrollArea } from "./ui/scroll-area";
import { Loader2 } from "lucide-react";

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

    useEffect(() => {
        if (trainingId) {
            loadAudit();
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [trainingId, refreshTrigger]);

    const loadAudit = async () => {
        setIsLoading(true);
        try {
            const data = await managerTrainingsApi.getTrainingAudit(trainingId);
            setLogs(data);
        } catch (error) {
            console.error("Failed to load audit logs", error);
        } finally {
            setIsLoading(false);
        }
    };

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
                return <UserPlus className="h-4 w-4 text-primary" />;
            case 'REMOVE_COLLABORATOR':
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
                        {logs.map((log) => (
                            <div key={log.id} className="relative pl-10 group">
                                {/* Dot Icon */}
                                <div className="absolute left-[-0.65rem] top-0 w-8 h-8 rounded-full border-4 border-background bg-muted flex items-center justify-center shadow-sm z-10 group-hover:bg-background transition-colors">
                                    {getActionIcon(log.action)}
                                </div>

                                <div className="flex flex-col">
                                    <div className="flex items-baseline justify-between gap-4 mb-1">
                                        <h4 className="text-sm font-bold leading-none">
                                            {formatActionName(log.action)}
                                        </h4>
                                        <span className="text-[10px] tabular-nums text-muted-foreground whitespace-nowrap">
                                            {new Date(log.created_at).toLocaleString([], { 
                                                month: 'short', 
                                                day: 'numeric', 
                                                hour: '2-digit', 
                                                minute: '2-digit' 
                                            })}
                                        </span>
                                    </div>
                                    
                                    <p className="text-xs text-muted-foreground mb-2">
                                        by <span className="font-semibold text-foreground uppercase tracking-tighter text-[10px] bg-muted px-1.5 py-0.5 rounded-sm">
                                            {log.user_name || "Unknown User"}
                                        </span>
                                    </p>

                                    {log.metadata_json && Object.keys(log.metadata_json).length > 0 && (
                                        <div className="rounded-lg bg-muted/50 p-2 border border-border/50">
                                            <div className="text-[10px] space-y-1">
                                                {Object.entries(log.metadata_json)
                                                    .filter(([key]) => key !== 'training_id' && key !== 'user_id')
                                                    .map(([key, value]) => (
                                                        <div key={key} className="flex gap-2">
                                                            <span className="font-bold text-muted-foreground lowercase">{key}:</span>
                                                            <span className="truncate max-w-[200px] italic">
                                                                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                                            </span>
                                                        </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
};
