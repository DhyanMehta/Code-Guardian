import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { App } from '../App';
import { clearResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import { backend, installation, json } from './fixtures';

afterEach(() => {
  cleanup(); clearResources(); clearWriteStates(); sessionStorage.clear();
  vi.restoreAllMocks(); vi.unstubAllGlobals();
});
const custom = { installation_id: 7, has_custom_standards: true, filename: 'current.md', version: 'v2', chunks: 3, uploaded_at: '2026-11-25T12:45:30+05:30' };
const second = { ...installation, id: 8, account_login: 'second-installation' };
const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
const settingsPath = '/settings/installation?installation_id=7';
const upload = () => screen.getByRole('button', { name: 'Upload standards' });
const choose = (input: HTMLElement, file: File) => fireEvent.change(input, { target: { files: [file] } });

function mockReads(response: (path: string, init: RequestInit) => Response | Promise<Response> | undefined) {
  const fetch = vi.fn(async (url: string, init: RequestInit) => response(new URL(url).pathname, init) ?? backend(url));
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

it('associates validation with the file field, replaces an invalid file and allows explicit cancellation', async () => {
  const fetch = mockReads(() => undefined);
  open(settingsPath);
  const input = await screen.findByLabelText('Custom coding standards');
  choose(input, new File(['example'], 'rules.txt'));
  expect(await screen.findByRole('alert')).toHaveTextContent('Choose a Markdown (.md) file.');
  expect(input).toHaveAccessibleDescription(/Markdown.*Choose a Markdown/);
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(upload()).toBeDisabled();
  choose(input, new File(['# Guidelines'], 'replacement.md'));
  await waitFor(() => expect(upload()).toBeEnabled());
  expect(screen.getByText('replacement.md')).toBeVisible();
  expect(screen.getByText(/12 bytes/)).toBeVisible();
  expect(input).not.toHaveAttribute('aria-invalid');
  fireEvent.click(screen.getByRole('button', { name: 'Clear file' }));
  expect(upload()).toBeDisabled();
  expect(input).toHaveFocus();
  expect(screen.queryByText('replacement.md')).toBeNull();
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});

it('ignores a validation result from a replaced file or a previous installation', async () => {
  const reads: FileReader[] = [];
  vi.spyOn(FileReader.prototype, 'readAsArrayBuffer').mockImplementation(function (this: FileReader) { reads.push(this); });
  const fetch = mockReads(path => path === '/installations' ? json([installation, second])
    : path === '/installations/8/settings' ? json({ installation_id: 8, review_mode: 'manual' })
    : path === '/installations/8/standards' ? json({ ...custom, installation_id: 8 }) : undefined);
  open(settingsPath);
  const input = await screen.findByLabelText('Custom coding standards');
  choose(input, new File(['first'], 'first.md'));
  choose(input, new File(['second'], 'second.md'));
  expect(upload()).toBeDisabled();
  await act(async () => reads[0].dispatchEvent(new Event('error')));
  expect(screen.queryByText('Unable to read standards file.')).toBeNull();
  fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '8' } });
  await screen.findByText('Custom standards: current.md');
  await act(async () => reads[1].dispatchEvent(new Event('error')));
  expect(screen.queryByText('second.md')).toBeNull();
  expect(screen.queryByText('Unable to read standards file.')).toBeNull();
  expect(upload()).toBeDisabled();
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});

it('focuses Cancel in the scoped reset dialog and restores focus without sending a DELETE', async () => {
  const fetch = mockReads(path => path === '/installations/7/standards' ? json(custom) : undefined);
  open(settingsPath);
  const trigger = await screen.findByRole('button', { name: 'Reset to defaults' });
  trigger.focus(); fireEvent.click(trigger);
  const dialog = screen.getByRole('dialog', { name: 'Reset coding standards?' });
  expect(dialog).toHaveAccessibleDescription(/owner.*every repository.*Earlier and running reviews/);
  expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus();
  fireEvent(dialog, new Event('cancel', { bubbles: true, cancelable: true }));
  expect(screen.queryByRole('dialog')).toBeNull();
  expect(trigger).toHaveFocus();
  expect(fetch.mock.calls.every(([, options]) => options.method === 'GET')).toBe(true);
});

it('keeps one pending upload, retains its file on uncertainty and requires an explicit reconciliation', async () => {
  let finish!: (response: Response) => void;
  const fetch = mockReads((path, options) => path === '/installations/7/standards' && options.method === 'POST'
    ? new Promise(resolve => { finish = resolve; }) : undefined);
  open(settingsPath);
  choose(await screen.findByLabelText('Custom coding standards'), new File(['# Rules'], 'rules.md'));
  await waitFor(() => expect(upload()).toBeEnabled());
  fireEvent.click(upload()); fireEvent.click(upload());
  expect(await screen.findByText('Uploading coding standards…')).toBeVisible();
  const writes = () => fetch.mock.calls.filter(([, options]) => options.method === 'POST');
  expect(writes()).toHaveLength(1);
  expect((writes()[0][1].body as FormData).get('file')).toBeInstanceOf(File);
  await act(async () => finish(json({ detail: 'Upload outcome unavailable' }, 503)));
  expect(await screen.findByText('Upload outcome unavailable')).toBeVisible();
  expect(screen.getByText('rules.md')).toBeVisible();
  expect(upload()).toBeDisabled();
  const retry = await screen.findByRole('button', { name: /allow an explicit retry/ });
  await waitFor(() => expect(retry).toBeEnabled());
  fireEvent.click(retry);
  expect(upload()).toBeEnabled();
  expect(writes()).toHaveLength(1);
});

it('does not associate a late confirmed upload with a newly selected scope', async () => {
  let finish!: (response: Response) => void;
  const fetch = mockReads((path, options) => {
    if (path === '/installations') return json([installation, second]);
    if (path === '/installations/7/standards' && options.method === 'POST') return new Promise(resolve => { finish = resolve; });
    if (path === '/installations/8/settings') return json({ installation_id: 8, review_mode: 'manual' });
    if (path === '/installations/8/standards') return json({ ...custom, installation_id: 8, filename: 'separate.md' });
  });
  open(settingsPath);
  choose(await screen.findByLabelText('Custom coding standards'), new File(['# Old'], 'old.md'));
  await waitFor(() => expect(upload()).toBeEnabled());
  fireEvent.click(upload());
  fireEvent.change(screen.getByLabelText('Installation'), { target: { value: '8' } });
  await screen.findByText('Custom standards: separate.md');
  await act(async () => finish(json({ ...custom, filename: 'old.md' })));
  expect(screen.queryByText(/Uploaded custom standards|old\.md/)).toBeNull();
  expect(upload()).toBeDisabled();
  expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST').map(([url]) => new URL(url).pathname)).toEqual(['/installations/7/standards']);
});
