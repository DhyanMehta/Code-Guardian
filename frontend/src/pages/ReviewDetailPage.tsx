import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { endpoints } from '../api/endpoints';
import { invalidateResources, useResource } from '../api/resources';
import { reviewPolling } from '../api/polling';
import { activeReview, lookupHistory, positiveId, repoUrl } from '../api/identity';
import type { Snapshot } from '../api/resources';
import type { ReviewDetail } from '../api/contracts';
import { AsyncState } from '../components/common/AsyncState';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { StatusBadge } from '../components/common/StatusBadge';
import { ReviewDelivery } from '../components/reviews/ReviewDelivery';
import { ReviewAgentResults } from '../components/reviews/ReviewAgentResults';
import { FindingsList } from '../components/reviews/FindingsList';
import { AgentTimeline } from '../components/reviews/AgentTimeline';
import { ReviewOverview } from '../components/reviews/ReviewOverview';
import { Button } from '../components/common/Button';
import { FriendlyTimestamp } from '../components/common/FriendlyTimestamp';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';
import { AutofixActions, useReviewHead } from '../components/reviews/AutofixActions';
import { ReviewProgress } from '../components/reviews/ReviewProgress';
export function ReviewDetailPage() {
  const { reviewId } = useParams();
  return reviewId ? <ReviewById key={reviewId} id={positiveId(reviewId)} /> : <LegacyReview />;
}
function LegacyReview() {
  const { owner, repo, number } = useParams(); const { user } = useAuth(); const { selected } = useInstallation(); const [pages, setPages] = useState(10);
  const pr = positiveId(number), full = `${owner}/${repo}`;
  const state = useResource(user && selected && !selected.suspended && pr ? `u:${user.id}:i:${selected.id}:repo:${full}:resolve:${pr}:${pages}` : null, s => lookupHistory(selected!.id, full, [pr!], s, pages));
  const review = pr ? state.data?.latest[pr] : undefined;
  if (review) return <Navigate to={`/reviews/${review.id}`} replace />;
  return <div className="space-y-4"><InstallationPicker />{!pr ? <p role="alert">Invalid pull request number.</p> : selected && !selected.suspended && <><AsyncState {...state} hasData={!!state.data} />{state.data && <p>{state.data.exhausted ? 'No review found for this pull request.' : 'History lookup incomplete.'}</p>}{state.data && !state.data.exhausted && <button className="underline" onClick={() => setPages(n => n + 10)}>Load more history</button>}</>}</div>;
}
function ReviewById({ id }: { id: number | null }) {
  const { user } = useAuth();
  const interval = useMemo(() => reviewPolling(), [id]);
  const state = useResource(user && id ? `u:${user.id}:review:${id}` : null, s => endpoints.review(id!, s, 0), interval);
  const terminal = useRef<string | null>(null);
  useEffect(() => {
    const r = state.data;
    if (r && ['completed', 'failed', 'skipped'].includes(r.status) && terminal.current !== r.status) {
      terminal.current = r.status;
      invalidateResources(`u:${user!.id}:i:${r.installation_id}:repo:${r.repo_full_name}:`);
    }
  }, [state.data, user]);
  if (!id) return <p role="alert">Invalid review ID.</p>;
  const refresh = (
    <div className="flex flex-wrap items-start justify-between gap-x-4">
      <ScopedRefreshStatus sources={[{ ...state, label: 'Review', hasData: !!state.data,
        monitoringPaused: state.monitoringPaused && ['pending', 'failed'].includes(state.data?.delivery_status ?? '') }]} />
      <Button variant="secondary" size="sm" aria-busy={state.loading || undefined} onClick={state.refresh}>Refresh review</Button>
    </div>
  );
  if (!state.data) return refresh;
  return <ReviewContent key={state.data.id} review={state.data} refresh={refresh} delayed={!!state.error} paused={!!state.monitoringPaused && ['pending', 'failed'].includes(state.data.delivery_status ?? '')} />;
}

function revisionLabel(r: ReviewDetail, head: Snapshot<string | null>) {
  if (!r.commit_sha) return 'Reviewed revision not recorded';
  if (!head.data) return head.loading ? 'Checking current PR head…' : 'Current PR head unconfirmed';
  const match = head.data === r.commit_sha;
  if (head.error || head.loading) return match ? 'Matched last loaded PR head' : 'Differs from last loaded PR head';
  return match ? 'Matches current PR head' : 'Outdated review · PR head changed';
}

