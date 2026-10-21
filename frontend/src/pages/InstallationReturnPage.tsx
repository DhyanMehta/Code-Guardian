import { useAuth, installationResumeKey } from '../context/AuthContext';
import { OnboardingPage } from './OnboardingPage';

export function InstallationReturnPage() {
  const { user, isLoading, authError, actionError, busy, refreshSession, loginWithGitHub } = useAuth();
  if (isLoading) return <p role="status">Checking your sign-in…</p>;
  if (authError) return <div role="alert">{authError} <button onClick={() => void refreshSession()}>Retry session check</button></div>;
  if (user) return <OnboardingPage />;
  return <section className="space-y-3"><h1>Sign in to verify repository access</h1><p>Your session is missing or expired. Sign in to check your GitHub installation.</p>{actionError && <p role="alert">{actionError}</p>}<button disabled={busy} onClick={() => { sessionStorage.setItem(installationResumeKey, '1'); void loginWithGitHub('/repos'); }}>Sign in and continue setup</button></section>;
}
