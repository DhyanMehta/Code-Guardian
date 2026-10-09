import { describe, it, expect, vi, afterEach } from 'vitest';
import { safeReturnPath, positiveId, lookupHistory } from '../api/identity';
import { endpoints } from '../api/endpoints';
import type { ReviewEnvelope } from '../api/contracts';
afterEach(() => vi.restoreAllMocks());
describe('identity', () => {
  it('preserves safe deep links and rejects redirects outside the app', () => {
    expect(safeReturnPath('/reviews/9?installation_id=1#finding')).toBe('/reviews/9?installation_id=1#finding');
    for (const path of ['//evil.test', '/\\evil.test', 'https://evil.test', '/auth/callback?code=secret']) expect(safeReturnPath(path)).toBe('/repos');
    expect(positiveId('1abc')).toBeNull(); expect(positiveId('0')).toBeNull(); expect(positiveId('42')).toBe(42);
  });
  it('does not turn a bounded unresolved history lookup into no review', async () => {
    vi.spyOn(endpoints, 'reviews').mockResolvedValue({ items: [{ id: 1, pr_number: 2 }], total: 2000 } as ReviewEnvelope);
    const result = await lookupHistory(1, 'owner/repo', [9], new AbortController().signal);
    expect(endpoints.reviews).toHaveBeenCalledTimes(10);
    expect(result.exhausted).toBe(false); expect(result.latest[9]).toBeUndefined(); expect(result.items).toHaveLength(1);
  });
});
