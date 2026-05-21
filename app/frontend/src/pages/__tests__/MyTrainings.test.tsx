import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils';
import { Routes, Route } from 'react-router-dom';
import { MyTrainings } from '../MyTrainings';

// ---- Mocks --------------------------------------------------------------

vi.mock('../../contexts/auth-context', () => ({
    useAuth: () => ({ user: { id: 'u1', full_name: 'Test User' } }),
}));

const getPublishedTrainings = vi.fn();
const getCertificates = vi.fn();

vi.mock('../../api/trainings', () => ({
    trainingsApi: {
        getPublishedTrainings: (...args: unknown[]) => getPublishedTrainings(...args),
        getCertificates: (...args: unknown[]) => getCertificates(...args),
    },
}));

vi.mock('../../api/certificates', () => ({
    certificatesApi: {
        viewCertificatePdf: vi.fn(),
    },
}));

// ---- Fixtures -----------------------------------------------------------

const TRAININGS = [
    { id: 't1', title: 'Active Course', status: 'in_progress', progress_percentage: 50, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
    { id: 't2', title: 'Pending Pickup', status: 'not_started', progress_percentage: 0, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
    { id: 't3', title: 'Done Course', status: 'completed', progress_percentage: 100, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
    { id: 't4', title: 'Old Expired', status: 'expired', progress_percentage: 30, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
];

beforeEach(() => {
    getPublishedTrainings.mockResolvedValue(TRAININGS);
    getCertificates.mockResolvedValue([]);
});

// ---- Tests --------------------------------------------------------------

describe('MyTrainings — filter pills', () => {
    it('renders the four filter pills with counts', async () => {
        renderWithProviders(<MyTrainings />);
        await waitFor(() => {
            expect(screen.getByRole('button', { name: /Active/ })).toBeInTheDocument();
        });
        // All four filter labels are present
        expect(screen.getByRole('button', { name: /^Active/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^Completed/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^Expired/ })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^All/ })).toBeInTheDocument();
    });

    it('defaults to "Active" filter — shows in-progress + not-started, hides completed/expired', async () => {
        renderWithProviders(<MyTrainings />);
        await waitFor(() => {
            expect(screen.getByText('Active Course')).toBeInTheDocument();
        });
        expect(screen.getByText('Pending Pickup')).toBeInTheDocument();
        expect(screen.queryByText('Done Course')).not.toBeInTheDocument();
        expect(screen.queryByText('Old Expired')).not.toBeInTheDocument();
    });

    it('switching to Completed filter shows only completed trainings', async () => {
        const user = userEvent.setup();
        renderWithProviders(<MyTrainings />);
        await waitFor(() => screen.getByText('Active Course'));

        await user.click(screen.getByRole('button', { name: /^Completed/ }));

        expect(screen.getByText('Done Course')).toBeInTheDocument();
        expect(screen.queryByText('Active Course')).not.toBeInTheDocument();
        expect(screen.queryByText('Old Expired')).not.toBeInTheDocument();
    });

    it('switching to All shows every training', async () => {
        const user = userEvent.setup();
        renderWithProviders(<MyTrainings />);
        await waitFor(() => screen.getByText('Active Course'));

        await user.click(screen.getByRole('button', { name: /^All/ }));

        expect(screen.getByText('Active Course')).toBeInTheDocument();
        expect(screen.getByText('Pending Pickup')).toBeInTheDocument();
        expect(screen.getByText('Done Course')).toBeInTheDocument();
        expect(screen.getByText('Old Expired')).toBeInTheDocument();
    });

    it('empty-state message shown when the filter has no matches', async () => {
        getPublishedTrainings.mockResolvedValueOnce([]);
        renderWithProviders(<MyTrainings />);
        await waitFor(() => {
            expect(screen.getByText(/No courses here/i)).toBeInTheDocument();
        });
        // The Active-filter empty message hints to check Completed
        expect(screen.getByText(/No active trainings/i)).toBeInTheDocument();
    });
});

describe('MyTrainings — card interactions', () => {
    it('clicking a course card navigates to the training viewer', async () => {
        const user = userEvent.setup();
        // Use a Routes wrapper so we can verify the navigation landed at the
        // expected URL via a marker component on the destination route.
        renderWithProviders(
            <Routes>
                <Route path="/" element={<MyTrainings />} />
                <Route path="/dashboard/learn/:id" element={<div data-testid="viewer-route">VIEWER MOUNTED</div>} />
            </Routes>,
        );
        await waitFor(() => screen.getByText('Active Course'));

        await user.click(screen.getByText('Active Course'));

        await waitFor(() => {
            expect(screen.getByTestId('viewer-route')).toBeInTheDocument();
        });
    });

    it('completed cards show "View Certificate" when a certificate is issued', async () => {
        getPublishedTrainings.mockResolvedValueOnce([
            { id: 't3', title: 'Done Course', status: 'completed', progress_percentage: 100, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: true, tenant_id: 'tn' },
        ]);
        getCertificates.mockResolvedValueOnce([
            { id: 'cert-1', training_id: 't3', certificate_id: 'cert-1', certificate_number: 'CERT-XYZ' },
        ]);
        const user = userEvent.setup();
        renderWithProviders(<MyTrainings />);

        // Switch to Completed filter
        await waitFor(() => screen.getByRole('button', { name: /^Completed/ }));
        await user.click(screen.getByRole('button', { name: /^Completed/ }));

        // View Certificate button is present for the completed card
        await waitFor(() => {
            expect(screen.getByText(/View Certificate/i)).toBeInTheDocument();
        });
    });

    it('completed cards without a certificate do NOT show "View Certificate"', async () => {
        getPublishedTrainings.mockResolvedValueOnce([
            { id: 't3', title: 'Done Course', status: 'completed', progress_percentage: 100, collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
        ]);
        getCertificates.mockResolvedValueOnce([]);
        const user = userEvent.setup();
        renderWithProviders(<MyTrainings />);

        await waitFor(() => screen.getByRole('button', { name: /^Completed/ }));
        await user.click(screen.getByRole('button', { name: /^Completed/ }));

        await waitFor(() => screen.getByText('Done Course'));
        expect(screen.queryByText(/View Certificate/i)).not.toBeInTheDocument();
    });
});
