import type { ComponentPropsWithoutRef } from 'react';

export function SectionCard({ className = '', ...props }: ComponentPropsWithoutRef<'div'>) {
  return <div className={`min-w-0 rounded-xl border border-divider bg-panel p-4 sm:p-5 ${className}`} {...props} />;
}
