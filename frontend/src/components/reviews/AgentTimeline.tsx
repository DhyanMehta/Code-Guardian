import { agents, type ReviewDetail } from '../../api/contracts';
import { agentLabels } from './ReviewPresentation';
export function AgentTimeline({review}: {review: ReviewDetail}) {
  const current = review.progress.filter(e=>e.attempt === review.attempt);
  const active = review.status === 'pending' || review.status === 'running';
  const stage = current.filter(e => e.agent === null).at(-1);
  const waitLabels = {
    provider_gate: 'Waiting for a provider slot',
    provider_token: 'Waiting for token allowance',
    provider_cooldown: 'Waiting for provider cooldown',
    provider_retry: 'Waiting to retry provider request',
    provider_priority: 'Optional drafts waiting for required analysis',
  };
  return (
    <section className="rounded-xl border border-primary-500/30 bg-neutral-900/80 p-5 space-y-4 shadow-xs" aria-label="Review execution progress">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800/60">
        <div className="flex items-center gap-3">
          {active && <span aria-hidden="true" className="h-5 w-5 shrink-0 rounded-full border-2 border-primary-400 border-t-transparent motion-safe:animate-spin" />}
          <h2 className="font-semibold text-base text-neutral-100">
            {review.status === 'pending' ? review.attempt ? 'Waiting to retry interrupted review' : 'Waiting for a worker' : active ? 'Review in progress' : 'Execution history'}
          </h2>
        </div>
        <p className="text-xs font-mono text-neutral-400">
          Attempt {review.attempt}{review.heartbeat_at && ` · Last worker heartbeat: ${new Date(review.heartbeat_at).toLocaleTimeString()}`}
        </p>
      </div>

      {stage && (
        <p className="capitalize text-sm font-mono text-neutral-300">
          {stage.stage}: {stage.status === 'started' ? review.status === 'running' ? 'in progress' : 'interrupted / not recorded complete' : stage.status}
        </p>
      )}

      {!current.length && (
        <p className="text-sm text-neutral-400">
          {active ? 'Execution events will appear when the worker starts.' : 'Live progress was not recorded for this historical review.'}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        {agents.map(agent => {
          const event = current.filter(e => e.agent === agent && e.stage === 'agent').at(-1);
          const latest = current.filter(e => e.agent === agent).at(-1);
          const wait = review.status === 'running' && latest?.status === 'started' && latest.stage in waitLabels
            ? waitLabels[latest.stage as keyof typeof waitLabels] : null;
          const label = event?.status === 'started' ? review.status === 'running' ? 'Running' : 'Interrupted' : event?.status === 'ok' ? 'Completed' : event?.status === 'degraded' ? 'Completed with limitations' : event?.status === 'failed' ? 'Failed' : active ? 'Waiting' : 'Not recorded';
          return (
            <div key={agent} className="rounded-lg border border-neutral-700/80 bg-neutral-950/60 p-3.5 space-y-1">
              <p className="font-medium text-sm text-neutral-200">{agentLabels[agent]}</p>
              <p className={`text-xs font-mono ${event?.status === 'ok' ? 'text-tertiary-400 font-semibold' : 'text-neutral-300'}`}>
                {wait ?? label}
              </p>
              {event && <p className="text-[11px] font-mono text-neutral-500">{new Date(event.created_at).toLocaleTimeString()}</p>}
            </div>
          );
        })}
      </div>

      <p className="text-xs text-neutral-400 leading-relaxed">
        These are recorded execution events. Running agents may be waiting for shared provider capacity; final coverage and findings appear after aggregation.
      </p>
    </section>
  );
}
