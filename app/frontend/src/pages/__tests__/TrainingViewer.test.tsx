import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils';
import { Routes, Route } from 'react-router-dom';
import { TrainingViewer } from '../TrainingViewer';

// ---- Mocks --------------------------------------------------------------

const getTraining = vi.fn();
const getTrainingStructure = vi.fn();
const completeChapter = vi.fn();
const completeTraining = vi.fn();
const submitQuiz = vi.fn();
const getCertificates = vi.fn();

vi.mock('../../api/trainings', () => ({
    trainingsApi: {
        getTraining: (...a: unknown[]) => getTraining(...a),
        getTrainingStructure: (...a: unknown[]) => getTrainingStructure(...a),
        completeChapter: (...a: unknown[]) => completeChapter(...a),
        completeTraining: (...a: unknown[]) => completeTraining(...a),
        submitQuiz: (...a: unknown[]) => submitQuiz(...a),
        getCertificates: (...a: unknown[]) => getCertificates(...a),
    },
}));

vi.mock('../../api/certificates', () => ({
    certificatesApi: { viewCertificatePdf: vi.fn() },
}));

vi.mock('../../contexts/auth-context', () => ({
    useAuth: () => ({
        user: { id: 'u1', full_name: 'Test Learner', is_sysadmin: false },
        activeMembership: { is_business_manager: false, is_training_creator: false },
    }),
}));

// react-player tries to do real network/DOM work that jsdom doesn't support.
vi.mock('react-player', () => ({ default: () => null }));

// ---- Fixtures -----------------------------------------------------------

const TRAINING_ID = 'tr-1';

const buildStructure = ({ m1Done = false, m2Done = false } = {}) => ({
    id: TRAINING_ID,
    title: 'Modular Course',
    description: 'desc',
    version: 1,
    is_published: true,
    is_ready: true,
    is_archived: false,
    requires_certificate: false,
    tenant_id: 'tn',
    collaborators: [],
    status: m1Done && m2Done ? 'completed' : 'in_progress',
    progress_percentage: 0,
    completed_chapters: (m1Done ? 1 : 0) + (m2Done ? 1 : 0),
    total_chapters: 2,
    certificate_id: null,
    modules: [
        {
            id: 'mod-1',
            title: 'Module One',
            sequence_order: 1,
            chapters: [
                {
                    id: 'ch-1', title: 'M1 Chapter', content_type: 'RICH_TEXT',
                    content_data: { text: '<p>m1 content</p>' }, sequence_order: 1,
                    is_completed: m1Done,
                },
            ],
        },
        {
            id: 'mod-2',
            title: 'Module Two',
            sequence_order: 2,
            chapters: [
                {
                    id: 'ch-2', title: 'M2 Chapter', content_type: 'RICH_TEXT',
                    content_data: { text: '<p>m2 content</p>' }, sequence_order: 2,
                    is_completed: m2Done,
                },
            ],
        },
    ],
    orphan_chapters: [],
});

beforeEach(() => {
    vi.clearAllMocks();
    getCertificates.mockResolvedValue([]);
    completeChapter.mockResolvedValue({ status: 'success', chapter_id: 'ch-1' });
    completeTraining.mockResolvedValue({ status: 'success', certificate_id: 'cert-xyz', requires_certificate: false });
});

const renderViewer = () =>
    renderWithProviders(
        <Routes>
            <Route path="/learn/:id" element={<TrainingViewer />} />
        </Routes>,
        { initialEntries: [`/learn/${TRAINING_ID}`] },
    );

// ---- Tests --------------------------------------------------------------

