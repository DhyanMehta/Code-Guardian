import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { clearResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import { backend, json, pull, review } from './fixtures';
import { validateStandards } from '../components/dashboard/SettingsTab';
beforeEach(() => sessionStorage.clear());
afterEach(() => { cleanup(); clearResources(); clearWriteStates(); vi.unstubAllGlobals(); });
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
describe('real write contracts', () => {
  it('rejects without claiming the branch was deleted', async () => {
    let current = review({ autofix_status: 'pending_approval', autofix: { ...review().autofix, status: 'pending_approval', branch: 'fix/review-9', applied_count: 1 } });
    const fetch = vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/reject') && options.method === 'POST') { current = { ...current, autofix_status: 'rejected', autofix: { ...current.autofix, status: 'rejected' } }; return Promise.resolve(json({ status: 'rejected', review_id: '9' })); }
      return Promise.resolve(url.endsWith('/reviews/9') ? json(current) : backend(url));
    });
    vi.stubGlobal('fetch', fetch); open('/reviews/9'); fireEvent.click(await screen.findByRole('button', { name: 'Reject fix branch' }));
    expect(await screen.findByText('Status: rejected')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'fix/review-9' })).toBeInTheDocument();
  });
  it('reconciles a conflict using the backend decision', async () => {
    let current = review({ autofix_status: 'pending_approval', autofix: { ...review().autofix, status: 'pending_approval' } });
    vi.stubGlobal('fetch', vi.fn((url: string, options: RequestInit) => {
      if (options.method === 'POST') { current = { ...current, autofix_status: 'rejected', autofix: { ...current.autofix, status: 'rejected' } }; return Promise.resolve(json({ detail: 'Decision already recorded' }, 409)); }
      return Promise.resolve(url.endsWith('/reviews/9') ? json(current) : backend(url));
    }));
    open('/reviews/9'); fireEvent.click(await screen.findByRole('button', { name: 'Approve fix branch' }));
    expect(await screen.findByText('Status: rejected')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve fix branch' })).not.toBeInTheDocument();
  });
  it('uploads multipart standards and resets metadata through the server', async () => {
    let custom = false;
    const fetch = vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/standards')) {
        if (options.method === 'POST') { custom = true; return Promise.resolve(json({ installation_id: 7, version: 'v2', filename: 'rules.md', chunks: 3, uploaded_at: '2026-10-07T00:00:00Z' })); }
        if (options.method === 'DELETE') { custom = false; return Promise.resolve(json({ status: 'deleted', installation_id: 7 })); }
        return Promise.resolve(json({ installation_id: 7, has_custom_standards: custom, version: custom ? 'v2' : null, filename: custom ? 'rules.md' : null, chunks: custom ? 3 : null, uploaded_at: null }));
      }
      return Promise.resolve(backend(url));
    });
    vi.stubGlobal('fetch', fetch); open('/repos/owner/httpx?installation_id=7&tab=settings');
    const input = await screen.findByLabelText('Custom coding standards');
    fireEvent.change(input, { target: { files: [new File(['# Rules'], 'rules.md')] } });
    fireEvent.click(screen.getByRole('button', { name: 'Upload standards' }));
    expect(await screen.findByText('Version: v2')).toBeInTheDocument();
    const post = fetch.mock.calls.find(([, o]) => o.method === 'POST')!; expect(post[1].body).toBeInstanceOf(FormData); expect(post[1].headers).toBeUndefined();
    fireEvent.click(screen.getByRole('button', { name: 'Reset to defaults' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm reset' }));
    expect(await screen.findByText('Default standards')).toBeInTheDocument();
  });
  it('triggers without a body and navigates using the numeric returned review ID', async () => {
    const fetch = vi.fn((url: string, options: RequestInit) => Promise.resolve(options.method === 'POST' ? json({ status: 'accepted', review_id: 12 }, 202) : url.endsWith('/reviews/12') ? json(review({ id: 12, status: 'pending', summary: 'Waiting for worker' })) : backend(url)));
    vi.stubGlobal('fetch', fetch); open('/repos/owner/httpx?installation_id=7');
    fireEvent.click(await screen.findByRole('button', { name: 'Run a new review' }));
    expect(await screen.findByText('Review #12 · owner/httpx PR #1')).toBeInTheDocument();
    const posts = fetch.mock.calls.filter(([, o]) => o.method === 'POST');
    expect(posts).toHaveLength(1); expect(posts[0][0]).toContain('/pulls/1/review'); expect(posts[0][1].body).toBeUndefined();
  });
  it('creates one fix branch, displays skipped reasons before approval, then persists the decision', async () => {
    let current = review({ fixable_count: 2 });
    const fetch = vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/autofix') && options.method === 'POST') {
        current = { ...current, autofix_status: 'pending_approval', autofix_branch: 'fix/review-9', autofix: { ...current.autofix, status: 'pending_approval', branch: 'fix/review-9', commit_sha: 'fix-sha', applied_count: 1, skipped_fixes: [{ target: 'file.py:retry', reason: 'Apply-time validation rejected draft' }] } };
        return Promise.resolve(json({ status: 'created', branch: 'fix/review-9', applied_fixes: 1, skipped_fixes: [{ target: 'file.py:retry', reason: 'Apply-time validation rejected draft' }] }, 201));
      }
      if (url.endsWith('/approve')) { current = { ...current, autofix_status: 'approved', autofix: { ...current.autofix, status: 'approved', approved_by: 'owner' } }; return Promise.resolve(json({ status: 'approved', review_id: '9' })); }
      return Promise.resolve(url.endsWith('/reviews/9') ? json(current) : backend(url));
    });
    vi.stubGlobal('fetch', fetch); open('/reviews/9');
    fireEvent.click(await screen.findByRole('button', { name: 'Create fix branch' }));
    expect(await screen.findByText(/Skipped file.py:retry: Apply-time/)).toBeInTheDocument();
    expect(screen.getByText('Applied fixes: 1')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Approve fix branch' }));
    expect(await screen.findByText('Status: approved')).toBeInTheDocument();
    const posts = fetch.mock.calls.filter(([, o]) => o.method === 'POST'); expect(posts).toHaveLength(2); posts.forEach(([, o]) => expect(o.body).toBeUndefined());
    expect(screen.queryByText('Quick AI Fix')).not.toBeInTheDocument();
  });
  it('blocks known stale-head creation', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/reviews/9') ? json(review({ fixable_count: 1 })) : url.includes('/pulls?') ? json([{ ...pull, head_sha: 'new-head' }]) : backend(url))));
    open('/reviews/9');
    expect(await screen.findByText('The PR head changed. Run a new review before creating fixes.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create fix branch' })).toBeDisabled();
  });
  it('does not replay an ambiguous auto-fix request', async () => {
    const fetch = vi.fn((url: string, options: RequestInit) => options.method === 'POST' ? Promise.reject(new TypeError('offline')) : Promise.resolve(url.endsWith('/reviews/9') ? json(review({ fixable_count: 1 })) : backend(url)));
    vi.stubGlobal('fetch', fetch); open('/reviews/9');
    fireEvent.click(await screen.findByRole('button', { name: 'Create fix branch' }));
    await screen.findByText(/The server may have completed this action/);
    expect(screen.getByRole('button', { name: 'Create fix branch' })).toBeDisabled();
    expect(fetch.mock.calls.filter(([, o]) => o.method === 'POST')).toHaveLength(1);
  });
  it('updates shared profile mode with a version and refetches the persisted result', async () => {
    let mode = 'manual';
    const fetch = vi.fn((url: string, options: RequestInit) => {
      if (url.endsWith('/profile/review-mode')) { if (options.method === 'PATCH') mode = JSON.parse(options.body as string).review_mode; return Promise.resolve(json({ installations:[{id:7,account_login:'owner',review_mode:mode}], review_mode: mode, version:mode })); }
      return Promise.resolve(backend(url));
    });
    vi.stubGlobal('fetch', fetch); open('/profile');
    fireEvent.change(await screen.findByLabelText('Review mode'), { target: { value: 'auto' } });
    fireEvent.click(screen.getByRole('button', { name: 'Apply to all administered installations' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Apply to all administered installations' })).toBeDisabled());
    expect(fetch.mock.calls.filter(([, o]) => o.method === 'PATCH')[0][1].body).toBe('{"review_mode":"auto","version":"manual"}');
  });
  it('validates standards extension, byte limit, and UTF-8', async () => {
    await expect(validateStandards(new File(['# Rules'], 'rules.md'))).resolves.toBeUndefined();
    await expect(validateStandards(new File(['rules'], 'rules.txt'))).rejects.toThrow('Markdown');
    await expect(validateStandards(new File([new Uint8Array(512 * 1024 + 1)], 'rules.md'))).rejects.toThrow('512 KiB');
    await expect(validateStandards(new File([new Uint8Array([0xff])], 'rules.md'))).rejects.toThrow('UTF-8');
  });
});
