import { ArrowUpRight, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import { severities, type PullRequest, type ReviewItem } from '../../api/contracts';
import { activeReview, repositoryDestination } from '../../api/identity';
import { diagnosticText } from '../reviews/diagnosticText';
import { Button } from '../common/Button';
import { SeverityBadge } from '../common/SeverityBadge';
import { StatusBadge } from '../common/StatusBadge';
import { WriteFeedback } from '../common/WriteFeedback';
import type { ComponentProps } from 'react';
import type { classifyPrActions } from './prActions';

interface Props {
  pr: PullRequest;
  repo: string;
  review?: ReviewItem;
  actions: ReturnType<typeof classifyPrActions>;
  feedback: ComponentProps<typeof WriteFeedback>;
  onRecover: () => void;
  onSubmit: () => void;
}

function revisionText(revision: Props['actions']['revision'], review: ReviewItem) {
  if (!review.commit_sha) return 'Reviewed revision not recorded';
  if (revision === 'unknown') return 'Current PR head unavailable';
  const same = revision === 'current';
  if (activeReview(review.status)) return same ? 'Targets the current revision' : 'Targets an older revision';
  if (!same) return 'Outdated · PR head has changed';
  return review.status === 'completed' ? 'Current revision reviewed' : 'Matches the current revision';
}

export function PullRequestRow({ pr, repo, review, actions, onRecover, onSubmit, feedback }: Props) {
  const saved = actions.destination ? review : undefined;
  const context = ` for ${repo} PR #${pr.number}`;
  const repository = repositoryDestination(repo);
  const destination = repository && Number.isSafeInteger(pr.number) && pr.number > 0
    ? `${repository}/pull/${pr.number}` : null;
  const title = <><span className="font-mono text-fg-muted">#{pr.number}</span>{' '}{pr.title}</>;
  return (
    <article aria-labelledby={`pr-title-${pr.number}`} className="min-w-0 rounded-xl border border-divider bg-panel p-4 text-fg [overflow-wrap:anywhere] sm:p-5">
      <h3 id={`pr-title-${pr.number}`} className="text-row-title md:text-row-title-wide">
        {destination ? <a href={destination} target="_blank" rel="noreferrer" className="control-target control-focus inline-block max-w-full content-center rounded-sm hover:text-link hover:underline">
          {title}
          <ArrowUpRight aria-hidden="true" className="ml-1 inline size-4 text-fg-muted" />
        </a> : title}
      </h3>
      <p className="mt-1 text-meta text-fg-muted">{pr.user ? `Opened by ${pr.user}` : 'Author unavailable'}</p>
      <div className="mt-2 grid min-w-0 gap-2 border-t border-divider pt-2 sm:mt-4 sm:gap-4 sm:pt-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="min-w-0 space-y-1 text-support text-fg-secondary sm:space-y-2">
          {saved && <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <strong className="text-fg">{actions.lastKnown ? 'Last known review' : 'Review'} #{saved.id}</strong>
              <StatusBadge status={saved.status} />
              <span>{revisionText(actions.revision, saved)}</span>
            </div>
            {actions.revision === 'outdated' && <p className="text-meta">Review revision <code>{saved.commit_sha?.slice(0, 12)}</code> · Current head <code>{pr.head_sha.slice(0, 12)}</code></p>}
            {(saved.status === 'failed' || saved.status === 'skipped') && (
              <p className="text-risk-medium">{saved.summary ? diagnosticText(saved.summary) : saved.status === 'failed' ? 'Analysis failed.' : 'Analysis was skipped.'}</p>
            )}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span>{saved.finding_count} {saved.finding_count === 1 ? 'finding' : 'findings'} reported</span>
              {severities.filter(level => saved.severity_counts[level] > 0).map(level => (
                <span key={level} className="inline-flex items-center gap-1 text-meta">
                  <SeverityBadge severity={level} size="sm" />{saved.severity_counts[level]}
                </span>
              ))}
            </div>
            {!!saved.degraded_agents.length && <p className="text-status-degraded">Degraded agents · {saved.degraded_agents.map(name => name.replaceAll('_', ' ')).join(', ')}</p>}
            <p>GitHub report · {saved.delivery_status ?? 'delivery not recorded'}</p>
          </>}
          {actions.explanation && <p>{actions.explanation}</p>}
          {actions.warning && <p className="text-risk-medium">{actions.warning}</p>}
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-2 lg:max-w-72 lg:justify-end">
          {actions.recoveryLabel && <Button onClick={onRecover}>{actions.recoveryLabel}</Button>}
          {actions.destination && <Link to={actions.destination} aria-label={`${actions.readLabel} #${saved!.id}${context}`}
            className={`control-target control-focus inline-flex items-center justify-center gap-2 rounded-lg px-3 text-control ${actions.primary === 'link' ? 'bg-action text-action-foreground hover:bg-action-hover' : 'text-link underline'}`}>
            {actions.readLabel}<ArrowRight aria-hidden="true" className="size-4" />
          </Link>}
          {actions.mutation && <Button variant={actions.primary === 'request' ? 'primary' : 'secondary'} size="sm"
            aria-label={actions.mutation + context} disabled={actions.disabled} aria-busy={feedback.busy || undefined} onClick={onSubmit}>
            {actions.mutation}
          </Button>}
        </div>
      </div>
      {(feedback.error || feedback.uncertain || feedback.busy) && <div className="mt-3"><WriteFeedback {...feedback} busyMessage="Requesting review…" /></div>}
      <details className="mt-1 text-meta text-fg-muted sm:mt-3">
        <summary className="control-target control-focus w-fit cursor-pointer content-center rounded pr-2 text-link">Commit details</summary>
        <dl className="grid gap-2 sm:grid-cols-2">
          <div><dt>Current PR head</dt><dd className="font-mono">{pr.head_sha || 'Not recorded'}</dd></div>
          {saved && <div><dt>Review revision</dt><dd className="font-mono">{saved.commit_sha || 'Not recorded'}</dd></div>}
        </dl>
      </details>
    </article>
  );
}
