import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { HistoryLookup } from '../../api/identity';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { StatusBadge } from '../common/StatusBadge';

interface Props {
  records: HistoryLookup;
  lastKnown: boolean;
}

export function LoadedReviewHistory({ records, lastKnown }: Props) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details onToggle={event => setExpanded(event.currentTarget.open)} className="min-w-0 rounded-xl border border-divider bg-panel [overflow-wrap:anywhere]">
      <summary className="control-target control-focus cursor-pointer content-center rounded-lg px-3 text-control text-fg hover:text-link">
        Loaded review history ({records.items.length} of {records.total})
      </summary>
      {expanded && <div className="space-y-2 border-t border-divider p-3">
        <p className="text-support text-fg-muted">
          {lastKnown ? 'Showing the last loaded review history.'
            : records.exhausted ? 'No additional history available.' : 'Older history has not been fully checked.'}
        </p>
        {!!records.items.length && (
          <ul aria-label="Historical reviews" className="divide-y divide-divider rounded-lg border border-divider bg-panel-inset">
            {records.items.map(review => (
              <li key={review.id} className="grid min-w-0 gap-y-2 px-3 py-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:gap-x-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <strong className="text-row-title text-fg">Review #{review.id} · PR #{review.pr_number}</strong>
                    <StatusBadge status={review.status} />
                  </div>
                  <FriendlyTimestamp kind="event" value={review.created_at} label="Created" />
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-fg-secondary">
                    <span>{review.finding_count} {review.finding_count === 1 ? 'finding' : 'findings'} reported</span>
                    <span>Revision {review.commit_sha ? <code className="font-mono">{review.commit_sha.slice(0, 12)}</code> : 'unavailable'}</span>
                    <span>GitHub report · {review.delivery_status ?? 'delivery not recorded'}</span>
                  </div>
                  {!!review.degraded_agents.length && (
                    <p className="mt-1 text-meta text-status-degraded">Degraded agents · {review.degraded_agents.map(agent => agent.replaceAll('_', ' ')).join(', ')}</p>
                  )}
                </div>
                <Link to={`/reviews/${review.id}`} aria-label={`View historical review #${review.id} for PR #${review.pr_number}`}
                  className="control-target control-focus inline-flex w-fit items-center rounded-lg border border-control-border px-3 text-control text-link hover:bg-panel-raised">
                  View Review
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>}
    </details>
  );
}
