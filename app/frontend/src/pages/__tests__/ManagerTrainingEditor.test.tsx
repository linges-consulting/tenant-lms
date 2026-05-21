import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test/utils';
import { Routes, Route } from 'react-router-dom';
import { ManagerTrainingEditor } from '../ManagerTrainingEditor';

// ---- Mocks --------------------------------------------------------------

const getTrainingStructure = vi.fn();
const updateTraining = vi.fn();
const markReady = vi.fn();
const sendToDraft = vi.fn();
const getTrainingHistory = vi.fn();
const createChapter = vi.fn();
const uploadBanner = vi.fn();
const createModule = vi.fn();
const deleteModule = vi.fn();
const deleteChapter = vi.fn();
const updateChapter = vi.fn();
const uploadChapterContent = vi.fn();

vi.mock('../../api/trainings', () => ({
    trainingsApi: {
        getTrainingStructure: (...a: unknown[]) => getTrainingStructure(...a),
    },
    managerTrainingsApi: {
        getTrainingHistory: (...a: unknown[]) => getTrainingHistory(...a),
        updateTraining: (...a: unknown[]) => updateTraining(...a),
        markReady: (...a: unknown[]) => markReady(...a),
        sendToDraft: (...a: unknown[]) => sendToDraft(...a),
        createChapter: (...a: unknown[]) => createChapter(...a),
        uploadBanner: (...a: unknown[]) => uploadBanner(...a),
        createModule: (...a: unknown[]) => createModule(...a),
        deleteModule: (...a: unknown[]) => deleteModule(...a),
        deleteChapter: (...a: unknown[]) => deleteChapter(...a),
        updateChapter: (...a: unknown[]) => updateChapter(...a),
        uploadChapterContent: (...a: unknown[]) => uploadChapterContent(...a),
    },
}));

vi.mock('../../api/certificates', () => ({
    certificatesApi: {
        listTemplates: vi.fn().mockResolvedValue([]),
        previewTemplatePdf: vi.fn(),
    },
}));

vi.mock('../../contexts/auth-context', () => ({
    useAuth: () => ({
        user: { id: 'u-creator', full_name: 'Creator', is_sysadmin: false },
        activeMembership: { is_training_creator: true, is_business_manager: false },
    }),
}));

// Heavy sub-components — replace with stubs so we don't pull TipTap into the test.
vi.mock('../../components/RichTextEditor', () => ({
    RichTextEditor: ({ content, onChange }: { content: string; onChange: (s: string) => void }) => (
        <textarea
            data-testid="rich-text-editor"
            value={content}
            onChange={(e) => onChange(e.target.value)}
        />
    ),
}));

vi.mock('../../components/TrainingAuditTimeline', () => ({
    TrainingAuditTimeline: () => <div data-testid="audit-timeline" />,
}));

// sonner toasts try to mount portals.
const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock('sonner', () => ({
    toast: {
        success: (...a: unknown[]) => toastSuccess(...a),
        error: (...a: unknown[]) => toastError(...a),
    },
}));

// ---- Fixtures -----------------------------------------------------------

const TRAINING_ID = 'tr-edit-1';

const baseStructure = {
    id: TRAINING_ID,
    title: 'Editable Training',
    description: 'desc',
    category: 'general',
    version: 1,
    is_published: false,
    is_ready: false,
    is_archived: false,
    requires_certificate: false,
    tenant_id: 'tn',
    created_by_id: 'u-creator',
    collaborators: [],
    structure_type: 'modular',
    modules: [],
    orphan_chapters: [],
    total_chapters: 0,
    thumbnail: null,
};

beforeEach(() => {
    // Reset call history so each test starts with a clean slate.
    vi.clearAllMocks();
    getTrainingStructure.mockResolvedValue(baseStructure);
    getTrainingHistory.mockResolvedValue([]);
    updateTraining.mockResolvedValue(baseStructure);
    uploadBanner.mockResolvedValue({ ...baseStructure, thumbnail: '/storage/banners/tn/tr-edit-1.png' });
    createChapter.mockResolvedValue({ id: 'new-ch', title: 'New Chapter' });
});

