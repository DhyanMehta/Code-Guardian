import React, { type ComponentPropsWithRef, type ReactNode, useId } from 'react';
import { Search } from 'lucide-react';

export interface SearchInputProps extends ComponentPropsWithRef<'input'> {
  wrapperClassName?: string;
  accessory?: ReactNode;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  wrapperClassName = '',
  className = '',
  placeholder = 'Search...',
  id,
  accessory,
  ...props
}) => {
  const generated = useId();
  return (
    <div className={`relative flex items-center w-full ${wrapperClassName}`}>
      <div className="absolute left-3.5 pointer-events-none text-fg-muted flex items-center justify-center">
        <Search className="w-4 h-4" aria-hidden="true" />
      </div>
      <input
        type="search"
        id={id ?? generated}
        aria-label="Search"
        placeholder={placeholder}
        className={`control-target control-focus w-full rounded-lg border border-control-border bg-panel-inset py-1.5 pl-10 pr-3.5 font-sans text-body text-fg placeholder:text-fg-muted hover:border-link transition-colors duration-100 ${className}`}
        {...props}
      />
      {accessory && <div className="absolute right-0 flex items-center">{accessory}</div>}
    </div>
  );
};
