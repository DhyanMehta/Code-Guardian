import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';
import { parseReview, type AgentCoverage, type ReviewDetail } from '../api/contracts';
import { clearResources } from '../api/resources';
import { ReviewOverview } from '../components/reviews/ReviewOverview';
import { backend, json, review } from './fixtures';

afterEach(() => { cleanup(); clearResources(); vi.unstubAllGlobals(); sessionStorage.clear(); });

function openReview(r: ReviewDetail, status = 200) {
  const fetch = vi.fn(async (input: string, _options?: RequestInit) => {
    const path = new URL(input).pathname;
    if (path === '/reviews/9') return json(status === 200 ? r : { detail: 'Access denied' }, status);
    if (path === '/health/ready') return json({ status: 'ready', checks: { worker: 'ok' } });
    return backend(input);
  });
  vi.stubGlobal('fetch', fetch);
  render(<MemoryRouter initialEntries={['/reviews/9']}><App /></MemoryRouter>);
  return fetch;
}

it('shares one scoped head read with fix controls, keeps section jumps local and loads the saved report on demand', async () => {
  const fetch = openReview(review({ fixable_count: 2 }));
  const nav = await screen.findByRole('navigation', { name: 'Review sections' });
  const links = within(nav).getAllByRole('link');
  expect(links.map(link => link.getAttribute('href'))).toEqual(['#overview', '#findings', '#agents', '#execution', '#delivery', '#autofix']);
  for (const link of links) expect(document.getElementById(link.getAttribute('href')!.slice(1))).toBeInTheDocument();
  await within(document.querySelector('main header')!).findByText('Matches current PR head');
  expect(fetch.mock.calls.filter(([url]) => url.includes('/pulls?'))).toHaveLength(1);
  expect(fetch.mock.calls.filter(([url]) => new URL(url).pathname === '/reviews/9')).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/report'))).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: 'Saved / rendered report' }));
  expect(await screen.findByText('# Saved report')).toBeInTheDocument();
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
});

it.each(['pending', 'running'] as const)('leads with progress for %s and omits final sections', async status => {
  openReview(review({ status }));
  const overview = await screen.findByRole('region', { name: 'Overview' });
  const progress = screen.getByText(/Review queued\.|Review running\./);
  expect(progress.compareDocumentPosition(overview) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(within(overview).queryByText(/findings reported/i)).toBeNull();
  expect(screen.queryByRole('link', { name: 'Agent results' })).toBeNull();
  expect(screen.queryByRole('link', { name: 'Auto-fix decisions' })).toBeNull();
});

it('withholds credential-bearing text in a saved completed analysis summary', () => {
  render(<ReviewOverview review={review({ summary: 'Authorization: Bearer fixture-only' })} active={false} />);
  expect(screen.getByText(/Diagnostic text withheld/)).toBeInTheDocument();
  expect(document.body).not.toHaveTextContent('fixture-only');
});

it.each(['failed', 'skipped'] as const)('shows the recorded %s reason alongside the actual count and separate delivery state', status => {
  render(<ReviewOverview review={review({ status, summary: 'Recorded terminal reason' })} active={false} />);
  expect(screen.getByText('Recorded terminal reason')).toBeVisible();
  expect(screen.getByRole('heading', { name: '0 findings reported' })).toBeVisible();
  expect(screen.getByText('GitHub delivery')).toHaveTextContent('Failed');
  expect(screen.getByText('Coverage not recorded')).toBeVisible();
  expect(screen.getByText(/Degraded outcome/)).toBeVisible();
});

const coverage: AgentCoverage = { status: 'complete', execution: 'completed', enrichment: 'skipped', eligible_files: [], analyzed_files: [],
  excluded_files: [], batches: { completed: 0, failed: 0, reused: 0 }, findings: 0, scanners: [] };
it('preserves partial, unknown, not-applicable and execution failure evidence separately from outcome', () => {
  const r = review();
  r.agent_runs = r.agent_runs.map(run => ({ ...run, recorded: true, outcome: 'ok', coverage }));
  const { rerender } = render(<ReviewOverview review={r} active={false} />);
  expect(screen.getByText('Complete coverage recorded')).toBeVisible();
  const states = ['partial', 'unknown', 'not_applicable', 'complete'] as const;
  r.agent_runs = r.agent_runs.map((run, i) => ({ ...run, outcome: i === 1 ? 'failed' : 'ok',
    coverage: { ...coverage, status: states[i], execution: i === 1 ? 'failed' : 'completed' } }));
  rerender(<ReviewOverview review={r} active={false} />);
  expect(screen.getByText(/Coverage partial/)).toBeVisible();
  expect(screen.getByText(/Failed outcome · Execution failed · Coverage unknown/)).toBeVisible();
  expect(screen.getByText(/Coverage not applicable/)).toBeVisible();
  expect(screen.queryByText('Complete coverage recorded')).toBeNull();
});

it.each([[null, 'Reviewed revision not recorded'], ['old', 'Outdated review · PR head changed']] as const)(
  'keeps nullable or outdated revision %s truthful', async (sha, message) => {
    openReview(review({ commit_sha: sha }));
    expect(await screen.findByText(message)).toBeInTheDocument();
  });

it('keeps exact source offsets and fractions available with a named event disclosure', async () => {
  const stamp = '2026-10-06T22:04:30.577029+05:30';
  openReview(review({ started_at: stamp }));
  const disclosure = (await screen.findByText('Execution started')).closest('summary')!;
  fireEvent.click(disclosure);
  expect(within(disclosure.parentElement!).getByText(stamp)).toBeVisible();
});

it('opens the addressed finding when the review arrives after a direct fragment visit', async () => {
  const original = window.location.href;
  window.history.replaceState(null, '', '/reviews/9#finding-6');
  try {
    const findings = Array.from({ length: 6 }, (_, i) => ({
      id: i + 1, agent: 'quality' as const, severity: 'low' as const, title: `Fixture finding ${i + 1}`,
      detail: null, file_path: null, line: null, fixable: false, fix_data: null, evidence: null, rank: i,
    }));
    openReview(review({ finding_count: 6, findings }));
    await screen.findByText('Fixture finding 6');
    expect(document.getElementById('finding-6')).toHaveAttribute('open');
    expect(document.getElementById('finding-1')).not.toHaveAttribute('open');
  } finally {
    window.history.replaceState(null, '', original);
  }
});

it('rejects absent severity fields before they can be rendered as zero', () => {
  expect(() => parseReview({ ...review(), severity_counts: { low: 0 } })).toThrow(/severity_counts/);
});

it('withholds review evidence after denied access', async () => {
  openReview(review(), 403);
  expect(await screen.findByRole('alert')).toBeVisible();
  expect(screen.queryByRole('navigation', { name: 'Review sections' })).toBeNull();
});

it('retains the authorized snapshot and keyboard focus after a failed refresh', async () => {
  const fetch = openReview(review());
  await screen.findByRole('heading', { name: /Review #9/ });
  const refresh = screen.getByRole('button', { name: 'Refresh review' });
  fetch.mockImplementation(async input => input.endsWith('/reviews/9') ? json({ detail: 'Unavailable' }, 503) : backend(input));
  refresh.focus();
  fireEvent.click(refresh);
  expect(await screen.findByRole('alert')).toHaveTextContent('Updates delayed');
  expect(screen.getByRole('region', { name: 'Overview' })).toBeVisible();
  expect(refresh).toHaveFocus();
});
