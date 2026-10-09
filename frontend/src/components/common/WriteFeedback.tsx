export function WriteFeedback({ error, uncertain, reconcile }: { error?: string; uncertain: boolean; reconcile: () => void }) {
  return error ? <div role="alert" className="space-y-2 text-sm text-severity-medium"><p>{error}</p>{uncertain && <><p>The server may have completed this action. Refresh and inspect its current state before retrying.</p><button className="underline" onClick={reconcile}>I checked the current state — allow an explicit retry</button></>}</div> : null;
}
