import React from 'react';

export interface ProgressBarSegment {
  key: string;
  value: number;
  colorClass: string;
  label?: string;
}

export interface ProgressBarProps {
  /**
   * Multi-color segment definitions.
   * If provided, values are normalized to percentages of total sum or given total.
   */
  segments?: ProgressBarSegment[];
  /**
   * Single-bar mode value (0-100 or relative to max).
   */
  value?: number;
  max?: number;
  colorClass?: string;
  height?: 'thin' | 'md' | 'thick';
  className?: string;
  id?: string;
  'aria-label'?: string;
}

const heightStyles = {
  thin: 'h-1',
  md: 'h-1.5',
  thick: 'h-2.5',
};

export const ProgressBar: React.FC<ProgressBarProps> = ({
  segments,
  value,
  max = 100,
  colorClass = 'bg-primary-500',
  height = 'md',
  className = '',
  id,
  'aria-label': ariaLabel = 'Status progress bar',
}) => {
  if (segments && segments.length > 0) {
    const totalValue = segments.reduce((sum, seg) => sum + Math.max(0, seg.value), 0);

    return (
      <div
        id={id}
        role="progressbar"
        aria-label={ariaLabel}
        aria-valuenow={totalValue}
        aria-valuemin={0}
        aria-valuemax={totalValue > 0 ? totalValue : 100}
        className={`w-full bg-neutral-800 overflow-hidden flex rounded-full ${heightStyles[height]} ${className}`}
      >
        {totalValue === 0 ? (
          <div className="w-full bg-neutral-800" />
        ) : (
          segments.map((seg) => {
            if (seg.value <= 0) return null;
            const percentage = (seg.value / totalValue) * 100;
            return (
              <div
                key={seg.key}
                title={seg.label ? `${seg.label}: ${seg.value}` : `${seg.key}: ${seg.value}`}
                style={{ width: `${percentage}%` }}
                className={`h-full transition-all duration-300 ${seg.colorClass}`}
              />
            );
          })
        )}
      </div>
    );
  }

  // Single value variant
  const normalizedValue = Math.min(Math.max(0, value ?? 0), max);
  const percentage = max > 0 ? (normalizedValue / max) * 100 : 0;

  return (
    <div
      id={id}
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuenow={normalizedValue}
      aria-valuemin={0}
      aria-valuemax={max}
      className={`w-full bg-neutral-800 overflow-hidden rounded-full ${heightStyles[height]} ${className}`}
    >
      <div
        style={{ width: `${percentage}%` }}
        className={`h-full transition-all duration-300 ${colorClass}`}
      />
    </div>
  );
};
