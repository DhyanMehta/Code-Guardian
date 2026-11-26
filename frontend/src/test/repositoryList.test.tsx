import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { ApiError } from '../api/client';
import { endpoints } from '../api/endpoints';
import { clearResources } from '../api/resources';
import { backend, installation, json, repo } from './fixtures';

const second = { ...installation, id: 8, account_login: 'another', review_mode: 'auto' as const };
const longName = 'another/' + 'long_repository_name_'.repeat(5);
const anotherRepo = { ...repo, id: 6, full_name: longName, html_url: 'https://github.com/' + longName, private: true, open_issues_count: 0 };

function open(path = '/repos?installation_id=7') {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

function mockReads(read: (url: URL, options?: RequestInit) => Response | Promise<Response> | undefined) {
  const fetch = vi.fn(async (url: string, options?: RequestInit) => read(new URL(url), options) ?? backend(url));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  cleanup();
  clearResources();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('Connected Repositories', () => {
  it('renders full identity, scoped primary links and verified secondary GitHub links', async () => {
    const fetch = mockReads(url => url.pathname === '/installations/7/repos' ? json([
      repo,
      anotherRepo,
      { ...repo, id: 9, full_name: 'owner/missing-url', html_url: '', default_branch: '' },
      { ...repo, id: 10, full_name: 'owner/spoof', html_url: 'https://github.com.example.com/owner/spoof' },
      { ...repo, id: 11, full_name: 'owner/mismatch', html_url: 'https://github.com/owner/httpx' },
    ]) : undefined);
    open();
    const list = await screen.findByRole('list', { name: 'Repositories' });
    const rows = within(list).getAllByRole('article');
    expect(rows).toHaveLength(5);
    const first = within(rows[0]);
    expect(first.getByRole('heading', { name: 'owner/httpx' })).toBeVisible();
    expect(first.getByText(/open issues and pull requests/)).toHaveTextContent('1 open issues and pull requests');
    expect(first.getByText('Public')).toBeVisible();
    expect(first.getByText('main')).toBeVisible();
    const workspace = first.getByRole('link', { name: 'View pull requests for owner/httpx' });
    expect(workspace).toHaveAttribute('href', '/repos/owner/httpx?installation_id=7');
    const github = first.getByRole('link', { name: 'Open owner/httpx on GitHub (opens in a new tab)' });
    expect(github).toHaveAttribute('href', repo.html_url);
    expect(github).toHaveAttribute('target', '_blank');
    expect(github).toHaveAttribute('rel', 'noopener noreferrer');
    expect(within(rows[1]).getByRole('heading', { name: longName })).toBeVisible();
    expect(within(rows[1]).getByText('Private')).toBeVisible();
    expect(within(rows[2]).queryByText('Default branch')).not.toBeInTheDocument();
    rows.forEach(row => {
      expect(within(row).getAllByRole('link', { name: /^View pull requests for / })).toHaveLength(1);
      expect(within(row).getAllByRole('link').filter(link => link.getAttribute('href')?.startsWith('/repos/'))).toHaveLength(1);
    });
    rows.slice(2).forEach(row => expect(within(row).getAllByRole('link')).toHaveLength(1));
    expect(fetch.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/auth/me', '/installations', '/installations/7/repos']);
  });

  it('filters by case-insensitive full name and clears from either recovery control with focus', async () => {
    mockReads(url => url.pathname === '/installations/7/repos' ? json([repo, anotherRepo]) : undefined);
    open();
    await screen.findByText('2 repositories');
    const search = screen.getByRole('searchbox', { name: 'Search repositories' });
    fireEvent.change(search, { target: { value: '  HTTPX  ' } });
    expect(screen.getByRole('status')).toHaveTextContent('1 of 2 repositories');
    expect(screen.queryByRole('heading', { name: longName })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Clear repository search' }));
    expect(search).toHaveFocus();
    expect(search).toHaveValue('');
    expect(screen.getByRole('heading', { name: longName })).toBeVisible();
    fireEvent.change(search, { target: { value: 'no-match' } });
    expect(screen.getByRole('status')).toHaveTextContent('0 of 2 repositories');
    expect(screen.getByRole('heading', { name: 'No repositories match your search' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Clear search' }));
    expect(search).toHaveFocus();
    expect(screen.getByRole('status')).toHaveTextContent('2 repositories');
  });

  it('clears the filter and discards an old refresh when switching installations', async () => {
    let resolveOld!: (response: Response) => void;
    const pending = new Promise<Response>(resolve => { resolveOld = resolve; });
    let resolveNew!: (response: Response) => void;
    const nextScope = new Promise<Response>(resolve => { resolveNew = resolve; });
    let oldSignal: AbortSignal | null | undefined;
    let firstRead = true;
    const requests = mockReads((url, options) => {
      if (url.pathname === '/installations') return json([installation, second]);
      if (url.pathname === '/installations/8/repos') return nextScope;
      if (url.pathname === '/installations/7/repos') {
        if (firstRead) { firstRead = false; return json([repo]); }
        oldSignal = options?.signal;
        return pending;
      }
    });
    open();
    await screen.findByRole('heading', { name: 'owner/httpx' });
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'HTTPX' } });
    fireEvent.click(screen.getByRole('button', { name: 'Refresh repositories' }));
    await waitFor(() => expect(oldSignal).toBeDefined());
    expect(screen.getByRole('searchbox')).toHaveValue('HTTPX');
    expect(screen.getByText('1 of 1 repositories')).toBeVisible();
    const picker = screen.getByRole('combobox', { name: 'Installation' });
    fireEvent.change(picker, { target: { value: '8' } });
    expect(oldSignal?.aborted).toBe(true);
    expect(screen.queryByRole('heading', { name: 'owner/httpx' })).not.toBeInTheDocument();
    expect(screen.getByRole('searchbox')).toHaveValue('');
    expect(screen.getByText('Loading repositories…')).toBeVisible();
    expect(screen.queryByText(/Last successful fetch/)).not.toBeInTheDocument();
    await act(async () => resolveNew(json([anotherRepo])));
    expect(await screen.findByRole('heading', { name: longName })).toBeVisible();
    await act(async () => resolveOld(json([repo])));
    expect(screen.queryByRole('heading', { name: 'owner/httpx' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Installation Settings' })).toHaveAttribute('href', '/settings/installation?installation_id=8');
    fireEvent.change(picker, { target: { value: '7' } });
    expect(screen.getByRole('searchbox')).toHaveValue('');
    expect(requests.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
  });

  it.each([
    ['999', /This installation is unavailable/],
    ['8', /This installation is suspended/],
  ])('gates repository reads for unavailable installation %s', async (id, message) => {
    sessionStorage.setItem('codeguardian:installation:1', '7');
    const fetch = mockReads(url => url.pathname === '/installations' ? json([installation, { ...second, suspended: true }]) : undefined);
    open('/repos?installation_id=' + id);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Installation Settings' })).not.toBeInTheDocument();
    expect(fetch.mock.calls.map(([url]) => new URL(url).pathname)).toEqual(['/auth/me', '/installations']);
  });

  it('keeps Installation Settings reachable when the repository list is empty', async () => {
    mockReads(url => url.pathname === '/installations/7/repos' ? json([]) : undefined);
    open();
    expect(await screen.findByRole('heading', { name: 'No accessible repositories' })).toBeVisible();
    fireEvent.click(screen.getByRole('link', { name: 'Installation Settings' }));
    expect(await screen.findByText('Default standards')).toBeVisible();
  });

  it('shows loading then a distinct first-read failure with retry', async () => {
    let resolve!: (response: Response) => void;
    const pending = new Promise<Response>(done => { resolve = done; });
    mockReads(url => url.pathname === '/installations/7/repos' ? pending : undefined);
    open();
    expect(await screen.findByText('Loading repositories…')).toBeVisible();
    await act(async () => resolve(json({ detail: 'Repository access unavailable' }, 403)));
    expect(await screen.findByRole('alert')).toHaveTextContent('Repository access unavailable');
    expect(screen.getByRole('button', { name: 'Retry repositories' })).toBeEnabled();
    expect(screen.queryByRole('heading', { name: /No accessible repositories/ })).not.toBeInTheDocument();
  });

  it('shows stale cached results and retains the count announcement after a transient read failure', async () => {
    mockReads(() => undefined);
    vi.spyOn(endpoints, 'repos').mockResolvedValueOnce([repo]).mockRejectedValue(new ApiError(503, 'Read unavailable'));
    open();
    await screen.findByRole('heading', { name: 'owner/httpx' });
    const status = screen.getByRole('status');
    const countNode = status.firstChild;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh repositories' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Updates delayed. Read unavailable');
    expect(screen.getByText('Showing the last loaded repositories.')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'owner/httpx' })).toBeVisible();
    expect(status.firstChild).toBe(countNode);
  });
});
