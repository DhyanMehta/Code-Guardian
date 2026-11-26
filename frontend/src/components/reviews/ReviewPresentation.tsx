import { agents, severities, type AgentRun, type ReviewDetail, type SeverityCounts } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { SeverityBadge } from '../common/SeverityBadge';
import { diagnosticText, scannerMessage } from './diagnosticText';
export const panelClass = 'rounded-xl border border-neutral-800/90 bg-neutral-900/80 p-5 space-y-3.5 shadow-xs transition-all duration-150 hover:border-neutral-700/70';
export const agentLabels = { security: 'Security', quality: 'Quality', test_gap: 'Test gaps', documentation: 'Documentation' };

export function Counts({ counts }: { counts: SeverityCounts }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-divider bg-panel p-3">
      <span className="text-meta md:text-meta-wide text-fg-muted">Severities</span>
      {severities.map(s => (
        <span
          key={s}
          className="inline-flex items-center gap-1.5"
        >
          <SeverityBadge severity={s} size="sm" />
          <span className="text-meta md:text-meta-wide tabular-nums text-fg">{counts[s]}</span>
        </span>
      ))}
    </div>
  );
}

export function Coverage({ review }: { review: ReviewDetail }) {
  if (review.status === 'pending' || review.status === 'running') {
    return <p className="text-sm text-neutral-400">Agent coverage will be reported when analysis finishes.</p>;
  }
  if (!review.agent_runs.some(r => r.coverage)) return <p className="text-sm text-neutral-400">Coverage not recorded</p>;
  const ok = agents.filter(a => review.agent_runs.some(r => r.agent === a && r.coverage?.execution === 'completed')).length;
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neutral-900/80 border border-neutral-800 text-xs font-mono">
      <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: ok === 4 ? 'var(--color-tertiary-400)' : 'var(--color-severity-medium)' }} />
      <span className={ok === 4 ? 'text-tertiary-400 font-semibold' : 'text-severity-medium font-semibold'}>
        {ok}/4 agents completed execution{ok < 4 ? ' — coverage incomplete or unrecorded.' : '.'}
      </span>
    </div>
  );
}

export function AgentRunCard({ run }: { run: AgentRun }) {
  return (
    <section className={panelClass}>
      <div className="flex items-center justify-between gap-3 pb-2 border-b border-neutral-800/60">
        <h3 className="font-semibold text-sm text-neutral-100 flex items-center gap-2">
          <span>{agentLabels[run.agent]}</span>
          <span className="text-neutral-500 font-normal">·</span>
          <span className="text-xs font-mono font-medium text-neutral-300">
            {run.coverage ? statusLabel(run.coverage.execution) : run.recorded ? statusLabel(run.outcome ?? 'unknown') : 'Not recorded'}
          </span>
        </h3>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-neutral-950/60 border border-neutral-800 text-neutral-400">
          {run.finding_count} findings reported
        </span>
      </div>

      <p className="text-xs text-neutral-400">{run.coverage ? `Coverage ${run.coverage.status} · ${run.coverage.analyzed_files.length}/${run.coverage.eligible_files.length} eligible files · drafts ${run.coverage.enrichment}` : 'Coverage not recorded'}</p>
      {run.coverage?.enrichment_counts && <p className="text-xs text-neutral-400">Draft targets: {run.coverage.enrichment_counts.completed} completed · {run.coverage.enrichment_counts.skipped} skipped · {run.coverage.enrichment_counts.failed} failed</p>}
      {!!run.coverage?.excluded_files.length && <details className="text-xs"><summary>Excluded files ({run.coverage.excluded_files.length})</summary><ul>{run.coverage.excluded_files.map(f => <li key={f.path}>{diagnosticText(f.path)} — {diagnosticText(f.reason)}</li>)}</ul></details>}
      {run.failure_reason && (
        <div className="p-2.5 rounded-lg bg-severity-medium-bg border border-severity-medium-border text-xs text-severity-medium">
          {diagnosticText(run.failure_reason)}
        </div>
      )}

      {run.notes.map((note, i) => (
        <p key={i} className="text-xs text-neutral-400 leading-relaxed">{diagnosticText(note)}</p>
      ))}

      {!!run.scanner_statuses?.length && (
        <div className="space-y-1.5 pt-1">
          <p className="text-xs font-mono uppercase text-neutral-400 tracking-wider">Scanner Engines</p>
          <ul className="text-xs space-y-1 font-mono">
            {run.scanner_statuses.map((s, i) => (
              <li key={i} className="p-2 rounded bg-neutral-950/60 border border-neutral-800/60 text-neutral-300 flex flex-wrap items-center justify-between gap-2">
                <span>{diagnosticText(s.scanner)}: <span className={s.ok ? 'text-tertiary-400 font-semibold' : 'text-severity-critical font-semibold'}>{s.ok ? 'Completed' : 'Failed'}</span> · {s.finding_count} raw findings</span>
                {s.error && <span className="text-severity-medium text-[11px]">{diagnosticText(s.error)}</span>}
                {s.error_type && <span className="text-neutral-500 text-[11px]">({diagnosticText(s.error_type)})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!!run.raw_findings?.length && (
        <details className="text-xs pt-1">
          <summary className="cursor-pointer text-xs font-mono text-primary-400 hover:text-primary-300 transition-colors">
            Raw scanner evidence ({run.raw_findings.length})
          </summary>
          <p className="text-[11px] text-neutral-400 my-2">
            Raw evidence is separate from accepted findings and is not added to the finding count.
          </p>
          <div className="space-y-2 mt-2">
            {run.raw_findings.map((f, i) => (
              <div key={`${f.fingerprint}:${i}`} className="border-t border-neutral-800/80 pt-2 text-xs space-y-1 font-mono">
                <p className="font-semibold text-neutral-200">{diagnosticText(f.scanner)} / {diagnosticText(f.rule_id)} · {f.severity}</p>
                <p className="text-neutral-400">{f.file_path ? diagnosticText(f.file_path) : 'Location unavailable'}{f.line !== null && `:${f.line}`}</p>
                <pre className="empty:hidden p-2 rounded bg-neutral-950 border border-neutral-800/60 whitespace-pre-wrap break-words text-[11px] text-neutral-300">{scannerMessage(f.scanner, f.message)}</pre>
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
