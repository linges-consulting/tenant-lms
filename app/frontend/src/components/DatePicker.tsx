import React, { useState, forwardRef, useImperativeHandle } from 'react';
import {
    format,
    parse,
    isValid,
    parseISO,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    addMonths,
    subMonths,
    isSameDay,
    isToday,
} from 'date-fns';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';
import { Button } from './ui/button';
import { cn } from '../lib/utils';
import { Calendar, ChevronLeft, ChevronRight, X } from 'lucide-react';

const INPUT_FORMAT = 'MM/dd/yyyy';
const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

function toDisplay(iso: string): string {
    if (!iso) return '';
    const d = parseISO(iso);
    return isValid(d) ? format(d, INPUT_FORMAT) : '';
}

function toISO(display: string): string {
    if (!display) return '';
    const d = parse(display, INPUT_FORMAT, new Date());
    return isValid(d) ? format(d, 'yyyy-MM-dd') : '';
}

function validateInput(text: string): string {
    if (!text) return '';
    if (!/^\d{2}\/\d{2}\/\d{4}$/.test(text)) return 'Use MM/DD/YYYY format';
    const d = parse(text, INPUT_FORMAT, new Date());
    if (!isValid(d)) return 'Invalid date';
    return '';
}

export interface DatePickerHandle {
    /** Triggers validation, shows error message, and returns true if the current value is valid. */
    validate: () => boolean;
}

interface DatePickerProps {
    value: string;         // YYYY-MM-DD or ''
    onChange: (val: string) => void;
    placeholder?: string;
    className?: string;
    align?: 'start' | 'center' | 'end';
}

export const DatePicker = forwardRef<DatePickerHandle, DatePickerProps>(({
    value,
    onChange,
    placeholder = 'MM/DD/YYYY',
    className,
    align = 'start',
}, ref) => {
    const [open, setOpen] = useState(false);
    const [inputText, setInputText] = useState(() => toDisplay(value));
    const [viewMonth, setViewMonth] = useState(() => {
        const d = value ? parseISO(value) : new Date();
        return isValid(d) ? d : new Date();
    });
    const [error, setError] = useState('');
    const [syncedValue, setSyncedValue] = useState(value);

    // Sync external value changes (derived state pattern — avoids useEffect setState)
    if (value !== syncedValue) {
        setSyncedValue(value);
        setInputText(toDisplay(value));
        if (value) {
            const d = parseISO(value);
            if (isValid(d)) setViewMonth(d);
        }
    }

    useImperativeHandle(ref, () => ({
        validate() {
            const err = validateInput(inputText);
            setError(err);
            if (inputText && err) onChange('');
            return !err;
        },
    }));

    const handleTextChange = (raw: string) => {
        setInputText(raw);
        setError('');
        const iso = toISO(raw);
        if (iso) {
            onChange(iso);
            const d = parseISO(iso);
            setViewMonth(d);
        } else if (!raw) {
            onChange('');
        }
    };

    const handleBlur = () => {
        const err = validateInput(inputText);
        setError(err);
        if (inputText && err) onChange('');
    };

    const handleDayClick = (day: Date) => {
        const iso = format(day, 'yyyy-MM-dd');
        onChange(iso);
        setInputText(format(day, INPUT_FORMAT));
        setError('');
        setOpen(false);
    };

    const handleClear = (e: React.MouseEvent) => {
        e.stopPropagation();
        onChange('');
        setInputText('');
        setError('');
    };

    // Build calendar grid — always 6 rows × 7 cols
    const monthStart = startOfMonth(viewMonth);
    const monthEnd = endOfMonth(viewMonth);
    const calDays = eachDayOfInterval({
        start: startOfWeek(monthStart, { weekStartsOn: 0 }),
        end: endOfWeek(monthEnd, { weekStartsOn: 0 }),
    });

    const selectedDate = value ? parseISO(value) : null;

    return (
        <div className={cn('flex flex-col gap-1', className)}>
            <Popover open={open} onOpenChange={setOpen}>
                <PopoverTrigger asChild>
                    <div
                        role="button"
                        tabIndex={0}
                        onKeyDown={e => e.key === 'Enter' && setOpen(true)}
                        className={cn(
                            'flex items-center gap-1.5 border rounded-md bg-background px-2.5 py-1.5 cursor-pointer',
                            'hover:border-primary/50 transition-colors',
                            open && 'border-primary/70 ring-1 ring-primary/20',
                            error && 'border-destructive ring-1 ring-destructive/20',
                        )}
                    >
                        <Calendar
                            className="h-3.5 w-3.5 text-muted-foreground shrink-0"
                            onClick={() => setOpen(v => !v)}
                        />
                        <input
                            type="text"
                            className="bg-transparent outline-none text-sm w-[84px] placeholder:text-muted-foreground"
                            placeholder={placeholder}
                            value={inputText}
                            onChange={e => handleTextChange(e.target.value)}
                            onBlur={handleBlur}
                            onClick={e => { e.stopPropagation(); setOpen(true); }}
                        />
                        {(inputText || value) && (
                            <button
                                type="button"
                                tabIndex={-1}
                                className="ml-auto text-muted-foreground hover:text-foreground transition-colors"
                                onClick={handleClear}
                            >
                                <X className="h-3 w-3" />
                            </button>
                        )}
                    </div>
                </PopoverTrigger>

                <PopoverContent className="w-auto p-0" align={align} sideOffset={6}>
                    <div className="p-3 select-none">
                        {/* Month nav */}
                        <div className="flex items-center justify-between mb-2">
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => setViewMonth(m => subMonths(m, 1))}
                            >
                                <ChevronLeft className="h-4 w-4" />
                            </Button>
                            <span className="text-sm font-semibold tabular-nums">
                                {format(viewMonth, 'MMMM yyyy')}
                            </span>
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                onClick={() => setViewMonth(m => addMonths(m, 1))}
                            >
                                <ChevronRight className="h-4 w-4" />
                            </Button>
                        </div>

                        {/* Weekday header */}
                        <div className="grid grid-cols-7 mb-0.5">
                            {WEEKDAYS.map(d => (
                                <div
                                    key={d}
                                    className="h-8 flex items-center justify-center text-[10px] font-medium text-muted-foreground"
                                >
                                    {d}
                                </div>
                            ))}
                        </div>

                        {/* Day grid */}
                        <div className="grid grid-cols-7">
                            {calDays.map(day => {
                                const inMonth = day.getMonth() === viewMonth.getMonth();
                                const selected = selectedDate && isValid(selectedDate) && isSameDay(day, selectedDate);
                                const today = isToday(day);
                                return (
                                    <button
                                        key={day.toISOString()}
                                        type="button"
                                        onClick={() => handleDayClick(day)}
                                        className={cn(
                                            'h-8 w-8 mx-auto flex items-center justify-center rounded-full text-xs font-medium transition-colors',
                                            !inMonth && 'text-muted-foreground/30',
                                            inMonth && !selected && 'hover:bg-muted',
                                            today && !selected && 'ring-1 ring-primary/60 text-primary',
                                            selected && 'bg-primary text-primary-foreground shadow-sm',
                                        )}
                                    >
                                        {format(day, 'd')}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Hint */}
                        <p className="text-[10px] text-muted-foreground mt-2 text-center">
                            Or type a date in MM/DD/YYYY format above
                        </p>
                    </div>
                </PopoverContent>
            </Popover>

            {error && (
                <p className="text-[10px] text-destructive leading-tight px-0.5">{error}</p>
            )}
        </div>
    );
});

DatePicker.displayName = 'DatePicker';
