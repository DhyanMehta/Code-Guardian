import React, { ButtonHTMLAttributes } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'quiet' | 'destructive' | 'inverted' | 'outlined' | 'github';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  github:
    'bg-[#24292f] enabled:hover:bg-[#2d333b] enabled:active:bg-[#1f242c] text-white border-[#444c56]',
  primary:
    'bg-action enabled:hover:bg-action-hover enabled:active:bg-action-hover text-action-foreground border-action',
  secondary:
    'bg-action-secondary enabled:hover:bg-action-secondary-hover enabled:active:bg-action-secondary-hover text-fg border-control-border',
  quiet:
    'bg-transparent enabled:hover:bg-action-secondary-hover enabled:active:bg-action-secondary-hover text-fg-secondary border-transparent',
  destructive:
    'bg-action-danger enabled:hover:bg-action-danger-hover enabled:active:bg-action-danger-hover text-risk-critical border-risk-critical/70',
  inverted:
    'bg-neutral-100 enabled:hover:bg-neutral-white enabled:active:bg-neutral-200 text-neutral-950 border-transparent',
  outlined:
    'bg-transparent enabled:hover:bg-action-secondary-hover enabled:active:bg-action-secondary-hover text-fg-secondary border-control-border',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 gap-1.5',
  md: 'px-4 py-2 gap-2',
  lg: 'px-5 py-2.5 gap-2.5',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  disabled = false,
  className = '',
  children,
  type = 'button',
  ...props
}) => {
  return (
    <button
      type={type}
      disabled={disabled || isLoading}
      className={`control-target control-focus inline-flex items-center justify-center rounded-lg border text-center font-sans text-control md:text-control-wide transition-colors duration-100 cursor-pointer disabled:cursor-not-allowed disabled:opacity-60 ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
      aria-busy={isLoading || props['aria-busy']}
    >
      {isLoading ? (
        <>
          <span aria-hidden="true" className="size-3.5 shrink-0 rounded-full border-2 border-current border-t-transparent motion-safe:animate-spin" />
          <span>{children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
};