function ReviewContent({ review: r, refresh, delayed, paused }: { review: ReviewDetail; refresh: React.ReactNode; delayed: boolean; paused: boolean }) {
  const { user } = useAuth();
  const head = useReviewHead(user!.id, r);
  const active = activeReview(r.status);
  const workspace = useRef<HTMLDivElement>(null);
  useEffect(() => {
    // The browser may resolve a fragment before the asynchronous record mounts.
    const reveal = () => {
      if (window.location.hash.startsWith('#finding-')) return; // FindingsList also resolves targets hidden by filters.
      const target = document.getElementById(window.location.hash.slice(1));
      if (!target || !target.closest('.review-workspace')) return;
      if (target instanceof HTMLDetailsElement) target.open = true;
      target.scrollIntoView?.({ block: 'start' });
    };
    if (window.location.hash) reveal();
    else {
      workspace.current?.scrollIntoView?.({ block: 'start' });
      workspace.current?.querySelector('h1')?.focus({ preventScroll: true });
    }
    window.addEventListener('hashchange', reveal);
    return () => window.removeEventListener('hashchange', reveal);
  }, [r.id]);

  const [sectionsOpen, setSectionsOpen] = useState(false);
  const sections = [
    ['overview', 'Overview'],
    ...(!active ? [['findings', 'Findings'], ['agents', 'Agent results']] : []),
    ['execution', 'Execution details'], ['delivery', 'GitHub delivery'],
    ...(r.autofix.status || (r.status === 'completed' && r.fixable_count > 0) ? [['autofix', 'Auto-fix decisions']] : []),
  ];
  const execution = (
    <section id="execution" aria-label="Execution details" tabIndex={-1} className="scroll-mt-20 space-y-3">
      <h2 className="text-section">Execution details</h2>
      <div className="grid gap-x-6 sm:grid-cols-3">
        <FriendlyTimestamp label="Review created" kind="event" value={r.created_at} />
        <FriendlyTimestamp label="Execution started" kind="event" value={r.started_at} />
        <FriendlyTimestamp label="Execution completed" kind="event" value={r.completed_at} />
      </div>
      <AgentTimeline review={r} />
    </section>
  );
  return (
    <div ref={workspace} className="review-workspace scroll-mt-24 space-y-4 text-fg">
      <header className="space-y-2 border-b border-divider pb-4">
        {r.installation_id !== null && <Link className="control-target control-focus inline-flex items-center rounded text-support text-link hover:underline"
          aria-label={`Back to pull requests for ${r.repo_full_name}`} to={repoUrl(r.installation_id, r.repo_full_name)}>← Pull requests</Link>}
        <h1 tabIndex={-1} className="text-page outline-none md:text-page-wide">
          Review #{r.id}<span className="sr-only"> · </span>
          <span className="mt-1 block text-row-title text-fg-secondary">{r.repo_full_name} <span className="whitespace-nowrap">PR #{r.pr_number}</span></span>
        </h1>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-support text-fg-secondary">
          <p className="inline-flex items-center gap-2">Analysis <StatusBadge status={r.status} />{r.is_fork && 'Fork PR'}</p>
          <div className="flex flex-wrap items-center gap-x-2">
            {r.commit_sha && <details><summary className="control-focus control-target cursor-pointer content-center rounded text-link">Revision <code>{r.commit_sha.slice(0, 12)}</code></summary>
              <p className="text-meta">Reviewed commit <code>{r.commit_sha}</code></p>{head.data && <p className="text-meta">Last loaded PR head <code>{head.data}</code></p>}</details>}
            <span>{revisionLabel(r, head)}</span>
          </div>
        </div>
      </header>

      {delayed && <p className="text-support text-status-degraded">Showing the last loaded review.</p>}
      {paused && <p className="text-support text-fg-muted">Automatic delivery monitoring paused after three minutes. Refresh to check again; the server may still retry delivery.</p>}
      <ReviewProgress status={r.status} attempt={r.attempt} />
      <ReviewOverview review={r} active={active} />
      {refresh}
      <nav aria-label="Review sections" className="border-y border-divider">
        <button type="button" aria-expanded={sectionsOpen} aria-controls="review-section-links" onClick={() => setSectionsOpen(open => !open)}
          className="control-focus control-target flex w-full items-center justify-between rounded text-control text-link sm:hidden">
          Jump to review section <span aria-hidden="true">{sectionsOpen ? '▴' : '▾'}</span>
        </button>
        <div id="review-section-links" className={`${sectionsOpen ? 'flex' : 'hidden'} flex-wrap gap-x-2 sm:flex`}>
          {sections.map(([id, label]) => <a key={id} href={`#${id}`} onClick={() => setSectionsOpen(false)} className="control-focus control-target inline-flex items-center rounded-md px-2 text-control text-link hover:bg-panel-raised hover:underline">{label}</a>)}
        </div>
      </nav>
      {!active && <>
        <section id="findings" tabIndex={-1} aria-label="Findings" className="scroll-mt-20 space-y-3">
          <h2 className="text-section">Findings</h2>
          <FindingsList findings={r.findings} reviewId={r.id} total={r.finding_count} standardsVersion={r.standards_version} />
        </section>
        <section id="agents" tabIndex={-1} aria-label="Agent results" className="scroll-mt-20 space-y-3">
          <h2 className="text-section">Agent results</h2>
          <ReviewAgentResults review={r} />
        </section>
      </>}
      {execution}
      <ReviewDelivery review={r} userId={user!.id} />
      <AutofixActions userId={user!.id} review={r} head={head} />
    </div>
  );
}
