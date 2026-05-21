import React from 'react';
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar';
import { getAvatarShapeById } from '../utils/avatar-shapes';
import { cn } from '../lib/utils';

interface UserAvatarProps {
    initials: string;
    shapeId?: string | null;
    className?: string;
    fallbackClassName?: string;
    /** Optional background color for the fallback initials (e.g. from tenant branding) */
    color?: string;
    /** Shape variant for the avatar */
    variant?: 'circle' | 'rounded-square';
}

/**
 * UserAvatar Component
 * Displays user avatar with image or initials
 * - If shapeId is provided, checks if it's an image avatar (avatar1-10), displays the image
 * - If shapeId is null, shows initials with neutral background
 * Image avatars are located in /public/avatars/
 */
export const UserAvatar: React.FC<UserAvatarProps & { avatarUrl?: string | null }> = ({
    initials,
    shapeId,
    avatarUrl,
    className = 'w-9 h-9',
    fallbackClassName = '',
    color,
    variant = 'rounded-square',
}) => {
    const combinedId = avatarUrl || shapeId;
    const isUrl = combinedId?.startsWith('http') || combinedId?.startsWith('/');
    const shape = isUrl ? null : getAvatarShapeById(combinedId);
    
    // Final image source: either the direct URL or the image path from the predefined shape
    const finalImageUrl = isUrl ? combinedId : (shape && 'image' in shape ? shape.image : null);
    const isImageAvatar = !!finalImageUrl;

    const roundedClass = variant === 'circle' ? 'rounded-full' : 'rounded-lg';

    return (
        <Avatar className={cn(className, roundedClass, 'border border-border shadow-sm overflow-hidden')}>
            {isImageAvatar ? (
                <>
                    <AvatarImage
                        src={finalImageUrl || ''}
                        alt="User profile"
                        className="w-full h-full object-cover"
                    />
                    <AvatarFallback
                        className={cn('text-foreground font-medium', roundedClass, fallbackClassName, !color && 'bg-muted')}
                        style={color ? { backgroundColor: color } : {}}
                    >
                        {initials}
                    </AvatarFallback>
                </>
            ) : (
                <AvatarFallback
                    className={cn('text-foreground font-medium', roundedClass, fallbackClassName, !color && 'bg-muted')}
                    style={color ? { backgroundColor: color } : {}}
                >
                    {initials}
                </AvatarFallback>
            )}
        </Avatar>
    );
};
