import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { clearResources } from '../api/resources';
import type { Finding, AgentCoverage } from '../api/contracts';
import { FindingsList } from '../components/reviews/FindingsList';
import { ReviewAgentResults } from '../components/reviews/ReviewAgentResults';
import { AgentRunCard } from '../components/reviews/ReviewPresentation';
import { backend, json, review } from './fixtures';

const findings: Finding[] = Array.from({length: 6}, (_, i) => ({
  id: i + 100, rank: i + 1, agent: i ? 'quality' : 'security', severity: i ? 'info' : 'unknown',
  title: `Finding title ${i}`, file_path: 'source/' + 'identifier_'.repeat(20) + '.ts', line: i + 1,
  detail: 'Recorded explanation', evidence: i ? { kind: i === 1 ? 'verified' : 'advisory', source_file: 'standards.md',
    cited_passage: 'Use typed inputs', symbol: 'entry', standards_version: 'snapshot-v3' } : null,
  fixable: i === 1, fix_data: i === 1 ? { test_code: '<script>alert(1)</script>' + 'x'.repeat(220) } : null,
}));
const props = { findings, total: findings.length, reviewId: 79, standardsVersion: 'review-version' };
const coverage: AgentCoverage = { execution: 'completed', status: 'complete', enrichment: 'skipped', eligible_files:['app.ts'],
  analyzed_files:['app.ts'], excluded_files:[{path:'docs.md',reason:'Non-source'}], batches:{completed:1,failed:0,reused:0},findings:1,scanners:[] };

afterEach(() => {
  cleanup(); clearResources(); vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

it('combines the filters, searches citations locally, retains rank order and resets through the keyboard-accessible button', () => {
  render(<FindingsList {...props} />);
  const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), {target:{value}});
  change('Filter findings by severity','info');
  change('Filter findings by agent','quality');
  change('Search findings','TYPED inputs');
  expect(screen.getByRole('status')).toHaveTextContent('Showing 5 of 6');
  expect([...document.querySelectorAll('details[id]')].map(e => e.id)).toEqual(['finding-101','finding-102','finding-103','finding-104','finding-105']);
  change('Search findings','no such evidence');
  expect(screen.getByText('No findings match these filters.')).toBeVisible();
  fireEvent.click(screen.getByRole('button',{name:'Clear filters'}));
  expect(screen.getByRole('searchbox')).toHaveFocus();
  expect(screen.getByRole('status')).toHaveTextContent('Showing 6 of 6');
  expect(within(document.getElementById('finding-100')!).getByText('Unknown')).toBeVisible();
});

it('clears conflicting filters once for an addressed fragment and preserves user focus and disclosure on refresh', () => {
  const {rerender} = render(<FindingsList {...props} />);
  const search = screen.getByRole('searchbox');
  fireEvent.change(search,{target:{value:'Finding title 1'}});
  function jump(hash: string) {
    act(() => {window.history.pushState(null,'',hash); window.dispatchEvent(new HashChangeEvent('hashchange'));});
  }
  jump('#finding-999');
  expect(search).toHaveValue('Finding title 1');
  jump('#finding-100');
  const target = document.getElementById('finding-100') as HTMLDetailsElement;
  expect(target).toHaveAttribute('open');
  expect(target.querySelector('summary')).toHaveFocus();
  expect(screen.getByRole('status')).toHaveTextContent('Filters cleared to show the linked finding.');
  fireEvent.click(target.querySelector('summary')!);
  search.focus();
  rerender(<FindingsList {...props} findings={[...findings]} />);
  expect(target).not.toHaveAttribute('open');
  expect(search).toHaveFocus();
});

it('discloses persisted rule evidence and historical version, and escapes code, paths and text', () => {
  render(<FindingsList {...props} findings={[findings[1],findings[2],{...findings[0],agent:'quality'}]} />);
  const entry = within(document.getElementById('finding-101')!);
  expect(entry.getAllByText('Verified rule')[0]).toBeVisible();
  for (const text of ['standards.md','snapshot-v3','Use typed inputs','entry']) expect(entry.getByText(text)).toBeVisible();
  expect(entry.getByText(findings[1].file_path!+':2')).toBeVisible();
  expect(entry.getByLabelText('Draft code')).toHaveTextContent('<script>alert(1)</script>');
  expect(document.querySelector('details script')).toBeNull();
  expect(within(document.getElementById('finding-102')!).getAllByText('Advisory')[0]).toBeVisible();
  expect(within(document.getElementById('finding-100')!).getByText('Unrecorded or unrecognized')).toBeVisible();
});

it('distinguishes zero reported findings from unavailable individual records', () => {
  const {rerender} = render(<FindingsList {...props} total={0} findings={[]} />);
  expect(screen.getByText(/No findings reported/)).toBeVisible();
  rerender(<FindingsList {...props} findings={[]} />);
  expect(screen.getByText(/reports 6 findings.*unavailable/)).toBeVisible();
});

