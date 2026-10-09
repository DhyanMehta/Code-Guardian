import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { clearResources, useResource } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import { backend, installation, item, json, repo, review, user } from './fixtures';
import { endpoints } from '../api/endpoints';
import { navigation } from '../context/AuthContext';
import { agentHistory, type AgentHistoryCache } from '../components/dashboard/AgentsTab';
beforeEach(() => { sessionStorage.clear(); vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(backend(url)))); });
afterEach(() => { cleanup(); clearResources(); clearWriteStates(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
describe('complete reliability flows', () => {
  it('does not fetch repositories until ambiguous installation identity is selected', async () => {
    const second = { ...installation, id: 8, account_login: 'another' };
    const fetch = vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me') ? json({ ...user, installations: [installation, second] }) : url.endsWith('/installations') ? json([installation, second]) : url.endsWith('/installations/8/repos') ? json([{ ...repo, full_name: 'another/httpx' }]) : backend(url)));
    vi.stubGlobal('fetch', fetch); open('/repos');
    const selector = await screen.findByLabelText('Installation');
    expect(fetch.mock.calls.some(([url]) => /\/installations\/\d+\/repos$/.test(url))).toBe(false);
    fireEvent.change(selector, { target: { value: '8' } });
    expect(await screen.findByText('another/httpx')).toBeInTheDocument();
    expect(screen.getByText('View pull requests →')).toHaveAttribute('href', '/repos/another/httpx?installation_id=8');
  });
  it('does not use saved selection to override an invalid explicit installation', async () => {
    sessionStorage.setItem('codeguardian:installation:1', '7'); open('/repos?installation_id=999');
    expect(await screen.findByText(/This installation is unavailable/)).toBeInTheDocument();
    expect(screen.queryByText('owner/httpx')).not.toBeInTheDocument();
  });
  it('shows real onboarding for zero installations', async () => {
    vi.spyOn(navigation, 'assign').mockImplementation(() => {});
    vi.stubEnv('VITE_GITHUB_APP_SLUG', 'guardian-test');
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me') ? json({ ...user, installations: [] }) : url.endsWith('/auth/installation-url') ? json({url:'https://github.com/apps/guardian-test/installations/new'}) : url.endsWith('/installations') ? json([]) : backend(url))));
    open('/repos');
    expect(await screen.findByRole('link', { name: /Choose repositories on GitHub/ })).toHaveAttribute('href', 'https://github.com/apps/guardian-test/installations/new');
    expect(screen.getByRole('button', { name: /Refresh GitHub access/ })).toBeInTheDocument();
  });
  it('resolves a legacy PR route to its review ID', async () => {
    open('/repos/owner/httpx/pulls/1?installation_id=7');
    expect(await screen.findByText('Review #9 · owner/httpx PR #1')).toBeInTheDocument();
  });
  it('handles skipped and failed records without inventing a clean review', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/reviews/9') ? json(review({ status: 'skipped', summary: 'Superseded by a newer review.' })) : backend(url))));
    open('/reviews/9'); await screen.findByText('Superseded by a newer review.');
    expect(screen.getByText('Analysis: Skipped')).toBeInTheDocument();
    expect(screen.queryByText('Saved / rendered report')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create fix branch' })).toBeDisabled();
  });
  it('expires the session centrally after a protected API returns 401', async () => {
    const fetch = vi.fn((url: string) => Promise.resolve(url.endsWith('/reviews/9') ? json({ detail: 'Expired' }, 401) : backend(url)));
    vi.stubGlobal('fetch', fetch); open('/reviews/9');
    expect(await screen.findByText('Session expired. Sign in again.')).toBeInTheDocument();
    expect(screen.queryByText('Review #9 · owner/httpx PR #1')).not.toBeInTheDocument();
  });
  it('shows repository access loss instead of a fabricated fallback', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/installations/7/repos') ? json([]) : backend(url))));
    open('/repos/owner/httpx?installation_id=7');
    expect(await screen.findByText('Repository not found or access unavailable for this installation.')).toBeInTheDocument();
    expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  });
  it('keeps settings read-only for installation members', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/installations') ? json([{ ...installation, role: 'member' }]) : backend(url))));
    open('/repos/owner/httpx?installation_id=7&tab=settings');
    expect(await screen.findByLabelText('Custom coding standards')).toBeDisabled();
    expect(screen.queryByLabelText('Review mode')).not.toBeInTheDocument();
  });
  it('discards a late response after repository identity changes', async () => {
    let resolveOld!: (value: string) => void;
    const old = new Promise<string>(resolve => { resolveOld = resolve; });
    function Page({ id }: { id: string }) { const data = useResource(id, () => id === 'old' ? old : Promise.resolve('new repository')); return <p>{data.data ?? 'Loading'}</p>; }
    const view = render(<Page id="old" />); view.rerender(<Page id="new" />);
    await screen.findByText('new repository');
    await act(async () => { resolveOld('old repository'); await old; });
    expect(screen.getByText('new repository')).toBeInTheDocument(); expect(screen.queryByText('old repository')).not.toBeInTheDocument();
  });
  it('bounds agent detail concurrency and reuses details for thirty seconds', async () => {
    vi.spyOn(endpoints, 'reviews').mockResolvedValue({ items: [1, 2, 3, 4, 5].map(id => ({ ...item(), id })), total: 5, offset: 0, limit: 5 });
    let active = 0, max = 0;
    const details = vi.spyOn(endpoints, 'review').mockImplementation(async id => { max = Math.max(max, ++active); await Promise.resolve(); active--; return review({ id }); });
    const cache: AgentHistoryCache = new Map(); const signal = new AbortController().signal;
    await agentHistory(7, 'owner/httpx', 5, signal, cache); await agentHistory(7, 'owner/httpx', 5, signal, cache);
    expect(max).toBe(2); expect(details).toHaveBeenCalledTimes(5);
  });
  it('refreshes a cached running review immediately when history reports completion', async () => {
    vi.spyOn(endpoints, 'reviews').mockResolvedValue({items:[item()],total:1,offset:0,limit:5});
    const details=vi.spyOn(endpoints,'review').mockResolvedValue(review());
    const cache:AgentHistoryCache=new Map([[9,{detail:review({status:'running'}),fetched:Date.now()}]]);
    const result=await agentHistory(7,'owner/httpx',5,new AbortController().signal,cache);
    expect(details).toHaveBeenCalledTimes(1);expect(result.results[0].detail?.status).toBe('completed');
  });
  it('normalizes an invalid tab while retaining installation and unrelated parameters', async () => {
    open('/repos/owner/httpx?installation_id=7&tab=invalid&keep=yes');
    await screen.findByText('Review #9 · Completed');
    expect(screen.getByRole('tab', { name: 'Pull Requests' })).toHaveAttribute('aria-selected', 'true');
    fireEvent.click(screen.getByRole('tab', { name: 'Settings' }));
    await waitFor(() => expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'repository-tabs-tab-settings'));
  });
});
