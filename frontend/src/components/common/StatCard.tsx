import React, { ReactNode } from 'react';

export interface StatCardProps {
  label: string;
  value: string | number;
  secondaryText?: string;
  icon?: ReactNode;
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    text: string;
  };
  className?: string;
  id?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  secondaryText,
  icon,
  trend,
  className = '',
  id,
}) => {
  return (
    <div
      id={id}
      className={`bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex flex-col justify-between transition-colors duration-150 ${className}`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wider text-neutral-400">
          {label}
        </span>
        {icon && (
          <div className="text-neutral-400 shrink-0">
            {icon}
          </div>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono text-neutral-100 tracking-tight">
          {value}
        </span>
      </div>

      {(secondaryText || trend) && (
        <div className="mt-2 pt-2 border-t border-neutral-800/60 flex items-center justify-between text-xs">
          {secondaryText && (
            <span className="text-neutral-400">
              {secondaryText}
            </span>
          )}
          {trend && (
            <span
              className={`font-mono font-medium ${
                trend.direction === 'up'
                  ? 'text-tertiary-400'
                  : trend.direction === 'down'
                  ? 'text-severity-critical'
                  : 'text-neutral-400'
              }`}
            >
              {trend.text}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
