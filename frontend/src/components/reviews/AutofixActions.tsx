import { useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { repoUrl } from '../../api/identity';
import { request } from '../../api/client';
import { parseCreated, parseDecision, type ReviewDetail } from '../../api/contracts';
import { endpoints } from '../../api/endpoints';
import { useResource, invalidateResources } from '../../api/resources';
import { useWrite } from '../../api/writes';
import { Button } from '../common/Button';
import { WriteFeedback } from '../common/WriteFeedback';
import { AsyncState } from '../common/AsyncState';
async function currentHead(r: ReviewDetail, signal: AbortSignal) {
  for (let page = 1; page <= 10; page++) {
    const pulls = await endpoints.pulls(r.installation_id!, r.repo_full_name, page, signal, 2, 'all');
    const pr = pulls.find(p => p.number === r.pr_number); if (pr) return pr.head_sha;
    if (pulls.length < 50) return null;
  }
  return null;
}
export function AutofixActions({ userId, review: r }: { userId: number; review: ReviewDetail }) {
  const write = useWrite(`u:${userId}:autofix:${r.id}`);
  const head = useResource(r.installation_id !== null ? `u:${userId}:head:${r.installation_id}:${r.repo_full_name}:${r.pr_number}` : null, s => currentHead(r, s));
  const previous = useRef(r.autofix.status);
  useEffect(() => { if (previous.current !== r.autofix.status) { previous.current = r.autofix.status; write.reconcile(); } }, [r.autofix.status, write.reconcile]);
  const stale = !!head.data && !!r.commit_sha && head.data !== r.commit_sha;
  const reason = r.status !== 'completed' ? 'Available after analysis completes.' : r.is_fork ? 'Fix branches are unavailable for fork PRs.' : !r.fixable_count ? 'No eligible drafts in this review.' : stale ? 'The PR head changed. Run a new review before creating fixes.' : null;
  const blocked = write.busy || write.uncertain;
  const refresh = () => {
    invalidateResources(`u:${userId}:review:${r.id}`);
    invalidateResources(`u:${userId}:i:${r.installation_id}:repo:${r.repo_full_name}:`);
  };
  return <div className="space-y-3">
    <p className="text-sm text-neutral-400">Revision freshness: {head.loading ? 'Checking…' : stale ? 'Outdated review' : head.data && r.commit_sha ? 'Matches current PR head' : 'Not confirmed'} <button className="underline" onClick={head.refresh}>Refresh PR head</button></p>
    {stale && r.installation_id !== null && <Link className="text-primary-400 underline" to={repoUrl(r.installation_id, r.repo_full_name)}>Open pull requests to run a new review</Link>}
    {(r.autofix.status === null || r.autofix.status === 'failed') && <><p className="text-sm text-neutral-400">Create one branch for all eligible drafts in this review. Apply-time checks may skip some drafts. Inspect the previews above before continuing.</p><AsyncState error={head.error} refresh={head.refresh} /><Button disabled={blocked || !!reason} onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix`, parseCreated, { method: 'POST' }), refresh)}>{write.busy ? 'Creating fix branch…' : 'Create fix branch'}</Button>{reason && <p className="text-sm text-neutral-400">{reason}</p>}{r.fixable_count > 0 && !head.data && <p className="text-xs text-neutral-400">Current-head freshness is not confirmed here; the server validates it before applying fixes.</p>}</>}
    {r.autofix.status === 'creating' && <p role="status">Fix branch creation is in progress. Updates are automatic while this page is active.</p>}
    {r.autofix.status === 'pending_approval' && <><p className="text-sm">Inspect the commit, applied count, and skipped fixes before recording your decision.</p><div className="flex gap-3"><Button disabled={blocked || stale} onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix/approve`, parseDecision, { method: 'POST' }), refresh)}>Approve fix branch</Button><Button variant="secondary" disabled={blocked} onClick={() => void write.run(() => request(`/reviews/${r.id}/autofix/reject`, parseDecision, { method: 'POST' }), refresh)}>Reject fix branch</Button></div>{stale && <p>The PR head changed; approval is unavailable. The branch remains available for inspection.</p>}</>}
    <WriteFeedback {...write} />
  </div>;
}
