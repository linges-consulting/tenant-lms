import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent, within } from '../../test/utils';
import { Routes, Route } from 'react-router-dom';
import { ManagerTrainingAssignments } from '../ManagerTrainingAssignments';

// ---- Mocks --------------------------------------------------------------

const listAssignments = vi.fn();
const getManagerTrainings = vi.fn();
const bulkAssign = vi.fn();

vi.mock('../../api/trainings', () => ({
    managerTrainingsApi: {
        listAssignments: (...a: unknown[]) => listAssignments(...a),
        getManagerTrainings: (...a: unknown[]) => getManagerTrainings(...a),
        bulkAssign: (...a: unknown[]) => bulkAssign(...a),
        deleteAssignment: vi.fn(),
    },
}));

const listTenantUsers = vi.fn();
vi.mock('../../api/users', () => ({
    userService: {
        listTenantUsers: (...a: unknown[]) => listTenantUsers(...a),
    },
}));

const groupsList = vi.fn();
const groupsListMembers = vi.fn();
vi.mock('../../api/groups', () => ({
    groupService: {
        list: (...a: unknown[]) => groupsList(...a),
        listMembers: (...a: unknown[]) => groupsListMembers(...a),
    },
}));

// ---- Fixtures -----------------------------------------------------------

const TRAINING_ID = 't-1';

beforeEach(() => {
    vi.clearAllMocks();
    listAssignments.mockResolvedValue([]);
    getManagerTrainings.mockResolvedValue([
        { id: TRAINING_ID, title: 'Compliance 101', collaborators: [], version: 1, is_published: true, is_ready: true, is_archived: false, requires_certificate: false, tenant_id: 'tn' },
    ]);
    // Standalone employees (right column). Names chosen NOT to collide with
    // group members so we can assert on each section independently.
    listTenantUsers.mockResolvedValue([
        { id: 'u-solo-1', email: 'solo1@example.com', full_name: 'Solo Employee One' },
        { id: 'u-solo-2', email: 'solo2@example.com', full_name: 'Solo Employee Two' },
    ]);
    groupsList.mockResolvedValue([
        { id: 'g1', name: 'Engineering', member_count: 2 },
        { id: 'g2', name: 'Sales', member_count: 1 },
    ]);
    groupsListMembers.mockImplementation((gid: string) => {
        if (gid === 'g1') {
            return Promise.resolve([
                { user_id: 'm-eng-1', user_email: 'eng1@example.com', user_name: 'Engineer Member' },
                { user_id: 'm-eng-2', user_email: 'eng2@example.com', user_name: 'Engineer Mate' },
            ]);
        }
        return Promise.resolve([
            { user_id: 'm-sales-1', user_email: 'sales1@example.com', user_name: 'Sales Person' },
        ]);
    });
    bulkAssign.mockResolvedValue({ message: 'ok', count: 1 });
});

// Route wrapper so useParams returns a training id.
const renderAssignments = () =>
    renderWithProviders(
        <Routes>
            <Route path="/manage/publish/:id/assignments" element={<ManagerTrainingAssignments />} />
        </Routes>,
        { initialEntries: [`/manage/publish/${TRAINING_ID}/assignments`] },
    );

// ---- Tests --------------------------------------------------------------

describe('ManagerTrainingAssignments — group expand on New Assignment tab', () => {
    it('renders groups with member counts', async () => {
        renderAssignments();
        await waitFor(() => {
            expect(screen.getByText('Engineering')).toBeInTheDocument();
        });
        expect(screen.getByText('Sales')).toBeInTheDocument();
        expect(screen.getByText('2 members')).toBeInTheDocument();
        expect(screen.getByText('1 members')).toBeInTheDocument();
    });

    it('clicking the View members chevron loads & shows the group\'s users', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        const viewButtons = screen.getAllByTitle('View members');
        // Engineering is the first group
        await user.click(viewButtons[0]);

        await waitFor(() => {
            expect(screen.getByText('Engineer Member')).toBeInTheDocument();
        });
        expect(screen.getByText('Engineer Mate')).toBeInTheDocument();
        expect(groupsListMembers).toHaveBeenCalledWith('g1');
    });

    it('clicking the chevron a second time collapses the member list', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        const viewButtons = screen.getAllByTitle('View members');
        await user.click(viewButtons[0]);
        await waitFor(() => screen.getByText('Engineer Member'));

        // Button now reads "Hide members"
        await user.click(screen.getByTitle('Hide members'));
        await waitFor(() => {
            expect(screen.queryByText('Engineer Member')).not.toBeInTheDocument();
        });
    });

    it('expanding does NOT select the group (chevron click is separate from row click)', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        const viewButtons = screen.getAllByTitle('View members');
        await user.click(viewButtons[0]);
        await waitFor(() => screen.getByText('Engineer Member'));

        // Selection counter should still say 0 (only the chevron was clicked).
        // The action bar text is "Select groups or employees above" when empty.
        expect(screen.getByText(/Select groups or employees above/i)).toBeInTheDocument();
    });

    it('clicking the row body (not the chevron) toggles selection', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        // Click on the group name text (which is inside the selectable row)
        await user.click(screen.getByText('Engineering'));
        await waitFor(() => {
            expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
        });
    });

    it('bulk-assigning selected groups calls the API with their ids', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        await user.click(screen.getByText('Engineering'));
        await waitFor(() => screen.getByText(/1 selected/i));

        const submit = screen.getByRole('button', { name: /Assign Selected/i });
        await user.click(submit);

        await waitFor(() => {
            expect(bulkAssign).toHaveBeenCalledTimes(1);
        });
        const [trainingId, payload] = bulkAssign.mock.calls[0];
        expect(trainingId).toBe(TRAINING_ID);
        expect(payload.group_ids).toEqual(['g1']);
        expect(payload.user_ids).toEqual([]);
    });
});

