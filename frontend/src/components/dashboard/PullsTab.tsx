import { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import { activeReview, lookupHistory, type HistoryLookup } from '../../api/identity';
import { ScopedRefreshStatus } from '../common/ScopedRefreshStatus';
import type { ReviewMode } from '../../api/contracts';
import { ApiError, transient } from '../../api/client';
import type { HistoryState } from './prActions';
import { TriggerReview } from '../reviews/TriggerReview';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../common/Button';
import { LoadedReviewHistory } from './LoadedReviewHistory';

export function PullsTab({ scope, installation, repo, mode }: { scope: string; installation: number; repo: string; mode: ReviewMode }) {
  const { user } = useAuth();
  const [page, setPage] = useState(1), [pages, setPages] = useState(10);
  const [scanAll, setScanAll] = useState(false);
  const pulls = useResource(`${scope}:pulls:${page}`, s => endpoints.pulls(installation, repo, page, s, 0), () => 60_000);
  const numbers = pulls.data?.map(p => p.number) ?? [];
  const history = useResource(pulls.data ? `${scope}:history:${numbers.join(',')}:${pages}:${scanAll}` : null, s => lookupHistory(installation, repo, numbers, s, pages, scanAll), data => data.items.some(r => activeReview(r.status)) ? 5_000 : 30_000);
  // Extending the search creates a new resource key. Keep the already-read page
  // available during that request, but never carry it across access or page changes.
  const pageIdentity = `${scope}:${page}:${numbers.join(',')}`;
  const [continuation, setContinuation] = useState<{ key: string; data: HistoryLookup; updatedAt?: number }>();
  const historyUnavailable = !!history.error && !transient(history.error);
  const previousPage = pulls.data && continuation?.key === pageIdentity && !historyUnavailable ? continuation : undefined;
  const records = history.data ?? previousPage?.data;
  useEffect(() => {
    if (historyUnavailable || !pulls.data) setContinuation(undefined);
  }, [historyUnavailable, pulls.data]);

  function extendHistory(scanOlder: boolean) {
    if (!records) return;
    setContinuation({ key: pageIdentity, data: records, updatedAt: history.updatedAt });
    if (scanOlder) {
      setScanAll(true);
      setPages(Math.ceil(records.items.length / 100) + 1);
    } else setPages(n => n + 10);
  }
  const denied = history.error instanceof ApiError && [401, 403, 404].includes(history.error.status);
  const historyState: HistoryState = denied ? 'denied' : history.error ? 'failed'
    : history.loading || !history.data ? 'loading' : history.data.exhausted ? 'ready' : 'bounded';
  return (
    <div className="space-y-3 sm:space-y-4">
      <div data-workspace-toolbar className="grid gap-x-4 border-b border-divider pb-1 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
        <div className="flex flex-wrap items-center justify-between gap-x-3 sm:contents">
          <h2 className="text-section text-fg sm:self-center md:text-section-wide">Open Pull Requests</h2>
          <Button variant="quiet" size="sm" className="shrink-0 max-sm:px-0" aria-label="Refresh pull requests"
            title="Refresh pull requests and review history" aria-busy={pulls.loading || history.loading || undefined}
            onClick={() => { pulls.refresh(); history.refresh(); }}
          >
            <RefreshCw aria-hidden="true" className="size-4" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
        <div className="min-w-0 sm:col-span-2">
          <ScopedRefreshStatus sources={[
            { ...pulls, label: 'Pull requests', hasData: !!pulls.data },
            {
              ...history, label: 'Review history', applicable: !!pulls.data, hasData: !!records,
              updatedAt: history.updatedAt ?? previousPage?.updatedAt,
            },
          ]} />
        </div>
      </div>

      {pulls.data?.length === 0 && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
          <p>No open pull requests on this page.</p>
        </div>
      )}

      <div className="grid gap-4">
        {pulls.data?.map(pr => {
          const latest = records?.latest[pr.number];
          const active = records?.items.find(item => item.pr_number === pr.number && activeReview(item.status));
          return (
            <TriggerReview key={pr.number} userId={user!.id} installation={installation} repo={repo}
              pr={pr} mode={mode} latest={history.data?.latest[pr.number]} review={active ?? latest} history={historyState}
              refreshHistory={history.refresh} loadOlder={() => extendHistory(false)} />
          );
        })}
      </div>
      {/* Pagination Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-divider pt-4">
        <Button variant="secondary" size="sm"
          disabled={page === 1}
          onClick={() => { setPage(n => n - 1); setContinuation(undefined); setScanAll(false); setPages(10); }}
        >
          Previous page
        </Button>
        <span className="text-meta text-fg-muted">Page {page}</span>
        <Button variant="secondary" size="sm"
          disabled={!pulls.data || pulls.data.length < 50}
          onClick={() => { setPage(n => n + 1); setContinuation(undefined); setScanAll(false); setPages(10); }}
        >
          Next page
        </Button>
      </div>

      {history.data && !history.data.exhausted && numbers.every(n => history.data!.latest[n]) && (
        <div>
          <Button variant="secondary" size="sm" onClick={() => extendHistory(true)}>
            Load older review history
          </Button>
        </div>
      )}

      {records && <LoadedReviewHistory records={records} lastKnown={!history.data || !!history.error} />}
    </div>
  );
}
