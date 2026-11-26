import { appInstallUrl } from '../../api/identity';
import { Button } from './Button';
import { entryLink } from './EntryPanel';
import { SectionCard } from './SectionCard';
export function OnboardingEmptyState({ slug, onContinue }: { slug?: string; onContinue?: () => void }) {
  const url = appInstallUrl(import.meta.env.VITE_GITHUB_APP_SLUG || slug);
  return <SectionCard className="max-w-[600px] space-y-3">
    <h2 className="text-section">Install the CodeGuardian GitHub App</h2>
    <p className="text-support text-fg-secondary">Choose your account and repositories on GitHub. After installation, continue with GitHub to refresh your access.</p>
    {url ? <a className={entryLink} href={url}>Install GitHub App / update repository access</a> : <p role="status" className="text-support text-fg-muted">GitHub App installation is unavailable: VITE_GITHUB_APP_SLUG is not configured.</p>}
    {onContinue && <div><Button variant="secondary" onClick={onContinue}>Continue with GitHub to refresh access</Button></div>}
  </SectionCard>;
}
