import { useEffect, useRef, useState } from 'react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { useAuth, navigation } from '../context/AuthContext';
import { useResource } from '../api/resources';
import { endpoints } from '../api/endpoints';
import { AsyncState } from '../components/common/AsyncState';
export function OnboardingPage() {
  const {user,refreshInstallations} = useAuth();
  const [params] = useSearchParams();
  const returning = useRef(params.has('setup_action') || params.has('installation_id') || !!sessionStorage.getItem(`install-redirect:${user?.id}`));
  const [checking,setChecking] = useState(returning.current);
  const [error,setError] = useState<string | null>(null);
  const [checked,setChecked] = useState(false);
  const refresh = async () => {
    setChecking(true); setError(null);
    try { await refreshInstallations(); setChecked(true); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not refresh GitHub access. Try again.'); }
    finally { setChecking(false); }
  };
  useEffect(()=>{ if (returning.current) void refresh(); },[refreshInstallations]);
  const state = useResource(user ? `u:${user.id}:installation-url` : null,endpoints.installationUrl);
  const url = state.data?.url;
  const safe = url && /^https:\/\/github\.com\/apps\/[A-Za-z0-9-]+\/installations\/new$/.test(url) ? url : null;
  useEffect(()=>{
    if (user && !returning.current && !user.installations.length && safe && !sessionStorage.getItem(`install-redirect:${user.id}`)) {
      sessionStorage.setItem(`install-redirect:${user.id}`,'1'); navigation.assign(safe);
    }
  },[user,safe]);
  if (user?.installations.length && !checking && !error) return <Navigate to="/repos" replace/>;
  return <section className="max-w-xl mx-auto rounded-xl border border-neutral-800 p-8 space-y-5"><p className="text-primary-400 text-sm">Connect your code · Step 2 of 2</p><h1 className="text-2xl font-bold">Choose repositories on GitHub</h1><p>Sign-in is complete. Install the CodeGuardian GitHub App on the account and repositories you want reviewed.</p><AsyncState {...state} hasData={!!state.data}/>{safe && <a className="inline-block rounded-md bg-neutral-100 text-neutral-950 px-4 py-2 hover:bg-white" href={safe} onClick={()=>sessionStorage.setItem(`install-redirect:${user?.id}`,'1')}>Choose repositories on GitHub</a>}{url && !safe && <p role="alert">The server returned an invalid installation URL.</p>}{checking && <p role="status">Checking your GitHub installation access…</p>}{error && <p role="alert">{error}</p>}{checked && !user?.installations.length && <p role="status">No accessible installation was found. If approval is required, ask your organization owner to approve the installation.</p>}<p className="text-sm text-neutral-400">If you cancelled, choose repositories again. Access refreshes automatically when GitHub returns you here. You can also check again below.</p><button className="underline disabled:opacity-50" disabled={checking} onClick={()=>void refresh()}>Refresh GitHub access</button></section>;
}
