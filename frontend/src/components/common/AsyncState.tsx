import { errorMessage } from '../../api/client';
export function AsyncState({ loading, error, hasData = false, refresh, updatedAt }: { loading?: boolean; error?: unknown; hasData?: boolean; refresh?: () => void; updatedAt?: number }) {
  return <>
    {loading && <p role="status" className="text-sm text-neutral-400">{hasData ? 'Refreshing…' : 'Loading…'}</p>}
    {!!error && <div role="alert" className="rounded-md border border-severity-medium/40 bg-neutral-900 p-3 text-sm text-severity-medium">{hasData ? 'Updates delayed. ' : ''}{errorMessage(error)} {refresh && <button className="underline ml-2" onClick={refresh}>Retry</button>}</div>}
    {updatedAt && <p className="text-xs text-neutral-500">Last updated {new Date(updatedAt).toLocaleTimeString()}</p>}
  </>;
}
