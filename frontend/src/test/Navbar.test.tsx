import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { clearResources } from '../api/resources';
import { AppLayout } from '../components/layout/AppLayout';
import { AuthProvider, navigation } from '../context/AuthContext';
import { backend, installation, json, repo, user } from './fixtures';

function shell(path = '/repos', state?: { from: { pathname: string; search?: string; hash?: string } }) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: path, state }]}>
      <AuthProvider>
        <AppLayout><button type="button">Page action</button></AppLayout>
      </AuthProvider>
    </MemoryRouter>,
  );
}

function HistoryControls() {
  const navigate = useNavigate();
  return (
    <>
      <button type="button" onClick={() => void navigate(-1)}>Back</button>
      <button type="button" onClick={() => void navigate(1)}>Forward</button>
    </>
  );
}

afterEach(() => {
  cleanup();
  clearResources();
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('global header', () => {
  it.each(['https://github.com/owner/repo', 'https://github.com:8443/login/oauth/authorize'])(
    'rejects a sign-in response for a different destination (%s)', async url => {
      const assign = vi.spyOn(navigation, 'assign').mockImplementation(() => {});
      vi.stubGlobal('fetch', vi.fn((input: string) => Promise.resolve(input.endsWith('/auth/me') ? json({}, 401) : json({url}))));
      shell('/');
      const signIn = screen.getByRole('button', { name: 'Sign in with GitHub' });
      await waitFor(() => expect(signIn).toBeEnabled());
      fireEvent.click(signIn);
      expect(await screen.findByRole('alert')).toHaveTextContent('Invalid GitHub authorization URL');
      expect(assign).not.toHaveBeenCalled();
    });
  it('uses the existing sign-in operation and preserves a protected return destination', async () => {
    const assign = vi.spyOn(navigation, 'assign').mockImplementation(() => {});
    const fetch = vi.fn((url: string) => Promise.resolve(url.endsWith('/auth/me')
      ? json({}, 401)
      : json({ url: 'https://github.com/login/oauth/authorize' })));
    vi.stubGlobal('fetch', fetch);
    shell('/', { from: { pathname: '/reviews/9', search: '?installation_id=7', hash: '#finding-1' } });

    const banner = screen.getByRole('banner');
    expect(within(banner).getByRole('button', { name: 'Sign in with GitHub' })).toBeDisabled();
    const signIn = within(banner).getByRole('button', { name: 'Sign in with GitHub' });
    await waitFor(() => expect(signIn).toBeEnabled());
    expect(within(banner).getByRole('link', { name: 'CodeGuardian AI' })).toHaveAttribute('href', '/');
    expect(within(banner).queryByRole('navigation')).not.toBeInTheDocument();
    fireEvent.click(signIn);
    await waitFor(() => expect(assign).toHaveBeenCalledWith('https://github.com/login/oauth/authorize'));
    expect(sessionStorage.getItem('codeguardian:return-to')).toBe('/reviews/9?installation_id=7#finding-1');
  });

  it('uses a single account disclosure across desktop and the compact breakpoint', async () => {
    const login = 'codeguardian-enterprise-installation-owner';
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(json({ ...user, github_login: login }))));
    shell();

    const banner = screen.getByRole('banner');
    const toggle = await screen.findByRole('button', { name: `Menu for ${login}` });
    const primary = within(banner).getByRole('navigation', { name: 'Primary' });
    const panel = document.getElementById(toggle.getAttribute('aria-controls')!);
    expect(primary).toHaveClass('hidden', 'md:block');
    expect(panel).toHaveAttribute('hidden');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(within(banner).queryByRole('link', { name: 'Profile settings' })).not.toBeInTheDocument();
    expect(within(banner).queryByRole('button', { name: 'Sign out' })).not.toBeInTheDocument();

    fireEvent.click(toggle);
    const account = within(banner).getByRole('navigation', { name: 'Account navigation' });
    expect(account).toBe(panel);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(account).toHaveTextContent(login);
    expect(banner.querySelectorAll('a[href="/profile"]')).toHaveLength(1);
    expect(within(banner).getAllByRole('button', { name: 'Sign out' })).toHaveLength(1);
    expect(within(account).getByRole('link', { name: 'Repositories' }).closest('li')).toHaveClass('md:hidden');
    expect(within(primary).getByRole('link', { name: 'Repositories' })).toHaveAttribute('aria-current', 'page');

    const profile = within(account).getByRole('link', { name: 'Profile settings' });
    profile.focus();
    fireEvent.keyDown(profile, { key: 'Escape' });
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(account).not.toBeVisible();

    fireEvent.click(toggle);
    const pageAction = screen.getByRole('button', { name: 'Page action' });
    act(() => pageAction.focus());
    expect(pageAction).toHaveFocus();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getByRole('link', { name: 'Skip to main content' })).toHaveAttribute('href', '#main-content');
  });

  it('delegates sign out exactly once and preserves the error and account on failure', async () => {
    const fetch = vi.fn((url: string, _options?: RequestInit) => Promise.resolve(url.endsWith('/auth/me')
      ? json(user)
      : json({ detail: 'Unavailable' }, 503)));
    vi.stubGlobal('fetch', fetch);
    shell('/profile');

    const toggle = await screen.findByRole('button', { name: 'Menu for owner' });
    fireEvent.click(toggle);
    expect(screen.getByRole('link', { name: 'Profile settings' })).toHaveAttribute('aria-current', 'page');
    act(() => toggle.focus());
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Sign out was not confirmed: Unavailable');
    const logout = fetch.mock.calls.filter(([url]) => url.endsWith('/auth/logout'));
    expect(logout).toHaveLength(1);
    expect(logout[0][1]?.method).toBe('POST');
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
  });

  it('preserves explicit scope through global destinations and Back/Forward', async () => {
    const second = { ...installation, id: 8, account_login: 'another' };
    const fetch = vi.fn((url: string, _options?: RequestInit) => {
      const path = new URL(url).pathname;
      if (path === '/auth/me') return Promise.resolve(json({ ...user, installations: [installation, second] }));
      if (path === '/installations') return Promise.resolve(json([installation, second]));
      if (path === '/installations/8/repos') return Promise.resolve(json([{ ...repo, full_name: 'another/httpx' }]));
      if (path === '/profile/review-mode') return Promise.resolve(json({ review_mode: null, installations: [], version: '1' }));
      return Promise.resolve(backend(url));
    });
    vi.stubGlobal('fetch', fetch);
    sessionStorage.setItem('codeguardian:installation:1', '7');
    render(
      <MemoryRouter initialEntries={['/repos/another/httpx?installation_id=8&tab=pulls']}>
        <App />
        <HistoryControls />
      </MemoryRouter>,
    );

    await screen.findByRole('heading', { name: 'Open Pull Requests' });
    const banner = screen.getByRole('banner');
    const primary = within(banner).getByRole('navigation', { name: 'Primary' });
    const repositories = within(primary).getByRole('link', { name: 'Repositories' });
    expect(repositories).toHaveAttribute('href', '/repos?installation_id=8');
    expect(repositories).toHaveAttribute('aria-current', 'location');
    expect(within(banner).getByRole('link', { name: 'CodeGuardian AI' })).toHaveAttribute('href', '/repos?installation_id=8');
    const toggle = within(banner).getByRole('button', { name: 'Menu for owner' });
    fireEvent.click(toggle);
    const profile = within(banner).getByRole('link', { name: 'Profile settings' });
    expect(profile).toHaveAttribute('href', '/profile?installation_id=8');
    fireEvent.click(profile);
    expect(await screen.findByRole('heading', { name: 'Profile settings' })).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(repositories).not.toHaveAttribute('aria-current');
    fireEvent.click(repositories);
    expect(await screen.findByRole('link', { name: 'View pull requests for another/httpx' })).toHaveAttribute('href', '/repos/another/httpx?installation_id=8');
    expect(repositories).toHaveAttribute('aria-current', 'page');

    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(await screen.findByRole('heading', { name: 'Profile settings' })).toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }));
    expect(await screen.findByRole('link', { name: 'View pull requests for another/httpx' })).toBeInTheDocument();
    expect(fetch.mock.calls.every(([, options]) => (options?.method ?? 'GET') === 'GET')).toBe(true);
    expect(fetch.mock.calls.some(([url]) => new URL(url).pathname === '/installations/7/repos')).toBe(false);
  });
});
