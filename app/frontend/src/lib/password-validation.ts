export interface PasswordValidationResult {
    score: number; // 0 to 4
    hasMinLength: boolean;
    hasLowerCase: boolean;
    hasUpperCase: boolean;
    hasNumber: boolean;
    hasSpecialChar: boolean;
}

export const validatePassword = (password: string): PasswordValidationResult => {
    const result: PasswordValidationResult = {
        score: 0,
        hasMinLength: password.length >= 8,
        hasLowerCase: /[a-z]/.test(password),
        hasUpperCase: /[A-Z]/.test(password),
        hasNumber: /[0-9]/.test(password),
        hasSpecialChar: /[!@#$%^&*(),.?":{}|<>]/.test(password),
    };

    if (password.length > 0) {
        if (result.hasMinLength) result.score++;
        if (result.hasLowerCase && result.hasUpperCase) result.score++;
        if (result.hasNumber) result.score++;
        if (result.hasSpecialChar) result.score++;
    }

    return result;
};

export const getStrengthLabel = (score: number): string => {
    switch (score) {
        case 0: return 'Very Weak';
        case 1: return 'Weak';
        case 2: return 'Fair';
        case 3: return 'Strong';
        case 4: return 'Very Strong';
        default: return 'Very Weak';
    }
};

export const getStrengthColor = (score: number): string => {
    switch (score) {
        case 0: return 'bg-destructive';
        case 1: return 'bg-orange-500';
        case 2: return 'bg-yellow-500';
        case 3: return 'bg-emerald-500';
        case 4: return 'bg-emerald-600';
        default: return 'bg-muted';
    }
};
