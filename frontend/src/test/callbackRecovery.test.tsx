import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { backend, json, user } from './fixtures';
import { clearResources } from '../api/resources';
import { installationResumeKey, navigation } from '../context/AuthContext';
afterEach(() => { cleanup(); clearResources(); sessionStorage.clear(); window.history.replaceState({}, '', '/'); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount(path: string) {
  window.history.replaceState({}, '', path);
  return render(<StrictMode><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></StrictMode>);
}
it.each(['', '?code=orphan', '?state=orphan', '?error=access_denied'])('recovers an incomplete callback %s without exchanging a code', async query => {
  const fetch = vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me') ? json({detail:'Unauthorized'},401) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback' + query);
  expect(await screen.findByRole('button',{name:'Try signing in again'})).toBeEnabled();
  expect(screen.queryByText('Completing sign-in…')).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/github/callback'))).toBe(false);
});
it('verifies a misrouted installation return using the existing session, not its installation ID', async () => {
  const fetch = vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me') ? json({...user,installations:[]}) : url.endsWith('/auth/installations/refresh') ? json(user) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback?installation_id=999999&setup_action=install');
  expect(await screen.findByText('owner/httpx')).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/installations/refresh'))).toHaveLength(1);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/github/callback'))).toBe(false);
  expect(sessionStorage.getItem(installationResumeKey)).toBeNull();
});
it('offers current-account recovery after reloading a cleaned callback', async () => {
  vi.stubGlobal('fetch',vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/me') ? json(user) : backend(url))));
  mount('/auth/callback');
  expect(await screen.findByRole('button',{name:/Continue with your current account/})).toBeEnabled();
});
it('preserves installation recovery when an expired session requires sign-in', async () => {
  const assign = vi.spyOn(navigation,'assign').mockImplementation(() => {});
  vi.stubGlobal('fetch',vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/me') ? json({detail:'Unauthorized'},401) : url.endsWith('/auth/github/login') ? json({url:'https://github.com/login/oauth/authorize?client_id=test'}) : backend(url))));
  mount('/auth/install?installation_id=123');
  const button = await screen.findByRole('button',{name:'Sign in and continue setup'});
  await act(async () => { fireEvent.click(button); });
  expect(sessionStorage.getItem(installationResumeKey)).toBe('1');
  await vi.waitFor(() => expect(assign).toHaveBeenCalledTimes(1));
});
it('resumes installation verification after fresh OAuth even with existing installations', async () => {
  sessionStorage.setItem(installationResumeKey,'1');
  const fetch = vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/github/callback') ? json({user}) : url.endsWith('/auth/me') || url.endsWith('/auth/installations/refresh') ? json(user) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback?code=resume-test-unique&state=valid-state');
  expect(await screen.findByText('owner/httpx')).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/github/callback'))).toHaveLength(1);
  expect(fetch.mock.calls.filter(([url]) => url.endsWith('/auth/installations/refresh'))).toHaveLength(1);
});
it('does not continue automatically after authorization is denied with an existing session', async () => {
  const fetch = vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/me') ? json(user) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback?error=access_denied&installation_id=123');
  expect(await screen.findByText('GitHub authorization was not completed.')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/installations/refresh'))).toBe(false);
});
it('keeps a rejected OAuth state as an error without falling back to installation access', async () => {
  const fetch = vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/github/callback') ? json({detail:'Invalid or missing OAuth state parameter.'},400) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback?code=invalid-state-test&state=expired&installation_id=123');
  expect(await screen.findByText('Invalid or missing OAuth state parameter.')).toBeInTheDocument();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/installations/refresh'))).toBe(false);
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/me'))).toBe(false);
});
it('retries a failed session lookup before recovering a misrouted installation', async () => {
  let fail = true;
  const fetch = vi.fn((url:string) => Promise.resolve(url.endsWith('/auth/me') ? fail ? json({detail:'Session service unavailable'},400) : json(user) : url.endsWith('/auth/installations/refresh') ? json(user) : backend(url)));
  vi.stubGlobal('fetch',fetch); mount('/auth/callback?setup_action=install');
  const retry = await screen.findByRole('button',{name:'Retry session check'});
  expect(screen.getByText('Session service unavailable')).toBeInTheDocument();
  fail = false; fireEvent.click(retry);
  expect(await screen.findByText('owner/httpx')).toBeInTheDocument();
});
