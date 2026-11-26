import { RefreshCw } from 'lucide-react';
import { severities, type TrendsResponse } from '../../api/contracts';
import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import { Button } from '../common/Button';
import { ScopedRefreshStatus } from '../common/ScopedRefreshStatus';
import { SectionCard } from '../common/SectionCard';
import { SeverityBadge } from '../common/SeverityBadge';
import { StatCard } from '../common/StatCard';
import { AnalyticsHistory } from './AnalyticsHistory';
import { WeightedFindings } from './WeightedFindings';

const severityFill = { critical: 'bg-risk-critical', high: 'bg-risk-high', medium: 'bg-risk-medium', low: 'bg-risk-low', info: 'bg-risk-info', unknown: 'bg-risk-unknown' };

function CountList({ counts }: { counts: Record<string, number> }) {
  return <dl className="mt-3 divide-y divide-divider">{Object.entries(counts).map(([label, count]) =>
    <div key={label} className="flex items-baseline justify-between gap-3 py-2">
      <dt className="text-support text-fg-secondary">{label}</dt><dd className="font-semibold tabular-nums">{count}</dd>
    </div>)}</dl>;
}

function AnalyticsEvidence({ data }: { data: TrendsResponse }) {
  const { range, totals, points } = data;
  const maxSeverity = Math.max(...severities.map(s => totals.severity_counts[s]));
  const outcomes = {
    Completed: totals.completed, Failed: totals.failed, Skipped: totals.skipped,
    Queued: points.filter(p => p.status === 'pending').length, Running: points.filter(p => p.status === 'running').length,
  };
  return <>
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Review records" value={totals.reviews} secondaryText={`Latest ${range.review_count} of up to ${range.requested_limit} records`} />
      <StatCard label="Completed reviews" value={totals.completed} secondaryText="Recorded analysis outcome" />
      <StatCard label="Reported findings" value={totals.findings} secondaryText="Occurrences across sampled reviews" />
      <StatCard label="Full execution coverage records" value={`${totals.coverage_recorded_reviews} of ${totals.reviews}`} secondaryText="Evidence from all four specialists" />
    </div>
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <SectionCard>
        <h3 className="text-section">Analysis outcomes</h3>
        <p className="mt-1 text-support text-fg-muted">Recorded status of {totals.reviews} sampled reviews.</p>
        <CountList counts={outcomes} />
      </SectionCard>
      <SectionCard>
        <h3 className="text-section">Execution coverage</h3>
        <p className="mt-1 text-support text-fg-muted">Full records require an outcome and coverage record for each specialist. A review can appear in several counts below.</p>
        <CountList counts={{
          'Confirmed complete': totals.coverage_complete_reviews,
          'Full records, coverage limited': points.filter(p => p.coverage_recorded && !p.coverage_complete).length,
          'Missing full records': totals.reviews - totals.coverage_recorded_reviews,
          'Degraded or failed specialist outcome': points.filter(p => p.degraded_agents.length > 0).length,
          'All reviews without confirmed complete coverage': totals.reviews_with_coverage_gap,
        }} />
      </SectionCard>
    </div>
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <SectionCard>
        <h3 className="text-section">Findings by severity</h3>
        <p className="mt-1 text-support text-fg-muted">{maxSeverity ? `Bar scale: 0 to ${maxSeverity} reported occurrences.` : 'Every severity bucket has zero reported occurrences.'}</p>
        <dl className="mt-4 space-y-3">{severities.map(s => <div key={s} className="grid grid-cols-[6rem_minmax(0,1fr)_auto] items-center gap-2">
          <dt><SeverityBadge severity={s} size="sm" /></dt>
          <dd className="contents"><span aria-hidden="true" className="block h-2 overflow-hidden rounded bg-panel-raised">
            <span className={`block h-full rounded ${severityFill[s]}`} style={{ width: `${maxSeverity ? totals.severity_counts[s] * 100 / maxSeverity : 0}%` }} />
          </span><span className="min-w-6 text-right tabular-nums">{totals.severity_counts[s]}</span></dd>
        </div>)}</dl>
      </SectionCard>
      <WeightedFindings points={points} totals={totals} />
    </div>
    <SectionCard>
      <h3 className="text-section">Auto-fix activity</h3>
      <p className="mt-1 text-support text-fg-muted">Sampled reviews with a saved auto-fix status and their recorded decisions.</p>
      <dl className="mt-4 grid gap-3 sm:grid-cols-3">{Object.entries({
        'Reviews with activity': totals.autofix.created, 'Approved decisions': totals.autofix.approved, 'Rejected decisions': totals.autofix.rejected,
      }).map(([label, value]) => <div key={label} className="border-l-2 border-divider pl-3">
        <dt className="text-meta text-fg-secondary">{label}</dt><dd className="text-section tabular-nums">{value}</dd>
      </div>)}</dl>
    </SectionCard>
    {points.length > 0 && <AnalyticsHistory points={points} />}
  </>;
}

export function AnalyticsTab({ scope, installation, repo }: { scope: string; installation: number; repo: string }) {
  const state = useResource(`${scope}:trends`, s => endpoints.trends(installation, repo, s), () => 30_000);
  return <div className="min-w-0 space-y-5 text-fg">
    <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div>
        <h2 className="text-page md:text-page-wide">Repository analytics</h2>
        <ScopedRefreshStatus sources={[{ ...state, label: 'Analytics', hasData: !!state.data }]} />
      </div>
      <Button variant="secondary" aria-busy={state.loading} onClick={state.refresh}><RefreshCw aria-hidden="true" className="size-4" />Refresh analytics</Button>
    </header>
    {state.data && <AnalyticsEvidence data={state.data} />}
  </div>;
}
