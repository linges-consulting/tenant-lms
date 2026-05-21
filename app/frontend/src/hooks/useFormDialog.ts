import { useState, useCallback } from 'react';

/**
 * Custom hook to manage form dialog state and reduce code duplication.
 * Handles: loading, errors, and form reset logic.
 */
export function useFormDialog() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const setLoadingState = useCallback((loading: boolean) => {
    setIsLoading(loading);
  }, []);

  const setErrorMessage = useCallback((message: string) => {
    setError(message);
  }, []);

  const clearError = useCallback(() => {
    setError('');
  }, []);

  const resetForm = useCallback(() => {
    setIsLoading(false);
    setError('');
  }, []);

  return {
    isLoading,
    setIsLoading: setLoadingState,
    error,
    setError: setErrorMessage,
    clearError,
    resetForm,
  };
}

/**
 * Hook for managing clipboard copy state and timeout.
 */
export function useCopyToClipboard(timeout = 2000) {
  const [copiedField, setCopiedField] = useState<string | null>(null);

  const copyToClipboard = useCallback(
    async (text: string, field: string) => {
      try {
        await navigator.clipboard.writeText(text);
        setCopiedField(field);
        const timer = setTimeout(() => setCopiedField(null), timeout);
        return () => clearTimeout(timer);
      } catch (err) {
        console.error('Failed to copy to clipboard:', err);
        throw new Error('Failed to copy to clipboard');
      }
    },
    [timeout]
  );

  return {
    copiedField,
    copyToClipboard,
    resetCopied: () => setCopiedField(null),
  };
}

/**
 * Hook for managing token visibility state.
 */
export function useTokenVisibility() {
  const [isVisible, setIsVisible] = useState(false);

  const toggle = useCallback(() => {
    setIsVisible(prev => !prev);
  }, []);

  const show = useCallback(() => {
    setIsVisible(true);
  }, []);

  const hide = useCallback(() => {
    setIsVisible(false);
  }, []);

  return {
    isVisible,
    toggle,
    show,
    hide,
  };
}

/**
 * Extract error message from API response.
 */
export function extractErrorMessage(error: unknown): string {
  if (typeof error === 'string') return error;
  const e = error as { response?: { data?: { detail?: unknown } }; message?: string };
  if (e?.response?.data?.detail) {
    const detail = e.response.data.detail;
    return typeof detail === 'string' ? detail : 'An error occurred';
  }
  if (e?.message) return e.message;
  return 'An unexpected error occurred';
}
