import { Button } from './Button';
import { diagnosticText } from '../reviews/diagnosticText';

interface WriteFeedbackProps {
  error?: string;
  uncertain: boolean;
  reconcile: () => void;
  busy?: boolean;
  busyMessage?: string;
  success?: string | null;
  canReconcile?: boolean;
}

export function WriteFeedback({ error, uncertain, reconcile, busy, busyMessage, success, canReconcile = true }: WriteFeedbackProps) {
  if (uncertain || error) {
    return (
      <div className="space-y-2 rounded-lg border border-risk-medium/35 bg-risk-medium-bg p-3 text-support text-risk-medium">
        <div role="alert" className="space-y-2 [overflow-wrap:anywhere]">
          {error && <p>{diagnosticText(error)}</p>}
          {uncertain && <p>The server may have completed this action. Refresh and inspect its current state before retrying.</p>}
        </div>
        {uncertain && (
          <Button variant="secondary" size="sm" className="max-w-full" disabled={!canReconcile} onClick={reconcile}>
            I checked the current state — allow an explicit retry
          </Button>
        )}
      </div>
    );
  }

  if (busy) return busyMessage ? <p role="status" className="text-support text-status-active">{busyMessage}</p> : null;
  return success ? (
    <p role="status" className="rounded-lg border border-divider bg-panel-inset p-3 text-support text-status-ok">{success}</p>
  ) : null;
}
