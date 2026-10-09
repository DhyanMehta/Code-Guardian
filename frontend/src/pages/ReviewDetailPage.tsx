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
  return <div className="space-y-5"><button className="text-primary-400 underline" onClick={state.refresh}>Refresh review</button><AsyncState {...state} hasData={!!state.data} />{state.monitoringPaused && ['pending', 'failed'].includes(state.data?.delivery_status ?? '') && <p className="text-sm text-neutral-400">Automatic delivery monitoring paused after three minutes. Refresh to check again; the server may still retry delivery.</p>}{state.data && <ReviewContent key={state.data.id} review={state.data} />}</div>;
}
function ReviewContent({ review: r }: { review: ReviewDetail }) {
  const { user } = useAuth(); const [reportOpen, setReportOpen] = useState(false);
  const report = useResource(reportOpen && ['completed', 'failed'].includes(r.status) ? `u:${user!.id}:report:${r.id}` : null, s => endpoints.report(r.id, s));
  return <>
    {r.installation_id !== null && <Link className="text-primary-400 text-sm" to={repoUrl(r.installation_id, r.repo_full_name)}>← {r.repo_full_name}</Link>}
    <header className="space-y-2"><h1 className="text-xl font-bold">Review #{r.id} · {r.repo_full_name} PR #{r.pr_number}</h1><p className="text-sm text-neutral-400">Revision: <span className="font-mono">{r.commit_sha ?? 'Not recorded'}</span></p><p>Analysis: {statusLabel(r.status)}{r.is_fork && ' · Fork PR'}</p><p className="text-xs text-neutral-400">Started: {r.started_at ?? 'Not recorded'} · Completed: {r.completed_at ?? 'Not recorded'}</p><p className="whitespace-pre-wrap">{r.summary}</p><Coverage review={r} /></header>
    <ReviewProgress status={r.status} />
    {(r.status === 'pending' || r.status === 'running') && <AgentTimeline review={r}/>}
    {r.status === 'pending' || r.status === 'running' ? <p className="text-neutral-400">Findings and agent results are not available yet.</p> : <>
    <Counts counts={r.severity_counts} /><h2 className="font-semibold">{r.finding_count} findings reported</h2>
    {!r.findings.length && <p className="text-neutral-400">No findings reported. Check agent coverage before interpreting this result.</p>}
    <FindingsList findings={r.findings} reviewId={r.id}/>
    <div className="grid sm:grid-cols-2 gap-3">{r.agent_runs.map(run => <AgentRunCard key={run.agent} run={run} />)}</div>
    <details className={panelClass}><summary className="cursor-pointer font-semibold">Execution history · attempt {r.attempt}</summary><AgentTimeline review={r}/></details>
    </>}
    <section className={panelClass}><h2 className="font-semibold">GitHub delivery</h2><p>{r.delivery_status ?? 'Not recorded'}</p>{r.delivery_error && <p className="text-severity-medium">{r.delivery_error}</p>}{r.delivery_status === 'posted' && r.comment_id && <a className="text-primary-400 underline" href={`${githubUrl(r.repo_full_name)}/pull/${r.pr_number}#issuecomment-${encodeURIComponent(r.comment_id)}`} target="_blank" rel="noreferrer">View GitHub comment</a>}<p className="text-sm text-neutral-400">Standards version: {r.standards_version ?? 'Default / not recorded'}</p></section>
    <section className={panelClass}><h2 className="font-semibold">Fix branch</h2><p>Status: {r.autofix.status ?? 'Not created'}</p>{r.autofix.branch && <a className="text-primary-400 underline" href={`${githubUrl(r.repo_full_name)}/tree/${encodeURIComponent(r.autofix.branch)}`} target="_blank" rel="noreferrer">{r.autofix.branch}</a>}{r.autofix.commit_sha && <p>Commit: <a className="text-primary-400" href={`${githubUrl(r.repo_full_name)}/commit/${encodeURIComponent(r.autofix.commit_sha)}`}>{r.autofix.commit_sha}</a></p>}<p>Applied fixes: {r.autofix.applied_count ?? 'Not recorded'}</p>{r.autofix.error && <p role="alert">{r.autofix.error}</p>}{r.autofix.skipped_fixes.map((s, i) => <p key={i} className="text-sm">Skipped {s.target ?? [s.target_file, s.target_function].filter(Boolean).join(':')}: {s.reason}</p>)}{r.autofix.approved_by && <p>Approved by {r.autofix.approved_by} at {r.autofix.approved_at ?? 'time not recorded'}</p>}<p className="text-xs text-neutral-400">Approval records a decision; it does not merge. Rejection does not delete the branch.</p></section>
    {['completed', 'failed'].includes(r.status) && <section className={panelClass}><button className="text-primary-400 underline" aria-expanded={reportOpen} onClick={() => setReportOpen(v => !v)}>Saved / rendered report</button>{reportOpen && <><AsyncState {...report} hasData={!!report.data} />{report.data && <pre className="text-xs whitespace-pre-wrap break-words">{report.data.markdown}</pre>}</>}</section>}
    <section className={panelClass}><AutofixActions userId={user!.id} review={r} /></section>
  </>;
}
