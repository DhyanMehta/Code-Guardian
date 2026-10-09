import { useState } from 'react';
import { Link } from 'react-router-dom';
import { GitBranch, Lock, Globe } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { useResource } from '../api/resources';
import { endpoints } from '../api/endpoints';
import { appInstallUrl, repoUrl } from '../api/identity';
import { SearchInput } from '../components/common/SearchInput';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { OnboardingEmptyState } from '../components/common/OnboardingEmptyState';
import { AsyncState } from '../components/common/AsyncState';
export function RepoListPage() {
  const { user, loginWithGitHub } = useAuth(); const { selected, installations } = useInstallation();
  const [search, setSearch] = useState('');
  const state = useResource(user && selected && !selected.suspended ? `u:${user.id}:i:${selected.id}:repos` : null, s => endpoints.repos(selected!.id, s));
  const installUrl = appInstallUrl(import.meta.env.VITE_GITHUB_APP_SLUG || selected?.app_slug);
  return <div className="space-y-6"><header className="border-b border-neutral-800 pb-4"><h1 className="text-xl font-bold">Connected Repositories</h1><p className="text-sm text-neutral-400">Repositories accessible to your GitHub App installation.</p></header><InstallationPicker />
    {installations?.length === 0 && <OnboardingEmptyState onContinue={() => void loginWithGitHub('/repos')} />}
    {selected && !selected.suspended && <><div className="flex flex-wrap items-center gap-4"><SearchInput aria-label="Search repositories" placeholder="Search repositories…" value={search} onChange={e => setSearch(e.target.value)} /><button className="text-primary-400 underline" onClick={state.refresh}>Refresh repositories</button>{installUrl && <a className="text-primary-400 underline" href={installUrl}>Update GitHub App access</a>}</div>
      <AsyncState {...state} hasData={!!state.data} />
      {state.data?.length === 0 && <p>No accessible repositories. Update the GitHub App's repository selection, then refresh.</p>}
      {!!state.data?.length && !state.data.some(r => r.full_name.toLowerCase().includes(search.toLowerCase())) && <p>No repositories match your search.</p>}
      <div className="space-y-2">{state.data?.filter(r => r.full_name.toLowerCase().includes(search.toLowerCase())).map(r => <article key={r.id} className="bg-neutral-900 border border-neutral-800 rounded-lg p-4 flex justify-between gap-4"><div><h2 className="flex items-center gap-2 font-mono font-semibold">{r.private ? <Lock size={16} aria-label="Private" /> : <Globe size={16} aria-label="Public" />}<Link className="hover:text-primary-400" to={repoUrl(selected.id, r.full_name)}>{r.full_name}</Link></h2><p className="text-xs text-neutral-400 flex items-center gap-2 mt-2"><GitBranch size={12} />{r.default_branch} · {r.open_issues_count} open issues / PRs · {selected.review_mode}</p></div><Link className="text-primary-400 text-sm self-center" to={repoUrl(selected.id, r.full_name)}>View pull requests →</Link></article>)}</div></>}
  </div>;
}