const renderEditor = () =>
    renderWithProviders(
        <Routes>
            <Route path="/manage/courses/:id" element={<ManagerTrainingEditor />} />
        </Routes>,
        { initialEntries: [`/manage/courses/${TRAINING_ID}`] },
    );

// ---- Tests --------------------------------------------------------------

describe('ManagerTrainingEditor — quiz type picker (change_list item 3)', () => {
    it('shows all 5 quiz question types when adding a Quiz chapter', async () => {
        const user = userEvent.setup();
        renderEditor();

        // Wait for the page to load
        await waitFor(() => screen.getByText('Editable Training'));

        // Click "+ Chapter" (standalone)
        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));

        // Switch the content type to Quiz
        await user.click(screen.getByRole('button', { name: /Quiz/i }));

        // Add a question
        await user.click(screen.getByRole('button', { name: /Add Question/i }));

        // Type picker exposes all 5 types
        expect(screen.getByRole('button', { name: 'Multiple Choice' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Multiple Select' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'True / False' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Matching' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Ordering' })).toBeInTheDocument();
    });

    it('selecting True / False locks the options to True and False (no "Add Option")', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        await user.click(screen.getByRole('button', { name: /Quiz/i }));
        await user.click(screen.getByRole('button', { name: /Add Question/i }));

        await user.click(screen.getByRole('button', { name: 'True / False' }));

        // True/False options auto-populate
        expect(screen.getByDisplayValue('True')).toBeInTheDocument();
        expect(screen.getByDisplayValue('False')).toBeInTheDocument();

        // "Add Option" button is hidden for true_false
        expect(screen.queryByRole('button', { name: /Add Option/ })).not.toBeInTheDocument();
    });

    it('selecting Matching reveals Left Items / Right Items / Correct Pairs sections', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        await user.click(screen.getByRole('button', { name: /Quiz/i }));
        await user.click(screen.getByRole('button', { name: /Add Question/i }));

        await user.click(screen.getByRole('button', { name: 'Matching' }));

        expect(screen.getByText('Left Items')).toBeInTheDocument();
        expect(screen.getByText('Right Items')).toBeInTheDocument();
        expect(screen.getByText(/Correct Pairs/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Add Left/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Add Right/i })).toBeInTheDocument();
    });

    it('selecting Ordering shows up/down move buttons (no correctness checkbox)', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        await user.click(screen.getByRole('button', { name: /Quiz/i }));
        await user.click(screen.getByRole('button', { name: /Add Question/i }));

        await user.click(screen.getByRole('button', { name: 'Ordering' }));

        // Per-option Move up / Move down controls appear (one pair per option, default 2 options).
        expect(screen.getAllByTitle('Move up').length).toBeGreaterThanOrEqual(2);
        expect(screen.getAllByTitle('Move down').length).toBeGreaterThanOrEqual(2);
    });
});

describe('ManagerTrainingEditor — banner upload (change_list item 1)', () => {
    it('uploading a banner file triggers managerTrainingsApi.uploadBanner', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        // The page renders a hidden file input for banner uploads.
        // Find any file input that accepts images (not the SCORM zip one if present).
        const inputs = document.querySelectorAll<HTMLInputElement>('input[type="file"]');
        const imageInput = Array.from(inputs).find(i =>
            (i.accept || '').includes('image'),
        );
        expect(imageInput, 'expected a banner file input').toBeTruthy();

        const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'banner.png', { type: 'image/png' });
        await user.upload(imageInput!, file);

        await waitFor(() => {
            expect(uploadBanner).toHaveBeenCalledTimes(1);
        });
        expect(uploadBanner.mock.calls[0][0]).toBe(TRAINING_ID);
        expect(uploadBanner.mock.calls[0][1]).toBe(file);
    });
});

// ===========================================================================
// Curriculum management — modules and chapters
// ===========================================================================

const structureWithChapter = {
    ...baseStructure,
    total_chapters: 1,
    orphan_chapters: [
        {
            id: 'orphan-1',
            title: 'Intro Chapter',
            content_type: 'RICH_TEXT',
            content_data: { text: '<p>hi</p>' },
            sequence_order: 1,
        },
    ],
};

