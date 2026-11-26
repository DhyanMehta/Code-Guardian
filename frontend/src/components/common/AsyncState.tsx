import { errorMessage } from '../../api/client';
import { diagnosticText } from '../reviews/diagnosticText';
import { Button } from './Button';
import { FriendlyTimestamp } from './FriendlyTimestamp';

interface AsyncStateProps {
  loading?: boolean;
  error?: unknown;
  hasData?: boolean;
  refresh?: () => void;
  updatedAt?: number;
  showExactFetchTime?: boolean;
}

export function AsyncState({ loading, error, hasData = false, refresh, updatedAt, showExactFetchTime = false }: AsyncStateProps) {
  const timestamp = updatedAt === undefined ? null : new Date(updatedAt);
  return (
    <>
      {loading && (
        <p role={hasData ? undefined : 'status'} className="text-support text-fg-muted">
          {hasData ? 'Refreshing…' : 'Loading…'}
        </p>
      )}
      {!!error && (
        <div className="space-y-2 rounded-lg border border-risk-medium/35 bg-risk-medium-bg p-3">
          <p role="alert" className="text-support text-risk-medium [overflow-wrap:anywhere]">
            {hasData ? 'Updates delayed. ' : ''}{diagnosticText(errorMessage(error))}
          </p>
          {refresh && <Button variant="secondary" size="sm" aria-busy={loading || undefined} onClick={refresh}>Retry</Button>}
        </div>
      )}
      {updatedAt !== undefined && (showExactFetchTime ? (
        <FriendlyTimestamp kind="fetch" value={updatedAt} label="Last successful fetch" />
      ) : timestamp && Number.isFinite(timestamp.getTime()) && (
        <p className="text-meta md:text-meta-wide text-fg-muted">
          Last updated <time dateTime={timestamp.toISOString()}>{timestamp.toLocaleTimeString()}</time>
        </p>
      ))}
    </>
  );
}

export function FetchDetails({ sources }: { sources: { label: string; updatedAt?: number }[] }) {
  const recorded = sources.flatMap(({ label, updatedAt }) =>
    updatedAt === undefined || !Number.isFinite(updatedAt) ? [] : [{ label, time: new Date(updatedAt) }],
  );
  if (!recorded.length) return null;

  return (
    <details className="text-meta md:text-meta-wide text-fg-muted">
      <summary className="control-target control-focus w-fit cursor-pointer content-center rounded-md pr-2 hover:text-fg">
        Refresh details
      </summary>
      <dl className="space-y-1 pb-1 pl-4">
        {recorded.map(({ label, time }) => (
          <div key={label} className="flex flex-wrap gap-x-2">
            <dt>{label}</dt>
            <dd><time dateTime={time.toISOString()}>{time.toLocaleString()}</time></dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
