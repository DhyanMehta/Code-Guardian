import { appInstallUrl } from '../../api/identity';
export function OnboardingEmptyState({ slug, onContinue }: { slug?: string; onContinue?: () => void }) {
  const url = appInstallUrl(import.meta.env.VITE_GITHUB_APP_SLUG || slug);
  return <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-8 space-y-4 text-center">
    <h2 className="text-lg font-bold">Install the CodeGuardian GitHub App</h2>
    <p className="text-neutral-400">Choose your account and repositories on GitHub. After installation, continue with GitHub to refresh your access.</p>
    {url ? <a className="inline-block text-primary-400 underline" href={url}>Install GitHub App / update repository access</a> : <p role="status">GitHub App installation is unavailable: VITE_GITHUB_APP_SLUG is not configured.</p>}
    {onContinue && <div><button className="underline text-primary-400" onClick={onContinue}>Continue with GitHub to refresh access</button></div>}
  </div>;
}
