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
  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-neutral-800/60">
        <div>
          <h2 className="text-base font-semibold text-neutral-100">Open Pull Requests</h2>
          <p className="text-xs text-neutral-400">Review status and analysis runs for current repository branches.</p>
        </div>
        <button
          type="button"
          className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer self-start sm:self-auto"
          onClick={() => { pulls.refresh(); history.refresh(); }}
        >
          Refresh pull requests
        </button>
      </div>

      <AsyncState {...pulls} hasData={!!pulls.data} />
      <AsyncState {...history} hasData={!!history.data} />

      {pulls.data?.length === 0 && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
          <p>No open pull requests on this page.</p>
        </div>
      )}

      <div className="grid gap-4">
        {pulls.data?.map(pr => {
          const review = history.data?.latest[pr.number];
          return (
            <article key={pr.number} className={panelClass}>
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <h3 className="font-semibold text-base">
                  <a
                    href={pr.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="hover:text-primary-400 transition-colors inline-flex items-center gap-2"
                  >
                    <span className="text-primary-400 font-mono text-sm">#{pr.number}</span>
                    <span>{pr.title}</span>
                  </a>
                </h3>
                <span className="text-xs font-mono text-neutral-400 bg-neutral-800/80 px-2 py-0.5 rounded border border-neutral-700/50 self-start sm:self-auto">
                  {pr.user ?? 'Unknown author'}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-3 text-xs font-mono text-neutral-400">
                <span className="inline-flex items-center gap-1.5 bg-neutral-950/60 px-2 py-1 rounded border border-neutral-800">
                  Current head: <span className="text-neutral-200">{pr.head_sha.slice(0, 12)}</span>
                </span>
              </div>

              <div className="pt-2 border-t border-neutral-800/60 space-y-2">
                {review ? (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/reviews/${review.id}`}
                        className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary-400 hover:text-primary-300 transition-colors"
                      >
                        Review #{review.id} · {statusLabel(review.status)}
                      </Link>
                    </div>
                    <p className="text-xs text-neutral-300">
                      {review.commit_sha === pr.head_sha
                        ? 'Reviewed revision matches current head.'
                        : review.commit_sha
                        ? 'Outdated review: the PR head has changed.'
                        : 'Reviewed revision not recorded.'}
                    </p>
                    <p className="text-xs text-neutral-400 font-mono">
                      {review.finding_count} findings reported · delivery {review.delivery_status ?? 'not recorded'}
                    </p>
                  </>
                ) : (
                  <p className="text-xs text-neutral-400">
                    {history.data?.exhausted ? 'No review yet.' : 'History lookup incomplete.'}
                  </p>
                )}
              </div>

              <div className="pt-2">
                <TriggerReview
                  key={`${installation}:${repo}:${pr.number}`}
                  userId={user!.id}
                  installation={installation}
                  repo={repo}
                  number={pr.number}
                  latest={review}
                />
              </div>
            </article>
          );
        })}
      </div>

      {!!history.data && !history.data.exhausted && numbers.some(n => !history.data!.latest[n]) && (
        <div className="text-center pt-2">
          <button
            type="button"
            className="text-xs font-mono text-primary-400 hover:text-primary-300 underline cursor-pointer"
            onClick={() => setPages(n => n + 10)}
          >
            Load more history to resolve older PRs
          </button>
        </div>
      )}

      {/* Pagination Controls */}
      <div className="flex items-center justify-between gap-4 pt-4 border-t border-neutral-800/60 text-sm">
        <button
          type="button"
          disabled={page === 1}
          onClick={() => { setPage(n => n - 1); setScanAll(false); setPages(10); }}
          className="px-3 py-1.5 rounded-lg border border-neutral-800 hover:border-neutral-700 bg-neutral-900 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium cursor-pointer transition-colors"
        >
          Previous page
        </button>
        <span className="font-mono text-xs text-neutral-400">Page {page}</span>
        <button
          type="button"
          disabled={!pulls.data || pulls.data.length < 50}
          onClick={() => { setPage(n => n + 1); setScanAll(false); setPages(10); }}
          className="px-3 py-1.5 rounded-lg border border-neutral-800 hover:border-neutral-700 bg-neutral-900 disabled:opacity-40 disabled:cursor-not-allowed text-xs font-medium cursor-pointer transition-colors"
        >
          Next page
        </button>
      </div>

      {history.data && !history.data.exhausted && (
        <div className="text-center">
          <button
            type="button"
            className="text-xs font-mono text-neutral-400 hover:text-neutral-200 underline cursor-pointer"
            onClick={() => { setScanAll(true); setPages(Math.ceil(history.data!.items.length / 100) + 1); }}
          >
            Load older review history
          </button>
        </div>
      )}

      {!!history.data?.items.length && (
        <details className="rounded-xl border border-neutral-800/80 bg-neutral-900/60 p-4 text-xs">
          <summary className="cursor-pointer font-semibold text-neutral-300 hover:text-neutral-100">
            Loaded review history ({history.data.items.length} of {history.data.total})
          </summary>
          <ul className="mt-3 space-y-2 pt-2 border-t border-neutral-800/60 font-mono">
            {history.data.items.map(r => (
              <li key={r.id} className="py-1 flex items-center justify-between">
                <Link className="text-primary-400 hover:underline" to={`/reviews/${r.id}`}>
                  Review #{r.id} · PR #{r.pr_number} · {r.status} · {r.commit_sha?.slice(0, 12) ?? 'unknown revision'}
                </Link>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
