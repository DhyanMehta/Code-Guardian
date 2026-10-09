import React from 'react';
import {
  OctagonAlert,
  TriangleAlert,
  CircleAlert,
  Info,
  HelpCircle,
  MinusCircle,
} from 'lucide-react';
import { SeverityLevel } from '../../types';

export interface SeverityBadgeProps {
  severity: SeverityLevel | string;
  size?: 'sm' | 'md';
  showLabel?: boolean;
  className?: string;
  id?: string;
}

interface SeverityConfig {
  label: string;
  badgeClass: string;
  icon: React.ComponentType<{ className?: string }>;
}

const severityConfigs: Record<string, SeverityConfig> = {
  critical: {
    label: 'Critical',
    badgeClass: 'bg-severity-critical-bg text-severity-critical-text border-severity-critical-border',
    icon: OctagonAlert,
  },
  high: {
    label: 'High',
    badgeClass: 'bg-severity-high-bg text-severity-high-text border-severity-high-border',
    icon: TriangleAlert,
  },
  medium: {
    label: 'Medium',
    badgeClass: 'bg-severity-medium-bg text-severity-medium-text border-severity-medium-border',
    icon: CircleAlert,
  },
  low: {
    label: 'Low',
    badgeClass: 'bg-severity-low-bg text-severity-low-text border-severity-low-border',
    icon: Info,
  },
  info: {
    label: 'Info',
    badgeClass: 'bg-severity-info-bg text-severity-info-text border-severity-info-border',
    icon: HelpCircle,
  },
  unknown: {
    label: 'Unknown',
    badgeClass: 'bg-severity-unknown-bg text-severity-unknown-text border-severity-unknown-border',
    icon: MinusCircle,
  },
};

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({
  severity,
  size = 'md',
  showLabel = true,
  className = '',
  id,
}) => {
  const normalizedKey = (severity || 'unknown').toLowerCase();
  const config = severityConfigs[normalizedKey] || severityConfigs.unknown;
  const IconComponent = config.icon;

  const sizeClasses =
    size === 'sm'
      ? 'px-1.5 py-0.5 text-[11px] gap-1'
      : 'px-2 py-0.5 text-xs gap-1.5';

  const iconSizes = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span
      id={id}
      role="status"
      aria-label={`Severity: ${config.label}`}
      className={`inline-flex items-center font-mono font-medium rounded-md border shrink-0 select-none ${config.badgeClass} ${sizeClasses} ${className}`}
    >
      <IconComponent className={`${iconSizes} shrink-0`} aria-hidden="true" />
      {showLabel && <span className="uppercase tracking-wider">{config.label.toUpperCase()}</span>}
    </span>
  );
};
