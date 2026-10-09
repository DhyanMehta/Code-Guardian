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
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  className = '',
  id,
}) => {
  const generated = useId();
  const scope = id ?? `tabs-${generated}`;
  return (
    <div
      id={scope}
      role="tablist"
      aria-label="Sub-navigation tabs"
      className={`flex items-center gap-1 border-b border-neutral-800 ${className}`}
    >
      {tabs.map((tab, index) => {
        const isActive = tab.id === activeTab;
        return (
          <button
            key={tab.id}
            role="tab"
            id={`${scope}-tab-${tab.id}`}
            aria-selected={isActive}
            aria-controls={`${scope}-panel-${tab.id}`}
            tabIndex={isActive ? 0 : -1}
            onKeyDown={event => {
              const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
              if (next === null) return;
              event.preventDefault(); onChange(tabs[next].id);
              document.getElementById(`${scope}-tab-${tabs[next].id}`)?.focus();
            }}
            type="button"
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors duration-150 relative cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50 ${
              isActive
                ? 'text-primary-400 font-semibold'
                : 'text-neutral-400 hover:text-neutral-200'
            }`}
          >
            {tab.icon && (
              <span className={isActive ? 'text-primary-400' : 'text-neutral-400'}>
                {tab.icon}
              </span>
            )}
            <span>{tab.label}</span>
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
            {isActive && (
              <div
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-500"
                aria-hidden="true"
              />
            )}
          </button>
        );
      })}
    </div>
  );
};
