import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { endpoints } from '../api/endpoints';
import { invalidateResources, useResource } from '../api/resources';
import { reviewPolling } from '../api/polling';
import { githubUrl, lookupHistory, positiveId, repoUrl, statusLabel } from '../api/identity';
import type { ReviewDetail } from '../api/contracts';
import { AsyncState } from '../components/common/AsyncState';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { AgentRunCard, Counts, Coverage, panelClass } from '../components/reviews/ReviewPresentation';
import { FindingsList } from '../components/reviews/FindingsList';
import { AgentTimeline } from '../components/reviews/AgentTimeline';
import { AutofixActions } from '../components/reviews/AutofixActions';
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
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-2 border-b border-neutral-800/60">
        <button
          type="button"
          className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline cursor-pointer"
          onClick={state.refresh}
        >
          Refresh review
        </button>
      </div>

      <AsyncState {...state} hasData={!!state.data} />

      {state.monitoringPaused && ['pending', 'failed'].includes(state.data?.delivery_status ?? '') && (
        <div className="p-3.5 rounded-xl bg-neutral-900 border border-neutral-800 text-sm text-neutral-400">
          <p className="text-sm text-neutral-400">Automatic delivery monitoring paused after three minutes. Refresh to check again; the server may still retry delivery.</p>
        </div>
      )}

      {state.data && <ReviewContent key={state.data.id} review={state.data} />}
    </div>
  );
}

