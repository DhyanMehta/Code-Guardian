import { Link } from 'react-router-dom';
import type { TrendPoint } from '../../api/contracts';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { StatusBadge } from '../common/StatusBadge';
import { hasObservation } from './WeightedFindings';

const headers = ['Review', 'Analysis', 'Findings', 'Weighted index', 'Execution evidence'];
const mobileLabel = 'text-meta text-fg-muted lg:sr-only';

export function AnalyticsHistory({ points }: { points: TrendPoint[] }) {
  return <section id="analytics-history" tabIndex={-1} aria-labelledby="history-heading" className="scroll-mt-20">
    <h3 id="history-heading" className="text-section">Review history</h3>
    <p className="mt-1 mb-4 text-support text-fg-muted">Sampled records in creation order, oldest first.</p>
    <table role="table" aria-labelledby="history-heading" className="block w-full text-left text-support lg:table">
      <thead role="rowgroup" className="sr-only bg-panel-inset text-meta text-fg-muted lg:not-sr-only lg:table-header-group">
        <tr role="row">{headers.map(h => <th key={h} role="columnheader" scope="col" className="p-3 font-medium">{h}</th>)}</tr>
      </thead>
      <tbody role="rowgroup" className="grid gap-3 lg:table-row-group">{points.map(p =>
        <tr key={p.review_id} role="row" className="grid grid-cols-2 gap-3 rounded-lg border border-divider bg-panel p-4 lg:table-row">
          <th role="rowheader" scope="row" className="col-span-2 min-w-0 font-normal lg:p-3">
            <div className="text-row-title">Review #{p.review_id} <span className="text-meta text-fg-muted">· PR #{p.pr_number}</span></div>
            <FriendlyTimestamp kind="event" label="Created" value={p.created_at} />
            <Link to={`/reviews/${p.review_id}`} aria-label={`View review #${p.review_id} for PR #${p.pr_number}`} className="control-focus inline-flex min-h-11 items-center rounded text-control text-link underline underline-offset-4">View review</Link>
          </th>
          <td role="cell" className="max-sm:col-span-2 max-sm:flex max-sm:items-center max-sm:gap-2 lg:p-3"><div aria-hidden="true" className={mobileLabel}>Analysis</div><StatusBadge status={p.status} /></td>
          <td role="cell" className="tabular-nums lg:p-3"><div aria-hidden="true" className={mobileLabel}>Reported findings</div>{p.total_findings}</td>
          <td role="cell" className="tabular-nums lg:p-3"><div aria-hidden="true" className={mobileLabel}>Weighted index</div>{p.weighted_index}
            {!hasObservation(p) && <span className="block text-meta text-fg-muted">No plotted observation</span>}
          </td>
          <td role="cell" className="col-span-2 min-w-0 lg:max-w-72 lg:p-3">
            <div aria-hidden="true" className={mobileLabel}>Execution evidence</div>
            <p>{p.coverage_complete ? 'Complete coverage' : p.coverage_recorded ? 'Full records · limited coverage' : 'Full records unavailable'}</p>
            {p.degraded_agents.length > 0 && <p className="text-meta text-risk-medium [overflow-wrap:anywhere]">Degraded/failed: {p.degraded_agents.join(', ')}</p>}
            {p.unrecorded_agents.length > 0 && <p className="text-meta text-fg-muted [overflow-wrap:anywhere]"><span className="sr-only">Agent outcomes · </span>Unrecorded: {p.unrecorded_agents.join(', ')}</p>}
          </td>
        </tr>)}</tbody>
    </table>
  </section>;
}
