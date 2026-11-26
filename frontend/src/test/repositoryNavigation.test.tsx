import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { Link, MemoryRouter, useLocation, useNavigate } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { clearResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import { backend, installation, json, pull, repo, user } from './fixtures';

const repoPath = '/repos/owner/httpx';
const second = { ...installation, id: 8, account_login: 'other', review_mode: 'auto' as const };

function LocationControls() {
  const navigate = useNavigate();
  const { pathname, search, hash } = useLocation();
  return (
    <>
      <output aria-label="Test URL">{pathname}{search}{hash}</output>
      <button type="button" onClick={() => void navigate(-1)}>Back</button>
      <button type="button" onClick={() => void navigate(1)}>Forward</button>
    </>
  );
}

function open(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /><LocationControls /></MemoryRouter>);
}

function mockBackend(read: (url: URL, options?: RequestInit) => Response | Promise<Response> | undefined = () => undefined) {
  const fetch = vi.fn(async (url: string, options?: RequestInit) => read(new URL(url), options) ?? backend(url));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

function media(matches: boolean) {
  const query = Object.assign(new EventTarget(), { matches });
  vi.stubGlobal('matchMedia', vi.fn(() => query));
  return (wide: boolean) => act(() => {
    query.matches = wide;
    query.dispatchEvent(Object.assign(new Event('change'), { matches: wide }));
  });
}

function url() {
  return new URL(screen.getByLabelText('Test URL').textContent!, 'http://localhost');
}

beforeEach(() => sessionStorage.clear());
afterEach(() => {
  cleanup();
  clearResources();
  clearWriteStates();
  vi.unstubAllGlobals();
});

describe('repository navigation', () => {
  it('renders one desktop tablist and restores explicit scope, view and query on history navigation', async () => {
    const fetch = mockBackend(u => u.pathname === '/installations' ? json([installation, second]) : undefined);
    sessionStorage.setItem('codeguardian:installation:1', '8');
    open(`${repoPath}?installation_id=7&keep=yes#anchor`);
    await screen.findByRole('link', { name: 'View Review #9 for owner/httpx PR #1' });

    const context = screen.getByRole('region', { name: 'Repository context' });
    expect(within(context).getByRole('heading', { level: 1 })).toHaveTextContent('owner/httpx');
    expect(within(context).getByText('Manual')).toBeVisible();
    expect(within(context).getByText('main')).toBeVisible();
    expect(within(context).getByRole('link', { name: 'All repositories' })).toHaveAttribute('href', '/repos?installation_id=7');
    expect(screen.getAllByRole('combobox', { name: 'Installation' })).toHaveLength(1);
    expect(screen.getByRole('combobox', { name: 'Installation' })).toHaveValue('7');
    expect(screen.queryByRole('complementary')).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Repository view' })).not.toBeInTheDocument();

    const tablist = screen.getByRole('tablist', { name: 'Repository views' });
    const tabs = within(tablist).getAllByRole('tab');
    expect(tabs.map(tab => tab.textContent)).toEqual(['Pull Requests', 'Analytics', 'Agent History']);
    expect(within(context).getByRole('link', { name: 'Installation Settings' })).toHaveAttribute('href', '/settings/installation?installation_id=7');
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true');
    expect(tabs.filter(tab => tab.tabIndex === 0)).toEqual([tabs[0]]);
    for (const tab of tabs) {
      const panel = document.getElementById(tab.getAttribute('aria-controls')!);
      expect(panel).toHaveAttribute('aria-labelledby', tab.id);
    }
    expect(screen.getAllByRole('tabpanel')).toHaveLength(1);

    fireEvent.keyDown(tabs[0], { key: 'ArrowRight' });
    expect(tabs[1]).toHaveFocus();
    await screen.findByRole('heading', { name: 'Weighted findings by review' });
    expect(url().searchParams.get('tab')).toBe('analytics');
    fireEvent.keyDown(tabs[1], { key: 'End' });
    expect(tabs[2]).toHaveFocus();
    await screen.findByRole('heading', { name: 'Specialist outcomes' });
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    expect(tabs[2]).toHaveAttribute('aria-selected', 'true');
    expect(url().searchParams.get('installation_id')).toBe('7');
    expect(url().searchParams.get('keep')).toBe('yes');
    fireEvent.keyDown(tabs[2], { key: 'Home' });
    expect(tabs[0]).toHaveFocus();
    expect(url().searchParams.get('tab')).toBe('pulls');
    expect(fetch.mock.calls.some(([request]) => new URL(request).pathname.startsWith('/installations/8/'))).toBe(false);
    expect(fetch.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
  });

  it.each([
    ['invalid', '999', /This installation is unavailable/],
    ['suspended', '8', /This installation is suspended/],
    ['inaccessible repository', '9', /Repository not found or access unavailable/],
  ])('keeps %s scope explicit and gates repository resources', async (_state, id, message) => {
    const fetch = mockBackend(u => {
      if (u.pathname === '/installations') return json([installation, { ...second, suspended: true }, { ...second, id: 9 }]);
      if (u.pathname === '/installations/9/repos') return json([]);
    });
    sessionStorage.setItem('codeguardian:installation:1', '7');
    open(`${repoPath}?installation_id=${id}&tab=settings`);
    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByRole('link', { name: 'All repositories' })).toHaveAttribute('href', `/repos?installation_id=${id}`);
    expect(screen.queryByRole('heading', { name: 'owner/httpx' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    const requests = fetch.mock.calls.map(([request]) => new URL(request).pathname);
    expect(requests).toEqual(id === '9' ? ['/auth/me', '/installations', '/installations/9/repos'] : ['/auth/me', '/installations']);
  });

  it('revalidates access on an installation switch and ignores an in-flight response from the old scope', async () => {
    let resolveOld!: (response: Response) => void;
    let resolveAccess!: (response: Response) => void;
    let oldSignal: AbortSignal | null | undefined;
    const old = new Promise<Response>(resolve => { resolveOld = resolve; });
    const newAccess = new Promise<Response>(resolve => { resolveAccess = resolve; });
    const fetch = mockBackend((u, options) => {
      if (u.pathname === '/installations') return json([installation, second]);
      if (u.pathname === '/installations/8/repos') return newAccess;
      if (u.pathname.startsWith('/installations/7/') && u.pathname.endsWith('/pulls')) {
        oldSignal = options?.signal;
        return old;
      }
      if (u.pathname.startsWith('/installations/8/') && u.pathname.endsWith('/pulls')) return json([{ ...pull, title: 'New scope PR' }]);
      if (u.pathname === '/reviews' && u.searchParams.get('installation_id') === '8') return json({ items: [], limit: 100, offset: 0, total: 0 });
    });
    open(`${repoPath}?installation_id=7&keep=yes`);
    await waitFor(() => expect(oldSignal).toBeDefined());
    fireEvent.change(screen.getByRole('combobox', { name: 'Installation' }), { target: { value: '8' } });
    expect(oldSignal?.aborted).toBe(true);
    expect(screen.queryByRole('heading', { name: 'owner/httpx' })).not.toBeInTheDocument();
    expect(fetch.mock.calls.some(([request]) => new URL(request).pathname.startsWith('/installations/8/repos/'))).toBe(false);
    await act(async () => resolveAccess(json([{ ...repo, default_branch: 'release' }])));
    expect(await screen.findByRole('link', { name: /New scope PR/ })).toBeVisible();
    expect(screen.getByText('release')).toBeVisible();
    expect(screen.getByText('Automatic')).toBeVisible();
    await act(async () => resolveOld(json([{ ...pull, title: 'Old scope PR' }])));
    expect(screen.queryByText('Old scope PR')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /New scope PR/ })).toBeVisible();
    expect(url().searchParams.get('installation_id')).toBe('8');
    expect(url().searchParams.get('keep')).toBe('yes');
  });

  it('uses one native chooser on compact screens and transfers focus without remounting active content', async () => {
    const resize = media(true);
    const fetch = mockBackend();
    open(`${repoPath}?installation_id=7&tab=pulls`);
    await screen.findByRole('link', { name: 'View Review #9 for owner/httpx PR #1' });
    const pullsTab = screen.getByRole('tab', { name: 'Pull Requests' });
    const refresh = screen.getByRole('button', { name: 'Refresh pull requests' });
    const count = fetch.mock.calls.length;
    act(() => pullsTab.focus());
    resize(false);
    const chooser = screen.getByRole('combobox', { name: 'Repository view' });
    expect(chooser).toHaveFocus();
    expect(chooser).toHaveValue('pulls');
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh pull requests' })).toBe(refresh);
    expect(fetch).toHaveBeenCalledTimes(count);
    expect(within(chooser).getAllByRole('option').map(option => option.textContent)).toEqual(['Pull Requests', 'Analytics', 'Agent History']);
    expect(screen.getByRole('link', { name: 'Installation Settings' })).toBeVisible();

    fireEvent.change(chooser, { target: { value: 'analytics' } });
    await screen.findByRole('heading', { name: 'Weighted findings by review' });
    fireEvent.change(chooser, { target: { value: 'agents' } });
    await screen.findByRole('heading', { name: 'Specialist outcomes' });
    expect(chooser).toHaveFocus();
    expect(screen.getByRole('region', { name: 'Agent History' })).toHaveAttribute('id', chooser.getAttribute('aria-controls'));
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(chooser).toHaveValue('analytics');
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    expect(chooser).toHaveValue('agents');
    act(() => chooser.focus());
    resize(true);
    expect(screen.getByRole('tab', { name: 'Agent History' })).toHaveFocus();
    expect(screen.queryByRole('combobox', { name: 'Repository view' })).not.toBeInTheDocument();
    const ids = [...document.querySelectorAll('[id^="repository-tabs-panel-"]')].map(panel => panel.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('uses recorded review scope even when a different installation is selected in the URL', async () => {
    mockBackend(u => u.pathname === '/auth/me' ? json({ ...user, installations: [installation, second] }) : undefined);
    sessionStorage.setItem('codeguardian:installation:1', '8');
    open('/reviews/9?installation_id=8#finding-1');
    await screen.findByRole('heading', { name: 'Review #9 · owner/httpx PR #1' });
    expect(screen.getByRole('link', { name: /owner\/httpx/ })).toHaveAttribute('href', `${repoPath}?installation_id=7`);
    expect(screen.queryByRole('combobox', { name: 'Installation' })).not.toBeInTheDocument();
    expect(url().hash).toBe('#finding-1');
  });
});

const settingsPath = '/settings/installation';
const scopedSettings = settingsPath + '?installation_id=7';
const custom = { installation_id: 7, has_custom_standards: true, filename: 'rules.md', version: 'v2', chunks: 3, uploaded_at: null };

describe('installation settings navigation', () => {
  it.each(['admin', 'member'])('reads standards directly as %s without requesting any repository', async role => {
    const fetch = mockBackend(u => {
      if (u.pathname === '/installations') return json([{ ...installation, role }]);
      if (u.pathname.endsWith('/repos')) return json([]);
      if (u.pathname.endsWith('/standards')) return json(custom);
    });
    open(settingsPath + '?keep=yes');
    await screen.findByText('Custom standards: rules.md');
    fireEvent.click(screen.getByText('Technical details'));
    expect(screen.getByText('Version: v2')).toBeVisible();
    expect(url().searchParams.get('installation_id')).toBe('7');
    expect(url().searchParams.get('keep')).toBe('yes');
    expect(screen.getByText(/Historical reviews retain/)).toBeVisible();
    expect(screen.getByLabelText('Custom coding standards')).toHaveProperty('disabled', role === 'member');
    expect(screen.getByRole('button', { name: 'Reset to defaults' })).toHaveProperty('disabled', role === 'member');
    expect(screen.getByRole('button', { name: 'Upload standards' })).toBeDisabled();
    expect(screen.getByRole('link', { name: 'Shared review automation' })).toHaveAttribute('href', '/profile?installation_id=7');
    expect(fetch.mock.calls.map(([u]) => new URL(u).pathname).sort()).toEqual(['/auth/me', '/installations', '/installations/7/settings', '/installations/7/standards']);
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('protects direct entry while signed out', async () => {
    const fetch = mockBackend(u => u.pathname === '/auth/me' ? json({ detail: 'Signed out' }, 401) : undefined);
    open(scopedSettings);
    await waitFor(() => expect(url().pathname).toBe('/'));
    expect(fetch.mock.calls.some(([u]) => u.includes('/installations/7/'))).toBe(false);
  });

  it.each(['ambiguous', 'invalid', 'suspended'])('requires recovery for %s scope without reading standards', async scenario => {
    const fetch = mockBackend(u => u.pathname === '/installations' ? json([installation, { ...second, suspended: true }]) : undefined);
    const query = scenario === 'ambiguous' ? '' : '?installation_id=' + (scenario === 'invalid' ? 'abc' : '8');
    if (query) sessionStorage.setItem('codeguardian:installation:1', '7');
    open(settingsPath + query);
    const selector = await screen.findByRole('combobox', { name: 'Installation' });
    expect(screen.getByText(scenario === 'ambiguous' ? /Select an installation to view/ : scenario === 'invalid' ? /This installation is unavailable/ : /This installation is suspended/)).toBeVisible();
    expect(fetch.mock.calls.some(([u]) => u.endsWith('/standards') || u.endsWith('/settings'))).toBe(false);
    fireEvent.change(selector, { target: { value: '7' } });
    await screen.findByText('Default standards');
    expect(url().search).toBe('?installation_id=7');
  });

  it('replaces an authorized legacy bookmark and keeps other parameters through history and reload', async () => {
    let allowRepo!: (r: Response) => void;
    const pending = new Promise<Response>(resolve => { allowRepo = resolve; });
    const fetch = mockBackend(u => u.pathname.endsWith('/repos') ? pending : undefined);
    const legacy = repoPath + '?tab=settings&keep=a&installation_id=7&keep=b';
    const view = render(<MemoryRouter initialEntries={['/repos?installation_id=7', legacy]} initialIndex={1}><App /><LocationControls /></MemoryRouter>);
    await waitFor(() => expect(fetch.mock.calls.some(([u]) => u.endsWith('/7/repos'))).toBe(true));
    expect(fetch.mock.calls.some(([u]) => u.endsWith('/standards') || u.endsWith('/settings'))).toBe(false);
    await act(async () => allowRepo(json([repo])));
    await screen.findByText('Default standards');
    const canonical = url().pathname + url().search;
    expect(url().pathname).toBe(settingsPath);
    expect(url().searchParams.getAll('keep')).toEqual(['a', 'b']);
    expect(url().searchParams.has('tab')).toBe(false);
    expect(url().searchParams.get('installation_id')).toBe('7');
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByRole('heading', { name: 'Connected Repositories' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Installation Settings' })).toHaveAttribute('href', scopedSettings);
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    await screen.findByText('Default standards');
    expect(url().pathname + url().search).toBe(canonical);
    view.unmount();
    clearResources();
    open(canonical);
    await screen.findByText('Default standards');
    expect(url().pathname + url().search).toBe(canonical);
  });

  it('discards staged state and a late standards read while preserving one form across resize', async () => {
    let finish!: (r: Response) => void;
    const pending = new Promise<Response>(resolve => { finish = resolve; });
    let signal: AbortSignal | null | undefined;
    const fetch = mockBackend((u, init) => {
      if (u.pathname === '/installations') return json([installation, second]);
      if (u.pathname === '/installations/7/standards') { signal = init?.signal; return pending; }
      if (u.pathname === '/installations/8/standards') return json({ ...custom, installation_id: 8, filename: 'other.md' });
      if (u.pathname === '/installations/8/settings') return json({ installation_id: 8, review_mode: 'auto' });
    });
    sessionStorage.setItem('codeguardian:installation:1', '7');
    const resize = media(true);
    open(settingsPath);
    const input = await screen.findByLabelText('Custom coding standards');
    fireEvent.change(input, { target: { files: [new File(['Rules'], 'local.md')] } });
    await waitFor(() => expect(screen.getByRole('button', { name: 'Upload standards' })).toBeEnabled());
    const count = fetch.mock.calls.length;
    resize(false);
    expect(screen.getByLabelText('Custom coding standards')).toBe(input);
    expect(fetch).toHaveBeenCalledTimes(count);
    expect(screen.getByRole('button', { name: 'Upload standards' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '8' } });
    await screen.findByText('Custom standards: other.md');
    expect(signal?.aborted).toBe(true);
    await act(async () => finish(json(custom)));
    expect(screen.queryByText('Custom standards: rules.md')).toBeNull();
    expect(screen.getByRole('button', { name: 'Upload standards' })).toBeDisabled();
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('rechecks a warm repository cache before resolving a bookmark after repository access is revoked', async () => {
    let reads = 0;
    const fetch = mockBackend(u => {
      if (u.pathname.endsWith('/7/repos')) return json(++reads === 1 ? [repo] : []);
    });
    render(
      <MemoryRouter initialEntries={['/repos?installation_id=7']}>
        <App /><Link to={repoPath + '?tab=settings&installation_id=7'}>Saved bookmark</Link><LocationControls />
      </MemoryRouter>,
    );
    await screen.findByRole('link', { name: 'View pull requests for owner/httpx' });
    fireEvent.click(screen.getByRole('link', { name: 'Saved bookmark' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/Repository not found/);
    expect(url().pathname).toBe(repoPath);
    expect(reads).toBe(2);
    expect(fetch.mock.calls.some(([u]) => u.endsWith('/standards') || u.endsWith('/settings'))).toBe(false);
  });

  it('honors a denied settings read even when membership and standards still have data', async () => {
    const fetch = mockBackend(u => u.pathname.endsWith('/settings') ? json({ detail: 'Access revoked' }, 403) : undefined);
    open(scopedSettings);
    expect(await screen.findByRole('alert')).toHaveTextContent('Access revoked');
    expect(screen.queryByLabelText('Custom coding standards')).toBeNull();
    expect(screen.queryByText('Default standards')).toBeNull();
    expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  });

  it('withdraws the form after membership is lost', async () => {
    let lost = false;
    mockBackend(u => {
      if (lost && u.pathname === '/installations') return json([second]);
      if (lost && u.pathname.startsWith('/installations/7/')) return json({ detail: 'Access revoked' }, 403);
    });
    open(scopedSettings);
    await screen.findByText('Default standards');
    lost = true;
    fireEvent.click(screen.getByRole('button', { name: 'Refresh installation settings' }));
    await screen.findByText(/This installation is unavailable/);
    expect(screen.queryByText('Default standards')).toBeNull();
    expect(screen.queryByLabelText('Custom coding standards')).toBeNull();
    expect(url().search).toBe('?installation_id=7');
  });

  it('keeps an uncertain reset with its original installation until explicitly reconciled', async () => {
    let settle!: (r: Response) => void;
    const pending = new Promise<Response>(resolve => { settle = resolve; });
    const fetch = mockBackend((u, init) => {
      if (u.pathname === '/installations') return json([installation, second]);
      if (u.pathname === '/installations/7/standards') return init?.method === 'DELETE' ? pending : json(custom);
      if (u.pathname === '/installations/8/standards') return json({ ...custom, installation_id: 8, filename: 'other.md' });
      if (u.pathname === '/installations/8/settings') return json({ installation_id: 8, review_mode: 'auto' });
    });
    open(scopedSettings);
    await screen.findByText('Custom standards: rules.md');
    fireEvent.click(screen.getByText('Technical details'));
    expect(screen.getByText('Version: v2')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Reset to defaults' }));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm reset' }));
    fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '8' } });
    await screen.findByText('Custom standards: other.md');
    await act(async () => settle(json({ detail: 'Outcome unknown' }, 503)));
    expect(screen.queryByText('Outcome unknown')).toBeNull();
    expect(screen.getByRole('button', { name: 'Reset to defaults' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '7' } });
    await screen.findByText('Outcome unknown');
    expect(screen.getByRole('button', { name: 'Reset to defaults' })).toBeDisabled();
    const reconcile = screen.getByRole('button', { name: /allow an explicit retry/ });
    await waitFor(() => expect(reconcile).toBeEnabled());
    fireEvent.click(reconcile);
    expect(screen.getByRole('button', { name: 'Reset to defaults' })).toBeEnabled();
    expect(fetch.mock.calls.filter(([, init]) => init?.method !== 'GET').map(([u]) => new URL(u).pathname)).toEqual(['/installations/7/standards']);
  });
});