// Silence unused import warning in jsdom
void within;

// ===========================================================================
// New Assignment tab — additional scenarios
// ===========================================================================

describe('ManagerTrainingAssignments — search, due date, mixed selection', () => {
    it('search filters BOTH the groups column and the employees column', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        const search = screen.getByPlaceholderText(/Search people or groups/i);
        await user.type(search, 'sales');

        await waitFor(() => {
            // Engineering filtered out
            expect(screen.queryByText('Engineering')).not.toBeInTheDocument();
        });
        // Sales group still visible
        expect(screen.getByText('Sales')).toBeInTheDocument();
        // Standalone employee names "Solo Employee" don't match "sales" → filtered out
        expect(screen.queryByText('Solo Employee One')).not.toBeInTheDocument();
        expect(screen.queryByText('Solo Employee Two')).not.toBeInTheDocument();
    });

    it('bulkAssign forwards the chosen due date in ISO format', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        // Select a group + a user
        await user.click(screen.getByText('Engineering'));
        await user.click(screen.getByText('Solo Employee One'));
        await waitFor(() => screen.getByText(/2 selected/i));

        // Set the due date via the native date input
        const dueDate = document.querySelector<HTMLInputElement>('input[type="date"]');
        expect(dueDate, 'expected a date input').toBeTruthy();
        await user.type(dueDate!, '2026-12-31');

        await user.click(screen.getByRole('button', { name: /Assign Selected/i }));

        await waitFor(() => {
            expect(bulkAssign).toHaveBeenCalledTimes(1);
        });
        const [trainingId, payload] = bulkAssign.mock.calls[0];
        expect(trainingId).toBe(TRAINING_ID);
        expect(payload.group_ids).toEqual(['g1']);
        expect(payload.user_ids).toEqual(['u-solo-1']);
        expect(payload.due_date).toBe('2026-12-31');
    });

    it('mixed user + group selection — selection counter and bulkAssign payload reflect both', async () => {
        const user = userEvent.setup();
        renderAssignments();
        await waitFor(() => screen.getByText('Engineering'));

        await user.click(screen.getByText('Engineering'));
        await user.click(screen.getByText('Sales'));
        await user.click(screen.getByText('Solo Employee One'));

        await waitFor(() => screen.getByText(/3 selected/i));

        await user.click(screen.getByRole('button', { name: /Assign Selected \(3\)/i }));

        await waitFor(() => {
            expect(bulkAssign).toHaveBeenCalledTimes(1);
        });
        const [, payload] = bulkAssign.mock.calls[0];
        expect(payload.group_ids.sort()).toEqual(['g1', 'g2']);
        expect(payload.user_ids).toEqual(['u-solo-1']);
    });
});

// ===========================================================================
// Active Assignments tab
// ===========================================================================

describe('ManagerTrainingAssignments — Active Assignments tab', () => {
    it('renders existing assignments and supports deletion', async () => {
        const user = userEvent.setup();
        const deleteAssignment = vi.fn().mockResolvedValue({});
        listAssignments.mockResolvedValue([
            { id: 'a-user', training_id: TRAINING_ID, user_id: 'u-solo-1', user_name: 'Solo Employee One', assigned_at: '2026-01-01T00:00:00Z' },
            { id: 'a-group', training_id: TRAINING_ID, group_id: 'g1', group_name: 'Engineering', assigned_at: '2026-01-01T00:00:00Z' },
        ]);

        // Replace deleteAssignment on the mocked module so we can spy on it.
        // The existing vi.mock for '../../api/trainings' defines deleteAssignment
        // as vi.fn(), but we need a fresh spy for this single test.
        const trainingsModule = await import('../../api/trainings');
        trainingsModule.managerTrainingsApi.deleteAssignment = deleteAssignment;

        renderAssignments();
        await waitFor(() => screen.getByRole('tab', { name: /Active Assignments/i }));

        // Switch to the Active tab
        await user.click(screen.getByRole('tab', { name: /Active Assignments/i }));

        // Both assignments listed
        await waitFor(() => {
            expect(screen.getByText('Solo Employee One')).toBeInTheDocument();
        });
        expect(screen.getByText('Engineering')).toBeInTheDocument();

        // Find the delete buttons (lucide-trash-2 icons inside ghost buttons)
        const trashButtons = Array.from(document.querySelectorAll('button'))
            .filter(b => b.querySelector('svg.lucide-trash-2'));
        expect(trashButtons.length).toBeGreaterThan(0);

        await user.click(trashButtons[0]);

        await waitFor(() => {
            expect(deleteAssignment).toHaveBeenCalledTimes(1);
        });
    });
});
