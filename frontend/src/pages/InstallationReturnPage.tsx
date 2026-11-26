import { useAuth, installationResumeKey } from '../context/AuthContext';
import { OnboardingPage } from './OnboardingPage';
import { Button } from '../components/common/Button';
import { EntryPanel, entryAlert } from '../components/common/EntryPanel';
import { diagnosticText } from '../components/reviews/diagnosticText';

export function InstallationReturnPage() {
  const { user, isLoading, authError, busy, refreshSession, loginWithGitHub } = useAuth();
  if (isLoading) return <EntryPanel title="Repository access"><p role="status" className="text-support">Checking your sign-in…</p></EntryPanel>;
  if (authError) return <EntryPanel title="Check your GitHub session">
    <p role="alert" className={entryAlert}>{diagnosticText(authError)}</p>
    <Button variant="secondary" onClick={() => void refreshSession()}>Retry session check</Button>
  </EntryPanel>;
  if (user) return <OnboardingPage />;
  return <EntryPanel title="Sign in to verify repository access">
    <p className="text-support text-fg-secondary">Your session is missing or expired. Sign in to check your GitHub installation.</p>
    <Button disabled={busy} onClick={() => { sessionStorage.setItem(installationResumeKey, '1'); void loginWithGitHub('/repos'); }}>Sign in and continue setup</Button>
  </EntryPanel>;
}
