import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { repoUrl, repositoryDestination } from '../../api/identity';
import { request } from '../../api/client';
import { parseCreated, parseDecision, type ReviewDetail } from '../../api/contracts';
import { endpoints } from '../../api/endpoints';
import { useResource, invalidateResources } from '../../api/resources';
import { useWrite } from '../../api/writes';
import { Button } from '../common/Button';
import { WriteFeedback } from '../common/WriteFeedback';
import { diagnosticError, diagnosticText } from './diagnosticText';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { AsyncState } from '../common/AsyncState';
async function currentHead(r: ReviewDetail, signal: AbortSignal) {
  for (let page = 1; page <= 10; page++) {
    const pulls = await endpoints.pulls(r.installation_id!, r.repo_full_name, page, signal, 2, 'all');
    const pr = pulls.find(p => p.number === r.pr_number); if (pr) return pr.head_sha;
    if (pulls.length < 50) return null;
  }
  return null;
}
export function useReviewHead(userId: number, r: ReviewDetail) {
  return useResource(r.installation_id !== null ? `u:${userId}:head:${r.installation_id}:${r.repo_full_name}:${r.pr_number}` : null, s => currentHead(r, s));
}

export function AutofixActions({ userId, review: r, head }: { userId: number; review: ReviewDetail; head: ReturnType<typeof useReviewHead> }) {
  const write = useWrite(`u:${userId}:autofix:${r.id}`);
  const previous = useRef(r.autofix.status);
  useEffect(() => { if (previous.current !== r.autofix.status) { previous.current = r.autofix.status; write.reconcile(); } }, [r.autofix.status, write.reconcile]);
  const stale = !!head.data && !!r.commit_sha && head.data !== r.commit_sha;
  const reason = r.status !== 'completed' ? 'Available after analysis completes.' : r.is_fork ? 'Fix branches are unavailable for fork PRs.' : !r.fixable_count ? 'No eligible drafts in this review.' : stale ? 'The PR head changed. Run a new review before creating fixes.' : null;
  const denied = write.errorStatus === 403;
  const blocked = write.busy || write.uncertain || denied;
  const fix = r.autofix;
  const canCreate = fix.status === null || fix.status === 'failed';
  const repo = repositoryDestination(r.repo_full_name);
  const linkStyle = 'control-focus control-target inline-flex max-w-full items-center rounded text-link underline';
  const freshness = head.loading ? 'Checking current PR head…' : head.error || !head.data || !r.commit_sha ? 'Current revision unconfirmed'
    : stale ? 'Outdated review' : 'Matches current PR head';
  const refresh = () => {
    invalidateResources(`u:${userId}:review:${r.id}`);
    invalidateResources(`u:${userId}:i:${r.installation_id}:repo:${r.repo_full_name}:`);
  };
  return <section id="autofix" aria-labelledby="autofix-title" tabIndex={-1} className="scroll-mt-20 space-y-3">
    <h2 id="autofix-title" className="text-section">Auto-fix proposal</h2>
    <div className="space-y-3 rounded-lg border border-divider bg-panel p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-row-title">{fix.status === 'pending_approval' ? 'Awaiting human decision' : fix.status !== null ? 'Status: ' + fix.status : fix.branch ? 'Proposal status not recorded' : 'No proposed branch'}</p>
        <p className="text-meta text-fg-muted">{r.fixable_count} eligible {r.fixable_count === 1 ? 'draft' : 'drafts'} recorded</p>
      </div>
      {fix.error && <p className="text-support text-status-failed">{diagnosticText(fix.error)}</p>}
      {(fix.branch || fix.commit_sha || fix.applied_count !== null) && <div className="space-y-1 border-y border-divider py-2 text-support">
        {fix.branch && <p>Proposed branch · {repo ? <a className={linkStyle} href={`${repo}/tree/${encodeURIComponent(fix.branch)}`} target="_blank" rel="noreferrer"><code>{fix.branch}</code></a> : <code>{fix.branch}</code>}</p>}
        {fix.commit_sha && <p>Proposed commit · {repo ? <a className={linkStyle} href={`${repo}/commit/${encodeURIComponent(fix.commit_sha)}`} target="_blank" rel="noreferrer"><code>{fix.commit_sha}</code></a> : <code>{fix.commit_sha}</code>}</p>}
        <p>Applied fixes: {fix.applied_count ?? 'Not recorded'}</p>
      </div>}
      {!!fix.skipped_fixes.length && <ul className="space-y-1 text-support text-status-degraded">{fix.skipped_fixes.map((s, i) =>
        <li key={i}>Skipped {s.target || [s.target_file, s.target_function].filter(Boolean).join(':') || 'target not recorded'}: {diagnosticText(s.reason)}</li>)}</ul>}
      {fix.approved_by && <p className="text-support">Approved by {fix.approved_by}</p>}
      {fix.approved_at && <FriendlyTimestamp label="Approval recorded" kind="event" value={fix.approved_at} />}
      {fix.status === 'approved' && <p className="text-support text-fg-secondary">Approval records the human decision. Merging the proposed commit is a separate operation.</p>}
      {fix.status === 'rejected' && <p className="text-support text-fg-secondary">Rejection records the decision and leaves the branch in place.</p>}
      {(canCreate || fix.status === 'pending_approval') && <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-x-4"><p className="text-support">Revision · {freshness}</p>
          <Button variant="quiet" size="sm" onClick={head.refresh}>Refresh PR head</Button></div>
        <AsyncState error={diagnosticError(head.error)} refresh={head.refresh} />
        {stale && r.installation_id !== null && <Link className={linkStyle} to={repoUrl(r.installation_id, r.repo_full_name)}>Open pull requests to run a new review</Link>}
        {(!head.data || !r.commit_sha || !!head.error) && <p className="text-meta text-fg-muted">{canCreate
          ? 'The server verifies the current PR revision before creating a fix branch.'
          : 'Current PR revision unavailable. Refresh the PR head to check whether the reviewed revision is current.'}</p>}
      </div>}
      {canCreate && <div className="space-y-3">
        <p className={reason ? 'text-support text-status-degraded' : 'text-support text-fg-secondary'}>{reason ?? 'Create one proposed branch from the eligible drafts. The server checks each draft again before writing the commit.'}</p>
        <Button disabled={blocked || !!reason} aria-busy={write.busy || undefined}
          onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix`, parseCreated, { method: 'POST' }), refresh)}>
          {write.busy ? 'Creating fix branch…' : 'Create fix branch'}
        </Button>
      </div>}
      {fix.status === 'creating' && <p role="status" className="text-support text-status-active">Fix branch creation is in progress. The review will refresh automatically.</p>}
      {fix.status === 'pending_approval' && <div className="space-y-3">
        <p className="text-support text-fg-secondary">Inspect the proposed changes before deciding. Approval records your decision for this branch. Rejection leaves the branch available for inspection.</p>
        {stale && <p className="text-support text-status-degraded">The PR head changed. Approval is unavailable for this revision.</p>}
        <div className="flex flex-wrap gap-3">
          <Button disabled={blocked || stale} onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix/approve`, parseDecision, { method: 'POST' }), refresh)}>Approve fix branch</Button>
          <Button variant="destructive" disabled={blocked} onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix/reject`, parseDecision, { method: 'POST' }), refresh)}>Reject fix branch</Button>
        </div>
      </div>}
      <WriteFeedback {...write} error={write.error && diagnosticText(write.error)} busyMessage={fix.status === 'pending_approval' ? 'Recording your decision…' : undefined} />
      {denied && <Button variant="secondary" size="sm" onClick={write.reconcile}>Access changed · allow an explicit retry</Button>}
    </div>
  </section>;
}
