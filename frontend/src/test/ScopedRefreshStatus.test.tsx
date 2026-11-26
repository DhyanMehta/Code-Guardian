import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';

const firstTime = Date.parse('2026-11-24T20:15:00.256Z');
const secondTime = firstTime + 60_000;

function sources() {
  return [
    { label: 'Pull requests', hasData: true, loading: false, updatedAt: firstTime, refresh: vi.fn() },
    { label: 'Review history', hasData: true, loading: false, updatedAt: secondTime, refresh: vi.fn() },
  ];
}
afterEach(() => vi.restoreAllMocks());

it('uses the oldest applicable successful fetch and discloses each exact client time', () => {
  const { container } = render(<ScopedRefreshStatus sources={[
    ...sources(), { label: 'Other', applicable: false, loading: false, hasData: false, refresh: vi.fn() },
  ]} />);
  const summary = container.querySelector('summary')!;
  expect(within(summary).getByText(/Oldest successful fetch/)).toBeVisible();
  expect(summary.querySelector('time')).toHaveAttribute('datetime', new Date(firstTime).toISOString());
  fireEvent.click(summary);
  const history = screen.getByText(/Review history last fetched/).closest('summary')!;
  fireEvent.click(history);
  expect(screen.getByText(new Date(secondTime).toISOString())).toBeVisible();
  expect(screen.getByText('Other · Unavailable')).toBeVisible();
});

it('states which source is refreshing without announcing repeated polling or claiming success', () => {
  const [pulls, history] = sources();
  render(<ScopedRefreshStatus sources={[pulls, { ...history, loading: true }]} />);
  expect(screen.getByText('Refreshing review history…')).toBeVisible();
  expect(screen.queryByRole('status')).toBeNull();
  expect(screen.queryByText(/Oldest successful fetch/)).toBeNull();
});

it('announces initial loading and shows awaiting data when no fetch is recorded', () => {
  const pending = { label: 'Pull requests', loading: true, hasData: false, refresh: vi.fn() };
  const { rerender, container } = render(<ScopedRefreshStatus sources={[pending]} />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading pull requests…');
  rerender(<ScopedRefreshStatus sources={[{ ...pending, loading: false }]} />);
  expect(screen.getByText('Awaiting data')).toBeVisible();
  expect(container.querySelector('time')).toBeNull();
});

it.each([0, 1])('reports failure of source %i and retries only that source', index => {
  const current = sources();
  const failed = current[index];
  render(<ScopedRefreshStatus sources={current.map((source, i) => i === index ? { ...source, error: new Error('Temporarily unavailable') } : source)} />);
  expect(screen.getByRole('alert')).toHaveTextContent(`${failed.label} · Updates delayed. Temporarily unavailable`);
  expect(screen.queryByText(/Oldest successful fetch/)).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: `Retry ${failed.label.toLowerCase()}` }));
  expect(failed.refresh).toHaveBeenCalledTimes(1);
  expect(current[1 - index].refresh).not.toHaveBeenCalled();
});

it('shows paused polling and offline status while retaining the source fetch time', () => {
  const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  const current = { ...sources()[0], monitoringPaused: true };
  const { container } = render(<ScopedRefreshStatus sources={[current]} />);
  expect(screen.getByText('Updates paused for pull requests')).toBeVisible();
  online.mockReturnValue(false);
  act(() => window.dispatchEvent(new Event('offline')));
  expect(screen.getByText('Offline · updates paused')).toBeVisible();
  fireEvent.click(container.querySelector('summary')!);
  expect(screen.getByText(/Pull requests last fetched/)).toBeVisible();
});
