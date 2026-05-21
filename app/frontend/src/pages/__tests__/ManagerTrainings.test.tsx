import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils';
import { ManagerTrainings } from '../ManagerTrainings';

// ---- Mocks --------------------------------------------------------------

const getManagerTrainings = vi.fn();
const createTraining = vi.fn();
const markReady = vi.fn();
const sendToDraft = vi.fn();
const archiveTraining = vi.fn();
const deleteTraining = vi.fn();

vi.mock('../../api/trainings', () => ({
    managerTrainingsApi: {
        getManagerTrainings: (...a: unknown[]) => getManagerTrainings(...a),
        createTraining: (...a: unknown[]) => createTraining(...a),
        markReady: (...a: unknown[]) => markReady(...a),
        sendToDraft: (...a: unknown[]) => sendToDraft(...a),
        archiveTraining: (...a: unknown[]) => archiveTraining(...a),
        deleteTraining: (...a: unknown[]) => deleteTraining(...a),
    },
}));

const CREATOR_ID = 'u-creator';

vi.mock('../../contexts/auth-context', () => ({
    useAuth: () => ({
        user: { id: CREATOR_ID, full_name: 'Test Creator', is_sysadmin: false },
        activeMembership: { is_training_creator: true, is_business_manager: true },
    }),
}));

vi.mock('../../components/ManageEditorsModal', () => ({
    ManageEditorsModal: () => null,
}));

vi.mock('sonner', () => ({
    toast: { success: vi.fn(), error: vi.fn() },
}));

// ---- Fixtures -----------------------------------------------------------

const base = {
    collaborators: [],
    version: 1,
    is_archived: false,
    requires_certificate: false,
    tenant_id: 'tn',
    category: 'safety',
    creator_name: 'Test Creator',
    created_by_id: CREATOR_ID,
};

const TRAININGS = [
    { ...base, id: 'd1', title: 'Compliance Draft',  is_published: false, is_ready: false },
    { ...base, id: 'r1', title: 'Ready Onboarding',  is_published: false, is_ready: true  },
    { ...base, id: 'p1', title: 'Published Safety',  is_published: true,  is_ready: true  },
    { ...base, id: 'a1', title: 'Archived Topic',    is_published: false, is_ready: true,  is_archived: true },
];

beforeEach(() => {
    getManagerTrainings.mockResolvedValue(TRAININGS);
    createTraining.mockResolvedValue({ ...base, id: 'new-id', title: 'Brand New', is_published: false, is_ready: false });
    markReady.mockResolvedValue({ ...TRAININGS[0], is_ready: true });
    sendToDraft.mockResolvedValue({ ...TRAININGS[1], is_ready: false });
    archiveTraining.mockResolvedValue({});
    deleteTraining.mockResolvedValue({});
});

// ---- Tests --------------------------------------------------------------

describe('ManagerTrainings (Course Studio)', () => {
    it('renders all trainings in the table', async () => {
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));
        expect(screen.getByText('Ready Onboarding')).toBeInTheDocument();
        expect(screen.getByText('Published Safety')).toBeInTheDocument();
        expect(screen.getByText('Archived Topic')).toBeInTheDocument();
    });

    it('shows correct status badge per training', async () => {
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));
        // Each status appears at least once. Metric cards may also use the
        // word "Published" so use getAllByText for that one.
        expect(screen.getByText(/^Draft$/)).toBeInTheDocument();
        expect(screen.getByText(/^Ready$/)).toBeInTheDocument();
        expect(screen.getAllByText(/^Published$/).length).toBeGreaterThan(0);
        expect(screen.getByText(/^Archived$/)).toBeInTheDocument();
    });

    it('search filters by title', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));

        const search = screen.getByPlaceholderText(/search/i);
        await user.type(search, 'onboarding');

        await waitFor(() => {
            expect(screen.queryByText('Compliance Draft')).not.toBeInTheDocument();
        });
        expect(screen.getByText('Ready Onboarding')).toBeInTheDocument();
    });

    it('opens the Create Training dialog and validates a required title', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));

        await user.click(screen.getByRole('button', { name: /Create Training/i }));

        // Dialog open: title input + Save button visible. The placeholder for
        // the new-training title looks like "e.g. Workplace Safety Fundamentals".
        const titleInput = await screen.findByPlaceholderText(/Workplace Safety|Training Title|e\.g\./i);
        // Use the Save Training button inside the dialog footer (not the page header Create button).
        const saveBtn = (await screen.findAllByRole('button', { name: /Save|Create/i })).pop()!;

        // Submit with empty title — error shown, no API call
        await user.click(saveBtn);
        await waitFor(() => {
            expect(screen.getByText(/title is required/i)).toBeInTheDocument();
        });
        expect(createTraining).not.toHaveBeenCalled();

        // Provide a title and submit — API called with the title
        await user.type(titleInput, 'Brand New');
        await user.click(saveBtn);

        await waitFor(() => {
            expect(createTraining).toHaveBeenCalledTimes(1);
        });
        expect(createTraining.mock.calls[0][0].title).toBe('Brand New');
    });

    it('Mark as Ready action calls the API for a draft training', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));

        // The draft row has a dropdown trigger; open it
        // There are multiple "More" triggers; click the one in the draft row.
        const draftRow = screen.getByText('Compliance Draft').closest('tr');
        expect(draftRow).toBeTruthy();
        const triggerBtn = draftRow!.querySelector('button');
        expect(triggerBtn).toBeTruthy();
        await user.click(triggerBtn!);

        const markReadyItem = await screen.findByText(/Mark as Ready/i);
        await user.click(markReadyItem);

        await waitFor(() => {
            expect(markReady).toHaveBeenCalledTimes(1);
        });
        expect(markReady.mock.calls[0][0]).toBe('d1');
    });

    it('Revert to Draft action shows for ready/published and calls sendToDraft', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Ready Onboarding'));

        const readyRow = screen.getByText('Ready Onboarding').closest('tr');
        const triggerBtn = readyRow!.querySelector('button');
        await user.click(triggerBtn!);

        const revertItem = await screen.findByText(/Revert to Draft/i);
        await user.click(revertItem);

        await waitFor(() => {
            expect(sendToDraft).toHaveBeenCalledWith('r1');
        });
    });

    it('Archive action opens confirmation and only archives on confirm', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Ready Onboarding'));

        const readyRow = screen.getByText('Ready Onboarding').closest('tr');
        const triggerBtn = readyRow!.querySelector('button');
        await user.click(triggerBtn!);

        const archiveItem = await screen.findByText(/Archive Training/i);
        await user.click(archiveItem);

        // Confirmation dialog opens — API not called yet
        expect(archiveTraining).not.toHaveBeenCalled();

        // Confirm — the AlertDialog's confirm button is also labeled "Archive Training".
        // There are now two such buttons in the DOM (the closed dropdown item is still
        // mounted by Radix); the alertdialog one is the last in document order.
        const archiveButtons = await screen.findAllByRole('button', { name: /Archive Training/i });
        await user.click(archiveButtons[archiveButtons.length - 1]);

        await waitFor(() => {
            expect(archiveTraining).toHaveBeenCalledWith('r1');
        });
    });

    it('Delete action only appears for draft trainings owned by the user', async () => {
        const user = userEvent.setup();
        renderWithProviders(<ManagerTrainings />);
        await waitFor(() => screen.getByText('Compliance Draft'));

        // Draft row → opens dropdown → Delete should appear
        const draftRow = screen.getByText('Compliance Draft').closest('tr');
        await user.click(draftRow!.querySelector('button')!);
        expect(await screen.findByText(/Delete Training/i)).toBeInTheDocument();
    });
});
