import React from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import Placeholder from '@tiptap/extension-placeholder';
import {
    Bold, Italic, Underline as UnderlineIcon,
    AlignLeft, AlignCenter, AlignRight, AlignJustify,
    List, ListOrdered, Link as LinkIcon, Image as ImageIcon,
    Heading1, Heading2, Heading3, Undo, Redo, Quote
} from 'lucide-react';
import { Button } from './ui/button';
import type { Editor } from '@tiptap/react';

interface RichTextEditorProps {
    content: string;
    onChange: (html: string) => void;
    placeholder?: string;
}

const MenuBar = ({ editor }: { editor: Editor | null }) => {
    if (!editor) {
        return null;
    }

    const addImage = () => {
        const url = window.prompt('URL');
        if (url) {
            editor.chain().focus().setImage({ src: url }).run();
        }
    };

    const setLink = () => {
        const previousUrl = editor.getAttributes('link').href;
        const url = window.prompt('URL', previousUrl);

        if (url === null) {
            return;
        }

        if (url === '') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run();
            return;
        }

        editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    };

    return (
        <div className="bg-muted p-2 border-b flex gap-1 flex-wrap sticky top-0 z-10">
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleBold().run()} 
                className={editor.isActive('bold') ? 'bg-accent text-accent-foreground' : ''}
                title="Bold"
            >
                <Bold className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleItalic().run()} 
                className={editor.isActive('italic') ? 'bg-accent text-accent-foreground' : ''}
                title="Italic"
            >
                <Italic className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleUnderline().run()} 
                className={editor.isActive('underline') ? 'bg-accent text-accent-foreground' : ''}
                title="Underline"
            >
                <UnderlineIcon className="w-4 h-4" />
            </Button>
            
            <div className="w-px h-6 bg-border mx-1 self-center" />

            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} 
                className={editor.isActive('heading', { level: 1 }) ? 'bg-accent text-accent-foreground' : ''}
                title="Heading 1"
            >
                <Heading1 className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} 
                className={editor.isActive('heading', { level: 2 }) ? 'bg-accent text-accent-foreground' : ''}
                title="Heading 2"
            >
                <Heading2 className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} 
                className={editor.isActive('heading', { level: 3 }) ? 'bg-accent text-accent-foreground' : ''}
                title="Heading 3"
            >
                <Heading3 className="w-4 h-4" />
            </Button>

            <div className="w-px h-6 bg-border mx-1 self-center" />

            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().setTextAlign('left').run()} 
                className={editor.isActive({ textAlign: 'left' }) ? 'bg-accent text-accent-foreground' : ''}
                title="Align Left"
            >
                <AlignLeft className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().setTextAlign('center').run()} 
                className={editor.isActive({ textAlign: 'center' }) ? 'bg-accent text-accent-foreground' : ''}
                title="Align Center"
            >
                <AlignCenter className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().setTextAlign('right').run()} 
                className={editor.isActive({ textAlign: 'right' }) ? 'bg-accent text-accent-foreground' : ''}
                title="Align Right"
            >
                <AlignRight className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().setTextAlign('justify').run()} 
                className={editor.isActive({ textAlign: 'justify' }) ? 'bg-accent text-accent-foreground' : ''}
                title="Justify"
            >
                <AlignJustify className="w-4 h-4" />
            </Button>

            <div className="w-px h-6 bg-border mx-1 self-center" />

            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleBulletList().run()} 
                className={editor.isActive('bulletList') ? 'bg-accent text-accent-foreground' : ''}
                title="Bullet List"
            >
                <List className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleOrderedList().run()} 
                className={editor.isActive('orderedList') ? 'bg-accent text-accent-foreground' : ''}
                title="Ordered List"
            >
                <ListOrdered className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().toggleBlockquote().run()} 
                className={editor.isActive('blockquote') ? 'bg-accent text-accent-foreground' : ''}
                title="Quote"
            >
                <Quote className="w-4 h-4" />
            </Button>

            <div className="w-px h-6 bg-border mx-1 self-center" />

            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={setLink} 
                className={editor.isActive('link') ? 'bg-accent text-accent-foreground' : ''}
                title="Insert Link"
            >
                <LinkIcon className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={addImage}
                title="Insert Image"
            >
                <ImageIcon className="w-4 h-4" />
            </Button>

            <div className="w-px h-6 bg-border mx-1 self-center" />

            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().undo().run()}
                title="Undo"
            >
                <Undo className="w-4 h-4" />
            </Button>
            <Button 
                size="sm" variant="ghost" type="button" 
                onClick={() => editor.chain().focus().redo().run()}
                title="Redo"
            >
                <Redo className="w-4 h-4" />
            </Button>
        </div>
    );
};

export const RichTextEditor: React.FC<RichTextEditorProps> = ({ content, onChange, placeholder }) => {
    const editor = useEditor({
        extensions: [
            StarterKit.configure({
                link: false,
                underline: false,
            }),
            Underline,
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: 'text-primary underline cursor-pointer',
                },
            }),
            Image.configure({
                HTMLAttributes: {
                    class: 'max-w-full h-auto rounded-lg shadow-sm my-4',
                },
            }),
            TextAlign.configure({
                types: ['heading', 'paragraph'],
            }),
            Placeholder.configure({
                placeholder: placeholder || 'Type content here...',
            }),
        ],
        content,
        onUpdate: ({ editor }) => {
            onChange(editor.getHTML());
        },
    });

    return (
        <div className="border rounded-md overflow-hidden flex flex-col min-h-[400px] bg-background focus-within:ring-1 ring-primary/30 transition-shadow transition-colors">
            <MenuBar editor={editor} />
            <EditorContent 
                editor={editor} 
                className="p-4 prose prose-emerald prose-sm max-w-none flex-1 outline-none text-foreground bg-background editor-content" 
            />
            <style dangerouslySetInnerHTML={{ __html: `
                .editor-content .ProseMirror {
                    min-height: 350px;
                    outline: none;
                }
                .editor-content .ProseMirror p.is-editor-empty:first-child::before {
                    content: attr(data-placeholder);
                    float: left;
                    color: hsl(var(--muted-foreground));
                    pointer-events: none;
                    height: 0;
                }
                .editor-content .ProseMirror img {
                    display: block;
                    margin-left: auto;
                    margin-right: auto;
                }
                .editor-content .ProseMirror img.align-left {
                    margin-left: 0;
                    margin-right: auto;
                }
                .editor-content .ProseMirror img.align-right {
                    margin-left: auto;
                    margin-right: 0;
                }
            `}} />
        </div>
    );
};
