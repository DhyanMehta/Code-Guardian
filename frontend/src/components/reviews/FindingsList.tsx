import { useEffect, useRef, useState } from 'react';
import { agents, severities, type Finding } from '../../api/contracts';
import { Button } from '../common/Button';
import { SearchInput } from '../common/SearchInput';
import { FindingCard, evidenceText } from './FindingCard';
import { agentLabels } from './ReviewPresentation';

const emptyFilters = { severity: 'all', agent: 'all', query: '' };
const selectClass = 'control-focus control-target w-full min-w-0 rounded-lg border border-control-border bg-panel-inset px-2 text-control text-fg';

function fragment() {
  return window.location.hash.match(/^#(finding-\d+)$/)?.[1] ?? null;
}

export function FindingsList({ findings, reviewId, total, standardsVersion }: {
  findings: Finding[]; reviewId: number; total: number; standardsVersion: string | null;
}) {
  const [filters, setFilters] = useState(emptyFilters);
  const [target, setTarget] = useState(fragment);
  const [notice, setNotice] = useState('');
  const search = useRef<HTMLInputElement>(null);
  const filtered = filters.severity !== 'all' || filters.agent !== 'all' || !!filters.query;
  const term = filters.query.trim().toLowerCase();
  const selected = findings.filter(f => {
    if (filters.severity !== 'all' && f.severity !== filters.severity) return false;
    if (filters.agent !== 'all' && f.agent !== filters.agent) return false;
    if (!term) return true;
    return [f.title, f.file_path, f.detail, f.line, agentLabels[f.agent], f.severity,
      ...['kind', 'symbol', 'source_file', 'cited_passage', 'standards_version'].map(key => evidenceText(f, key))]
      .join(' ').toLowerCase().includes(term);
  });

  useEffect(() => {
    const changed = () => { setTarget(fragment()); setNotice(''); };
    window.addEventListener('hashchange', changed);
    return () => window.removeEventListener('hashchange', changed);
  }, []);
  useEffect(() => {
    if (!target || !findings.some(f => `finding-${f.id}` === target)) return;
    const card = document.getElementById(target);
    if (card instanceof HTMLDetailsElement) {
      card.open = true;
      card.querySelector('summary')?.focus({ preventScroll: true });
      card.scrollIntoView?.({ block: 'start' });
      setTarget(null);
    } else if (filtered) {
      setFilters(emptyFilters);
      setNotice('Filters cleared to show the linked finding.');
    }
  }, [target, findings, filtered]);

  function change(key: keyof typeof emptyFilters, value: string) {
    setNotice('');
    setFilters(previous => ({ ...previous, [key]: value }));
  }
  if (!findings.length) return <p className="text-support text-fg-secondary">{total
    ? `This review reports ${total} findings. Individual finding records are unavailable.`
    : 'No findings reported. Check agent coverage before interpreting this result.'}</p>;

  return (
    <div className="space-y-2">
      <div role="group" aria-label="Finding filters" className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-[minmax(7rem,0.7fr)_minmax(8rem,0.8fr)_minmax(12rem,2fr)]">
        <label className="min-w-0 text-meta text-fg-secondary">Severity
          <select className={selectClass} aria-label="Filter findings by severity" value={filters.severity} onChange={e => change('severity', e.target.value)}>
            <option value="all">All severities</option>
            {severities.map(s => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>
        </label>
        <label className="min-w-0 text-meta text-fg-secondary">Agent
          <select className={selectClass} aria-label="Filter findings by agent" value={filters.agent} onChange={e => change('agent', e.target.value)}>
            <option value="all">All agents</option>
            {agents.map(a => <option key={a} value={a}>{agentLabels[a]}</option>)}
          </select>
        </label>
        <div className="col-span-2 min-w-0 sm:col-span-1">
          <label htmlFor={`search-findings-${reviewId}`} className="text-meta text-fg-secondary">Search findings</label>
          <SearchInput id={`search-findings-${reviewId}`} ref={search} aria-label="Search findings" placeholder="Title, file, or evidence" value={filters.query} onChange={e => change('query', e.target.value)} />
        </div>
      </div>
      <div className="flex min-h-8 flex-wrap items-center justify-between gap-x-3 text-meta text-fg-muted">
        <p role="status">Showing {selected.length} of {total} findings{notice && <span className="block">{notice}</span>}</p>
        {filtered && <Button variant="quiet" size="sm" onClick={() => { setFilters(emptyFilters); setNotice(''); search.current?.focus(); }}>Clear filters</Button>}
      </div>
      {total !== findings.length && <p className="text-support text-status-degraded">{findings.length} individual records available for this review.</p>}
      {!selected.length && <p className="rounded-lg border border-divider p-4 text-support">No findings match these filters.</p>}
      {selected.map(f => <FindingCard key={`${reviewId}:${f.id}`} finding={f} initiallyOpen={selected.length <= 5} standardsVersion={standardsVersion} />)}
    </div>
  );
}
