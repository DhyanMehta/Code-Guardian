import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { clearReturnPath, useAuth } from '../context/AuthContext';
import { errorMessage } from '../api/client';
export function AuthCallbackPage() {
  const [params] = useSearchParams(); const navigate = useNavigate();
  const original = useRef({ code: params.get('code'), state: params.get('state'), error: params.get('error') });
  const { completeOAuth, loginWithGitHub } = useAuth();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    const { code, state, error: denied } = original.current;
    window.history.replaceState(window.history.state, '', window.location.pathname);
    if (denied || !code || !state) { setError(denied ? 'GitHub authorization was not completed.' : 'Invalid OAuth callback: missing code or state.'); return; }
    void completeOAuth(code, state).then(path => { if (active) { clearReturnPath(); navigate(path, { replace: true }); } }).catch(e => { if (active) setError(errorMessage(e)); });
    return () => { active = false; };
  }, [completeOAuth, navigate]);
  return error ? <div role="alert" className="space-y-3"><p>{error}</p><button className="underline" onClick={() => void loginWithGitHub('/repos')}>Try signing in again</button></div> : <p role="status">Completing sign-in…</p>;
}
