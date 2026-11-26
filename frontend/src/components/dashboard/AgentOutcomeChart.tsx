import { Link } from 'react-router-dom';
import { agents, type ReviewDetail } from '../../api/contracts';
import { activeReview } from '../../api/identity';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { SectionCard } from '../common/SectionCard';
import { diagnosticText } from '../reviews/diagnosticText';
import { agentLabels } from '../reviews/ReviewPresentation';
import { isSpecialistIssue, outcomeColors, outcomeLabels, outcomes, outcomeText, recordedOutcome } from './specialistEvidence';

export function AgentOutcomeChart({ reviews, unavailable, total }: { reviews: ReviewDetail[]; unavailable: number; total: number }) {
  const terminal = reviews.filter(review => !activeReview(review.status));
  const remaining = Math.max(0, total - reviews.length - unavailable);

  return <>
    <SectionCard aria-label="Loaded review sample" className="space-y-2">
      <p className="text-row-title">{reviews.length + unavailable} of {total} review records in the loaded sample</p>
      <p className="text-support text-fg-secondary">{terminal.length} terminal reviews · {reviews.length - terminal.length} active · {unavailable} unavailable · {remaining} outside this sample</p>
      <p className="text-support text-fg-muted">Historical outcomes use the {terminal.length} loaded terminal reviews. Execution and coverage are recorded separately.</p>
    </SectionCard>
    <section aria-labelledby="specialist-outcomes" className="space-y-3">
      <h3 id="specialist-outcomes" className="text-section">Specialist outcomes</h3>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {agents.map(agent => {
          const runs = terminal.map(review => review.agent_runs.find(run => run.agent === agent));
          const counts = { ok: 0, degraded: 0, failed: 0, unrecorded: 0 };
          for (const run of runs) counts[recordedOutcome(run)]++;
          const missing = runs.filter(run => !run?.coverage).length;
          const limited = runs.filter(run => run?.coverage?.status === 'partial' || run?.coverage?.status === 'unknown').length;
          const issueReview = reviews.find(review => review.agent_runs.some(run => run.agent === agent && isSpecialistIssue(run)));
          const issue = issueReview?.agent_runs.find(run => run.agent === agent && isSpecialistIssue(run));

          return <article key={agent} aria-label={`${agentLabels[agent]} Agent`} className="min-w-0 rounded-xl border border-divider bg-panel p-4 [overflow-wrap:anywhere]">
            <h4 className="text-row-title">{agentLabels[agent]} Agent</h4>
            <p className="mt-1 text-meta text-fg-muted">{counts.ok} of {terminal.length} recorded with outcome OK</p>
            <dl className="mt-3 grid grid-cols-2 gap-2">
              {outcomes.map(outcome => <div key={outcome} className="rounded-md bg-panel-inset px-2 py-1.5 max-sm:flex max-sm:flex-wrap max-sm:items-baseline max-sm:justify-between max-sm:gap-x-1">
                <dt className={`text-meta ${outcomeColors[outcome]}`}>{outcomeLabels[outcome]}</dt>
                <dd className="text-row-title tabular-nums">{counts[outcome]}</dd>
              </div>)}
            </dl>
            <p className="mt-3 text-meta text-fg-secondary">Coverage unrecorded for {missing} · partial or unknown for {limited}</p>
            <div className="mt-3 border-t border-divider pt-3">
              <p className="text-meta font-semibold">Latest issue in loaded history</p>
              {issueReview && issue ? <>
                <p className="mt-1 text-support text-status-degraded">
                  Outcome {outcomeText(issue)}{issue.coverage?.status === 'partial' && ' · Partial coverage'}
                </p>
                {issue.failure_reason
                  ? <p className="line-clamp-2 text-support text-fg-secondary">{diagnosticText(issue.failure_reason)}</p>
                  : <p className="text-support text-fg-muted">Reason not recorded</p>}
                <FriendlyTimestamp kind="event" value={issueReview.created_at} label="Review created" />
                <Link to={`/reviews/${issueReview.id}#agents`} aria-label={`View ${agentLabels[agent]} issue in review #${issueReview.id}`}
                  className="control-focus inline-flex min-h-11 items-center rounded text-control text-link underline underline-offset-4">Review #{issueReview.id}</Link>
              </> : <p className="mt-1 text-support text-fg-muted">None recorded in this sample.</p>}
            </div>
          </article>;
        })}
      </div>
    </section>
  </>;
}
