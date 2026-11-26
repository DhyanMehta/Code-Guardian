import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api/client';
import type { AgentCoverage, ReviewDetail } from '../api/contracts';
import { endpoints } from '../api/endpoints';
import { clearResources } from '../api/resources';
import { AgentOutcomeChart } from '../components/dashboard/AgentOutcomeChart';
import { AgentsTab } from '../components/dashboard/AgentsTab';
import { item, json, review } from './fixtures';

afterEach(() => { cleanup(); clearResources(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const coverage: AgentCoverage = {
  execution: 'completed', status: 'complete', enrichment: 'skipped',
  eligible_files: [], analyzed_files: [], excluded_files: [], batches: { completed: 0, failed: 0, reused: 0 },
  findings: 0, scanners: [],
};
const envelope = (records: ReviewDetail[], limit = 5, total = records.length) =>
  ({ items: records.map(item), total, limit, offset: 0 });
const page = (scope = 'i:7:owner/httpx', installation = 7, repo = 'owner/httpx') =>
  <MemoryRouter><AgentsTab scope={scope} installation={installation} repo={repo} /></MemoryRouter>;
const execution = () => screen.getByRole('region', { name: 'Execution history' });

it('counts terminal, active, unavailable and remaining records separately and identifies every specialist', () => {
  const degraded = review({ id: 71 });
  const failed = review({ id: 65, status: 'failed', agent_runs: [
    { ...degraded.agent_runs[0], outcome: 'failed', failure_reason: null },
  ] });
  const historical = review({ id: 61, status: 'skipped', agent_runs: [
    { ...degraded.agent_runs[0], outcome: 'unknown', recorded: false },
  ] });
  render(<MemoryRouter><AgentOutcomeChart reviews={[review({ status: 'running', agent_runs: [] }), degraded, failed, historical]} unavailable={1} total={9} /></MemoryRouter>);
  expect(screen.getByText(/3 terminal reviews · 1 active · 1 unavailable · 4 outside this sample/)).toBeVisible();
  const specialists = screen.getAllByRole('article');
  expect(specialists.map(el => el.getAttribute('aria-label'))).toEqual(['Security Agent', 'Quality Agent', 'Test gaps Agent', 'Documentation Agent']);
  const security = within(specialists[0]);
  expect(security.getByText('0 of 3 recorded with outcome OK')).toBeVisible();
  for (const label of ['Degraded', 'Failed', 'Unrecorded']) {
    expect(security.getByText(label, { selector: 'dt' }).nextElementSibling).toHaveTextContent(/^1$/);
  }
  expect(security.getByRole('link')).toHaveAttribute('href', '/reviews/71#agents');
});

it('chooses the first issue in the server order, including partial coverage without fabricating a reason', () => {
  const result = review({ id: 8 });
  result.agent_runs[0] = { ...result.agent_runs[0], outcome: 'ok', failure_reason: null, coverage: { ...coverage, status: 'partial' } };
  render(<MemoryRouter><AgentOutcomeChart reviews={[result, review({ id: 90 })]} unavailable={0} total={2} /></MemoryRouter>);
  const security = within(screen.getByRole('article', { name: 'Security Agent' }));
  expect(security.getByText('Outcome OK · Partial coverage')).toBeVisible();
  expect(security.getByText('Reason not recorded')).toBeVisible();
  expect(security.getByRole('link')).toHaveAttribute('href', '/reviews/8#agents');
});

it.each([
  { name: 'empty history', records: [] },
  { name: 'active-only history', records: [review({ status: 'pending' })] },
])('handles $name without a terminal denominator', async ({ records }) => {
  vi.spyOn(endpoints, 'reviews').mockResolvedValue(envelope(records));
  vi.spyOn(endpoints, 'review').mockImplementation(async id => records.find(record => record.id === id)!);
  render(page());
  expect(await screen.findByText(new RegExp(`0 terminal reviews · ${records.length} active`))).toBeVisible();
  if (!records.length) expect(screen.getByText('No review history yet.')).toBeVisible();
});

it('uses one authorized five-detail read, discloses exact timestamps and evidence locally, and links to the saved review with zero writes', async () => {
  const timestamp = '2026-11-04T20:30:54.000121+05:30';
  const saved = review({ created_at: timestamp, finding_count: 1, agent_counts: { security: 1, quality: 0, test_gap: 0, documentation: 0 }, standards_version: 'v42' });
  saved.agent_runs = [
    { ...saved.agent_runs[0], outcome: 'degraded', coverage, failure_reason: 'Authorization: Bearer fixture-credential',
      scanner_statuses: [{ scanner: 'gitleaks', ok: true, finding_count: 5, error: null, error_type: null }],
      raw_findings: [{ scanner: 'gitleaks', fingerprint: 'f', rule_id: 'fixture-rule', file_path: 'example', line: 1, severity: 'high', message: 'sensitive match payload' }] },
    { ...saved.agent_runs[1], recorded: true, outcome: 'ok' },
    { ...saved.agent_runs[2], recorded: false, outcome: 'unknown' },
  ];
  const records = [saved, ...[8, 7, 6, 5].map(id => review({ id }))];
  const read = vi.fn((url: string, _options: RequestInit) => Promise.resolve(json(
    new URL(url).pathname === '/reviews' ? envelope(records, 5, 10) : records.find(record => url.endsWith('/'+record.id)),
  )));
  vi.stubGlobal('fetch', read);
  render(<MemoryRouter><Routes>
    <Route path="/" element={<AgentsTab scope="scope" installation={7} repo="owner/httpx" />} />
    <Route path="/reviews/9" element={<p>Saved review destination</p>} />
  </Routes></MemoryRouter>);
  const record = await screen.findByRole('article', { name: 'Review #9' });
  expect(within(record).getByText('1 finding reported · 1 of 4 specialist coverage records')).toBeVisible();
  expect(record).toHaveTextContent('Quality OK');
  expect(record).toHaveTextContent('Test gaps Unknown');
  expect(record).toHaveTextContent('Documentation Unrecorded');
  const [time, disclosure, scanners] = Array.from(record.querySelectorAll('summary'));
  fireEvent.click(time);
  expect(within(record).getByText(timestamp)).toBeVisible();
  fireEvent.click(disclosure);
  fireEvent.click(scanners);
  expect(within(record).getByText('gitleaks · Completed · 5 raw detections')).toBeVisible();
  expect(within(record).getByText(/Accepted findings are counted separately/)).toBeVisible();
  expect(within(record).getByText('Complete', { exact: true })).toBeVisible();
  expect(within(record).getByText('Standards version · v42')).toBeVisible();
  expect(screen.queryByText(/fixture-credential|sensitive match payload/)).toBeNull();
  expect(read).toHaveBeenCalledTimes(6);
  expect(read.mock.calls[0][0]).toContain('installation_id=7&repo=owner%2Fhttpx&limit=5&offset=0');
  expect(read.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
  fireEvent.click(screen.getByRole('link', { name: 'View Security issue in review #9' }));
  expect(screen.getByText('Saved review destination')).toBeVisible();
  expect(read).toHaveBeenCalledTimes(6);
});

it('keeps details open and focus on the continuation control while older evidence loads', async () => {
  const first = [9, 8, 7, 6, 5].map(id => review({ id }));
  const older = [4, 3].map(id => review({ id }));
  let resolveList!: (result: ReturnType<typeof envelope>) => void;
  const lists = vi.spyOn(endpoints, 'reviews').mockResolvedValueOnce(envelope(first, 5, 7))
    .mockImplementationOnce(() => new Promise(resolve => { resolveList = resolve; }));
  const details = vi.spyOn(endpoints, 'review').mockImplementation(async id => review({ id }));
  render(page());
  const row = await screen.findByRole('article', { name: 'Review #9' });
  const disclosure = row.querySelector(':scope > details > summary')!;
  fireEvent.click(disclosure);
  const more = screen.getByRole('button', { name: 'Load older reviews' });
  more.focus(); fireEvent.click(more);
  expect(screen.getByText('Loading older review details…')).toBeVisible();
  expect(disclosure.closest('details')).toHaveAttribute('open');
  await act(async () => resolveList(envelope([...first, ...older], 10)));
  expect((await within(execution()).findAllByRole('article')).map(el => el.getAttribute('aria-label'))).toEqual([...first, ...older].map(r => 'Review #'+r.id));
  expect(lists.mock.calls.map(call => call[3])).toEqual([5, 10]);
  expect(details).toHaveBeenCalledTimes(7);
  expect(screen.getByRole('button', { name: 'All available reviews loaded' })).toHaveFocus();
  expect(disclosure.closest('details')).toHaveAttribute('open');
});

it('separates partial detail failure and retries through the existing bounded read', async () => {
  const records = [review(), review({ id: 8 })];
  vi.spyOn(endpoints, 'reviews').mockResolvedValue(envelope(records));
  const read = vi.spyOn(endpoints, 'review').mockRejectedValueOnce(new ApiError(503, 'Detail temporarily unavailable'))
    .mockImplementation(async id => review({ id }));
  render(page());
  expect(await screen.findByText(/1 terminal reviews · 0 active · 1 unavailable/)).toBeVisible();
  expect(screen.getByText('Detail unavailable · Detail temporarily unavailable')).toBeVisible();
  expect(screen.getByRole('link', { name: 'View review #9 for PR #1' })).toHaveAttribute('href', '/reviews/9');
  const retry = screen.getByRole('button', { name: 'Retry unavailable details' });
  retry.focus(); fireEvent.click(retry);
  expect(await screen.findByRole('article', { name: 'Review #9' })).toBeVisible();
  expect(read.mock.calls.map(call => call[0])).toEqual([9, 8, 9]);
  expect(screen.getByRole('heading', { name: 'Execution history' })).toHaveFocus();
});

it('drops a late previous-scope detail even when the new scope uses the same record ID', async () => {
  let resolveOld!: (detail: ReviewDetail) => void;
  const old = review({ finding_count: 99 });
  vi.spyOn(endpoints, 'reviews').mockResolvedValue(envelope([review()]));
  const read = vi.spyOn(endpoints, 'review').mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; })).mockResolvedValue(review());
  const view = render(page());
  await waitFor(() => expect(read).toHaveBeenCalledTimes(1));
  expect(screen.getByText('Checking saved review details · 0 of 1 checked.')).toBeVisible();
  const signal = read.mock.calls[0][1];
  view.rerender(page('i:8:other/repo', 8, 'other/repo'));
  await screen.findByRole('article', { name: 'Review #9' });
  await act(async () => resolveOld(old));
  expect(signal.aborted).toBe(true);
  expect(screen.queryByText(/99 findings reported/)).toBeNull();
});

it('retains the loaded snapshot through a transient failure and offline, then clears it on access denial', async () => {
  const list = vi.spyOn(endpoints, 'reviews').mockResolvedValue(envelope([review()]));
  vi.spyOn(endpoints, 'review').mockResolvedValue(review());
  render(page());
  await screen.findByRole('article', { name: 'Review #9' });
  const refresh = screen.getByRole('button', { name: 'Refresh agent history' });
  list.mockRejectedValue(new ApiError(503, 'History temporarily unavailable'));
  fireEvent.click(refresh);
  expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last loaded agent history.');
  expect(screen.getByRole('article', { name: 'Review #9' })).toBeVisible();
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
  act(() => window.dispatchEvent(new Event('offline')));
  expect(screen.getByText('Offline · updates paused')).toBeVisible();
  list.mockRejectedValue(new ApiError(403, 'Access denied'));
  vi.useFakeTimers();
  try {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    act(() => window.dispatchEvent(new Event('online')));
    await act(async () => vi.advanceTimersByTimeAsync(11_000));
  } finally { vi.useRealTimers(); }
  expect(screen.getByRole('alert')).toHaveTextContent('Access denied');
  expect(screen.queryByRole('article', { name: 'Review #9' })).toBeNull();
});
