import { useSyncExternalStore } from 'react';
import { errorMessage } from '../../api/client';
import { diagnosticText } from '../reviews/diagnosticText';
import { Button } from './Button';
import { FriendlyTimestamp } from './FriendlyTimestamp';

interface RefreshSource {
  label: string;
  applicable?: boolean;
  loading: boolean;
  updatedAt?: number;
  error?: unknown;
  hasData: boolean;
  monitoringPaused?: boolean;
  refresh: () => void;
}

function subscribe(listener: () => void) {
  window.addEventListener('online', listener);
  window.addEventListener('offline', listener);
  return () => {
    window.removeEventListener('online', listener);
    window.removeEventListener('offline', listener);
  };
}

const isOnline = () => navigator.onLine !== false;
const hasFetchTime = (source: RefreshSource): source is RefreshSource & { updatedAt: number } =>
  typeof source.updatedAt === 'number' && Number.isFinite(source.updatedAt);

export function ScopedRefreshStatus({ sources }: { sources: RefreshSource[] }) {
  const online = useSyncExternalStore(subscribe, isOnline);
  const applicable = sources.filter(source => source.applicable !== false);
  const failed = applicable.filter(source => source.error != null);
  const refreshing = applicable.filter(source => source.loading);
  const recorded = applicable.filter(hasFetchTime);
  const paused = applicable.filter(source => source.monitoringPaused);
  const initial = refreshing.length > 0 && refreshing.every(source => !source.hasData);
  const names = (entries: RefreshSource[]) => entries.map(source => source.label.toLowerCase()).join(' and ');
  const settled = applicable.length > 0 && applicable.length === recorded.length && !failed.length && !refreshing.length;
  const oldest = settled ? Math.min(...recorded.map(source => source.updatedAt)) : undefined;
  let message = 'Awaiting data';
  if (!online) message = 'Offline · updates paused';
  else if (refreshing.length) message = `${initial ? 'Loading' : 'Refreshing'} ${names(refreshing)}…`;
  else if (failed.length) message = 'Some data is unavailable';
  else if (paused.length) message = `Updates paused for ${names(paused)}`;

  return (
    <div className="min-w-0 space-y-1">
      <details>
        <summary className="control-target control-focus w-fit max-w-full cursor-pointer content-center rounded-md pr-2 text-meta text-fg-muted hover:text-fg md:text-meta-wide">
          {oldest !== undefined && online && !paused.length
            ? <FriendlyTimestamp kind="fetch" value={oldest} label={applicable.length > 1 ? 'Oldest successful fetch' : 'Last successful fetch'} inline />
            : <span role={initial && online && !failed.length ? 'status' : undefined}>{message}</span>}
          <span className="sr-only"> · Refresh details</span>
        </summary>
        <ul aria-label="Refresh sources" className="space-y-1 border-l border-divider pl-3">
          {sources.map(source => (
            <li key={source.label}>
              {hasFetchTime(source) && source.applicable !== false
                ? <FriendlyTimestamp kind="fetch" value={source.updatedAt} label={`${source.label} last fetched`} />
                : <p className="py-1 text-meta text-fg-muted">{source.label} · {source.applicable === false ? 'Unavailable' : 'No successful fetch recorded'}</p>}
            </li>
          ))}
        </ul>
      </details>
      {failed.map(source => (
        <div key={source.label} className="flex flex-wrap items-center gap-x-3 rounded-lg border border-risk-medium/35 bg-risk-medium-bg px-3 py-1 text-support text-risk-medium">
          <p role="alert" className="min-w-0 [overflow-wrap:anywhere]">
            {source.label} · {source.hasData ? 'Updates delayed. ' : ''}{diagnosticText(errorMessage(source.error))}
            {source.hasData && <span className="block">Showing the last loaded {source.label.toLowerCase()}.</span>}
          </p>
          <Button variant="secondary" size="sm" aria-busy={source.loading || undefined} onClick={source.refresh}>
            Retry {source.label.toLowerCase()}
          </Button>
        </div>
      ))}
    </div>
  );
}
