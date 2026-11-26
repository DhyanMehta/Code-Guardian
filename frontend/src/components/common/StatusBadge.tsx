import type { ReviewStatus } from '../../api/contracts';

type Status = ReviewStatus | 'degraded' | 'unknown';

const appearances: Record<Status, { label: string; color: string }> = {
  completed: { label: 'Completed', color: 'text-status-ok' },
  running: { label: 'Running', color: 'text-status-active' },
  pending: { label: 'Queued', color: 'text-status-active' },
  failed: { label: 'Failed', color: 'text-status-failed' },
  skipped: { label: 'Skipped', color: 'text-status-unrecorded' },
  degraded: { label: 'Degraded', color: 'text-status-degraded' },
  unknown: { label: 'Unknown', color: 'text-status-unrecorded' },
};

export function StatusBadge({ status }: { status: Status }) {
  const { label, color } = appearances[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md bg-panel-raised px-2 py-0.5 text-meta md:text-meta-wide ${color}`}>
      <span aria-hidden="true" className="size-1.5 shrink-0 rounded-full bg-current" />
      {label}
    </span>
  );
}
