import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clearReturnPath, installationResumeKey, useAuth } from '../context/AuthContext';
import { errorMessage } from '../api/client';

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const original = useRef({ code: params.get('code'), state: params.get('state'), error: params.get('error'), installation: params.has('installation_id') || params.has('setup_action') });
  const { completeOAuth, loginWithGitHub, refreshSession, user, authError, actionError, busy } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    let active = true;
    const { code, state, error: denied, installation } = original.current;
    window.history.replaceState(window.history.state, '', window.location.pathname);
    if (installation) sessionStorage.setItem(installationResumeKey, '1');
    if (denied || !code || !state) {
      setError(denied ? 'GitHub authorization was not completed.' : installation ? 'Repository selection returned without a complete sign-in response.' : 'This sign-in link is incomplete or has already been used.');
      // Installation parameters are navigation hints, never proof of identity.
      void refreshSession().then(() => { if (active) setChecked(true); });
    } else {
      void completeOAuth(code, state).then(path => { if (active) { clearReturnPath(); navigate(path, { replace: true }); } }).catch(e => { if (active) { setError(errorMessage(e)); setChecked(true); } });
    }
    return () => { active = false; };
  }, [completeOAuth, refreshSession, navigate]);
  useEffect(() => {
    if (checked && user && !authError && original.current.installation && !original.current.error) navigate('/auth/install?setup_action=resume', { replace: true });
  }, [checked, user, authError, navigate]);
  if (!checked) return <p role="status">Completing sign-in…</p>;
  return <div role="alert" className="space-y-3">
    <p>{authError || error}</p>
    {actionError && <p>{actionError}</p>}
    {authError ? <button className="underline" onClick={() => void refreshSession()}>Retry session check</button> : user ? <button className="underline" onClick={() => navigate('/auth/install?setup_action=resume', { replace: true })}>Continue with your current account ({user.github_login})</button> : null}
    <button className="underline" disabled={busy} onClick={() => void loginWithGitHub('/repos')}>Try signing in again</button>
  </div>;
}
