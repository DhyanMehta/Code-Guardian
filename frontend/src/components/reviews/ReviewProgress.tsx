import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import type { ReviewStatus } from '../../api/contracts';

// Service readiness is separate from the review's recorded execution events.
export function ReviewProgress({ status }: { status: ReviewStatus }) {
  const active = status === 'pending' || status === 'running';
  const health = useResource(active ? 'service:readiness' : null, endpoints.readiness, () => 15_000);
  if (!active) return null;
  return <section role="status" className="rounded-lg border border-neutral-700 p-4 space-y-2">
    <p>{status === 'pending' ? 'Review queued. Analysis has not started yet.' : 'Review running. Results will appear automatically when analysis finishes.'}</p>
    {health.error ? <p>Cannot check worker availability right now. The review status will continue to refresh.</p>
      : health.data?.checks.worker === 'unavailable' ? <p className="text-severity-medium">The review worker is unavailable or its heartbeat is stale. The server operator needs to start or restore the worker; refreshing this page does not start analysis.</p>
      : health.data?.status === 'not_ready' ? <p className="text-severity-medium">A backend dependency is unavailable. The server operator needs to check service readiness.</p>
      : status === 'pending' && health.data && <p>The worker is available. This review is waiting for its turn in the queue.</p>}
    <p className="text-sm text-neutral-400">Review status updates every five seconds while this tab is visible. Updates pause when hidden or offline and back off after connection errors. Final findings appear after aggregation.</p>
  </section>;
}
