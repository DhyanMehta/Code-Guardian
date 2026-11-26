import { ChevronDown } from 'lucide-react';
import type { Finding } from '../../api/contracts';
import { SeverityBadge } from '../common/SeverityBadge';
import { agentLabels } from './ReviewPresentation';

export function evidenceText(finding: Finding, key: string) {
  const value = finding.evidence?.[key];
  return typeof value === 'string' && value.trim() ? value : undefined;
}

export function FindingCard({ finding: f, initiallyOpen, standardsVersion }: {
  finding: Finding; initiallyOpen: boolean; standardsVersion: string | null;
}) {
  const kind = evidenceText(f, 'kind');
  const qualifier = kind === 'verified' ? 'Verified rule' : kind === 'advisory' ? 'Advisory' : undefined;
  const citation = evidenceText(f, 'cited_passage');
  const symbol = evidenceText(f, 'symbol');
  const source = evidenceText(f, 'source_file');
  const version = evidenceText(f, 'standards_version') ?? standardsVersion;
  const draft = f.fix_data?.test_code ?? f.fix_data?.docstring;
  return (
    <details id={`finding-${f.id}`} open={initiallyOpen || undefined} className="group min-w-0 rounded-lg border border-divider bg-panel">
      <summary className="control-focus flex min-h-11 cursor-pointer list-none items-start gap-3 rounded-lg px-3 py-3 hover:bg-panel-raised sm:px-4">
        <span className="grid min-w-0 flex-1 gap-x-4 gap-y-1 sm:grid-cols-[auto_minmax(0,1fr)]">
          <span className="flex flex-wrap items-center gap-2 sm:row-span-2 sm:self-start">
            <SeverityBadge severity={f.severity} size="sm" />
            <span className="text-meta text-fg-muted sm:hidden">{agentLabels[f.agent]}</span>
          </span>
          <span className="text-row-title text-fg md:text-row-title-wide">{f.title}</span>
          <span className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1 text-meta text-fg-muted">
            <span className="hidden sm:inline">{agentLabels[f.agent]}</span>
            <code className="min-w-0 text-(length:--text-code) leading-(--text-code--line-height) [overflow-wrap:anywhere]">{f.file_path ?? 'Location unavailable'}{f.line !== null && `:${f.line}`}</code>
            {qualifier && <span className="font-semibold text-fg-secondary">{qualifier}</span>}
          </span>
        </span>
        <ChevronDown aria-hidden="true" className="mt-1 size-4 shrink-0 text-link group-open:rotate-180" />
      </summary>
      <div className="space-y-3 border-t border-divider px-3 py-4 text-support text-fg-secondary sm:px-4">
        <a className="control-target control-focus inline-flex items-center rounded text-meta text-link underline" href={`#finding-${f.id}`}>Finding #{f.id}</a>
        <p className="whitespace-pre-wrap">{f.detail || 'No additional detail recorded.'}</p>
        {f.agent === 'test_gap' && <p className="text-meta text-fg-muted">Static test-reference analysis. Execution coverage is reported separately.</p>}
        {f.agent === 'quality' && <div className="space-y-2">
          <h4 className="text-row-title text-fg">Rule evidence</h4>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            <div><dt className="text-meta text-fg-muted">Classification</dt><dd>{qualifier ?? 'Unrecorded or unrecognized'}</dd></div>
            {symbol && <div><dt className="text-meta text-fg-muted">Symbol</dt><dd><code>{symbol}</code></dd></div>}
            {source && <div><dt className="text-meta text-fg-muted">Standards source</dt><dd><code>{source}</code></dd></div>}
            {version && <div><dt className="text-meta text-fg-muted">Historical standards version</dt><dd><code>{version}</code></dd></div>}
          </dl>
          {citation && <blockquote className="whitespace-pre-wrap border-l-2 border-link bg-panel-inset px-3 py-2">{citation}</blockquote>}
        </div>}
        {f.fixable && <div className="space-y-2">
          <h4 className="text-row-title text-fg">Eligible draft preview</h4>
          {typeof draft === 'string' && draft ? <pre tabIndex={0} aria-label="Draft code" className="control-focus max-h-72 max-w-full overflow-auto rounded-md bg-code p-3 text-(length:--text-code) leading-(--text-code--line-height) text-fg"><code>{draft}</code></pre> : <p>Preview unavailable for this stored draft format.</p>}
          <p className="text-meta text-fg-muted">Drafts are revalidated when creating the review’s fix branch.</p>
        </div>}
      </div>
    </details>
  );
}
