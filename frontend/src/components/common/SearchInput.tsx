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
      <div className="absolute left-3 pointer-events-none text-neutral-400 flex items-center justify-center">
        <Search className="w-4 h-4" aria-hidden="true" />
      </div>
      <input
        type="search"
        id={id ?? generated}
        aria-label="Search"
        placeholder={placeholder}
        className={`w-full pl-9 pr-3.5 py-2 text-sm bg-neutral-900 text-neutral-100 placeholder:text-neutral-400 border border-neutral-800 rounded-md transition-colors duration-150 focus:outline-none focus:border-primary-500 focus:ring-1 focus:ring-primary-500 font-sans ${className}`}
        {...props}
      />
    </div>
  );
};
