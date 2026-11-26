import { agents, type AgentRun, type ReviewDetail } from '../../api/contracts';
import { statusLabel } from '../../api/identity';
import { agentLabels } from './ReviewPresentation';
import { diagnosticText, scannerMessage } from './diagnosticText';

function FileList({ title, files }: { title: string; files: string[] }) {
  return <div className="min-w-0">
    <h4 className="text-meta font-semibold text-fg">{title} ({files.length})</h4>
    {!!files.length && <ul className="mt-1 space-y-1 font-mono text-(length:--text-code) leading-(--text-code--line-height)">{files.map((file, index) => <li key={index}>{diagnosticText(file)}</li>)}</ul>}
  </div>;
}

function AgentEvidence({ run }: { run: AgentRun }) {
  const c = run.coverage;
  const raw = run.raw_findings ?? [];
  if (!c && !raw.length && !run.scanner_statuses?.length && !run.scanner_info) return null;
  return <details className="mt-2 border-t border-divider">
    <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">
      Technical evidence<span className="sr-only"> for {agentLabels[run.agent]}</span>
    </summary>
    <div className="grid min-w-0 gap-4 pb-1 text-support text-fg-secondary">
      {c && <>
        <div className="grid gap-3 sm:grid-cols-3">
          <FileList title="Eligible files" files={c.eligible_files} />
          <FileList title="Analyzed files" files={c.analyzed_files} />
          <FileList title="Excluded files" files={c.excluded_files.map(file => `${file.path} — ${file.reason}`)} />
        </div>
        <p>Batches · {c.batches.completed} completed · {c.batches.failed} failed · {c.batches.reused} reused</p>
        {c.enrichment_counts && <p>Draft enrichment targets · {c.enrichment_counts.completed} completed · {c.enrichment_counts.skipped} skipped · {c.enrichment_counts.failed} failed</p>}
        {c.scanners.map(scanner => <div key={scanner.scanner}>
          <p className="font-semibold">{diagnosticText(scanner.scanner)} · {scanner.completed ? 'Completed' : 'Completion unconfirmed'}</p>
          <FileList title="Eligible scanner files" files={scanner.eligible_files} />
        </div>)}
      </>}
      {!!run.scanner_statuses?.length && <div><h4 className="text-row-title text-fg">Scanner runs</h4>
        <ul className="divide-y divide-divider">{run.scanner_statuses.map((s, index) => <li key={index} className="py-2">
          <strong>{diagnosticText(s.scanner)}</strong> · {s.ok ? 'Completed' : 'Failed'} · {s.finding_count} raw {s.finding_count === 1 ? 'detection' : 'detections'}
          {s.error_type && <p>{diagnosticText(s.error_type)}</p>}
          {s.error && <p className="text-status-degraded">{diagnosticText(s.error)}</p>}
        </li>)}</ul></div>}
      {!run.scanner_statuses?.length && run.scanner_info && <p>{diagnosticText(run.scanner_info)}</p>}
      {!!raw.length && <details><summary className="control-focus control-target w-fit cursor-pointer content-center rounded text-control text-link">Raw scanner detections ({raw.length})</summary>
        <p className="mb-2">Accepted findings are counted separately.</p>
        <ul className="divide-y divide-divider">{raw.map((f, index) => <li key={index} className="space-y-1 py-2">
          <strong>{diagnosticText(f.scanner)} · {diagnosticText(f.rule_id)}</strong> · {statusLabel(f.severity)}
          <p className="font-mono text-(length:--text-code) leading-(--text-code--line-height)">{f.file_path ? diagnosticText(f.file_path) : 'Location unavailable'}{f.line !== null && `:${f.line}`}</p>
          <p className="whitespace-pre-wrap empty:hidden">{scannerMessage(f.scanner, f.message)}</p>
        </li>)}</ul></details>}
    </div>
  </details>;
}

export function ReviewAgentResults({ review }: { review: ReviewDetail }) {
  return <div className="space-y-2">{agents.map(agent => {
    const run = review.agent_runs.find(entry => entry.agent === agent);
    const c = run?.coverage;
    const outcome = run?.outcome === 'unknown' ? 'Unknown' : !run?.recorded || !run.outcome ? 'Not recorded' : run.outcome === 'ok' ? 'OK' : statusLabel(run.outcome);
    const accepted = review.agent_counts[agent];
    const fields = [
      ['Recorded outcome', outcome],
      ['Execution', c ? statusLabel(c.execution) : 'Not recorded'],
      ['Coverage', c ? statusLabel(c.status) : 'Not recorded'],
      ['Accepted findings', accepted],
      ['Draft enrichment', c ? statusLabel(c.enrichment) : 'Not recorded'],
    ];
    return <article key={agent} aria-labelledby={`agent-result-${agent}`} className="min-w-0 rounded-lg border border-divider bg-panel px-4 py-3 [overflow-wrap:anywhere]">
      <div className="grid items-start gap-3 lg:grid-cols-[minmax(8rem,0.9fr)_minmax(0,5fr)]">
        <h3 id={`agent-result-${agent}`} className="text-row-title text-fg">{agentLabels[agent]}</h3>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-5">
          {fields.map(([label,value]) => <div key={label}><dt className="text-meta text-fg-muted">{label}</dt>
            <dd className={`text-support font-semibold ${value === 'Failed' ? 'text-status-failed' : value === 'Degraded' || value === 'Partial' ? 'text-status-degraded' : value === 'OK' ? 'text-status-ok' : 'text-fg'}`}>{value}</dd>
          </div>)}
        </dl>
      </div>
      {run && run.finding_count !== accepted && <p className="mt-2 text-support">Agent run reported {run.finding_count} findings.</p>}
      {run?.failure_reason && <p className="mt-2 text-support text-status-degraded">{diagnosticText(run.failure_reason)}</p>}
      {run?.notes.map((note,index) => <p key={index} className="mt-2 text-support text-fg-secondary">{diagnosticText(note)}</p>)}
      {run?.scanner_statuses?.filter(s => !s.ok).map((s,i) => <p key={i} className="mt-2 text-support text-status-failed">{diagnosticText(s.scanner)} scanner failed{s.error_type ? ` · ${diagnosticText(s.error_type)}` : ''}</p>)}
      {run && <AgentEvidence run={run} />}
    </article>;
  })}</div>;
}
