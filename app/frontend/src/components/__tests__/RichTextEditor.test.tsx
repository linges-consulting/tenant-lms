import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderWithProviders, screen } from '../../test/utils';
import { RichTextEditor } from '../RichTextEditor';

describe('RichTextEditor', () => {
    let warnSpy: ReturnType<typeof vi.spyOn>;

    beforeEach(() => {
        warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    });

    afterEach(() => {
        warnSpy.mockRestore();
    });

    it('renders the toolbar buttons', () => {
        renderWithProviders(<RichTextEditor content="" onChange={() => {}} />);
        expect(screen.getByTitle('Bold')).toBeInTheDocument();
        expect(screen.getByTitle('Italic')).toBeInTheDocument();
        expect(screen.getByTitle('Underline')).toBeInTheDocument();
        expect(screen.getByTitle('Insert Link')).toBeInTheDocument();
        expect(screen.getByTitle('Insert Image')).toBeInTheDocument();
    });

    it('does NOT emit the TipTap duplicate-extension warning for link/underline', () => {
        // Regression for change_list item 2: StarterKit v3 bundles Link and
        // Underline, so registering them separately caused
        //   [tiptap warn]: Duplicate extension names found: ['link', 'underline']
        // The fix disables those two inside StarterKit.configure(...).
        renderWithProviders(<RichTextEditor content="<p>hello</p>" onChange={() => {}} />);
        const allWarnings = warnSpy.mock.calls
            .flat()
            .map((arg) => (typeof arg === 'string' ? arg : JSON.stringify(arg)))
            .join(' ');
        expect(allWarnings).not.toMatch(/Duplicate extension names/i);
        expect(allWarnings).not.toMatch(/'link'/i);
        expect(allWarnings).not.toMatch(/'underline'/i);
    });
});
