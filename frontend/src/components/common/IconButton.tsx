import React, { ButtonHTMLAttributes, ReactNode } from 'react';

export type IconButtonVariant = 'solid-neutral' | 'solid-primary' | 'solid-danger' | 'quiet';
export type IconButtonSize = 'sm' | 'md' | 'lg';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  'aria-label': string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
}

const variantStyles: Record<IconButtonVariant, string> = {
  'solid-neutral': 'bg-action-secondary enabled:hover:bg-action-secondary-hover text-fg border-control-border',
  'solid-primary': 'bg-action enabled:hover:bg-action-hover text-action-foreground border-action',
  'solid-danger': 'bg-action-danger enabled:hover:bg-action-danger-hover text-risk-critical border-risk-critical/70',
  quiet: 'bg-transparent enabled:hover:bg-action-secondary-hover text-fg-secondary border-transparent',
};

const sizeStyles: Record<IconButtonSize, string> = {
  sm: 'size-10 [&_svg]:size-4',
  md: 'size-11 [&_svg]:size-5',
  lg: 'size-12 [&_svg]:size-6',
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
      className={`control-target control-focus inline-flex items-center justify-center shrink-0 rounded-lg border transition-colors duration-100 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      <span className="inline-flex" aria-hidden="true">{icon}</span>
    </button>
  );
};
