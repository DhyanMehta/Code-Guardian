import type { AgentRun } from '../../api/contracts';
import { statusLabel } from '../../api/identity';

export const outcomes = ['ok', 'degraded', 'failed', 'unrecorded'] as const;
export const outcomeLabels = { ok: 'OK', degraded: 'Degraded', failed: 'Failed', unrecorded: 'Unrecorded' };
export const outcomeColors = { ok: 'text-status-ok', degraded: 'text-status-degraded', failed: 'text-status-failed', unrecorded: 'text-fg-muted' };

export function recordedOutcome(run?: AgentRun): typeof outcomes[number] {
  if (run?.recorded && run.outcome && run.outcome !== 'unknown') return run.outcome;
  return 'unrecorded';
}

export function outcomeText(run?: AgentRun) {
  return run?.outcome === 'unknown' ? 'Unknown' : outcomeLabels[recordedOutcome(run)];
}

export function isSpecialistIssue(run: AgentRun) {
  const outcome = recordedOutcome(run);
  return outcome === 'degraded' || outcome === 'failed' || run.coverage?.status === 'partial';
}

export function coverageText(run?: AgentRun) {
  return run?.coverage ? statusLabel(run.coverage.status) : 'Not recorded';
}