describe('ManagerTrainingEditor — Save metadata', () => {
    it('refuses to save when there are zero chapters and opens the Cannot Save modal', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Save$/ }));

        await waitFor(() => {
            expect(screen.getByText(/Cannot Save/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/at least 1 chapter/i)).toBeInTheDocument();
        expect(updateTraining).not.toHaveBeenCalled();
    });

    it('calls updateTraining with current metadata once the training has a chapter', async () => {
        const user = userEvent.setup();
        getTrainingStructure.mockResolvedValue(structureWithChapter);
        updateTraining.mockResolvedValue(structureWithChapter);
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        // Edit the title input
        const titleInputs = screen.getAllByDisplayValue('Editable Training');
        const titleInput = titleInputs[0];
        await user.clear(titleInput);
        await user.type(titleInput, 'Renamed Training');

        await user.click(screen.getByRole('button', { name: /^Save$/ }));

        await waitFor(() => {
            expect(updateTraining).toHaveBeenCalledTimes(1);
        });
        const [trainingId, payload] = updateTraining.mock.calls[0];
        expect(trainingId).toBe(TRAINING_ID);
        expect(payload.title).toBe('Renamed Training');
    });
});

describe('ManagerTrainingEditor — Mark Ready / Revert to Draft', () => {
    it('Mark Ready button calls markReady on the API', async () => {
        const user = userEvent.setup();
        getTrainingStructure.mockResolvedValue(structureWithChapter);
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /Mark Ready/i }));

        await waitFor(() => {
            expect(markReady).toHaveBeenCalledWith(TRAINING_ID);
        });
    });

    it('Revert to Draft button shows when training is ready and calls sendToDraft', async () => {
        const user = userEvent.setup();
        getTrainingStructure.mockResolvedValue({ ...structureWithChapter, is_ready: true, is_published: false });
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /Revert to Draft/i }));

        await waitFor(() => {
            expect(sendToDraft).toHaveBeenCalledWith(TRAINING_ID);
        });
    });
});

