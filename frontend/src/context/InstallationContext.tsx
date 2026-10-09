import { createContext, useContext, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { endpoints } from '../api/endpoints';
import { positiveId } from '../api/identity';
import { useResource } from '../api/resources';
import type { Installation } from '../api/contracts';
interface Selection { installations?: Installation[]; selected?: Installation; loading: boolean; error?: unknown; invalid: boolean; select: (id: number) => void; refresh: () => void }
const Context = createContext<Selection | undefined>(undefined);
export function InstallationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth(); const [params, setParams] = useSearchParams();
  const state = useResource(user ? `u:${user.id}:installations` : null, endpoints.installations);
  const explicit = params.get('installation_id');
  const saved = user ? sessionStorage.getItem(`codeguardian:installation:${user.id}`) : null;
  const selected = explicit !== null ? state.data?.find(i => i.id === positiveId(explicit)) : state.data?.length === 1 ? state.data[0] : state.data?.find(i => i.id === positiveId(saved));
  const select = (id: number) => {
    if (!user || !state.data?.some(i => i.id === id)) return;
    sessionStorage.setItem(`codeguardian:installation:${user.id}`, String(id));
    setParams(previous => { const next = new URLSearchParams(previous); next.set('installation_id', String(id)); return next; });
  };
  return <Context.Provider value={{ installations: state.data, selected, loading: state.loading, error: state.error, invalid: explicit !== null && !!state.data && !selected, select, refresh: state.refresh }}>{children}</Context.Provider>;
}
export function useInstallation() { const context = useContext(Context); if (!context) throw new Error('InstallationProvider required'); return context; }
