import type { ProgressEvent, ReviewDetail } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { agentLabels } from './ReviewPresentation';

const stageNames: Record<ProgressEvent['stage'], string> = {
  checkout: 'Checkout', analysis: 'Analysis', agent: 'Agent checkpoint', aggregation: 'Aggregation',
  provider_gate: 'Provider slot', provider_token: 'Token allowance', provider_cooldown: 'Provider cooldown',
  provider_retry: 'Provider retry', provider_priority: 'Required analysis priority',
};
const waitLabels: Partial<Record<ProgressEvent['stage'], string>> = {
  provider_gate: 'Waiting for a provider slot', provider_token: 'Waiting for token allowance',
  provider_cooldown: 'Waiting for provider cooldown', provider_retry: 'Waiting to retry provider request',
  provider_priority: 'Optional drafts waiting for required analysis',
};

export function AgentTimeline({ review }: { review: ReviewDetail }) {
  const attempts = new Map<number, ProgressEvent[]>();
  for (const event of review.progress) {
    const events = attempts.get(event.attempt);
    if (events) events.push(event);
    else attempts.set(event.attempt, [event]);
  }
  const active = review.status === 'pending' || review.status === 'running';
  const attemptNumbers = [...new Set([...attempts.keys(), review.attempt])].sort((a, b) => b - a);
  return <div className="space-y-3">
    {review.heartbeat_at && <FriendlyTimestamp label="Last worker heartbeat" kind="event" value={review.heartbeat_at} />}
    {attemptNumbers.map(attempt => {
      const events = attempts.get(attempt) ?? [];
      const current = attempt === review.attempt;
      const running = current && review.status === 'running';
      const latest = new Map<string, ProgressEvent>();
      for (const event of events) {
        if (!event.stage.startsWith('provider_')) latest.set(event.agent ?? event.stage, event);
      }
      const interruptions = [...latest.values()].filter(e => e.status === 'started' && !running);
      const exceptions = events.filter(e => e.status === 'failed' || e.status === 'degraded');
      const last = events.at(-1);
      const waits = new Map<string, ProgressEvent>();
      for (const event of events) waits.set(event.agent ?? 'review', event);
      const waiting = running ? [...waits.values()].filter(event => event.status === 'started' && waitLabels[event.stage]) : [];
      return <article key={attempt} aria-label={`Attempt ${attempt}`} className="min-w-0 rounded-lg border border-divider bg-panel px-4 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-row-title">{attempt > 0 ? `Attempt ${attempt}` : active ? 'Awaiting first recorded attempt' : 'No numbered attempt recorded'}</h3>
          <span className="text-meta text-fg-muted">{events.length} recorded {events.length === 1 ? 'event' : 'events'}</span>
        </div>
        {waiting.map(event => <p key={event.id} className="mt-2 text-support text-status-active">{event.agent && agentLabels[event.agent] + ' · '}<span>{waitLabels[event.stage]}</span></p>)}
        {current && running && last && !waiting.includes(last) && <p className="mt-2 text-support">Latest checkpoint · {last.agent ? agentLabels[last.agent] + ' · ' : ''}{stageNames[last.stage]} · {statusLabel(last.status)}</p>}
        {exceptions.map(event => <p key={event.id} className="mt-2 text-support text-status-degraded">
          {event.agent ? agentLabels[event.agent] : stageNames[event.stage]} · <strong>{event.status === 'degraded' ? 'Completed with limitations' : 'Failed'}</strong>
        </p>)}
        {interruptions.map(event => <p key={event.id} className="mt-2 text-support text-status-degraded">
          <strong>{current && review.status !== 'failed' && review.status !== 'pending' ? 'Finish unrecorded' : 'Interrupted'}</strong> · {event.agent ? agentLabels[event.agent] : stageNames[event.stage]} has a start without a recorded finish in this attempt.
        </p>)}
        {current && review.status === 'pending' && attempt > 0 && <p className="mt-2 text-support">Waiting to retry interrupted review.</p>}
        {!events.length && <p className="mt-2 text-support text-fg-secondary">{active && current ? 'No checkpoints recorded for this attempt yet.' : 'No checkpoint events were recorded for this attempt.'}</p>}
        <details className="mt-2 border-t border-divider">
          <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">Execution history · attempt {attempt}</summary>
          {events.length ? <ol aria-label={`Recorded events for attempt ${attempt}`} className="divide-y divide-divider">
            {events.map(event => <li key={event.id} className="grid items-baseline gap-x-4 py-2 sm:grid-cols-[minmax(0,1fr)_minmax(8rem,auto)_minmax(0,1fr)]">
              <span className="text-support font-semibold">{event.agent ? agentLabels[event.agent] + ' · ' : ''}{stageNames[event.stage]}</span>
              <span className="text-meta text-fg-secondary">{statusLabel(event.status)}</span>
              <FriendlyTimestamp label="Checkpoint recorded" kind="event" value={event.created_at} />
            </li>)}
          </ol> : <p className="pb-2 text-support text-fg-muted">Event times and stage details are unavailable.</p>}
        </details>
      </article>;
    })}
  </div>;
}
