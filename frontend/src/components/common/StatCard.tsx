import React, { ReactNode } from 'react';
import { SectionCard } from './SectionCard';

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
    <SectionCard id={id} className={className}>
      <dl>
        <dt className="flex items-start justify-between gap-2 text-meta md:text-meta-wide text-fg-muted">
          {label}
          {icon && <span className="shrink-0 text-fg-muted" aria-hidden="true">{icon}</span>}
        </dt>
        <dd className="mt-1 text-metric md:text-metric-wide tabular-nums text-fg">{value}</dd>
      </dl>
      {(secondaryText || trend) && (
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-divider pt-2 text-meta md:text-meta-wide">
          {secondaryText && (
            <span className="text-fg-muted">
              {secondaryText}
            </span>
          )}
          {trend && (
            <span
              className={
                trend.direction === 'up'
                  ? 'text-status-ok'
                  : trend.direction === 'down'
                  ? 'text-status-failed'
                  : 'text-fg-muted'
              }
            >
              {trend.text}
            </span>
          )}
        </div>
      )}
    </SectionCard>
  );
};
