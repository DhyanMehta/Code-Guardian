import { useState } from 'react';
import { agents, severities, type Finding } from '../../api/contracts';
import { FindingCard, agentLabels } from './ReviewPresentation';
export function FindingsList({ findings, reviewId }: { findings: Finding[]; reviewId: number }) {
  const [agent, setAgent] = useState('all'),
    [severity, setSeverity] = useState('all'),
    [query, setQuery] = useState('');
  const selected = findings.filter(
    f =>
      (agent === 'all' || f.agent === agent) &&
      (severity === 'all' || f.severity === severity) &&
      `${f.title} ${f.file_path ?? ''} ${f.detail ?? ''}`.toLowerCase().includes(query.toLowerCase())
  );
  if (!findings.length) return null;

  return (
    <section className="space-y-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 rounded-xl bg-neutral-900/60 border border-neutral-800/80">
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-neutral-300">
            <span>Agent</span>
            <select
              aria-label="Filter findings by agent"
              className="bg-neutral-900 border border-neutral-700/80 hover:border-neutral-600 rounded-lg py-1.5 px-3 text-xs text-neutral-100 font-sans focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 cursor-pointer"
              value={agent}
              onChange={e => setAgent(e.target.value)}
            >
              <option value="all">All agents</option>
              {agents.map(a => (
                <option key={a} value={a}>
                  {agentLabels[a]}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-xs font-mono text-neutral-300">
            <span>Severity</span>
            <select
              aria-label="Filter findings by severity"
              className="bg-neutral-900 border border-neutral-700/80 hover:border-neutral-600 rounded-lg py-1.5 px-3 text-xs text-neutral-100 font-sans focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 cursor-pointer capitalize"
              value={severity}
              onChange={e => setSeverity(e.target.value)}
            >
              <option value="all">All severities</option>
              {severities.map(s => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="w-full md:w-64">
          <input
            className="w-full bg-neutral-900 border border-neutral-700/80 hover:border-neutral-600 rounded-lg py-1.5 px-3 text-xs text-neutral-100 placeholder:text-neutral-400 font-sans focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400"
            type="search"
            aria-label="Search findings"
            placeholder="Search findings or files…"
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center justify-between text-xs font-mono text-neutral-400 px-1">
        <p className="text-sm text-neutral-400">Showing {selected.length} of {findings.length} findings</p>
      </div>

      {!selected.length && !!findings.length && (
        <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
          <p>No findings match these filters.</p>
        </div>
      )}

      <div className="space-y-3">
        {selected.map(f => (
          <FindingCard key={`${reviewId}:${f.id}`} finding={f} initiallyOpen={selected.length <= 5} />
        ))}
      </div>
    </section>
  );
}
