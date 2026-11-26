import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { useAuth, navigation, installationResumeKey } from '../context/AuthContext';
import { useResource } from '../api/resources';
import { endpoints } from '../api/endpoints';
import { positiveId } from '../api/identity';
import { Button } from '../components/common/Button';
import { EntryPanel, entryAlert, entryLink } from '../components/common/EntryPanel';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';
import { diagnosticError, diagnosticText } from '../components/reviews/diagnosticText';
export function OnboardingPage() {
  const {user,refreshInstallations} = useAuth();
  const [params] = useSearchParams();
  const action = params.get('setup_action');
  const updating = action === 'update';
  const cancelled = params.has('error') || action === 'cancel' || action === 'cancelled';
  const requestedId = positiveId(params.get('installation_id'));
  const returning = useRef(params.has('setup_action') || params.has('installation_id') || !!sessionStorage.getItem(`install-redirect:${user?.id}`));
  const [checking,setChecking] = useState(returning.current && !cancelled);
  const [error,setError] = useState<string | null>(null);
  const [checked,setChecked] = useState(false);
  const [verifiedId, setVerifiedId] = useState<number | null>(null);
  const refresh = async () => {
    setChecking(true); setError(null);
    setVerifiedId(null);
    try {
      const fresh = await refreshInstallations();
      sessionStorage.removeItem(installationResumeKey);
      if (updating && !cancelled) {
        const installation = fresh.installations.find(item => item.id === requestedId && !item.suspended);
        if (installation) setVerifiedId(installation.id);
        else setError('Couldn’t verify which installation was updated.');
      }
      setChecked(true);
    }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not refresh GitHub access. Try again.'); }
    finally { setChecking(false); }
  };
  useEffect(()=>{ if (returning.current && !cancelled) void refresh(); },[refreshInstallations, cancelled]);
  const state = useResource(user ? `u:${user.id}:installation-url` : null,endpoints.installationUrl);
  const url = state.data?.url;
  const safe = url && /^https:\/\/github\.com\/apps\/[A-Za-z0-9-]+\/installations\/new$/.test(url) ? url : null;
  useEffect(()=>{
    if (user && !cancelled && !returning.current && !user.installations.length && safe && !sessionStorage.getItem(`install-redirect:${user.id}`)) {
      sessionStorage.setItem(`install-redirect:${user.id}`,'1'); navigation.assign(safe);
    }
  },[user,safe,cancelled]);
  if (updating || cancelled) {
    if (!cancelled && !checking && verifiedId !== null && verifiedId === requestedId) {
      return <Navigate to={`/repos?installation_id=${verifiedId}`} replace />;
    }
    return (
      <EntryPanel title="Repository access">
        {checking && <p role="status" className="text-support text-fg-muted">Checking repository access…</p>}
        {cancelled && <p role="status" className="text-support text-fg-secondary">GitHub did not confirm the repository access update.</p>}
        {error && <p role="alert" className={entryAlert}>{diagnosticText(error)}</p>}
        <div className="flex flex-wrap gap-3">
          <Button disabled={checking} aria-busy={checking || undefined} onClick={() => void refresh()}>Refresh GitHub access</Button>
          <Link className={entryLink} to="/repos">View repositories</Link>
        </div>
      </EntryPanel>
    );
  }
  if (user?.installations.length && !checking && !error) return <Navigate to="/repos" replace/>;
  return <EntryPanel title="Choose repositories on GitHub">
    <p className="text-support text-fg-secondary">Install the CodeGuardian GitHub App on the account and repositories you want reviewed.</p>
    {checking && <p role="status" className="text-support text-fg-muted">Checking your GitHub installation access…</p>}
    {error && <p role="alert" className={entryAlert}>{diagnosticText(error)}</p>}
    {checked && !user?.installations.length && <p role="status" className="text-support text-fg-secondary">
      No accessible installation was found. If approval is required, ask your organization owner to approve the installation.
    </p>}
    {!safe && <ScopedRefreshStatus sources={[{ ...state, label: 'GitHub installation link', hasData: !!state.data, error: diagnosticError(state.error) }]} />}
    {url && !safe && <p role="alert" className={entryAlert}>The server returned an invalid installation URL.</p>}
    <p className="text-support text-fg-muted">Access refreshes when GitHub returns you here. You can also refresh if an owner approves access later.</p>
    <div className="flex flex-wrap gap-3">
      {safe && <a className="control-target control-focus inline-flex items-center rounded-lg bg-action px-3 text-control text-action-foreground hover:bg-action-hover"
        href={safe} onClick={() => sessionStorage.setItem(`install-redirect:${user?.id}`, '1')}>Choose repositories on GitHub</a>}
      <Button variant="secondary" disabled={checking} aria-busy={checking || undefined} onClick={() => void refresh()}>Refresh GitHub access</Button>
    </div>
  </EntryPanel>;
}
