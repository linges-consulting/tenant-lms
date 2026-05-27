import React from 'react';
import * as LucideIcons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

export type IconName = keyof typeof LucideIcons;

interface IconProps extends LucideProps {
  name: string;
}

export const Icon: React.FC<IconProps> = ({ name, ...props }) => {
  const LucideIcon = (LucideIcons as unknown as Record<string, React.ComponentType<LucideProps>>)[name];

  if (!LucideIcon) {
    return <LucideIcons.HelpCircle {...props} />;
  }

  return <LucideIcon {...props} />;
};
