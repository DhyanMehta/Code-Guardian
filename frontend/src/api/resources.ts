import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { ApiError, transient } from './client';

export type Snapshot<T> = { data?: T; error?: unknown; loading: boolean; updatedAt?: number; monitoringPaused?: boolean };
type Reader<T> = (signal: AbortSignal) => Promise<T>;
export type Interval<T> = (data: T, visibleMs: number) => number | false;
type Entry<T> = { snapshot: Snapshot<T>; read: Reader<T>; interval?: Interval<T>; listeners: Set<() => void>; timer?: ReturnType<typeof setTimeout>; controller?: AbortController; version: number; failures: number; retryAt: number; visibleMs: number; visibleSince?: number; stopped: boolean };
const entries = new Map<string, Entry<unknown>>();
const empty = { loading: true };
const idle = { loading: false };
const visible = () => document.visibilityState !== 'hidden' && navigator.onLine !== false;
const elapsed = (e: Entry<unknown>) => e.visibleMs + (e.visibleSince === undefined ? 0 : Date.now() - e.visibleSince);
function publish<T>(e: Entry<T>, patch: Partial<Snapshot<T>>) { e.snapshot = { ...e.snapshot, ...patch }; e.listeners.forEach(l => l()); }
function cancel<T>(e: Entry<T>) { clearTimeout(e.timer); e.version++; e.controller?.abort(); e.controller = undefined; if (e.visibleSince !== undefined) { e.visibleMs += Date.now() - e.visibleSince; e.visibleSince = undefined; } }
function schedule<T>(e: Entry<T>, ms: number) { clearTimeout(e.timer); if (e.listeners.size && visible()) e.timer = setTimeout(() => void fetchEntry(e), ms); }
async function fetchEntry<T>(e: Entry<T>) {
  if (!e.listeners.size || !visible() || e.controller || e.stopped) return;
  if (e.retryAt > Date.now()) { schedule(e, e.retryAt - Date.now()); return; }
  e.visibleSince ??= Date.now();
  const version = ++e.version; const controller = new AbortController(); e.controller = controller;
  publish(e, { loading: true });
  try {
    const data = await e.read(controller.signal);
    if (version !== e.version) return;
    e.failures = 0; e.retryAt = 0;
    const interval = e.interval?.(data, elapsed(e as Entry<unknown>));
    if (interval === false) e.stopped = true;
    publish(e, { data, error: undefined, loading: false, updatedAt: Date.now(), monitoringPaused: interval === false });
    if (typeof interval === 'number') schedule(e, interval);
  } catch (error) {
    if (version !== e.version || controller.signal.aborted) return;
    publish(e, { error, loading: false, ...(!transient(error) ? { data: undefined } : {}) });
    if (e.interval && transient(error)) {
      const ms = Math.max(Math.min(10_000 * 2 ** e.failures++, 60_000), error instanceof ApiError ? error.retryAfter : 0);
      e.retryAt = Date.now() + ms; schedule(e, ms);
    } else e.stopped = true;
  } finally { if (e.controller === controller) e.controller = undefined; }
}
function environmentChanged() {
  for (const e of entries.values()) {
    if (!e.listeners.size) continue;
    if (!visible()) { cancel(e); publish(e, { loading: false }); }
    else { e.visibleSince = Date.now(); if (!e.stopped && (e.interval || !e.snapshot.data)) void fetchEntry(e); }
  }
}
document.addEventListener('visibilitychange', environmentChanged);
window.addEventListener('online', environmentChanged);
window.addEventListener('offline', environmentChanged);
export function clearResources() { for (const e of entries.values()) { cancel(e); e.stopped = true; publish(e, { data: undefined, error: undefined, loading: false }); } entries.clear(); }
export function invalidateResources(prefix: string) { for (const [key, e] of entries) if (key.startsWith(prefix)) { cancel(e); e.stopped = false; e.snapshot = { ...e.snapshot, updatedAt: undefined }; if (e.listeners.size) void fetchEntry(e); } }
export function useResource<T>(key: string | null, read: Reader<T>, interval?: Interval<T>) {
  const reader = useRef(read); reader.current = read;
  const policy = useRef(interval); policy.current = interval;
  const entry = useCallback(() => {
    if (!key) return undefined;
    if (!entries.has(key)) entries.set(key, { snapshot: empty, read: s => reader.current(s), interval: interval ? (d, ms) => policy.current?.(d as T, ms) ?? false : undefined, listeners: new Set(), version: 0, failures: 0, retryAt: 0, visibleMs: 0, stopped: false });
    return entries.get(key) as Entry<T>;
  }, [key, !!interval]);
  const subscribe = useCallback((listener: () => void) => {
    const e = entry(); if (!e) return () => {};
    e.read = s => reader.current(s);
    e.interval = policy.current ? (d, ms) => policy.current?.(d, ms) ?? false : undefined;
    const firstSubscriber = e.listeners.size === 0;
    e.listeners.add(listener); e.visibleSince ??= visible() ? Date.now() : undefined;
    if (!e.snapshot.updatedAt || Date.now() - e.snapshot.updatedAt > 30_000) {
      // Terminal polling stops for the current visit, not forever in the cache.
      if (firstSubscriber) e.stopped = false;
      void fetchEntry(e);
    }
    else if (e.interval && !e.stopped) { const ms = e.interval(e.snapshot.data!, elapsed(e as Entry<unknown>)); if (typeof ms === 'number') schedule(e, ms); }
    return () => { e.listeners.delete(listener); if (!e.listeners.size) cancel(e); };
  }, [entry]);
  const getSnapshot = useCallback((): Snapshot<T> => entry()?.snapshot ?? idle, [entry]);
  const state = useSyncExternalStore(subscribe, getSnapshot);
  const refresh = useCallback(() => { const e = entry(); if (!e) return; e.stopped = false; e.failures = 0; e.visibleMs = 0; e.visibleSince = visible() ? Date.now() : undefined; void fetchEntry(e); }, [entry]);
  useEffect(() => { const e = entry(); if (e && !e.listeners.size) cancel(e); }, [entry]);
  return { ...state, refresh };
}
