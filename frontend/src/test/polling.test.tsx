import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearResources, useResource } from '../api/resources';
import { reviewPolling } from '../api/polling';
import { ApiError } from '../api/client';
import { review } from './fixtures';
beforeEach(() => { vi.useFakeTimers(); vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible'); });
afterEach(() => { cleanup(); clearResources(); vi.restoreAllMocks(); vi.useRealTimers(); });
const tick = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
describe('automatic progress updates', () => {
  it('does not show loading or fetch while a dependent query is disabled', async () => {
    const read = vi.fn().mockResolvedValue('loaded');
    const hook = renderHook(({ key }: { key: string | null }) => useResource(key, read), { initialProps: { key: null } as { key: string | null } });
    expect(hook.result.current.loading).toBe(false);
    expect(read).not.toHaveBeenCalled();
    hook.rerender({ key: 'enabled' }); await tick();
    expect(hook.result.current.data).toBe('loaded');
  });
  it('revalidates a cached terminal review when revisited after the cache TTL', async () => {
    const read = vi.fn().mockResolvedValue(review({ delivery_status: 'posted' }));
    const first = renderHook(() => useResource('revisit', read, reviewPolling())); await tick(); first.unmount();
    await tick(31000);
    renderHook(() => useResource('revisit', read, reviewPolling())); await tick();
    expect(read).toHaveBeenCalledTimes(2);
  });
  it('ignores an in-flight response after hiding and never overlaps requests', async () => {
    let resolve!: (value: ReturnType<typeof review>) => void;
    const pending = new Promise<ReturnType<typeof review>>(r => { resolve = r; });
    const read = vi.fn().mockReturnValueOnce(pending).mockResolvedValue(review({ status: 'running' }));
    const hook = renderHook(() => useResource('inflight', read, reviewPolling())); await tick(10000); expect(read).toHaveBeenCalledTimes(1);
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden'); act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { resolve(review({ summary: 'Obsolete response' })); await pending; }); expect(hook.result.current.data).toBeUndefined();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible'); act(() => document.dispatchEvent(new Event('visibilitychange'))); await tick(); expect(read).toHaveBeenCalledTimes(2);
  });
  it('deduplicates, waits five seconds, stops at terminal status, and cleans up', async () => {
    const read = vi.fn().mockResolvedValueOnce(review({ status: 'running' })).mockResolvedValue(review({ delivery_status: 'posted' }));
    const policy = reviewPolling();
    const a = renderHook(() => useResource('review', read, policy));
    const b = renderHook(() => useResource('review', read, policy));
    await tick(); expect(read).toHaveBeenCalledTimes(1);
    await tick(4999); expect(read).toHaveBeenCalledTimes(1);
    await tick(1); expect(read).toHaveBeenCalledTimes(2);
    await tick(120000); expect(read).toHaveBeenCalledTimes(2);
    a.unmount(); b.unmount(); expect(vi.getTimerCount()).toBe(0);
  });
  it('backs off 10/20/40/60 seconds then resets after success', async () => {
    const read = vi.fn().mockRejectedValueOnce(new ApiError(503, 'Unavailable')).mockRejectedValueOnce(new ApiError(503, 'Unavailable')).mockRejectedValueOnce(new ApiError(503, 'Unavailable')).mockRejectedValueOnce(new ApiError(503, 'Unavailable')).mockResolvedValue(review({ status: 'running' }));
    renderHook(() => useResource('backoff', read, reviewPolling()));
    await tick(); expect(read).toHaveBeenCalledTimes(1);
    for (const [delay, calls] of [[10000, 2], [20000, 3], [40000, 4], [60000, 5]]) { await tick(delay - 1); expect(read).toHaveBeenCalledTimes(calls - 1); await tick(1); expect(read).toHaveBeenCalledTimes(calls); }
    await tick(5000); expect(read).toHaveBeenCalledTimes(6);
  });
  it('pauses while hidden and resumes immediately without overlapping requests', async () => {
    const read = vi.fn().mockResolvedValue(review({ status: 'running' })); const policy = reviewPolling();
    renderHook(() => useResource('hidden', read, policy)); await tick();
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden');
    act(() => document.dispatchEvent(new Event('visibilitychange'))); await tick(60000); expect(read).toHaveBeenCalledTimes(1);
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
    act(() => document.dispatchEvent(new Event('visibilitychange'))); await tick(); expect(read).toHaveBeenCalledTimes(2);
  });
  it('honors Retry-After and stops on permission denial', async () => {
    const read = vi.fn().mockRejectedValueOnce(new ApiError(429, 'Slow down', 90000)).mockRejectedValue(new ApiError(403, 'Forbidden'));
    renderHook(() => useResource('permission', read, () => 5000)); await tick(); await tick(89999); expect(read).toHaveBeenCalledTimes(1); await tick(1); expect(read).toHaveBeenCalledTimes(2); await tick(120000); expect(read).toHaveBeenCalledTimes(2);
  });
  it('limits terminal delivery monitoring to three visible minutes', () => {
    const policy = reviewPolling(); const r = review();
    expect(policy(r, 100)).toBe(15000); expect(policy(r, 179999)).toBe(15000); expect(policy(r, 180100)).toBe(false);
    expect(policy(r, 0)).toBe(15000);
    expect(policy(review({ autofix: { ...r.autofix, status: 'creating' } }), 180100)).toBe(5000);
  });
});