it('uses only the loaded review for filtering, disclosure and clear', async () => {
  const fetch = vi.fn(async (url:string,_init?:RequestInit) => new URL(url).pathname === '/reviews/9' ? json(review({ findings, finding_count:6 })) : backend(url));
  vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter initialEntries={['/reviews/9']}><App /></MemoryRouter>);
  await screen.findByText('Finding title 0');
  await within(document.querySelector('main header')!).findByText('Matches current PR head');
  const requests = fetch.mock.calls.length;
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'standards.md'}});
  fireEvent.click(screen.getByRole('button',{name:'Clear filters'}));
  fireEvent.click(document.querySelector('#finding-101 summary')!);
  expect(screen.getByRole('heading',{name:'6 findings reported'})).toBeVisible();
  expect(fetch).toHaveBeenCalledTimes(requests);
  expect(fetch.mock.calls.every(([,init])=>init?.method==='GET')).toBe(true);
});

it.each([
  ['ok',null,'OK','Not recorded','Not recorded','Not recorded'],
  ['ok',coverage,'OK','Completed','Complete','Skipped'],
  ['ok',{...coverage,status:'partial'},'OK','Completed','Partial','Skipped'],
  ['degraded',{...coverage,status:'partial',enrichment:'failed'},'Degraded','Completed','Partial','Failed'],
  ['failed',{...coverage,execution:'failed',status:'unknown'},'Failed','Failed','Unknown','Skipped'],
  ['ok',{...coverage,status:'not_applicable'},'OK','Completed','Not applicable','Skipped'],
  ['unknown',null,'Unknown','Not recorded','Not recorded','Not recorded'],
] as const)('distinguishes %s outcome and %j coverage', (outcome,c,label,execution,status,enrichment) => {
  const r = review();
  r.agent_runs = [{...r.agent_runs[0], outcome, recorded:outcome!=='unknown', coverage:c}];
  render(<ReviewAgentResults review={r} />);
  const card = screen.getByRole('article',{name:'Security'});
  const field = (name:string) => within(card).getByText(name).nextElementSibling;
  expect(field('Recorded outcome')).toHaveTextContent(label);
  expect(field('Execution')).toHaveTextContent(execution);
  expect(field('Coverage')).toHaveTextContent(status);
  expect(field('Draft enrichment')).toHaveTextContent(enrichment);
  expect(within(card).getByText('Scanner unavailable')).toBeVisible();
  expect(within(screen.getByRole('article',{name:'Quality'})).getByText('Recorded outcome').nextElementSibling).toHaveTextContent('Not recorded');
});

it('keeps raw scanner detections apart from accepted counts and withholds secret-scanner messages', () => {
  const r = review(); r.agent_counts.security=1;
  r.agent_runs[0]={...r.agent_runs[0],coverage, finding_count:1,
    scanner_statuses:[{scanner:'gitleaks',ok:true,finding_count:2,error:null,error_type:null}],
    raw_findings:[1,2].map(i=>({scanner:'gitleaks',fingerprint:String(i),rule_id:'fixture-rule',severity:'high',file_path:'app.ts',line:i,message:'private fixture match'}))};
  render(<ReviewAgentResults review={r} />);
  const card = within(screen.getByRole('article',{name:'Security'}));
  expect(card.getByText('Accepted findings').nextElementSibling).toHaveTextContent('1');
  fireEvent.click(card.getByText('Technical evidence'));
  expect(card.getByText('docs.md — Non-source')).toBeVisible();
  fireEvent.click(card.getByText('Raw scanner detections (2)'));
  expect(card.getByText('app.ts:2')).toBeVisible();
  expect(card.queryByText('private fixture match')).toBeNull();
});

it('redacts sensitive diagnostics even inside collapsed disclosures while retaining safe scanner evidence', () => {
  const r = review();
  const secret = 'Authorization: Bearer fixture-only';
  r.agent_runs[0] = { ...r.agent_runs[0], failure_reason: secret, notes: [secret],
    scanner_statuses: [{ scanner: 'bandit', ok: false, finding_count: 2, error: secret, error_type: secret }],
    raw_findings: ['bandit', 'semgrep', ' Gitleaks '].map((scanner, i) => ({
      scanner, fingerprint: String(i), rule_id: 'fixture-rule', severity: 'high', file_path: 'app.ts', line: i,
      message: [secret, 'Recorded rule explanation', 'private match excerpt'][i],
    })) };
  render(<ReviewAgentResults review={r} />);
  render(<AgentRunCard run={r.agent_runs[0]} />);
  expect(document.body).not.toHaveTextContent(/fixture-only|private match excerpt/);
  expect(document.body).toHaveTextContent('Recorded rule explanation');
  expect(document.body).toHaveTextContent('Diagnostic text withheld');
});
