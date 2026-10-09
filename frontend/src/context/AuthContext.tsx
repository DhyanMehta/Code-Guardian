import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, errorMessage, request } from '../api/client';
import { parse, parseCallback, parseLogout, parseUser, shape, string, type UserProfile } from '../api/contracts';
import { safeReturnPath } from '../api/identity';
import { clearResources, invalidateResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
const returnKey = 'codeguardian:return-to';
const exchanges = new Map<string, Promise<UserProfile>>();
export const navigation = { assign: (url: string) => window.location.assign(url) };
interface AuthContextType {
  user: UserProfile | null; isAuthenticated: boolean; isLoading: boolean;
  authError: string | null; actionError: string | null; busy: boolean;
  refreshSession: () => Promise<void>;
  refreshInstallations: () => Promise<UserProfile>;
  loginWithGitHub: (returnTo?: string) => Promise<void>;
  logout: () => Promise<void>;
  completeOAuth: (code: string, state: string) => Promise<string>;
}
const AuthContext = createContext<AuthContextType | undefined>(undefined);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const generation = useRef(0), action = useRef(false), userId = useRef<number | null>(null);
  const accept = useCallback((next: UserProfile | null) => {
    if (userId.current !== (next?.id ?? null)) { clearResources(); clearWriteStates(); }
    userId.current = next?.id ?? null; setUser(next);
  }, []);
  const refreshSession = useCallback(async () => {
    const ticket = ++generation.current; setLoading(true); setAuthError(null);
    try { const next = await request('/auth/me', parseUser, { auth: false }); if (ticket === generation.current) accept(next); }
    catch (e) { if (ticket === generation.current) { if (e instanceof ApiError && e.status === 401) accept(null); else setAuthError(errorMessage(e)); } }
    finally { if (ticket === generation.current) setLoading(false); }
  }, [accept]);
  useEffect(() => {
    if (window.location.pathname !== '/auth/callback') void refreshSession();
    const expire = () => { generation.current++; accept(null); setLoading(false); setAuthError(null); setActionError('Session expired. Sign in again.'); };
    window.addEventListener('codeguardian:unauthorized', expire);
    return () => { generation.current++; window.removeEventListener('codeguardian:unauthorized', expire); };
  }, [refreshSession, accept]);
  const loginWithGitHub = useCallback(async (returnTo?: string) => {
    if (action.current) return;
    action.current = true; setBusy(true); setActionError(null);
    try {
      sessionStorage.setItem(returnKey, safeReturnPath(returnTo ?? (window.location.pathname === '/' ? '/repos' : window.location.pathname + window.location.search + window.location.hash)));
      const data = await request('/auth/github/login', parse<{ url: string }>(shape({ url: string })), { auth: false, retries: 0 });
      const url = new URL(data.url);
      if (url.protocol !== 'https:' || url.hostname !== 'github.com') throw new Error('Invalid GitHub authorization URL.');
      navigation.assign(url.href);
    } catch (e) { setActionError(errorMessage(e)); }
    finally { action.current = false; setBusy(false); }
  }, []);
  const completeOAuth = useCallback(async (code: string, state: string) => {
    const ticket = ++generation.current; setLoading(true); setAuthError(null);
    const key = `${code}:${state}`;
    // Keep the settled promise too: remounting must not replay a single-use code.
    if (!exchanges.has(key)) exchanges.set(key, (async () => {
      await request('/auth/github/callback', parseCallback, { method: 'POST', body: { code, state }, auth: false });
      return request('/auth/me', parseUser, { auth: false });
    })());
    try { const next = await exchanges.get(key)!; if (ticket === generation.current) { accept(next); invalidateResources(`u:${next.id}:`); } return next.installations.length ? safeReturnPath(sessionStorage.getItem(returnKey)) : '/auth/install'; }
    catch (e) { if (ticket === generation.current) { accept(null); setAuthError(errorMessage(e)); } throw e; }
    finally { if (ticket === generation.current) setLoading(false); }
  }, [accept]);
  const logout = useCallback(async () => {
    if (action.current) return;
    action.current = true; setBusy(true); setActionError(null);
    try { await request('/auth/logout', parseLogout, { method: 'POST' }); generation.current++; accept(null); exchanges.clear(); sessionStorage.removeItem(returnKey); }
    catch (e) { setActionError(`Sign out was not confirmed: ${errorMessage(e)}`); }
    finally { action.current = false; setBusy(false); }
  }, [accept]);
  const sync = useRef<Promise<UserProfile> | null>(null);
  const refreshInstallations = useCallback(() => {
    if (!sync.current) {
      const ticket = generation.current;
      sync.current = request('/auth/installations/refresh', parseUser, {method:'POST'}).then(next => {
        if (ticket === generation.current && userId.current === next.id) {
          accept(next); invalidateResources(`u:${next.id}:`);
        }
        return next;
      }).finally(() => { sync.current = null; });
    }
    return sync.current;
  }, [accept]);
  return <AuthContext.Provider value={{ user, isAuthenticated: !!user, isLoading, authError, actionError, busy, refreshSession, refreshInstallations, loginWithGitHub, logout, completeOAuth }}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be used within an AuthProvider'); return value; }
export function clearReturnPath() { sessionStorage.removeItem(returnKey); }
