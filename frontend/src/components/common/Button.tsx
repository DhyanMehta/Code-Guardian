import React, { ButtonHTMLAttributes } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'inverted' | 'outlined' | 'github';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  github: 'bg-[#24292f] hover:bg-[#32383f] text-white border border-[#57606a] shadow-xs disabled:opacity-50 disabled:cursor-not-allowed',
  primary:
    'bg-primary-600 hover:bg-primary-500 active:bg-primary-700 text-neutral-white border border-transparent shadow-xs disabled:bg-primary-950 disabled:text-neutral-500 disabled:cursor-not-allowed',
  secondary:
    'bg-neutral-800 hover:bg-neutral-700 active:bg-neutral-750 text-neutral-100 border border-neutral-700/80 shadow-xs disabled:bg-neutral-900 disabled:text-neutral-600 disabled:cursor-not-allowed',
  inverted:
    'bg-neutral-100 hover:bg-neutral-white active:bg-neutral-200 text-neutral-950 font-semibold border border-transparent shadow-xs disabled:bg-neutral-400 disabled:text-neutral-700 disabled:cursor-not-allowed',
  outlined:
    'bg-transparent hover:bg-neutral-800/80 active:bg-neutral-800 text-neutral-200 border border-neutral-700 hover:border-neutral-600 shadow-xs disabled:border-neutral-850 disabled:text-neutral-600 disabled:cursor-not-allowed',
};

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-2.5 py-1.5 text-xs font-medium gap-1.5',
  md: 'px-3.5 py-2 text-sm font-medium gap-2',
  lg: 'px-4.5 py-2.5 text-base font-medium gap-2.5',
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
      className={`inline-flex items-center justify-center rounded-md transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas cursor-pointer select-none font-sans ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {isLoading ? (
        <>
          <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" />
          <span>{children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
};
