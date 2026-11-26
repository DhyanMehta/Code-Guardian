import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { ContractError, parseTrends, type TrendPoint } from '../api/contracts';
import { clearResources } from '../api/resources';
import { AnalyticsTab } from '../components/dashboard/AnalyticsTab';
import { json, trends } from './fixtures';

afterEach(() => { cleanup(); clearResources(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const tab = (scope = 'user:7:owner/httpx', installation = 7, repo = 'owner/httpx') =>
  <MemoryRouter><AnalyticsTab scope={scope} installation={installation} repo={repo} /></MemoryRouter>;

function sample(overrides: Partial<TrendPoint>[]) {
  const points = overrides.map((changes, i) => ({ ...trends.points[0], review_id: i + 1, ...changes }));
  return { ...trends, range: { ...trends.range, review_count: points.length }, points, totals: { ...trends.totals,
    reviews: points.length, completed: points.filter(p => p.status === 'completed').length,
    failed: points.filter(p => p.status === 'failed').length, skipped: points.filter(p => p.status === 'skipped').length,
    coverage_recorded_reviews: points.filter(p => p.coverage_recorded).length,
    coverage_complete_reviews: points.filter(p => p.coverage_complete).length,
    reviews_with_coverage_gap: points.filter(p => !p.coverage_complete).length,
  } };
}
function mockRead(data: unknown) {
  const read = vi.fn((_url: string, _options?: RequestInit) => Promise.resolve(json(data)));
  vi.stubGlobal('fetch', read);
  return read;
}
const metric = (label: string) => screen.getAllByText(label, { selector: 'dt' })[0].nextElementSibling;

it('keeps sample, terminal and active outcomes, overlapping coverage counts and decisions distinct', async () => {
  const data = sample([{coverage_recorded:true, coverage_complete:true, degraded_agents:[], unrecorded_agents:[]},
    {coverage_recorded:true, unrecorded_agents:[]}, {status:'failed'}, {status:'pending'}, {status:'running'}, {status:'skipped'}]);
  data.totals.autofix = { created: 3, approved: 1, rejected: 1 };
  data.totals.findings = 13;
  data.totals.severity_counts = { ...data.totals.severity_counts, high: 4 };
  mockRead(data); render(tab());
  await screen.findByText('Latest 6 of up to 50 records');
  for (const [label, value] of Object.entries({
    'Review records':'6', 'Completed reviews':'2','Reported findings':'13', 'Full execution coverage records':'2 of 6',
    Completed:'2', Failed:'1', Skipped:'1', Queued:'1', Running:'1', 'Confirmed complete':'1',
    'Full records, coverage limited':'1','Missing full records':'4','Degraded or failed specialist outcome':'5',
    'All reviews without confirmed complete coverage':'5','Reviews with activity':'3','Approved decisions':'1','Rejected decisions':'1',
  })) expect(metric(label)).toHaveTextContent(value);
  expect(screen.getByText('High').closest('dt')?.nextElementSibling).toHaveTextContent('4');
  expect(screen.getByText('Unknown').closest('dt')?.nextElementSibling).toHaveTextContent('0');
  expect(screen.queryByText(/merged|deployed|successful fixes/i)).toBeNull();
});

it('places measured zero on the baseline, skips non-observations and preserves server order and exact values', async () => {
  const sameTime = '2026-01-01T10:00:00.123456+05:30';
  const data = sample([{review_id:42, created_at:sameTime}, {status:'running'}, {status:'pending'}, {status:'skipped'},
    {status:'failed'}, {status:'failed', total_findings:1, weighted_index:5}, {review_id:13, weighted_index:10, created_at:sameTime}]);
  mockRead(data); const {container} = render(tab()); await screen.findByRole('table');
  const marks = Array.from(container.querySelectorAll<HTMLElement>('[data-review]'));
  expect(marks.map(m => [m.dataset.review, m.style.bottom])).toEqual([['42','0%'], ['6','50%'], ['13','100%']]);
  expect(screen.getByText(/Weights per reported finding/)).toHaveTextContent('critical 10 · high 5 · medium 2 · low 1 · info 0 · unknown 0');
  const rows = screen.getAllByRole('row').slice(1);
  expect(rows.map(r => within(r).getByRole('link').getAttribute('href'))).toEqual(data.points.map(p => '/reviews/'+p.review_id));
  expect(screen.getAllByText('No plotted observation')).toHaveLength(4);
  fireEvent.click(rows[0].querySelector('summary')!);
  expect(within(rows[0]).getByText(sameTime)).toBeVisible();
  expect(within(rows[6]).getAllByRole('cell')[2]).toHaveTextContent('10');
});

it.each([0, 1])('handles %i records and zero severity buckets without invalid geometry', async count => {
  mockRead(sample(Array.from({length:count}, () => ({})))); const {container} = render(tab());
  await screen.findByText(`Latest ${count} of up to 50 records`);
  expect(screen.getByText('Every severity bucket has zero reported occurrences.')).toBeVisible();
  expect(container.innerHTML).not.toMatch(/NaN|Infinity/);
  expect(container.querySelectorAll('[data-review]')).toHaveLength(count);
  if (!count) expect(screen.getByText('No review history yet.')).toBeVisible();
});
it('retains malformed source dates for inspection and rejects missing severity or unfamiliar statuses', async () => {
  const data = sample([{created_at:'2026-01-01T10:00:00',degraded_agents:['long-specialist-identifier'.repeat(12)]}]);
  mockRead(data);render(tab()); const record = await screen.findByRole('rowheader');
  expect(record).toHaveTextContent('Time unavailable');
  fireEvent.click(record.querySelector('summary')!);expect(within(record).getByText(data.points[0].created_at!)).toBeVisible();
  expect(() => parseTrends({...data,totals:{...data.totals,severity_counts:{high:2}}})).toThrow(ContractError);
  expect(() => parseTrends({...data,points:[{...data.points[0],status:'other'}]})).toThrow(ContractError);
});
it('uses one scoped GET, retains focus on refresh and follows a canonical link without issuing writes or detail prefetches', async () => {
  const read=mockRead(trends);
  render(<MemoryRouter><Routes><Route path="/" element={<AnalyticsTab scope="a" installation={7} repo="owner/httpx"/>}/><Route path="/reviews/9" element={<p>Saved review destination</p>}/></Routes></MemoryRouter>);
  const link=await screen.findByRole('link',{name:'View review #9 for PR #1'});
  link.focus(); fireEvent.click(screen.getByRole('button',{name:'Refresh analytics'}));
  await waitFor(()=>expect(screen.getByRole('button',{name:'Refresh analytics'})).not.toHaveAttribute('aria-busy','true'));
  expect(link).toHaveFocus();fireEvent.click(link);expect(await screen.findByText('Saved review destination')).toBeVisible();
  expect(read).toHaveBeenCalledTimes(2);
  for(const [url,opts] of read.mock.calls) {
    expect(new URL(url).pathname+new URL(url).search).toBe('/metrics/trends?installation_id=7&repo=owner%2Fhttpx&limit=50');
    expect(opts?.method).toBe('GET');
  }
});
it('ignores delayed responses after switching both installation and repository', async () => {
  let finish!: (response: Response) => void;
  const read=mockRead(sample([{review_id:200}])).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
  const view=render(tab()); expect(screen.getByRole('status')).toHaveTextContent('Loading analytics');
  view.rerender(tab('user:8:other/repo',8,'other/repo'));
  await screen.findByRole('link',{name:/View review #200/});
  await act(async()=>finish(json(sample([{review_id:999}]))));
  expect(screen.queryByRole('link',{name:/#999/})).toBeNull();expect(read.mock.calls[1][0]).toContain('installation_id=8&repo=other%2Frepo');
});
it('clears cached metrics on permission loss and exposes recovery', async () => {
  const read=mockRead(trends);render(tab());await screen.findByRole('table');
  read.mockImplementation(()=>Promise.resolve(json({detail:'Access denied'},403)));
  fireEvent.click(screen.getByRole('button',{name:'Refresh analytics'}));expect(await screen.findByRole('alert')).toHaveTextContent('Access denied');
  expect(screen.queryByRole('table')).toBeNull();expect(screen.getByRole('button',{name:'Retry analytics'})).toBeVisible();
});
it('retains the sample through transport retries, then reports stale and offline states', async () => {
  const read=mockRead(trends);render(tab());await screen.findByRole('table');
  vi.useFakeTimers();
  try {
    read.mockImplementation(()=>Promise.resolve(json({detail:'Temporarily unavailable'},503)));
    fireEvent.click(screen.getByRole('button',{name:'Refresh analytics'}));
    await act(async()=>{await vi.advanceTimersByTimeAsync(3500);});
    expect(screen.getByRole('alert')).toHaveTextContent('Showing the last loaded analytics');
    vi.spyOn(navigator,'onLine','get').mockReturnValue(false);
    act(()=>window.dispatchEvent(new Event('offline')));
    expect(screen.getByText('Offline · updates paused')).toBeVisible();expect(screen.getByRole('table')).toBeVisible();
  } finally {vi.useRealTimers();}
});
