import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ReviewProgress } from '../components/reviews/ReviewProgress';
import { clearResources } from '../api/resources';

afterEach(() => { cleanup(); clearResources(); vi.unstubAllGlobals(); });
it('explains a missing worker from the real 503 readiness contract and hides on completion', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'not_ready', checks: { database: 'ok', chromadb: 'ok', worker: 'unavailable', configuration: 'ok' } }), { status: 503 }));
  vi.stubGlobal('fetch', fetch);
  const view = render(<ReviewProgress status="pending" />);
  expect(await screen.findByText(/worker is unavailable or its heartbeat is stale/)).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(1);
  view.rerender(<ReviewProgress status="completed" />);
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
it('distinguishes an available busy worker from a transport failure', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'ready', checks: { database: 'ok', chromadb: 'ok', worker: 'ok', configuration: 'ok' } }))));
  const view = render(<ReviewProgress status="pending" />);
  expect(await screen.findByText(/waiting for its turn in the queue/)).toBeInTheDocument();
  view.unmount(); clearResources();
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
  render(<ReviewProgress status="running" />);
  await waitFor(() => expect(screen.getByText(/Cannot check worker availability/)).toBeInTheDocument());
});
