import { Link } from 'react-router-dom';
import { agents, type AgentRun, type ReviewDetail } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { StatusBadge } from '../common/StatusBadge';
import { diagnosticText } from '../reviews/diagnosticText';
import { agentLabels } from '../reviews/ReviewPresentation';
import { coverageText, isSpecialistIssue, outcomeColors, outcomeText, recordedOutcome } from './specialistEvidence';

export function HistoryReviewLink({ id, pr }: { id: number; pr: number }) {
  return <Link to={`/reviews/${id}`} aria-label={`View review #${id} for PR #${pr}`}
    className="control-focus inline-flex min-h-11 items-center rounded text-control text-link underline underline-offset-4">View review</Link>;
}

function ScannerEvidence({ run }: { run: AgentRun }) {
  const scans = run.scanner_statuses ?? [];
  const raw = run.raw_findings ?? [];
  if (!scans.length && !raw.length) return null;
  return <details className="mt-1">
    <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">
      Scanner evidence<span className="sr-only"> for {agentLabels[run.agent]}</span>
    </summary>
    {!!scans.length && <ul className="space-y-1 text-support">{scans.map((scan, index) => <li key={index}>
      {diagnosticText(scan.scanner)} · {scan.ok ? 'Completed' : 'Failed'} · {scan.finding_count} raw {scan.finding_count === 1 ? 'detection' : 'detections'}
    </li>)}</ul>}
    <p className="mt-2 text-meta text-fg-muted">{raw.length} raw {raw.length === 1 ? 'detection record' : 'detection records'} saved. Accepted findings are counted separately.</p>
    {!!raw.length && <ul className="mt-1 space-y-1 text-meta">{raw.map((item, index) => <li key={index}>
      {diagnosticText(item.scanner)} · Rule {diagnosticText(item.rule_id)} · {statusLabel(item.severity)}
    </li>)}</ul>}
  </details>;
}

function SpecialistDetails({ agent, run, accepted }: { agent: typeof agents[number]; run?: AgentRun; accepted: number }) {
  const coverage = run?.coverage;
  const fields = [
    ['Recorded outcome', outcomeText(run)],
    ['Execution', coverage ? statusLabel(coverage.execution) : 'Not recorded'],
    ['Coverage', coverageText(run)],
    ['Accepted findings', accepted],
    ['Draft enrichment', coverage ? statusLabel(coverage.enrichment) : 'Not recorded'],
  ];
  return <section className="min-w-0 py-3 [overflow-wrap:anywhere]">
    <h5 className="mb-2 text-row-title">{agentLabels[agent]}</h5>
    <dl className="grid grid-cols-2 gap-2 sm:grid-cols-5">{fields.map(([label, value]) => <div key={label}>
      <dt className="text-meta text-fg-muted">{label}</dt>
      <dd className="text-support font-semibold">{value}</dd>
    </div>)}</dl>
    {run?.failure_reason && <p className="mt-2 text-support text-status-degraded">{diagnosticText(run.failure_reason)}</p>}
    {coverage?.enrichment_counts && <p className="mt-2 text-meta text-fg-secondary">Draft targets · {coverage.enrichment_counts.completed} completed · {coverage.enrichment_counts.skipped} skipped · {coverage.enrichment_counts.failed} failed</p>}
    {run && <ScannerEvidence run={run} />}
  </section>;
}

export function AgentHistoryRecord({ review }: { review: ReviewDetail }) {
  const runs = agents.map(agent => ({ agent, run: review.agent_runs.find(run => run.agent === agent) }));
  const missing = runs.filter(({ run }) => !run?.coverage).length;
  const limited = runs.filter(({ run }) => run?.coverage?.status === 'partial' || run?.coverage?.status === 'unknown').length;
  const issues = runs.filter(({ run }) => run && isSpecialistIssue(run)).map(({ agent }) => agentLabels[agent]);

  return <article aria-label={`Review #${review.id}`} className="min-w-0 rounded-xl border border-divider bg-panel p-4">
    <div className="flex flex-wrap items-start justify-between gap-x-4">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-row-title">Review #{review.id} <span className="text-meta text-fg-muted">· PR #{review.pr_number}</span></h4>
          <StatusBadge status={review.status} />
        </div>
        <FriendlyTimestamp kind="event" value={review.created_at} label="Created" />
      </div>
      <HistoryReviewLink id={review.id} pr={review.pr_number} />
    </div>
    <p className="text-support">
      {review.finding_count} {review.finding_count === 1 ? 'finding' : 'findings'} reported · {4 - missing} of 4 specialist coverage records
    </p>
    <p className="text-meta text-fg-secondary">
      {missing === 4 ? 'Coverage not recorded' : missing > 0 ? `Coverage not recorded for ${missing}` : 'Coverage recorded for all specialists'}
      {limited > 0 && ` · Partial or unknown coverage for ${limited}`}
      {issues.length > 0 && <span className="text-status-degraded"> · Recorded issues: {issues.join(', ')}</span>}
    </p>
    <ul aria-label="Recorded specialist outcomes" className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-meta">
      {runs.map(({ agent, run }) => <li key={agent}>{agentLabels[agent]} <span className={outcomeColors[recordedOutcome(run)]}>{outcomeText(run)}</span></li>)}
    </ul>
    <details className="mt-2 border-t border-divider">
      <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">
        Specialist details<span className="sr-only"> for review #{review.id}</span>
      </summary>
      {review.standards_version && <p className="text-meta text-fg-muted [overflow-wrap:anywhere]">Standards version · {diagnosticText(review.standards_version)}</p>}
      <div className="divide-y divide-divider">{runs.map(({ agent, run }) =>
        <SpecialistDetails key={agent} agent={agent} run={run} accepted={review.agent_counts[agent]} />)}</div>
    </details>
  </article>;
}
