import { agents, severities, type AgentRun, type Finding, type ReviewDetail, type SeverityCounts } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { SeverityBadge } from '../common/SeverityBadge';
export const panelClass = 'rounded-lg border border-neutral-800 bg-neutral-900 p-4 space-y-3';
export const agentLabels = { security: 'Security', quality: 'Quality', test_gap: 'Test gaps', documentation: 'Documentation' };
export function Counts({ counts }: { counts: SeverityCounts }) {
  return <div className="flex flex-wrap gap-3">{severities.map(s => <span key={s} className="flex gap-1.5 items-center text-sm"><SeverityBadge severity={s} /><span className="font-mono">{counts[s]}</span></span>)}</div>;
}
export function Coverage({ review }: { review: ReviewDetail }) {
  if (review.status === 'pending' || review.status === 'running') return <p className="text-neutral-400">Agent coverage will be reported when analysis finishes.</p>;
  const ok = agents.filter(a => review.agent_runs.some(r => r.agent === a && r.recorded && r.outcome === 'ok')).length;
  return <p className={ok === 4 ? 'text-tertiary-400' : 'text-severity-medium'}>{ok}/4 agents completed analysis successfully{ok < 4 ? ' — coverage incomplete or unrecorded.' : '.'}</p>;
}
export function AgentRunCard({ run }: { run: AgentRun }) {
  return <section className={panelClass}><h3 className="font-semibold">{agentLabels[run.agent]} · {run.recorded ? statusLabel(run.outcome ?? 'unknown') : 'Not recorded'}</h3><p className="text-sm text-neutral-400">{run.finding_count} findings reported</p>
    {run.failure_reason && <p className="text-severity-medium text-sm">{run.failure_reason}</p>}
    {run.notes.map((note, i) => <p key={i} className="text-sm text-neutral-400">{note}</p>)}
    {!!run.scanner_statuses?.length && <ul className="text-sm">{run.scanner_statuses.map((s, i) => <li key={i}>{s.scanner}: {s.ok ? 'Completed' : 'Failed'} · {s.finding_count} raw findings{s.error && ` — ${s.error}`}{s.error_type && ` (${s.error_type})`}</li>)}</ul>}
    {!!run.raw_findings?.length && <details><summary className="cursor-pointer text-sm text-primary-400">Raw scanner evidence ({run.raw_findings.length})</summary><p className="text-xs text-neutral-400 my-2">Raw evidence is separate from accepted findings and is not added to the finding count.</p>{run.raw_findings.map((f, i) => <div key={`${f.fingerprint}:${i}`} className="border-t border-neutral-800 py-2 text-sm"><p>{f.scanner} / {f.rule_id} · {f.severity}</p><p>{f.file_path ?? 'Location unavailable'}{f.line !== null && `:${f.line}`}</p><pre className="whitespace-pre-wrap break-words text-xs text-neutral-400">{f.message}</pre></div>)}</details>}
  </section>;
}
export function FindingCard({ finding, initiallyOpen }: { finding: Finding; initiallyOpen: boolean }) {
  const f = finding, evidence = f.evidence;
  const field = (key: string) => typeof evidence?.[key] === 'string' ? evidence[key] as string : null;
  const code = typeof f.fix_data?.test_code === 'string' ? f.fix_data.test_code : typeof f.fix_data?.docstring === 'string' ? f.fix_data.docstring : null;
  return <details className={panelClass} open={initiallyOpen || undefined} id={`finding-${f.id}`}><summary className="cursor-pointer"><span className="inline-flex flex-wrap items-center gap-2"><SeverityBadge severity={f.severity} /><span className="font-medium">{f.title}</span><span className="text-xs text-neutral-500">{agentLabels[f.agent]}</span></span></summary>
    <p className="text-xs font-mono text-neutral-400">{f.file_path ?? 'Location not recorded'}{f.line !== null && `:${f.line}`}</p>
    <p className="text-sm whitespace-pre-wrap">{f.detail ?? 'No additional detail recorded.'}</p>
    {f.agent === 'test_gap' && <p className="text-xs text-neutral-400">Static test-reference analysis; this does not measure execution coverage.</p>}
    {f.agent === 'quality' && <div className="text-sm space-y-1"><p>Evidence: {field('kind') === 'verified' ? 'Verified rule' : field('kind') === 'advisory' ? 'Advisory' : 'Not recorded / unrecognized'}</p><p>Symbol: {field('symbol') ?? 'Not recorded'}</p><p>Source: {field('source_file') ?? 'Not recorded'}</p><p>Standards version: {field('standards_version') ?? 'Not recorded'}</p>{field('cited_passage') && <blockquote className="border-l-2 border-primary-500 pl-3 whitespace-pre-wrap">{field('cited_passage')}</blockquote>}</div>}
    {f.fixable && <section><h4 className="text-sm font-semibold">Eligible draft preview</h4>{code ? <pre className="mt-2 p-3 rounded bg-neutral-950 text-xs overflow-auto whitespace-pre-wrap">{code}</pre> : <p className="text-sm text-neutral-400">Preview unavailable for this stored draft format.</p>}<p className="text-xs text-neutral-400">Drafts are revalidated when creating the review's fix branch.</p></section>}
  </details>;
}
