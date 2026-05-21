/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

interface AllProvidersProps {
    children: React.ReactNode;
    initialEntries?: string[];
}

const AllProviders: React.FC<AllProvidersProps> = ({ children, initialEntries = ['/'] }) => {
    return <MemoryRouter initialEntries={initialEntries}>{children}</MemoryRouter>;
};

export interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
    initialEntries?: string[];
}

export function renderWithProviders(ui: React.ReactElement, options: CustomRenderOptions = {}) {
    const { initialEntries, ...rest } = options;
    return render(ui, {
        wrapper: ({ children }) => <AllProviders initialEntries={initialEntries}>{children}</AllProviders>,
        ...rest,
    });
}

export * from '@testing-library/react';
export { default as userEvent } from '@testing-library/user-event';
