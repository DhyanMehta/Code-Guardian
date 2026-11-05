import React, { InputHTMLAttributes, useId } from 'react';
import { Search } from 'lucide-react';

export interface SearchInputProps extends InputHTMLAttributes<HTMLInputElement> {
  wrapperClassName?: string;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  wrapperClassName = '',
  className = '',
  placeholder = 'Search...',
  id,
  ...props
}) => {
  const generated = useId();
  return (
    <div className={`relative flex items-center w-full ${wrapperClassName}`}>
      <div className="absolute left-3.5 pointer-events-none text-neutral-400 flex items-center justify-center">
        <Search className="w-4 h-4" aria-hidden="true" />
      </div>
      <input
        type="search"
        id={id ?? generated}
        aria-label="Search"
        placeholder={placeholder}
        className={`w-full pl-10 pr-3.5 py-2 text-sm bg-neutral-900/90 text-neutral-100 placeholder:text-neutral-400/80 border border-neutral-700/60 hover:border-neutral-600 rounded-lg shadow-2xs transition-all duration-150 focus:outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 font-sans ${className}`}
        {...props}
      />
    </div>
  );
};
