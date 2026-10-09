import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, request } from '../api/client';
import { ContractError, parseAccepted, parseDecision } from '../api/contracts';
afterEach(() => vi.unstubAllGlobals());
describe('API transport and contracts', () => {
  it('sends cookies and validates numeric trigger identity', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'accepted', review_id: 9 }), { status: 202 }));
    vi.stubGlobal('fetch', fetch);
    expect(await request('/trigger', parseAccepted, { method: 'POST' })).toEqual({ status: 'accepted', review_id: 9 });
    expect(fetch.mock.calls[0][1]).toMatchObject({ credentials: 'include', method: 'POST' });
    expect(fetch.mock.calls[0][1].headers).toBeUndefined();
  });
  it('does not replay writes on ambiguous failure', async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError('offline')); vi.stubGlobal('fetch', fetch);
    await expect(request('/write', parseAccepted, { method: 'POST' })).rejects.toBeInstanceOf(ApiError);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('keeps decision IDs as strings and rejects incompatible contracts', () => {
    expect(parseDecision({ status: 'approved', review_id: '9' }).review_id).toBe('9');
    expect(() => parseDecision({ status: 'approved', review_id: 9 })).toThrow(ContractError);
    expect(() => parseAccepted({ status: 'completed', review_id: 9 })).toThrow(ContractError);
  });
  it('lets the browser supply multipart boundaries', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}')); vi.stubGlobal('fetch', fetch);
    const body = new FormData(); body.append('file', new Blob(['hello']), 'rules.md');
    await request('/upload', v => v, { method: 'POST', body });
    expect(fetch.mock.calls[0][1].body).toBe(body);
    expect(fetch.mock.calls[0][1].headers).toBeUndefined();
  });
});
