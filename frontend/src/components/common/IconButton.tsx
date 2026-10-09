import React, { ButtonHTMLAttributes, ReactNode } from 'react';

export type IconButtonVariant = 'solid-neutral' | 'solid-primary' | 'solid-danger';
export type IconButtonSize = 'sm' | 'md' | 'lg';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  'aria-label': string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
}

const variantStyles: Record<IconButtonVariant, string> = {
  'solid-neutral': 'bg-neutral-800 hover:bg-neutral-700 active:bg-neutral-750 text-neutral-200 border border-neutral-700/80',
  'solid-primary': 'bg-primary-500 hover:bg-primary-600 active:bg-primary-700 text-neutral-white border border-primary-600',
  'solid-danger': 'bg-severity-critical-bg hover:bg-severity-critical-border text-severity-critical-text border border-severity-critical-border',
};

const sizeStyles: Record<IconButtonSize, string> = {
  sm: 'w-7 h-7 text-xs rounded-md',
  md: 'w-8 h-8 text-sm rounded-md',
  lg: 'w-9 h-9 text-base rounded-md',
};

export const IconButton: React.FC<IconButtonProps> = ({
  icon,
  'aria-label': ariaLabel,
  variant = 'solid-neutral',
  size = 'md',
  className = '',
  disabled = false,
  type = 'button',
  ...props
}) => {
  return (
    <button
      type={type}
      aria-label={ariaLabel}
      disabled={disabled}
      className={`inline-flex items-center justify-center shrink-0 transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {icon}
    </button>
  );
};
