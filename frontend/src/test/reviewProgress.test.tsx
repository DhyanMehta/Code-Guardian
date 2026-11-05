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

it('shows provider wait reasons without replacing the terminal agent outcome', async () => {
  const { AgentTimeline } = await import('../components/reviews/AgentTimeline');
  const { review } = await import('./fixtures');
  const { parseReview } = await import('../api/contracts');
  const common = { attempt: 1, agent: 'quality' as const, created_at: '2026-11-04T08:00:00Z' };
  const active = review({ attempt: 1, status: 'running', progress: [
    { ...common, id: 1, stage: 'agent', status: 'started' },
    { ...common, id: 2, stage: 'provider_token', status: 'started' },
  ] });
  const view = render(<AgentTimeline review={parseReview(active)} />);
  expect(screen.getByText('Waiting for token allowance')).toBeInTheDocument();
  view.rerender(<AgentTimeline review={parseReview({
    ...active, status: 'completed', progress: [
      ...active.progress, { ...common, id: 3, stage: 'agent', status: 'degraded' },
    ],
  })} />);
  expect(screen.queryByText('Waiting for token allowance')).not.toBeInTheDocument();
  expect(screen.getByText('Completed with limitations')).toBeInTheDocument();
});
