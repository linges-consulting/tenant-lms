import { cn } from '@/lib/utils';

interface PageLoaderProps {
    /** Full-viewport centered loader — use for top-level page loads */
    fullPage?: boolean;
    /** Optional label shown below the spinner */
    label?: string;
    className?: string;
}

export function PageLoader({ fullPage = false, label, className }: PageLoaderProps) {
    return (
        <div
            role="status"
            aria-label={label ?? 'Loading'}
            className={cn(
                'flex flex-col items-center justify-center gap-3',
                fullPage ? 'h-[80vh]' : 'min-h-[200px] w-full',
                className,
            )}
        >
            <div className="relative h-9 w-9" aria-hidden="true">
                <div className="absolute inset-0 rounded-full border-4 border-muted" />
                <div className="absolute inset-0 rounded-full border-4 border-primary border-t-transparent animate-spin" />
            </div>
            {label && (
                <p className="text-sm text-muted-foreground motion-safe:animate-pulse">{label}</p>
            )}
        </div>
    );
}
