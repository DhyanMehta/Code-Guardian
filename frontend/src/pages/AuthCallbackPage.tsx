import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clearReturnPath, installationResumeKey, useAuth } from '../context/AuthContext';
import { errorMessage } from '../api/client';
import { Button } from '../components/common/Button';
import { EntryPanel, entryAlert } from '../components/common/EntryPanel';
import { diagnosticText } from '../components/reviews/diagnosticText';

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const original = useRef({ code: params.get('code'), state: params.get('state'), error: params.get('error'), installation: params.has('installation_id') || params.has('setup_action') });
  const { completeOAuth, loginWithGitHub, refreshSession, user, authError, isLoading, busy } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const issue = useRef<HTMLParagraphElement>(null);
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
      void completeOAuth(code, state).then(path => { if (active) { clearReturnPath(); navigate(path, { replace: true }); } }).catch(e => {
        if (!active) return;
        let message = diagnosticText(errorMessage(e));
        for (const value of [code, state]) {
          if (value && message.includes(value)) message = 'GitHub sign-in could not be verified. Start sign-in again.';
        }
        setError(message);
        setChecked(true);
      });
    }
    return () => { active = false; };
  }, [completeOAuth, refreshSession, navigate]);
  useEffect(() => {
    if (checked && user && !authError && original.current.installation && !original.current.error) navigate('/auth/install?setup_action=resume', { replace: true });
  }, [checked, user, authError, navigate]);
  useEffect(() => { if (checked) issue.current?.focus(); }, [checked]);
  if (!checked) return <EntryPanel title="GitHub sign-in">
    <p role="status" className="text-support text-fg-muted">Completing sign-in…</p>
  </EntryPanel>;
  return <EntryPanel title="Resume GitHub sign-in">
    <p ref={issue} tabIndex={-1} role="alert" className={`${entryAlert} control-focus`}>{diagnosticText(authError || error || 'Sign-in needs another check.')}</p>
    {isLoading && <p role="status" className="text-support text-fg-muted">Checking your sign-in…</p>}
    <div className="flex flex-wrap gap-3">
      {authError ? <Button variant="secondary" disabled={isLoading} onClick={() => void refreshSession()}>Retry session check</Button>
        : user ? <Button onClick={() => navigate('/auth/install?setup_action=resume', { replace: true })}>Continue with your current account ({user.github_login})</Button> : null}
      <Button variant={user || authError ? 'secondary' : 'primary'} disabled={busy || isLoading} onClick={() => void loginWithGitHub('/repos')}>Try signing in again</Button>
    </div>
  </EntryPanel>;
}