describe('TrainingViewer — module-level completion & progressive lock', () => {
    it('renders both module titles in the sidebar', async () => {
        getTraining.mockResolvedValue({ ...buildStructure(), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure());

        renderViewer();

        await waitFor(() => {
            expect(screen.getByText('Module One')).toBeInTheDocument();
        });
        expect(screen.getByText('Module Two')).toBeInTheDocument();
    });

    it('shows N/total badges on each module header reflecting completion', async () => {
        getTraining.mockResolvedValue({ ...buildStructure({ m1Done: true }), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure({ m1Done: true }));

        renderViewer();

        // Expect "1/1" badge for Module One (complete) and "0/1" for Module Two
        await waitFor(() => {
            expect(screen.getByText('1/1')).toBeInTheDocument();
        });
        expect(screen.getByText('0/1')).toBeInTheDocument();
    });

    it('locks Module 2 chapter visually when Module 1 is incomplete (progressive)', async () => {
        getTraining.mockResolvedValue({ ...buildStructure(), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure());

        renderViewer();

        // Sidebar entries render as <button> elements; restrict to buttons to
        // avoid colliding with the active chapter title (rendered as <h1>).
        await waitFor(() => {
            expect(screen.getByRole('button', { name: /M2 Chapter/ })).toBeInTheDocument();
        });

        const m2Button = screen.getByRole('button', { name: /M2 Chapter/ });
        expect(m2Button).toBeDisabled();

        const m1Button = screen.getByRole('button', { name: /M1 Chapter/ });
        expect(m1Button).not.toBeDisabled();
    });

    it('unlocks Module 2 chapter once Module 1\'s chapter is complete', async () => {
        getTraining.mockResolvedValue({ ...buildStructure({ m1Done: true }), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure({ m1Done: true }));

        renderViewer();

        await waitFor(() => {
            expect(screen.getByRole('button', { name: /M2 Chapter/ })).toBeInTheDocument();
        });

        const m2Button = screen.getByRole('button', { name: /M2 Chapter/ });
        expect(m2Button).not.toBeDisabled();
    });
});

// ===========================================================================
// Chapter completion
// ===========================================================================

describe('TrainingViewer — chapter completion', () => {
    it('renders the active chapter title in the main content area', async () => {
        getTraining.mockResolvedValue({ ...buildStructure(), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure());

        renderViewer();

        await waitFor(() => {
            // The active chapter title shows as a heading (h1).
            expect(screen.getByRole('heading', { name: 'M1 Chapter' })).toBeInTheDocument();
        });
    });

    it('clicking "Next Lesson" calls trainingsApi.completeChapter for the active chapter', async () => {
        const user = userEvent.setup();
        getTraining.mockResolvedValue({ ...buildStructure(), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure());

        renderViewer();

        await waitFor(() => screen.getByRole('heading', { name: 'M1 Chapter' }));

        await user.click(screen.getByRole('button', { name: /Next Lesson/i }));

        await waitFor(() => {
            expect(completeChapter).toHaveBeenCalledTimes(1);
        });
        expect(completeChapter.mock.calls[0][0]).toBe(TRAINING_ID);
        expect(completeChapter.mock.calls[0][1]).toBe('ch-1');
    });

    it('the last chapter button reads "Finish Course" instead of "Next Lesson"', async () => {
        // Only one chapter, no module — easier to assert "Finish Course"
        const single = {
            ...buildStructure({ m1Done: false }),
            modules: [{
                id: 'm-only', title: 'Only Module', sequence_order: 1,
                chapters: [{
                    id: 'ch-only', title: 'The Only Chapter', content_type: 'RICH_TEXT',
                    content_data: { text: '<p>only</p>' }, sequence_order: 1, is_completed: false,
                }],
            }],
            total_chapters: 1,
        };
        getTraining.mockResolvedValue({ ...single, status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(single);

        renderViewer();

        await waitFor(() => screen.getByRole('heading', { name: 'The Only Chapter' }));
        expect(screen.getByRole('button', { name: /Finish Course/i })).toBeInTheDocument();
    });

    it('shows the completion screen when training.status === completed', async () => {
        const completed = {
            ...buildStructure({ m1Done: true, m2Done: true }),
            status: 'completed',
            completed_chapters: 2,
            total_chapters: 2,
            completed_at: '2026-05-20T10:00:00Z',
        };
        getTraining.mockResolvedValue(completed);
        getTrainingStructure.mockResolvedValue(completed);

        renderViewer();

        await waitFor(() => {
            expect(screen.getByText(/Training Completed!/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/2 \/ 2/)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Back to Dashboard/i })).toBeInTheDocument();
    });

    it('shows the sidebar Progress bar reflecting completed chapters', async () => {
        getTraining.mockResolvedValue({ ...buildStructure({ m1Done: true }), status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(buildStructure({ m1Done: true }));

        renderViewer();

        // 1 of 2 chapters complete → 50% in the compact sidebar progress label.
        await waitFor(() => {
            expect(screen.getByText('50%')).toBeInTheDocument();
        });
    });
});

// ===========================================================================
// Quiz interaction
// ===========================================================================

describe('TrainingViewer — quiz interaction', () => {
    it('lets a learner pick an answer and submit a multiple-choice quiz', async () => {
        const user = userEvent.setup();

        const quizStructure = {
            ...buildStructure(),
            modules: [],
            orphan_chapters: [
                {
                    id: 'qz-1', title: 'Knowledge Check', content_type: 'QUIZ',
                    sequence_order: 1, is_completed: false,
                    content_data: {
                        passing_score: 80,
                        max_attempts: 0,
                        questions: [
                            {
                                id: 'q1',
                                text: 'Pick the right answer',
                                type: 'multiple_choice',
                                options: [
                                    { id: 'a', text: 'Answer Alpha' },
                                    { id: 'b', text: 'Answer Bravo' },
                                ],
                                correct_option_ids: ['a'],
                            },
                        ],
                    },
                    attempts_count: 0,
                },
            ],
            total_chapters: 1,
        };
        getTraining.mockResolvedValue({ ...quizStructure, status: 'in_progress' });
        getTrainingStructure.mockResolvedValue(quizStructure);

        submitQuiz.mockResolvedValue({
            score: 100,
            passed: true,
            attempt_number: 1,
            max_attempts: 0,
            is_locked: false,
        });

        renderViewer();

        await waitFor(() => screen.getByText('Pick the right answer'));

        // Select the correct answer
        await user.click(screen.getByText('Answer Alpha'));

        // Submit via "Process Results"
        await user.click(screen.getByRole('button', { name: /Process Results/i }));

        await waitFor(() => {
            expect(submitQuiz).toHaveBeenCalledTimes(1);
        });
        const [trainingId, chapterId, submission] = submitQuiz.mock.calls[0];
        expect(trainingId).toBe(TRAINING_ID);
        expect(chapterId).toBe('qz-1');
        expect(submission.answers[0]).toMatchObject({
            question_id: 'q1',
            selected_option_ids: ['a'],
        });

        // After submission, the result summary appears (Trophy / "Assessment Passed")
        await waitFor(() => {
            expect(screen.getByText(/Assessment Passed/i)).toBeInTheDocument();
        });
    });
});
