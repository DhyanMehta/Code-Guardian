import React, { useId, useState } from 'react';
import { AgentOutcome } from '../../types';

export interface AgentHistoryDot {
  reviewId: number;
  outcome: AgentOutcome;
  failureReason: string | null;
}

interface AgentHistoryDotsProps {
  dots: AgentHistoryDot[];
  className?: string;
}

const outcomeStyles: Record<NonNullable<AgentOutcome>, { dot: string; label: string }> = {
  unknown: { dot: 'bg-neutral-600 border-neutral-500', label: 'Unknown' },
  ok: {
    dot: 'bg-tertiary-500 border-tertiary-400',
    label: 'OK',
  },
  degraded: {
    dot: 'bg-severity-medium border-severity-medium',
    label: 'Degraded',
  },
  failed: {
    dot: 'bg-severity-critical border-severity-critical',
    label: 'Failed',
  },
};

/**
 * Horizontal row of small colored dots representing per-agent outcome history
 * across multiple review runs. Hovering a dot reveals the review ID, outcome,
 * and failure_reason (if present).
 *
 * Outcome color coding:
 *   green  = ok
 *   amber  = degraded (outcome != null but not fully clean)
 *   red    = failed
 *   gray   = null / unknown
 */
export const AgentHistoryDots: React.FC<AgentHistoryDotsProps> = ({ dots, className = '' }) => {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const scope = useId();

  if (dots.length === 0) {
    return (
      <span className="text-[11px] font-mono text-neutral-500 italic">No history</span>
    );
  }

  return (
    <div className={`flex items-center gap-1.5 ${className}`} role="list" aria-label="Agent run history">
      {dots.map((dot, idx) => {
        const styles =
          dot.outcome && outcomeStyles[dot.outcome]
            ? outcomeStyles[dot.outcome]
            : { dot: 'bg-neutral-600 border-neutral-500', label: 'Unknown' };

        const isActive = activeIdx === idx;

        return (
          <div key={dot.reviewId} className="relative" role="listitem">
            {/* Tooltip */}
            {isActive && (
              <div
                className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 z-50 min-w-max"
                role="tooltip"
                id={`${scope}-dot-tooltip-${dot.reviewId}`}
              >
                <div className="bg-neutral-850 border border-neutral-700 rounded-md px-2.5 py-1.5 text-[11px] font-mono shadow-lg">
                  <div className="text-neutral-200 font-semibold">
                    Review #{dot.reviewId}
                  </div>
                  <div
                    className={`mt-0.5 font-medium ${
                      dot.outcome === 'ok'
                        ? 'text-tertiary-400'
                        : dot.outcome === 'degraded'
                        ? 'text-severity-medium'
                        : dot.outcome === 'failed' ? 'text-severity-critical' : 'text-neutral-400'
                    }`}
                  >
                    {styles.label}
                  </div>
                  {dot.failureReason && (
                    <div className="mt-1 text-neutral-400 max-w-xs break-words leading-snug">
                      {dot.failureReason}
                    </div>
                  )}
                  {/* Caret */}
                  <div className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-neutral-700" />
                </div>
              </div>
            )}

            {/* Dot */}
            <button
              type="button"
              aria-label={`Review #${dot.reviewId}: ${styles.label}${dot.failureReason ? ` — ${dot.failureReason}` : ''}`}
              aria-describedby={isActive ? `${scope}-dot-tooltip-${dot.reviewId}` : undefined}
              onKeyDown={event => { if (event.key === 'Escape') setActiveIdx(null); }}
              onMouseEnter={() => setActiveIdx(idx)}
              onMouseLeave={() => setActiveIdx(null)}
              onFocus={() => setActiveIdx(idx)}
              onBlur={() => setActiveIdx(null)}
              className={`w-3 h-3 rounded-full border cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary-500 transition-transform hover:scale-125 ${styles.dot}`}
            />
          </div>
        );
      })}
    </div>
  );
};
