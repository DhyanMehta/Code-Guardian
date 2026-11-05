import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import type { ReviewStatus } from '../../api/contracts';

// Service readiness is separate from the review's recorded execution events.
export function ReviewProgress({ status }: { status: ReviewStatus }) {
  const active = status === 'pending' || status === 'running';
  const health = useResource(active ? 'service:readiness' : null, endpoints.readiness, () => 15_000);
  if (!active) return null;
  return (
    <section role="status" className="rounded-xl border border-primary-500/40 bg-neutral-900/80 p-5 space-y-3 shadow-xs">
      <div className="flex items-center gap-3">
        <span className="w-4 h-4 border-2 border-primary-400 border-t-transparent rounded-full motion-safe:animate-spin shrink-0" />
        <p className="font-semibold text-sm text-neutral-100">
          {status === 'pending'
            ? 'Review queued. Analysis has not started yet.'
            : 'Review running. Results will appear automatically when analysis finishes.'}
        </p>
      </div>

      {health.error ? (
        <p className="text-xs text-neutral-300">
          Cannot check worker availability right now. The review status will continue to refresh.
        </p>
      ) : health.data?.checks.worker === 'unavailable' ? (
        <div className="p-3 rounded-lg bg-severity-medium-bg border border-severity-medium-border text-xs text-severity-medium font-medium">
          The review worker is unavailable or its heartbeat is stale. The server operator needs to start or restore the worker; refreshing this page does not start analysis.
        </div>
      ) : health.data?.status === 'not_ready' ? (
        <div className="p-3 rounded-lg bg-severity-medium-bg border border-severity-medium-border text-xs text-severity-medium font-medium">
          A backend dependency is unavailable. The server operator needs to check service readiness.
        </div>
      ) : status === 'pending' && health.data ? (
        <p className="text-xs text-tertiary-400 font-mono">
          The worker is available. This review is waiting for its turn in the queue.
        </p>
      ) : null}

      <p className="text-xs text-neutral-400 leading-relaxed border-t border-neutral-800/60 pt-2 font-mono">
        Review status updates every five seconds while this tab is visible. Updates pause when hidden or offline and back off after connection errors. Final findings appear after aggregation.
      </p>
    </section>
  );
}
