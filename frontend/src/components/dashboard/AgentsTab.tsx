import { useEffect, useRef, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { ApiError, errorMessage, transient } from '../../api/client';
import type { ReviewDetail, ReviewItem } from '../../api/contracts';
import { endpoints } from '../../api/endpoints';
import { activeReview } from '../../api/identity';
import { useResource } from '../../api/resources';
import { Button } from '../common/Button';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { ScopedRefreshStatus } from '../common/ScopedRefreshStatus';
import { SectionCard } from '../common/SectionCard';
import { StatusBadge } from '../common/StatusBadge';
import { diagnosticError, diagnosticText } from '../reviews/diagnosticText';
import { AgentHistoryRecord, HistoryReviewLink } from './AgentHistoryRecord';
import { AgentOutcomeChart } from './AgentOutcomeChart';

const PAGE_SIZE = 5;
const HISTORY_LIMIT = 200;

export type AgentHistoryCache = Map<number, { detail: ReviewDetail; fetched: number }>;
interface HistoryRecord { id: number; item: ReviewItem; detail?: ReviewDetail; error?: string }
interface DetailProgress { checked: number; total: number }

export async function agentHistory(
  installation: number, repo: string, count: number, signal: AbortSignal,
  cache: AgentHistoryCache = new Map(), onProgress?: (progress: DetailProgress) => void,
) {
  const list = await endpoints.reviews(installation, repo, signal, count).catch(error => {
    if (!signal.aborted && error instanceof ApiError && [401, 403].includes(error.status)) cache.clear();
    throw error;
  });
  signal.throwIfAborted();
  const results: HistoryRecord[] = new Array(list.items.length);
  let cursor = 0;
  let checked = 0;
  onProgress?.({ checked, total: results.length });
  await Promise.all([0, 1].map(async () => {
    while (cursor < list.items.length && !signal.aborted) {
      const index = cursor++;
      const item = list.items[index];
      const id = item.id;
      try {
        const cached = cache.get(id);
        const active = cached && activeReview(cached.detail.status);
        const detail = cached && cached.detail.status === item.status && Date.now() - cached.fetched < (active ? 5_000 : 30_000)
          ? cached.detail : await endpoints.review(id, signal);
        signal.throwIfAborted();
        if (cached?.detail !== detail) cache.set(id, { detail, fetched: Date.now() });
        results[index] = { id, item, detail };
      } catch (error) {
        if (signal.aborted) throw error;
        cache.delete(id);
        results[index] = { id, item, error: diagnosticText(errorMessage(error)) };
      }
      checked++;
      onProgress?.({ checked, total: results.length });
    }
  }));
  signal.throwIfAborted();
  return { results, total: list.total };
}

interface HistoryScope { scope: string; installation: number; repo: string }

export function AgentsTab(props: HistoryScope) {
  return <ScopedAgentsTab key={props.scope} {...props} />;
}

function ScopedAgentsTab({ scope, installation, repo }: HistoryScope) {
  const [count, setCount] = useState(PAGE_SIZE);
  const [detailProgress, setDetailProgress] = useState<DetailProgress | null>(null);
  const cache = useRef<AgentHistoryCache>(new Map());
  const historyHeading = useRef<HTMLHeadingElement>(null);
  const restoreRetryFocus = useRef(false);
  const lastSample = useRef<{ data: Awaited<ReturnType<typeof agentHistory>>; updatedAt?: number; count: number }>(null);
  const state = useResource(`${scope}:agents:${count}`, signal => {
    setDetailProgress(null);
    return agentHistory(installation, repo, count, signal, cache.current, setDetailProgress);
  },
    data => data.results.some(r => r.detail && activeReview(r.detail.status)) ? 5_000 : 30_000);
  const mayRetain = !state.error || transient(state.error);
  useEffect(() => {
    if (state.data) lastSample.current = { data: state.data, updatedAt: state.updatedAt, count };
    else if (!mayRetain) lastSample.current = null;
  }, [state.data, state.updatedAt, mayRetain, count]);

  const previous = mayRetain ? lastSample.current : null;
  const data = state.data ?? previous?.data;
  const continuing = !state.data && !!previous && previous.count < count;
  const canLoadMore = !!data && data.total > count && count < HISTORY_LIMIT;
  const details = data?.results.flatMap(record => record.detail ? [record.detail] : []) ?? [];
  const unavailable = data ? data.results.length - details.length : 0;
  useEffect(() => {
    if (!unavailable && restoreRetryFocus.current) {
      restoreRetryFocus.current = false;
      if (document.activeElement === document.body) historyHeading.current?.focus();
    }
  }, [unavailable]);
  const refresh = () => { cache.current.clear(); state.refresh(); };

  return <div className="min-w-0 space-y-5 text-fg">
    <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div>
        <h2 className="text-page md:text-page-wide">Agent History</h2>
        <p className="text-support text-fg-muted">Recorded specialist outcomes and execution evidence from saved reviews.</p>
        <ScopedRefreshStatus sources={[{
          ...state, label: 'Agent history', hasData: !!data, updatedAt: state.updatedAt ?? previous?.updatedAt,
          error: diagnosticError(state.error),
        }]} />
      </div>
      <Button variant="secondary" aria-busy={state.loading || undefined} onClick={refresh}>
        <RefreshCw aria-hidden="true" className="size-4" />Refresh agent history
      </Button>
    </header>
    {state.loading && !data && <p className="text-support text-fg-muted">{detailProgress
      ? `Checking saved review details · ${detailProgress.checked} of ${detailProgress.total} checked.`
      : 'Reading the history list…'}</p>}
    {data && <>
      <AgentOutcomeChart reviews={details} unavailable={unavailable} total={data.total} />
      <section aria-labelledby="execution-history" className="space-y-3">
        <h3 id="execution-history" ref={historyHeading} tabIndex={-1} className="text-section control-focus">Execution history</h3>
        {!data.results.length && <SectionCard><p className="text-support text-fg-muted">No review history yet.</p></SectionCard>}
        {unavailable > 0 && <div className="flex flex-wrap items-center gap-x-3">
          <p className="text-support text-status-degraded">{unavailable} {unavailable === 1 ? 'review detail unavailable' : 'review details unavailable'}.</p>
          <Button variant="secondary" size="sm" aria-busy={state.loading || undefined} onClick={event => {
            restoreRetryFocus.current = document.activeElement === event.currentTarget;
            state.refresh();
          }}>Retry unavailable details</Button>
        </div>}
        {data.results.map(record => record.detail ? <AgentHistoryRecord key={record.id} review={record.detail} /> :
          <SectionCard key={record.id}>
            <div className="flex flex-wrap items-center gap-2">
              <h4 className="text-row-title">Review #{record.id} · PR #{record.item.pr_number}</h4>
              <StatusBadge status={record.item.status} />
            </div>
            <FriendlyTimestamp kind="event" value={record.item.created_at} label="Created" />
            <p className="text-support text-status-degraded [overflow-wrap:anywhere]">Detail unavailable · {record.error}</p>
            <HistoryReviewLink id={record.id} pr={record.item.pr_number} />
          </SectionCard>)}
        {(canLoadMore || count > PAGE_SIZE) && <Button
          variant="secondary"
          aria-busy={(continuing && state.loading) || undefined}
          aria-disabled={state.loading || !canLoadMore || continuing || undefined}
          onClick={() => { if (canLoadMore && !state.loading && !continuing) setCount(n => Math.min(n + PAGE_SIZE, HISTORY_LIMIT)); }}
        >
          {continuing || canLoadMore ? 'Load older reviews' : data.total > count ? 'History limit reached' : 'All available reviews loaded'}
        </Button>}
        {continuing && state.loading && <>
          <p role="status" className="text-support text-fg-muted">Loading older review details…</p>
          {detailProgress && <p className="text-meta text-fg-muted">{detailProgress.checked} of {detailProgress.total} details checked</p>}
        </>}
        {count === HISTORY_LIMIT && data.total > count && !continuing && (
          <p className="text-support text-fg-muted">This view is limited to the latest {HISTORY_LIMIT} review records.</p>
        )}
      </section>
    </>}
  </div>;
}
