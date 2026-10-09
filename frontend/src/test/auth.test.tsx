import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { AuthCallbackPage } from '../pages/AuthCallbackPage';
import { installation } from './fixtures';
const user = { id: 1, github_user_id: 2, github_login: 'test', avatar_url: null, installations: [installation] };
const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
afterEach(() => { vi.unstubAllGlobals(); window.history.replaceState({}, '', '/'); sessionStorage.clear(); });
function Session() { const auth = useAuth(); return <><p>{auth.isLoading ? 'Checking' : auth.user?.github_login ?? 'Anonymous'}</p><p>{auth.actionError}</p><button onClick={() => void auth.logout()}>Logout</button></>; }
describe('authentication lifecycle', () => {
  it('exchanges a single-use callback once under StrictMode and restores a deep link', async () => {
    window.history.replaceState({}, '', '/auth/callback?code=unique-test&state=state');
    sessionStorage.setItem('codeguardian:return-to', '/reviews/9?installation_id=1#finding');
    const fetch = vi.fn((url: string) => Promise.resolve(json(url.endsWith('/auth/me') ? user : { user })));
    vi.stubGlobal('fetch', fetch);
    render(<StrictMode><MemoryRouter initialEntries={['/auth/callback?code=unique-test&state=state']}><AuthProvider><Routes><Route path="/auth/callback" element={<AuthCallbackPage />} /><Route path="/reviews/9" element={<Session />} /></Routes></AuthProvider></MemoryRouter></StrictMode>);
    expect(await screen.findByText('test')).toBeInTheDocument();
    expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/github/callback'))).toHaveLength(1);
    expect(window.location.search).toBe('');
  });
  it('retains the session when logout fails', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me') ? json(user) : json({ detail: 'Unavailable' }, 503))));
    render(<AuthProvider><Session /></AuthProvider>);
    await screen.findByText('test'); fireEvent.click(screen.getByText('Logout'));
    await waitFor(() => expect(screen.getByText(/Sign out was not confirmed/)).toBeInTheDocument());
    expect(screen.getByText('test')).toBeInTheDocument();
  });
  it('routes a new OAuth user to installation before the dashboard', async () => {
    window.history.replaceState({}, '', '/auth/callback?code=first-install&state=state');
    const fresh = { ...user, installations: [] };
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(json(url.endsWith('/auth/me') ? fresh : {user:fresh}))));
    render(<MemoryRouter initialEntries={['/auth/callback?code=first-install&state=state']}><AuthProvider><Routes><Route path="/auth/callback" element={<AuthCallbackPage/>}/><Route path="/auth/install" element={<p>Choose repositories first</p>}/></Routes></AuthProvider></MemoryRouter>);
    expect(await screen.findByText('Choose repositories first')).toBeInTheDocument();
  });
});
