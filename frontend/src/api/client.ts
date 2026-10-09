import { ContractError } from './contracts';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080').replace(/\/$/, '');
export class ApiError extends Error {
  constructor(public status: number, message: string, public retryAfter = 0) { super(message); this.name = 'ApiError'; }
}
export const transient = (e: unknown) => e instanceof ApiError && (e.status === 0 || e.status === 429 || e.status >= 500);
export const errorMessage = (e: unknown) => e instanceof Error ? e.message : 'Request failed.';
export function delay(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
    if (signal?.aborted) abort(); else signal?.addEventListener('abort', abort, { once: true });
  });
}
interface Options { method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'; body?: unknown; signal?: AbortSignal; retries?: number; auth?: boolean; acceptedStatuses?: number[] }
export async function request<T>(path: string, decode: (v: unknown) => T, options: Options = {}): Promise<T> {
  const method = options.method || 'GET';
  const retries = options.retries ?? (method === 'GET' ? 2 : 0);
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    options.signal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(abort, method === 'GET' ? 15_000 : 120_000);
    try {
      const multipart = options.body instanceof FormData;
      const response = await fetch(`${API_BASE}${path}`, {
        method, credentials: 'include', signal: controller.signal,
        headers: options.body !== undefined && !multipart ? { 'Content-Type': 'application/json' } : undefined,
        body: options.body === undefined ? undefined : multipart ? options.body as FormData : JSON.stringify(options.body),
      });
      const text = await response.text();
      let data: unknown;
      try { data = text ? JSON.parse(text) : null; } catch { data = null; }
      if (!response.ok && !options.acceptedStatuses?.includes(response.status)) {
        if (response.status === 401 && options.auth !== false) window.dispatchEvent(new Event('codeguardian:unauthorized'));
        const detail = data && typeof data === 'object' && 'detail' in data ? data.detail : null;
        const message = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : `Request failed (${response.status}).`;
        const header = response.headers.get('Retry-After');
        const retryAfter = header ? Math.max(0, /^\d+(\.\d+)?$/.test(header) ? Number(header) * 1000 : Date.parse(header) - Date.now()) : 0;
        throw new ApiError(response.status, message, Number.isFinite(retryAfter) ? retryAfter : 0);
      }
      return decode(data);
    } catch (error) {
      if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      const e = error instanceof ApiError || error instanceof ContractError ? error : new ApiError(0, controller.signal.aborted ? 'Request timed out. Its outcome may still be pending.' : 'Network error. Check your connection.');
      if (method !== 'GET' || attempt >= retries || !transient(e)) throw e;
      await delay(Math.max(1000 * (attempt + 1), e instanceof ApiError ? e.retryAfter : 0), options.signal);
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener('abort', abort);
    }
  }
}
