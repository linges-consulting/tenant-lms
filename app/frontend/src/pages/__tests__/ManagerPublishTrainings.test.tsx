import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils';
import { ManagerPublishTrainings } from '../ManagerPublishTrainings';

const getManagerTrainings = vi.fn();
const publishTraining = vi.fn();
const unpublishTraining = vi.fn();

vi.mock('../../api/trainings', () => ({
    managerTrainingsApi: {
        getManagerTrainings: (...a: unknown[]) => getManagerTrainings(...a),
        publishTraining: (...a: unknown[]) => publishTraining(...a),
        unpublishTraining: (...a: unknown[]) => unpublishTraining(...a),
    },
}));

const baseTraining = {
    collaborators: [],
    version: 1,
    is_archived: false,
    requires_certificate: false,
    tenant_id: 'tn',
    category: 'Safety',
    creator_name: 'Owner',
};

const TRAININGS = [
    { ...baseTraining, id: 'd1', title: 'Draft One',     is_published: false, is_ready: false, lifecycle_status: 'draft' as const },
    { ...baseTraining, id: 'r1', title: 'Ready One',     is_published: false, is_ready: true,  lifecycle_status: 'ready' as const },
    { ...baseTraining, id: 'p1', title: 'Published One', is_published: true,  is_ready: true,  lifecycle_status: 'published' as const },
    { ...baseTraining, id: 'a1', title: 'Archived One',  is_published: false, is_ready: true,  lifecycle_status: 'archived' as const, is_archived: true },
];

beforeEach(() => {
    getManagerTrainings.mockResolvedValue(TRAININGS);
    publishTraining.mockResolvedValue({ ...TRAININGS[1], is_published: true, lifecycle_status: 'published' });
    unpublishTraining.mockResolvedValue({ ...TRAININGS[2], is_published: false, is_ready: true, lifecycle_status: 'ready' });
});

describe('ManagerPublishTrainings', () => {
    it('defaults to the "Ready to Publish" filter — only Ready trainings visible', async () => {
        renderWithProviders(<ManagerPublishTrainings />);
        await waitFor(() => {
            expect(screen.getByText('Ready One')).toBeInTheDocument();
        });
        expect(screen.queryByText('Draft One')).not.toBeInTheDocument();
        expect(screen.queryByText('Published One')).not.toBeInTheDocument();
        expect(screen.queryByText('Archived One')).not.toBeInTheDocument();
    });

    it('switching to "All" shows every training', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerPublishTrainings />);
        await waitFor(() => screen.getByText('Ready One'));

        await user.click(screen.getByRole('button', { name: /^All/ }));

        for (const t of TRAININGS) {
            expect(screen.getByText(t.title)).toBeInTheDocument();
        }
    });

    it('clicking Publish on a Ready training calls publishTraining', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerPublishTrainings />);
        await waitFor(() => screen.getByText('Ready One'));

        const publishBtn = screen.getByRole('button', { name: /^Publish$/ });
        await user.click(publishBtn);

        await waitFor(() => {
            expect(publishTraining).toHaveBeenCalledWith('r1');
        });
    });

    it('clicking Unpublish on a Published training calls unpublishTraining (from All view)', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerPublishTrainings />);
        await waitFor(() => screen.getByText('Ready One'));

        await user.click(screen.getByRole('button', { name: /^All/ }));
        await waitFor(() => screen.getByText('Published One'));

        const unpublishBtn = screen.getByRole('button', { name: /Unpublish/i });
        await user.click(unpublishBtn);

        await waitFor(() => {
            expect(unpublishTraining).toHaveBeenCalledWith('p1');
        });
    });

    it('preview button opens the Preview Training dialog with Content + Simulate options', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerPublishTrainings />);
        await waitFor(() => screen.getByText('Ready One'));

        await user.click(screen.getByTitle('Preview training'));

        await waitFor(() => {
            expect(screen.getByText(/^Preview Training$/)).toBeInTheDocument();
        });
        expect(screen.getByText('View Content')).toBeInTheDocument();
        expect(screen.getByText('Simulate Training')).toBeInTheDocument();
    });
});
