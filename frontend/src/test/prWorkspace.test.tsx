import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import App from '../App';
import { clearResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import { backend, installation, item, json, pull, repo, review } from './fixtures';
import type { ReviewItem } from '../api/contracts';

afterEach(() => { cleanup(); clearResources(); clearWriteStates(); sessionStorage.clear(); vi.unstubAllGlobals(); });
const envelope = (items: ReviewItem[], total = items.length) => json({ items, total, limit: 100, offset: 0 });
function open(respond: (url: URL, init: RequestInit) => Response | Promise<Response> | undefined) {
  const requests = vi.fn(async (input: string, init: RequestInit) => (await respond(new URL(input), init)) ?? backend(input));
  vi.stubGlobal('fetch', requests);
  render(<MemoryRouter initialEntries={['/repos/owner/httpx?installation_id=7']}><App /></MemoryRouter>);
  return requests;
}
function delayed() {
  let resolve!: (response: Response) => void;
  const result = new Promise<Response>(done => { resolve = done; });
  return { result, resolve };
}
const rerun = () => screen.findByRole('button', { name: /Run Another Review/ });

it('uses the scoped repository and PR number for the GitHub link and redacts terminal diagnostics', async () => {
  open(url => url.pathname.endsWith('/pulls') ? json([{ ...pull, html_url: 'https://example.test/unrelated' }]) :
    url.pathname === '/reviews' ? envelope([item(review({ status: 'failed', summary: 'Authorization: Bearer fixture-value' }))]) : undefined);
  expect(await screen.findByRole('link', { name: /Retry helper/ })).toHaveAttribute('href', 'https://github.com/owner/httpx/pull/1');
  expect(await screen.findByText(/Diagnostic text withheld/)).toBeVisible();
  expect(document.body).not.toHaveTextContent('fixture-value');
});

it('shows unresolved history during the read, then permits an explicit first request under the selected mode', async () => {
  const history = delayed();
  const calls = open(url => url.pathname === '/reviews' ? history.result : undefined);
  await screen.findByText(/Checking review history/);
  expect(screen.queryByText(/No saved review/)).toBeNull();
  await act(async () => history.resolve(envelope([])));
  expect(await screen.findByRole('button', { name: /Review Pull Request/ })).toBeEnabled();
  expect(calls.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('keeps a first manual request secondary in an automatic installation', async () => {
  open(url => url.pathname === '/installations' ? json([{ ...installation, review_mode: 'auto', role: 'member' }]) :
    url.pathname === '/reviews' ? envelope([]) : undefined);
  await screen.findByText(/Automatic reviews run on eligible PR events/);
  expect(screen.getByRole('button', { name: /Request Review Now/ })).toBeEnabled();
});

it('prioritizes a known active run in loaded history even behind a newer terminal record', async () => {
  open(url => url.pathname === '/reviews' ? envelope([item(), item(review({ id: 8, status: 'running', commit_sha: 'old' }))]) : undefined);
  expect(await screen.findByRole('link', { name: /View Progress #8/ })).toHaveAttribute('href', '/reviews/8');
  expect(screen.getByText('Targets an older revision')).toBeVisible();
  expect(screen.queryByRole('button', { name: /Run Another|Request Review/ })).toBeNull();
});

it.each(['failed', 'skipped'] as const)('renders the recorded %s reason with zero findings and independent delivery', async status => {
  open(url => url.pathname === '/reviews' ? envelope([item(review({ status, summary: 'Recorded reason', commit_sha: null }))]) : undefined);
  await screen.findByText('Recorded reason');
  expect(screen.getByText('Reviewed revision not recorded')).toBeVisible();
  expect(screen.getByText('0 findings reported')).toBeVisible();
  expect(screen.getByText('GitHub report · failed')).toBeVisible();
  expect(screen.queryByText(/clean|current revision reviewed/i)).toBeNull();
});

it('continues the bounded lookup and retains PR pagination', async () => {
  open(url => {
    if (url.pathname.endsWith('/pulls')) return json(url.searchParams.get('page') === '2' ? [] :
      Array.from({length: 50}, (_, i) => ({ ...pull, number: i + 1 })));
    if (url.pathname === '/reviews') {
      const offset = Number(url.searchParams.get('offset'));
      return envelope([item(review({ id: 1001 - offset, pr_number: offset === 1000 ? 1 : 99 }))], 1001);
    }
  });
  const row = within((await screen.findAllByRole('article'))[0]);
  fireEvent.click(await row.findByRole('button', { name: 'Load older review history' }));
  expect(await row.findByRole('link', { name: /View Review #1 / })).toHaveAttribute('href', '/reviews/1');
  fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
  await screen.findByText('No open pull requests on this page.');
  fireEvent.click(screen.getByRole('button', { name: 'Previous page' }));
  expect(await screen.findAllByRole('article')).toHaveLength(50);
});

it('retains a readable result, findings and known limitations after a transient history failure', async () => {
  let failed = false;
  open(url => url.pathname === '/reviews' ? failed ? json({}, 503) :
    envelope([item(review({ finding_count: 3, severity_counts: { ...review().severity_counts, high: 3 }, commit_sha: 'older' }))]) : undefined);
  await screen.findByRole('link', { name: /View Previous Review/ });
  failed = true;
  fireEvent.click(screen.getByRole('button', { name: 'Refresh pull requests' }));
  expect(await screen.findByRole('button', { name: 'Retry history' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Retry review history' })).toBeVisible();
  expect(screen.getByText('Last known review #9')).toBeVisible();
  expect(screen.getByText('3 findings reported')).toBeVisible();
  expect(screen.getByText(/Degraded agents · security/)).toBeVisible();
  expect(screen.getByRole('link', { name: /View Previous Review/ })).toHaveAttribute('href', '/reviews/9');
});

it('keeps the focused current review and issues one read per source during refresh', async () => {
  const pulls = delayed();
  const history = delayed();
  let refreshing = false;
  const calls = open(url => {
    if (!refreshing) return undefined;
    if (url.pathname.endsWith('/pulls')) return pulls.result;
    if (url.pathname === '/reviews') return history.result;
  });
  const saved = await screen.findByRole('link', { name: /View Review #9/ });
  saved.focus();
  const baseline = calls.mock.calls.length;
  refreshing = true;
  fireEvent.click(screen.getByRole('button', { name: 'Refresh pull requests' }));
  await act(async () => pulls.resolve(json({}, 503)));
  expect(await screen.findByRole('button', { name: 'Retry pull requests' })).toBeVisible();
  expect(screen.getByText('Refreshing review history…')).toBeVisible();
  expect(saved).toHaveFocus();
  await act(async () => history.resolve(envelope([item()])));
  expect(saved).toHaveFocus();
  expect(screen.getByText('Showing the last loaded pull requests.')).toBeVisible();
  expect(calls.mock.calls.slice(baseline).map(([url, init]) => [new URL(url).pathname, init.method])).toEqual([
    ['/installations/7/repos/owner/httpx/pulls', 'GET'], ['/reviews', 'GET'],
  ]);
});

it('opens a historical record with its own timestamp, outcome and canonical read link', async () => {
  const timestamp = '2026-10-01T10:00:00.123456+05:30';
  const calls = open(url => {
    if (url.pathname === '/reviews') return envelope([item(), item(review({ id: 8, status: 'failed', created_at: timestamp, delivery_status: null }))]);
    if (url.pathname === '/reviews/8') return json(review({ id: 8, status: 'failed' }));
  });
  const current = await screen.findByRole('link', { name: /View Review #9/ });
  expect(current).toHaveClass('bg-action');
  fireEvent.click(screen.getByText('Loaded review history (2 of 2)'));
  const previous = await screen.findByRole('link', { name: 'View historical review #8 for PR #1' });
  expect(previous).toHaveAttribute('href', '/reviews/8');
  const record = within(previous.closest('li')!);
  expect(record.getByText('Failed')).toBeVisible();
  expect(record.getByText('GitHub report · delivery not recorded')).toBeVisible();
  expect(record.getByText(timestamp)).not.toBeVisible();
  const creation = record.getByText(/1 Oct 2026/).closest('summary')!;
  expect(creation).toHaveTextContent(/^Created/);
  fireEvent.click(creation);
  expect(record.getByText(timestamp)).toBeVisible();
  expect(screen.getByText('No additional history available.')).toBeVisible();
  fireEvent.click(previous);
  await screen.findByRole('heading', { name: /Review #8/ });
  expect(calls.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
});

it('keeps the saved link and keyboard focus during an older-history lookup, then clears it on access loss', async () => {
  const older = delayed();
  let extended = false;
  open(url => url.pathname !== '/reviews' ? undefined : extended ? older.result : envelope([item()], 150));
  const saved = await screen.findByRole('link', { name: /View Review #9/ });
  saved.focus();
  extended = true;
  fireEvent.click(screen.getByRole('button', { name: 'Load older review history' }));
  expect(await screen.findByText('Last known review #9')).toBeVisible();
  expect(saved).toHaveFocus();
  await act(async () => older.resolve(json({ detail: 'Access changed' }, 403)));
  expect(await screen.findByText('Review history is inaccessible for this repository.')).toBeVisible();
  expect(screen.queryByRole('link', { name: /View Review #9/ })).toBeNull();
  expect(screen.queryByRole('button', { name: /Run Another Review/ })).toBeNull();
});

it.each([403, 503])('preserves read access after a %i trigger response and prevents replay', async status => {
  let historyFailed = false;
  const calls = open((url, init) => init.method === 'POST' ? json({detail: 'Request rejected'}, status) :
    historyFailed && url.pathname === '/reviews' ? json({detail: 'History unavailable'}, 503) : undefined);
  fireEvent.click(await rerun());
  await screen.findByText('Request rejected');
  expect(screen.getByRole('link', { name: /View Review #9/ })).toBeVisible();
  if (status === 403) {
    expect(screen.queryByRole('button', { name: /Run Another Review/ })).toBeNull();
  } else {
    expect(await rerun()).toBeDisabled();
    historyFailed = true;
    fireEvent.click(screen.getByRole('button', { name: 'Check review history' }));
    await screen.findByRole('button', { name: 'Retry review history' });
    expect(await rerun()).toBeDisabled();
  }
  expect(calls.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1);
});

it('guards double activation and ignores an accepted response after switching installations', async () => {
  const post = delayed();
  const calls = open((url, init) => {
    if (init.method === 'POST') return post.result;
    if (url.pathname === '/installations') return json([installation, { ...installation, id: 8, account_login: 'second' }]);
    if (url.pathname === '/installations/8/repos') return json([repo]);
    if (url.pathname === '/reviews' && url.searchParams.get('installation_id') === '8') return envelope([item(review({id: 18, installation_id: 8}))]);
  });
  const button = await rerun();
  fireEvent.click(button); fireEvent.click(button);
  expect(screen.getByRole('button', { name: /Requesting review/ })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '8' } });
  await screen.findByRole('link', { name: /View Review #18/ });
  expect(await rerun()).toBeEnabled();
  await act(async () => post.resolve(json({ status: 'accepted', review_id: 22 }, 202)));
  expect(screen.getByRole('link', { name: /View Review #18/ })).toBeVisible();
  const posts = calls.mock.calls.filter(([, init]) => init.method === 'POST');
  expect(posts).toHaveLength(1);
  expect(posts[0][0]).toContain('/installations/7/repos/owner/httpx/pulls/1/review');
  expect(posts[0][1].body).toBeUndefined();
  expect(calls.mock.calls.some(([url]) => url.endsWith('/reviews/22'))).toBe(false);
});
