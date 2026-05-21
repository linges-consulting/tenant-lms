/**
 * Predefined Avatar Images
 * Provides avatar images for user profiles with consistent styling
 */

export const AVATAR_SHAPES = [
    { id: 'avatar1', label: 'Avatar 1', image: '/avatars/avatar1.png' },
    { id: 'avatar2', label: 'Avatar 2', image: '/avatars/avatar2.png' },
    { id: 'avatar3', label: 'Avatar 3', image: '/avatars/avatar3.png' },
    { id: 'avatar4', label: 'Avatar 4', image: '/avatars/avatar4.png' },
    { id: 'avatar5', label: 'Avatar 5', image: '/avatars/avatar5.png' },
    { id: 'avatar6', label: 'Avatar 6', image: '/avatars/avatar6.png' },
    { id: 'avatar7', label: 'Avatar 7', image: '/avatars/avatar7.png' },
    { id: 'avatar8', label: 'Avatar 8', image: '/avatars/avatar8.png' },
    { id: 'avatar9', label: 'Avatar 9', image: '/avatars/avatar9.png' },
    { id: 'avatar10', label: 'Avatar 10', image: '/avatars/avatar10.png' },
] as const;

export type AvatarShapeId = typeof AVATAR_SHAPES[number]['id'];

// eslint-disable-next-line react-refresh/only-export-components
export const getAvatarShapeById = (id: string | null | undefined): typeof AVATAR_SHAPES[number] | null => {
    if (!id) return null;
    return AVATAR_SHAPES.find(shape => shape.id === id) || null;
};

/**
 * Image renderers for each avatar type
 */
// eslint-disable-next-line react-refresh/only-export-components
export const AvatarShapeRenderer: Record<AvatarShapeId, React.FC<{ className?: string }>> = {
    avatar1: ({ className = '' }) => (
        <img src="/avatars/avatar1.png" alt="Avatar 1" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar2: ({ className = '' }) => (
        <img src="/avatars/avatar2.png" alt="Avatar 2" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar3: ({ className = '' }) => (
        <img src="/avatars/avatar3.png" alt="Avatar 3" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar4: ({ className = '' }) => (
        <img src="/avatars/avatar4.png" alt="Avatar 4" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar5: ({ className = '' }) => (
        <img src="/avatars/avatar5.png" alt="Avatar 5" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar6: ({ className = '' }) => (
        <img src="/avatars/avatar6.png" alt="Avatar 6" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar7: ({ className = '' }) => (
        <img src="/avatars/avatar7.png" alt="Avatar 7" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar8: ({ className = '' }) => (
        <img src="/avatars/avatar8.png" alt="Avatar 8" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar9: ({ className = '' }) => (
        <img src="/avatars/avatar9.png" alt="Avatar 9" className={`w-full h-full object-cover ${className}`} />
    ),
    avatar10: ({ className = '' }) => (
        <img src="/avatars/avatar10.png" alt="Avatar 10" className={`w-full h-full object-cover ${className}`} />
    ),
};

/**
 * Get the next shape in rotation (for cycling through shapes)
 */
// eslint-disable-next-line react-refresh/only-export-components
export const getNextAvatarShape = (currentShapeId: string | null | undefined): AvatarShapeId => {
    const currentIndex = AVATAR_SHAPES.findIndex(s => s.id === currentShapeId);
    const nextIndex = (currentIndex + 1) % AVATAR_SHAPES.length;
    return AVATAR_SHAPES[nextIndex].id;
};
