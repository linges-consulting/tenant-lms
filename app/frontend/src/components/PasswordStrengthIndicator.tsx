import React from 'react';
import { Check, X } from 'lucide-react';
import { validatePassword, getStrengthLabel, getStrengthColor } from '../lib/password-validation';
import { cn } from '../lib/utils';

interface PasswordStrengthIndicatorProps {
    password: string;
}

export const PasswordStrengthIndicator: React.FC<PasswordStrengthIndicatorProps> = ({ password }) => {
    const result = validatePassword(password);

    if (!password) return null;

    const requirements = [
        { label: '8+ characters', met: result.hasMinLength },
        { label: 'Upper & lowercase', met: result.hasLowerCase && result.hasUpperCase },
        { label: 'At least one number', met: result.hasNumber },
        { label: 'At least one special character', met: result.hasSpecialChar },
    ];

    return (
        <div className="space-y-3 mt-2 slide-in-from-top-1 animate-in duration-200">
            <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Strength: {getStrengthLabel(result.score)}</span>
                <span className="text-xs text-muted-foreground">{result.score}/4</span>
            </div>

            <div className="grid grid-cols-4 gap-1.5">
                {[0, 1, 2, 3].map((step) => (
                    <div
                        key={step}
                        className={cn('h-1.5 rounded-full transition-all duration-500', step < result.score ? getStrengthColor(result.score) : 'bg-muted')}
                    />
                ))}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1.5 pt-1">
                {requirements.map((req, i) => (
                    <div key={i} className="flex items-center gap-2">
                        <div className={cn('flex-shrink-0 w-4 h-4 rounded-full flex items-center justify-center', req.met ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground/50')}>
                            {req.met ? <Check className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
                        </div>
                        <span className={cn('text-[11px]', req.met ? 'text-foreground font-medium' : 'text-muted-foreground')}>
                            {req.label}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
};
