import { useState } from 'react';
import { Link } from 'react-router-dom';
import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import { activeReview, lookupHistory, statusLabel } from '../../api/identity';
import { AsyncState } from '../common/AsyncState';
import { panelClass } from '../reviews/ReviewPresentation';
import { TriggerReview } from '../reviews/TriggerReview';
import { useAuth } from '../../context/AuthContext';
export function PullsTab({ scope, installation, repo }: { scope: string; installation: number; repo: string }) {
  const { user } = useAuth();
  const [page, setPage] = useState(1), [pages, setPages] = useState(10);
  const [scanAll, setScanAll] = useState(false);
  const pulls = useResource(`${scope}:pulls:${page}`, s => endpoints.pulls(installation, repo, page, s, 0), () => 60_000);
  const numbers = pulls.data?.map(p => p.number) ?? [];
  const history = useResource(pulls.data ? `${scope}:history:${numbers.join(',')}:${pages}:${scanAll}` : null, s => lookupHistory(installation, repo, numbers, s, pages, scanAll), data => data.items.some(r => activeReview(r.status)) ? 5_000 : 30_000);
  return <div className="space-y-4"><button className="text-primary-400 underline" onClick={() => { pulls.refresh(); history.refresh(); }}>Refresh pull requests</button><AsyncState {...pulls} hasData={!!pulls.data} /><AsyncState {...history} hasData={!!history.data} />
    {pulls.data?.length === 0 && <p>No open pull requests on this page.</p>}
    {pulls.data?.map(pr => { const review = history.data?.latest[pr.number]; return <article key={pr.number} className={panelClass}><div className="flex flex-wrap justify-between gap-3"><h3 className="font-semibold"><a href={pr.html_url} target="_blank" rel="noreferrer" className="hover:text-primary-400">#{pr.number} {pr.title}</a></h3><span className="text-sm text-neutral-400">{pr.user ?? 'Unknown author'}</span></div>
      <p className="font-mono text-xs text-neutral-400">Current head: {pr.head_sha.slice(0, 12)}</p>
      {review ? <><Link to={`/reviews/${review.id}`} className="text-primary-400">Review #{review.id} · {statusLabel(review.status)}</Link><p className="text-sm">{review.commit_sha === pr.head_sha ? 'Reviewed revision matches current head.' : review.commit_sha ? 'Outdated review: the PR head has changed.' : 'Reviewed revision not recorded.'}</p><p className="text-sm text-neutral-400">{review.finding_count} findings reported · delivery {review.delivery_status ?? 'not recorded'}</p></> : <p>{history.data?.exhausted ? 'No review yet.' : 'History lookup incomplete.'}</p>}
      <TriggerReview key={`${installation}:${repo}:${pr.number}`} userId={user!.id} installation={installation} repo={repo} number={pr.number} latest={review} />
    </article>; })}
    {!!history.data && !history.data.exhausted && numbers.some(n => !history.data!.latest[n]) && <button className="underline" onClick={() => setPages(n => n + 10)}>Load more history to resolve older PRs</button>}
    <div className="flex gap-4"><button disabled={page === 1} onClick={() => { setPage(n => n - 1); setScanAll(false); setPages(10); }}>Previous page</button><span>Page {page}</span><button disabled={!pulls.data || pulls.data.length < 50} onClick={() => { setPage(n => n + 1); setScanAll(false); setPages(10); }}>Next page</button></div>
    {history.data && !history.data.exhausted && <button className="underline" onClick={() => { setScanAll(true); setPages(Math.ceil(history.data!.items.length / 100) + 1); }}>Load older review history</button>}
    {!!history.data?.items.length && <details><summary className="cursor-pointer">Loaded review history ({history.data.items.length} of {history.data.total})</summary><ul className="mt-3 space-y-2">{history.data.items.map(r => <li key={r.id}><Link className="text-primary-400" to={`/reviews/${r.id}`}>Review #{r.id} · PR #{r.pr_number} · {r.status} · {r.commit_sha?.slice(0, 12) ?? 'unknown revision'}</Link></li>)}</ul></details>}
  </div>;
}
