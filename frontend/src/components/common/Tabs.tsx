import React, { ReactNode, useId } from 'react';

export interface TabItem {
  id: string;
  label: string;
  count?: number;
  icon?: ReactNode;
}

export interface TabsProps {
  tabs: TabItem[];
  activeTab: string;
  onChange: (tabId: string) => void;
  className?: string;
  id?: string;
  variant?: 'tabs' | 'sidebar' | 'responsive';
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className = '',
  id,
  variant = 'tabs',
}) => {
  const generated = useId();
  const scope = id ?? `tabs-${generated}`;
  const isSidebar = variant === 'sidebar';
  const isResponsive = variant === 'responsive';

  const containerClasses = isSidebar
    ? `flex flex-col gap-1 w-full ${className}`
    : isResponsive
    ? `flex flex-row lg:flex-col items-center lg:items-stretch gap-1 lg:gap-1.5 overflow-x-auto lg:overflow-x-visible border-b lg:border-b-0 border-neutral-800 w-full ${className}`
    : `flex items-center gap-1 border-b border-neutral-800 overflow-x-auto ${className}`;

  return (
    <div
      id={scope}
      role="tablist"
      aria-label="Sub-navigation tabs"
      aria-orientation={isSidebar ? 'vertical' : undefined}
      className={containerClasses}
    >
      {tabs.map((tab, index) => {
        const isActive = tab.id === activeTab;
        const buttonClasses = isSidebar
          ? `flex items-center justify-between w-full px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 ${
              isActive
                ? 'text-primary-400 font-semibold bg-neutral-900 border border-primary-500/30 shadow-xs'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/40 border border-transparent'
            }`
          : isResponsive
          ? `flex items-center gap-2.5 px-3.5 py-2 lg:py-2.5 text-sm font-medium whitespace-nowrap lg:whitespace-normal rounded-lg lg:rounded-xl lg:w-full transition-all duration-150 relative cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 ${
              isActive
                ? 'text-primary-400 font-semibold lg:bg-neutral-900 lg:border lg:border-primary-500/30 lg:shadow-xs'
                : 'text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/40 border border-transparent'
            }`
          : `flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors duration-150 relative cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 ${
              isActive
                ? 'text-primary-400 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200'
            }`;

        return (
          <button
            key={tab.id}
            role="tab"
            id={`${scope}-tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`${scope}-panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            onKeyDown={event => {
              const next =
                event.key === 'ArrowRight' || event.key === 'ArrowDown'
                  ? (index + 1) % tabs.length
                  : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
                  ? (index + tabs.length - 1) % tabs.length
                  : event.key === 'Home'
                  ? 0
                  : event.key === 'End'
                  ? tabs.length - 1
                  : null;
              if (next === null) return;
              event.preventDefault();
              onChange(tabs[next].id);
              document.getElementById(`${scope}-tab-${tabs[next].id}`)?.focus();
            }}
            type="button"
            onClick={() => onChange(tab.id)}
            className={buttonClasses}
          >
            <div className="flex items-center gap-2.5">
              {tab.icon && (
                <span className={isActive ? 'text-primary-400' : 'text-neutral-400'}>
                  {tab.icon}
                </span>
              )}
              <span>{tab.label}</span>
            </div>

            {typeof tab.count === 'number' && (
              <span
                className={`ml-1 px-1.5 py-0.2 rounded-full text-xs font-mono font-medium ${
                  isActive
                    ? 'bg-primary-500/20 text-primary-300'
                    : 'bg-neutral-800 text-neutral-400'
                }`}
              >
                {tab.count}
              </span>
            )}

            {isActive && !isSidebar && (
              <div
                className={`absolute bottom-0 left-0 right-0 h-0.5 bg-primary-500 ${isResponsive ? 'lg:hidden' : ''}`}
                aria-hidden="true"
              />
            )}
          </button>
        );
      })}
    </div>
  );
};
