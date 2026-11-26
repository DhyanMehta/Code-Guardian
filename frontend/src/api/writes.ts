import { useCallback, useSyncExternalStore } from 'react';
import { ApiError, errorMessage } from './client';
import { ContractError } from './contracts';
type WriteState = { busy: boolean; error?: string; errorStatus?: number; uncertain: boolean };
const initial: WriteState = { busy: false, uncertain: false };
const states = new Map<string, WriteState>(), listeners = new Set<() => void>();
const publish = (key: string, state: WriteState) => { states.set(key, state); listeners.forEach(l => l()); };
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function useWrite(key: string) {
  const get = useCallback(() => states.get(key) ?? initial, [key]);
  const state = useSyncExternalStore(subscribe, get);
  const reconcile = useCallback(() => { if (!states.get(key)?.busy) publish(key, initial); }, [key]);
  const run = useCallback(async <T,>(operation: () => Promise<T>, settled: () => void): Promise<T | undefined> => {
    if (states.get(key)?.busy || states.get(key)?.uncertain) return;
    const pending = { busy: true, uncertain: false };
    publish(key, pending);
    let result: T;
    try {
      result = await operation();
    }
    catch (e) {
      if (states.get(key) !== pending) return;
      const uncertain = e instanceof ContractError || e instanceof ApiError && (e.status === 0 || e.status >= 500);
      publish(key, { busy: false, uncertain, error: errorMessage(e), errorStatus: e instanceof ApiError ? e.status : undefined });
      settled();
      return undefined;
    }
    if (states.get(key) !== pending) return;
    publish(key, initial);
    settled();
    return result;
  }, [key]);
  return { ...state, run, reconcile };
}
export function clearWriteStates() { states.clear(); listeners.forEach(l => l()); }
