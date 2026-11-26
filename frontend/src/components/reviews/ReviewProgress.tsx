import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import type { ReviewStatus } from '../../api/contracts';

export function ReviewProgress({ status, attempt = 0 }: { status: ReviewStatus; attempt?: number }) {
  const active = status === 'pending' || status === 'running';
  const health = useResource(active ? 'service:readiness' : null, endpoints.readiness, () => 15_000);
  if (!active) return null;
  let availability: string | undefined;
  if (health.error) availability = 'Cannot check worker availability right now.';
  else if (health.data?.checks.worker === 'unavailable') availability = 'The review worker is unavailable or its heartbeat is stale. A server operator can restore it.';
  else if (health.data?.status === 'not_ready') availability = 'A backend dependency is unavailable. A server operator can check service readiness.';
  else if (status === 'pending' && health.data?.checks.worker === 'ok') availability = 'The worker is available. This review is waiting for its turn in the queue.';
  return <section aria-label="Analysis progress" className="space-y-2 rounded-lg border border-divider bg-panel p-4">
    <h2 className="text-row-title text-fg">{status === 'running' ? 'Review running.' : attempt > 0 ? 'Review queued. Waiting for another attempt.' : 'Review queued.'}</h2>
    {availability && <p className="text-support text-fg-secondary">{availability}</p>}
    <p className="text-meta text-fg-muted">Status refreshes every five seconds while visible and online. Connection errors slow the updates.</p>
  </section>;
}