describe('ManagerTrainingEditor — curriculum CRUD', () => {
    it('Add Module: clicking + Module then Save Module calls createModule', async () => {
        const user = userEvent.setup();
        createModule.mockResolvedValue({ id: 'mod-1', title: 'Intro Module', sequence_order: 1 });
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Module$/ }));

        const titleInput = await screen.findByPlaceholderText(/Introduction|Module/i);
        await user.type(titleInput, 'Intro Module');

        await user.click(screen.getByRole('button', { name: /Save Module/i }));

        await waitFor(() => {
            expect(createModule).toHaveBeenCalledTimes(1);
        });
        expect(createModule.mock.calls[0][1]).toMatchObject({ title: 'Intro Module' });
    });

    it('Add Chapter (RICH_TEXT) calls createChapter with the typed content', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        // Open the "Add Standalone Chapter" form
        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));

        // Default chapter title required + RICH_TEXT is reachable from the Text button.
        // Choose "Text" content type
        await user.click(screen.getByRole('button', { name: /^Text$/ }));

        // Fill chapter title (placeholder is "e.g. Fundamental Concepts")
        const chapterTitle = await screen.findByPlaceholderText(/Fundamental Concepts/i);
        await user.type(chapterTitle, 'My First Chapter');

        // Fill the (stubbed) RichTextEditor body
        const rte = screen.getByTestId('rich-text-editor');
        await user.type(rte, 'Some content body');

        // Save the chapter
        const saveBtns = screen.getAllByRole('button', { name: /Save Chapter/i });
        await user.click(saveBtns[0]);

        await waitFor(() => {
            expect(createChapter).toHaveBeenCalledTimes(1);
        });
        const [trainingId, payload] = createChapter.mock.calls[0];
        expect(trainingId).toBe(TRAINING_ID);
        expect(payload.title).toBe('My First Chapter');
        expect(payload.content_type).toBe('RICH_TEXT');
        expect((payload.content_data as { text: string }).text).toContain('Some content body');
    });

    it('Add Chapter rejects an empty title (no API call, inline validation + toast)', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        await user.click(screen.getByRole('button', { name: /^Text$/ }));

        // Click Save with empty title
        const saveBtns = screen.getAllByRole('button', { name: /Save Chapter/i });
        await user.click(saveBtns[0]);

        // Inline error appears, API not called
        await waitFor(() => {
            expect(screen.getByText(/Chapter title is required/i)).toBeInTheDocument();
        });
        expect(createChapter).not.toHaveBeenCalled();
        // Toast surfaces the same problem so the user notices without scrolling
        expect(toastError).toHaveBeenCalledWith(expect.stringMatching(/title is required/i));
    });

    it('Add Chapter toasts on Video URL validation failure', async () => {
        const user = userEvent.setup();
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        // Video is the default type — fill title + a malformed URL
        const chapterTitle = await screen.findByPlaceholderText(/Fundamental Concepts/i);
        await user.type(chapterTitle, 'Bad URL Chapter');
        const urlInput = screen.getByPlaceholderText(/YouTube, Vimeo, or MP4 URL/i);
        await user.type(urlInput, 'not-a-url');

        const saveBtns = screen.getAllByRole('button', { name: /Save Chapter/i });
        await user.click(saveBtns[0]);

        expect(createChapter).not.toHaveBeenCalled();
        expect(toastError).toHaveBeenCalledWith(expect.stringMatching(/valid URL/i));
    });

    it('Add Chapter toasts on backend save failure', async () => {
        const user = userEvent.setup();
        createChapter.mockRejectedValueOnce({ message: 'A chapter with this title already exists.' });
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Chapter$/ }));
        await user.click(screen.getByRole('button', { name: /^Text$/ }));

        const chapterTitle = await screen.findByPlaceholderText(/Fundamental Concepts/i);
        await user.type(chapterTitle, 'Dup Chapter');
        const rte = screen.getByTestId('rich-text-editor');
        await user.type(rte, 'body');

        const saveBtns = screen.getAllByRole('button', { name: /Save Chapter/i });
        await user.click(saveBtns[0]);

        await waitFor(() => {
            expect(createChapter).toHaveBeenCalledTimes(1);
        });
        await waitFor(() => {
            expect(toastError).toHaveBeenCalledWith(expect.stringMatching(/already exists/i));
        });
    });

    it('Add Module toasts on backend save failure', async () => {
        const user = userEvent.setup();
        createModule.mockRejectedValueOnce({ message: 'Module name already in use.' });
        renderEditor();
        await waitFor(() => screen.getByText('Editable Training'));

        await user.click(screen.getByRole('button', { name: /^Module$/ }));
        const titleInput = await screen.findByPlaceholderText(/Introduction|Module/i);
        await user.type(titleInput, 'Dup Module');
        await user.click(screen.getByRole('button', { name: /Save Module/i }));

        await waitFor(() => {
            expect(createModule).toHaveBeenCalledTimes(1);
        });
        await waitFor(() => {
            expect(toastError).toHaveBeenCalledWith(expect.stringMatching(/already in use/i));
        });
    });

    it('Delete chapter button opens confirmation and calls deleteChapter on confirm', async () => {
        const user = userEvent.setup();
        getTrainingStructure.mockResolvedValue(structureWithChapter);
        deleteChapter.mockResolvedValue({});
        renderEditor();
        await waitFor(() => screen.getByText('Intro Chapter'));

        // Hover over the chapter row to reveal its delete button. In jsdom there
        // is no hover-state CSS, so the button is in the DOM either way.
        const deleteButtons = screen.getAllByRole('button').filter(b =>
            b.querySelector('svg.lucide-trash-2') !== null
            || b.getAttribute('aria-label')?.match(/delete/i),
        );
        // The first trash button is the chapter delete (no module rendered yet).
        expect(deleteButtons.length).toBeGreaterThan(0);
        await user.click(deleteButtons[0]);

        // Confirmation dialog → click confirm
        const confirmButtons = await screen.findAllByRole('button', { name: /Delete Chapter|Delete/i });
        await user.click(confirmButtons[confirmButtons.length - 1]);

        await waitFor(() => {
            expect(deleteChapter).toHaveBeenCalledTimes(1);
        });
        expect(deleteChapter.mock.calls[0][0]).toBe(TRAINING_ID);
        expect(deleteChapter.mock.calls[0][1]).toBe('orphan-1');
    });
});