function ReviewContent({ review: r }: { review: ReviewDetail }) {
  const { user } = useAuth();
  const [reportOpen, setReportOpen] = useState(false);
  const report = useResource(
    reportOpen && ['completed', 'failed'].includes(r.status) ? `u:${user!.id}:report:${r.id}` : null,
    s => endpoints.report(r.id, s)
  );

  return (
    <div className="space-y-6">
      {r.installation_id !== null && (
        <Link className="inline-flex items-center gap-1.5 text-primary-400 hover:text-primary-300 text-sm font-mono transition-colors" to={repoUrl(r.installation_id, r.repo_full_name)}>
          ← {r.repo_full_name}
        </Link>
      )}

      {/* Review Header Banner */}
      <header className="rounded-xl border border-neutral-800/90 bg-neutral-900/80 p-5 sm:p-6 space-y-4 shadow-xs">
        <div className="space-y-1.5">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-neutral-100">
            Review #{r.id} · {r.repo_full_name} PR #{r.pr_number}
          </h1>
          <p className="text-sm text-neutral-400">
            Revision: <span className="font-mono text-neutral-200">{r.commit_sha ?? 'Not recorded'}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-neutral-800/60 text-xs font-mono">
          <p className="text-neutral-200">
            Analysis: {statusLabel(r.status)}{r.is_fork && ' · Fork PR'}
          </p>
          <span className="text-neutral-600">|</span>
          <p className="text-xs text-neutral-400">
            Started: {r.started_at ?? 'Not recorded'} · Completed: {r.completed_at ?? 'Not recorded'}
          </p>
        </div>

        {r.summary && (
          <p className="whitespace-pre-wrap text-sm text-neutral-300 leading-relaxed pt-2 border-t border-neutral-800/60">
            {r.summary}
          </p>
        )}

        <div className="pt-2">
          <Coverage review={r} />
        </div>
      </header>

      <ReviewProgress status={r.status} />

      {(r.status === 'pending' || r.status === 'running') && <AgentTimeline review={r} />}

      {r.status === 'pending' || r.status === 'running' ? (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-6 text-center">
          <p className="text-neutral-400">Findings and agent results are not available yet.</p>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="space-y-3">
            <Counts counts={r.severity_counts} />
            <div className="flex items-center justify-between pt-1">
              <h2 className="font-semibold text-lg text-neutral-100">{r.finding_count} findings reported</h2>
            </div>
          </div>

          {!r.findings.length && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
              <p className="text-neutral-400">No findings reported. Check agent coverage before interpreting this result.</p>
            </div>
          )}

          <FindingsList findings={r.findings} reviewId={r.id} />

          <div className="space-y-3">
            <h3 className="text-sm font-mono uppercase tracking-wider text-neutral-400">Agent Fleet Results</h3>
            <div className="grid sm:grid-cols-2 gap-3">
              {r.agent_runs.map(run => (
                <AgentRunCard key={run.agent} run={run} />
              ))}
            </div>
          </div>

          <details className={panelClass}>
            <summary className="cursor-pointer font-semibold text-neutral-200 hover:text-white">
              Execution history · attempt {r.attempt}
            </summary>
            <div className="pt-3">
              <AgentTimeline review={r} />
            </div>
          </details>
        </div>
      )}

      {/* GitHub Delivery Section */}
      <section className={panelClass}>
        <h2 className="font-semibold text-base text-neutral-100 pb-2 border-b border-neutral-800/60">GitHub delivery</h2>
        <div className="space-y-2 text-sm">
          <p className="font-mono text-xs text-neutral-300">Status: {r.delivery_status ?? 'Not recorded'}</p>
          {r.delivery_error && <p className="text-severity-medium text-xs">{r.delivery_error}</p>}
          {r.delivery_status === 'posted' && r.comment_id && (
            <p>
              <a
                className="text-primary-400 hover:text-primary-300 underline font-mono text-xs"
                href={`${githubUrl(r.repo_full_name)}/pull/${r.pr_number}#issuecomment-${encodeURIComponent(r.comment_id)}`}
                target="_blank"
                rel="noreferrer"
              >
                View GitHub comment
              </a>
            </p>
          )}
          <p className="text-sm text-neutral-400">Standards version: {r.standards_version ?? 'Default / not recorded'}</p>
        </div>
      </section>

      {/* Fix Branch Section */}
      <section className={panelClass}>
        <h2 className="font-semibold text-base text-neutral-100 pb-2 border-b border-neutral-800/60">Fix branch</h2>
        <div className="space-y-2 text-sm">
          <p className="font-mono text-xs text-neutral-300">Status: {r.autofix.status ?? 'Not created'}</p>
          {r.autofix.branch && (
            <p className="font-mono text-xs">
              Branch: <a className="text-primary-400 hover:text-primary-300 underline" href={`${githubUrl(r.repo_full_name)}/tree/${encodeURIComponent(r.autofix.branch)}`} target="_blank" rel="noreferrer">{r.autofix.branch}</a>
            </p>
          )}
          {r.autofix.commit_sha && (
            <p className="font-mono text-xs">
              Commit: <a className="text-primary-400 hover:text-primary-300" href={`${githubUrl(r.repo_full_name)}/commit/${encodeURIComponent(r.autofix.commit_sha)}`}>{r.autofix.commit_sha}</a>
            </p>
          )}
          <p className="text-xs font-mono text-neutral-400">Applied fixes: {r.autofix.applied_count ?? 'Not recorded'}</p>
          {r.autofix.error && <p role="alert" className="text-severity-critical text-xs">{r.autofix.error}</p>}
          {r.autofix.skipped_fixes.map((s, i) => (
            <p key={i} className="text-sm text-neutral-400">
              Skipped {s.target ?? [s.target_file, s.target_function].filter(Boolean).join(':')}: {s.reason}
            </p>
          ))}
          {r.autofix.approved_by && (
            <p className="text-xs font-mono text-tertiary-400">
              Approved by {r.autofix.approved_by} at {r.autofix.approved_at ?? 'time not recorded'}
            </p>
          )}
          <p className="text-xs text-neutral-400 pt-1">
            Approval records a decision; it does not merge. Rejection does not delete the branch.
          </p>
        </div>
      </section>

      {['completed', 'failed'].includes(r.status) && (
        <section className={panelClass}>
          <button
            type="button"
            className="text-primary-400 hover:text-primary-300 underline font-mono text-xs cursor-pointer"
            aria-expanded={reportOpen}
            onClick={() => setReportOpen(v => !v)}
          >
            Saved / rendered report
          </button>
          {reportOpen && (
            <div className="pt-3 space-y-3">
              <AsyncState {...report} hasData={!!report.data} />
              {report.data && (
                <pre className="p-4 rounded-xl bg-code border border-neutral-800 text-xs font-mono text-neutral-200 whitespace-pre-wrap break-words overflow-auto max-h-96">
                  {report.data.markdown}
                </pre>
              )}
            </div>
          )}
        </section>
      )}

      <section className={panelClass}>
        <AutofixActions userId={user!.id} review={r} />
      </section>
    </div>
  );
}
