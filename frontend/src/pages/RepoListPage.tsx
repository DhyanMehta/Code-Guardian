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
  return (
    <div className="space-y-6">
      <header className="border-b border-neutral-800/80 pb-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-neutral-100">Connected Repositories</h1>
            <p className="text-sm text-neutral-400 mt-1">Repositories accessible to your GitHub App installation.</p>
          </div>
          {installUrl && (
            <a
              className="inline-flex items-center gap-1.5 text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-4 self-start sm:self-auto"
              href={installUrl}
            >
              Update GitHub App access
            </a>
          )}
        </div>
      </header>

      <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-xl p-4 sm:p-5">
        <InstallationPicker />
      </div>

      {installations?.length === 0 && (
        <OnboardingEmptyState onContinue={() => void loginWithGitHub('/repos')} />
      )}

      {selected && !selected.suspended && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-neutral-900/40 border border-neutral-800/60 rounded-xl p-3 sm:p-4">
            <div className="flex-1 max-w-md">
              <SearchInput
                aria-label="Search repositories"
                placeholder="Search repositories…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <button
                type="button"
                className="text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer font-medium"
                onClick={state.refresh}
              >
                Refresh repositories
              </button>
            </div>
          </div>

          <AsyncState {...state} hasData={!!state.data} />

          {state.data?.length === 0 && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center space-y-2">
              <p className="text-neutral-300 font-medium">No accessible repositories.</p>
              <p className="text-sm text-neutral-400">Update the GitHub App's repository selection, then refresh.</p>
            </div>
          )}

          {!!state.data?.length && !state.data.some(r => r.full_name.toLowerCase().includes(search.toLowerCase())) && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
              No repositories match your search.
            </div>
          )}

          <div className="grid gap-3">
            {state.data
              ?.filter(r => r.full_name.toLowerCase().includes(search.toLowerCase()))
              .map(r => (
                <article
                  key={r.id}
                  className="bg-neutral-900/80 hover:bg-neutral-850/80 border border-neutral-800 hover:border-neutral-700/80 rounded-xl p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all duration-150 shadow-2xs group"
                >
                  <div className="space-y-2">
                    <h2 className="flex items-center gap-2 font-mono font-semibold text-base">
                      {r.private ? (
                        <span className="p-1 rounded bg-neutral-800 text-neutral-400" title="Private repository">
                          <Lock size={14} aria-label="Private" />
                        </span>
                      ) : (
                        <span className="p-1 rounded bg-neutral-800 text-neutral-400" title="Public repository">
                          <Globe size={14} aria-label="Public" />
                        </span>
                      )}
                      <Link
                        className="text-neutral-100 group-hover:text-primary-400 transition-colors"
                        to={repoUrl(selected.id, r.full_name)}
                      >
                        {r.full_name}
                      </Link>
                    </h2>
                    <p className="text-xs text-neutral-400 flex flex-wrap items-center gap-2 font-mono">
                      <span className="inline-flex items-center gap-1 text-neutral-300">
                        <GitBranch size={13} className="text-neutral-500" />
                        {r.default_branch}
                      </span>
                      <span className="text-neutral-600">·</span>
                      <span>{r.open_issues_count} open issues / PRs</span>
                      <span className="text-neutral-600">·</span>
                      <span className="px-1.5 py-0.5 rounded text-[11px] bg-primary-500/10 text-primary-300 border border-primary-500/20">
                        {selected.review_mode}
                      </span>
                    </p>
                  </div>
                  <Link
                    className="inline-flex items-center gap-1.5 text-primary-400 hover:text-primary-300 font-medium text-sm self-start sm:self-center transition-colors group-hover:translate-x-0.5 motion-safe:transition-transform"
                    to={repoUrl(selected.id, r.full_name)}
                  >
                    View pull requests →
                  </Link>
                </article>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
