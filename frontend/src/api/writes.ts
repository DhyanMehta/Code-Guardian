import { useCallback, useSyncExternalStore } from 'react';
import { ApiError, errorMessage } from './client';
import { ContractError } from './contracts';
type WriteState = { busy: boolean; error?: string; uncertain: boolean };
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
    publish(key, { busy: true, uncertain: false });
    try { const result = await operation(); publish(key, initial); return result; }
    catch (e) {
      const uncertain = e instanceof ContractError || e instanceof ApiError && (e.status === 0 || e.status >= 500);
      publish(key, { busy: false, uncertain, error: errorMessage(e) });
      return undefined;
    } finally { settled(); }
  }, [key]);
  return { ...state, run, reconcile };
}
export function clearWriteStates() { states.clear(); listeners.forEach(l => l()); }
