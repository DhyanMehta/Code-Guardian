import type { ReviewItem, ReviewMode } from '../../api/contracts';
import { activeReview } from '../../api/identity';

export type HistoryState = 'ready' | 'bounded' | 'loading' | 'failed' | 'denied';
export interface PrActionInput {
  history: HistoryState;
  review?: ReviewItem; // Caller selects the newest known active review before a terminal result.
  head: string;
  mode: ReviewMode;
  busy: boolean;
  uncertain: boolean;
  writeDenied: boolean;
}

export function classifyPrActions({ history, review, head, mode, busy, uncertain, writeDenied }: PrActionInput) {
  const readable = history === 'denied' ? undefined : review;
  const active = !!readable && activeReview(readable.status);
  const revision = !readable?.commit_sha || !head ? 'unknown' : readable.commit_sha === head ? 'current' : 'outdated';
  const destination = readable ? `/reviews/${readable.id}` : undefined;
  const readLabel = readable?.status === 'pending' ? 'View Queued Review'
    : readable?.status === 'running' ? 'View Progress'
    : revision === 'outdated' ? 'View Previous Review'
    : readable?.status === 'failed' ? 'Inspect Failed Review'
    : readable?.status === 'skipped' ? 'Inspect Skipped Review' : 'View Review';

  const firstManual = !readable && history === 'ready' && mode === 'manual';
  const mutation = active || writeDenied || history === 'denied' ? undefined
    : busy ? 'Requesting review…'
    : readable ? (revision === 'outdated' ? 'Review Current Revision' : 'Run Another Review')
    : firstManual ? 'Review Pull Request' : 'Request Review Now';
  let primary: 'link' | 'request' | 'refresh' | 'older' | 'none' = 'none';
  let recoveryLabel: string | undefined;
  let explanation: string | undefined;
  if (history === 'denied') {
    explanation = 'Review history is inaccessible for this repository.';
  } else if (uncertain) {
    primary = 'refresh';
    recoveryLabel = 'Check review history';
  } else if (history === 'failed') {
    primary = 'refresh';
    recoveryLabel = 'Retry history';
    explanation = 'Review history unavailable.';
  } else if (!readable && history === 'bounded') {
    primary = 'older';
    recoveryLabel = 'Load older review history';
    explanation = 'Older history has not been fully checked. Another review may already exist.';
  } else if (readable) {
    primary = 'link';
  } else if (history === 'loading') {
    explanation = 'Checking review history. Another review may already exist.';
  } else if (mode === 'auto') {
    explanation = 'No saved review yet. Automatic reviews run on eligible PR events.';
  } else {
    primary = mutation ? 'request' : 'none';
    explanation = 'No saved review yet. A request queues a review of the current PR head.';
  }
  return { primary, destination, readLabel, mutation, recoveryLabel, explanation, revision,
    disabled: busy || uncertain, lastKnown: !!readable && (history === 'failed' || history === 'loading'),
    warning: writeDenied ? 'Repository write access is required to request a review.' : undefined };
}
