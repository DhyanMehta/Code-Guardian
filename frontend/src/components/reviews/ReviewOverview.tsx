import { agents, severities, type ReviewDetail } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { SeverityBadge } from '../common/SeverityBadge';
import { agentLabels } from './ReviewPresentation';
import { diagnosticText } from './diagnosticText';

function CoverageSummary({ review }: { review: ReviewDetail }) {
  const runs = agents.map(agent => review.agent_runs.find(run => run.agent === agent));
  const recorded = runs.filter(run => run?.coverage).length;
  const executed = runs.filter(run => run?.coverage?.execution === 'completed').length;
  const complete = runs.every(run => run?.recorded && run.outcome === 'ok' &&
    (run.coverage?.status === 'complete' || run.coverage?.status === 'not_applicable'));
  return (
    <div className="space-y-1">
      <h3 className="text-meta text-fg-muted">Execution coverage</h3>
      <p className="text-row-title">{complete ? 'Complete coverage recorded' : recorded ? `Coverage recorded for ${recorded} of ${agents.length} agents` : 'Coverage not recorded'}</p>
      {!recorded && <p className="text-support text-fg-secondary">The extent of analysis is unknown for this review.</p>}
      {recorded > 0 && <p className="text-support text-fg-secondary">{executed} of {agents.length} agents recorded completed execution.</p>}
      <ul className="space-y-1 text-support">
        {agents.map((agent, index) => {
          const run = runs[index];
          const evidence: string[] = [];
          if (run?.outcome === 'degraded' || run?.outcome === 'failed') evidence.push(`${statusLabel(run.outcome)} outcome`);
          if (run?.coverage && run.coverage.execution !== 'completed') evidence.push(`Execution ${run.coverage.execution.replaceAll('_', ' ')}`);
          if (run?.coverage && run.coverage.status !== 'complete') evidence.push(`Coverage ${run.coverage.status.replaceAll('_', ' ')}`);
          if (recorded && !run?.coverage) evidence.push('Coverage not recorded');
          if (!run?.recorded || !run.outcome || run.outcome === 'unknown') evidence.push('Outcome unknown');
          return evidence.length ? <li key={agent}><strong>{agentLabels[agent]}</strong> · {evidence.join(' · ')}</li> : null;
        })}
      </ul>
    </div>
  );
}

export function ReviewOverview({ review: r, active }: { review: ReviewDetail; active: boolean }) {
  return (
    <section id="overview" tabIndex={-1} aria-label="Overview" className="scroll-mt-20 rounded-xl border border-divider bg-panel text-fg">
      <div className="grid gap-4 p-4 sm:p-5 lg:grid-cols-[1.1fr_1fr] lg:gap-8">
        <div>
          {active ? <><h2 className="text-section">{r.status === 'pending' ? 'Awaiting analysis' : 'Analysis in progress'}</h2><p className="mt-2 text-support text-fg-secondary">Findings and agent results are not available yet.</p></> : <>
            <h2 className="text-section"><span className="text-metric-wide tabular-nums">{r.finding_count}</span> {r.finding_count === 1 ? 'finding' : 'findings'} reported</h2>
            <dl aria-label="Reported findings by severity" className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
              {severities.map(level => <div key={level} className="flex items-center justify-between gap-1 border-b border-divider pb-2">
                <dt><SeverityBadge severity={level} size="sm" /></dt>
                <dd className={`tabular-nums ${r.severity_counts[level] ? 'font-semibold text-fg' : 'text-fg-muted'}`}>{r.severity_counts[level]}</dd>
              </div>)}
            </dl>
          </>}
        </div>
        <div className="space-y-3 border-t border-divider pt-3 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          {!active && <CoverageSummary review={r} />}
          <p className="text-support text-fg-secondary">GitHub delivery <strong className="ml-1 text-fg">{r.delivery_status === 'pending' ? 'Pending' : r.delivery_status ? statusLabel(r.delivery_status) : 'Not recorded'}</strong></p>
        </div>
      </div>
      {r.summary && (r.status === 'failed' || r.status === 'skipped'
        ? <p className="border-t border-divider p-4 text-support text-status-degraded">{diagnosticText(r.summary)}</p>
        : <details className="border-t border-divider px-4 sm:px-5"><summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-support text-link">Recorded analysis summary</summary><p className="whitespace-pre-wrap pb-4 text-support">{diagnosticText(r.summary)}</p></details>)}
    </section>
  );
}
