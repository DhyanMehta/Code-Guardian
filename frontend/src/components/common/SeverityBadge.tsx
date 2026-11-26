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
    badgeClass: 'bg-risk-critical-bg text-risk-critical',
    icon: OctagonAlert,
  },
  high: {
    label: 'High',
    badgeClass: 'bg-risk-high-bg text-risk-high',
    icon: TriangleAlert,
  },
  medium: {
    label: 'Medium',
    badgeClass: 'bg-risk-medium-bg text-risk-medium',
    icon: CircleAlert,
  },
  low: {
    label: 'Low',
    badgeClass: 'bg-risk-low-bg text-risk-low',
    icon: Info,
  },
  info: {
    label: 'Info',
    badgeClass: 'bg-risk-info-bg text-risk-info',
    icon: HelpCircle,
  },
  unknown: {
    label: 'Unknown',
    badgeClass: 'bg-risk-unknown-bg text-risk-unknown',
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
  const config = Object.hasOwn(severityConfigs, normalizedKey)
    ? severityConfigs[normalizedKey]
    : severityConfigs.unknown;
  const IconComponent = config.icon;

  const sizeClasses =
    size === 'sm'
      ? 'px-1.5 py-0.5 gap-1'
      : 'px-2 py-1 gap-1.5';

  const iconSizes = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span
      id={id}
      className={`inline-flex shrink-0 items-center rounded-md text-meta md:text-meta-wide ${config.badgeClass} ${sizeClasses} ${className}`}
    >
      <IconComponent className={`${iconSizes} shrink-0`} aria-hidden="true" />
      <span className={showLabel ? undefined : 'sr-only'}>{config.label}</span>
    </span>
  );
};
