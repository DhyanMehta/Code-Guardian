import { useId, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, BookMarked, ExternalLink, GitBranch, Globe, Lock, RefreshCw, X } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { useResource } from '../api/resources';
import { endpoints } from '../api/endpoints';
import { appInstallUrl, repoUrl } from '../api/identity';
import type { Repository } from '../api/contracts';
import { SearchInput } from '../components/common/SearchInput';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { OnboardingEmptyState } from '../components/common/OnboardingEmptyState';
import { Button } from '../components/common/Button';
import { IconButton } from '../components/common/IconButton';
import { SectionCard } from '../components/common/SectionCard';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';

function githubRepositoryUrl(repository: Repository) {
  try {
    const url = new URL(repository.html_url);
    if (url.origin === 'https://github.com' && !url.username && !url.password &&
        !url.search && !url.hash &&
        decodeURIComponent(url.pathname).replace(/\/$/, '').toLowerCase() === '/' + repository.full_name.toLowerCase()) {
      return repository.html_url;
    }
  } catch {
    // The workspace link remains available even if GitHub did not supply a usable URL.
  }
  return undefined;
}

function RepositoryRow({ repository, installationId }: { repository: Repository; installationId: number }) {
  const github = githubRepositoryUrl(repository);
  const Visibility = repository.private ? Lock : Globe;

  return (
    <article className="grid min-w-0 gap-3 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4 sm:py-4">
      <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-1.5">
        <span className="grid size-8 place-items-center rounded-lg border border-divider bg-panel-raised text-fg-secondary sm:row-span-2 sm:size-9 sm:self-start">
          <BookMarked aria-hidden="true" className="size-4" />
        </span>
        <h2 className="text-row-title text-fg [overflow-wrap:anywhere] md:text-row-title-wide">{repository.full_name}</h2>
        <div className="col-span-2 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-meta text-fg-muted sm:col-span-1 sm:col-start-2 md:text-meta-wide">
          <span className="inline-flex items-center gap-1.5">
            <Visibility aria-hidden="true" className="size-3.5 shrink-0" />
            {repository.private ? 'Private' : 'Public'}
          </span>
          {repository.default_branch && (
            <span className="inline-flex min-w-0 max-w-full items-start gap-1.5" title="Default branch">
              <GitBranch aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span className="sr-only">Default branch </span>
              <code className="min-w-0 font-mono text-fg-secondary [overflow-wrap:anywhere]">{repository.default_branch}</code>
            </span>
          )}
          <span><span className="font-semibold tabular-nums text-fg-secondary">{repository.open_issues_count}</span> open issues and pull requests</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:justify-end">
        <Link
          to={repoUrl(installationId, repository.full_name)}
          aria-label={`View pull requests for ${repository.full_name}`}
          className="control-target control-focus inline-flex items-center justify-center gap-1.5 rounded-lg bg-action px-3 text-control text-action-foreground transition-colors hover:bg-action-hover md:text-control-wide"
        >
          View pull requests
          <ArrowRight aria-hidden="true" className="hidden size-4 shrink-0 sm:block" />
        </Link>
        {github && (
          <a
            href={github}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${repository.full_name} on GitHub (opens in a new tab)`}
            className="control-target control-focus inline-flex items-center justify-center gap-1.5 rounded-lg px-1 text-control text-fg-secondary transition-colors hover:bg-action-secondary-hover hover:text-fg sm:px-2 md:text-control-wide"
          >
            GitHub
            <ExternalLink aria-hidden="true" className="size-4 shrink-0" />
          </a>
        )}
      </div>
    </article>
  );
}

function RepositoryList({ installationId, userId }: { installationId: number; userId: number }) {
  const searchId = useId();
  const searchInput = useRef<HTMLInputElement>(null);
  const [search, setSearch] = useState('');
  const state = useResource(`u:${userId}:i:${installationId}:repos`, signal => endpoints.repos(installationId, signal));
  const query = search.trim().toLowerCase();
  const filtered = state.data?.filter(repository => repository.full_name.toLowerCase().includes(query));
  const count = filtered?.length ?? 0;

  function clearSearch() {
    setSearch('');
    searchInput.current?.focus();
  }

  return (
    <div className="space-y-3">
      <div data-workspace-toolbar className="space-y-1">
        <div className="flex min-w-0 flex-wrap items-end gap-x-3 gap-y-2">
          <div className="min-w-0 flex-1 sm:max-w-md">
            <label htmlFor={searchId} className="mb-1 block text-control text-fg-secondary">Search repositories</label>
            <SearchInput
              ref={searchInput}
              id={searchId}
              aria-label="Search repositories"
              placeholder="Filter by name…"
              className={search ? 'pr-14 [&::-webkit-search-cancel-button]:appearance-none' : ''}
              value={search}
              onChange={event => setSearch(event.target.value)}
              accessory={search ? <IconButton aria-label="Clear repository search" variant="quiet" size="sm" icon={<X />} onClick={clearSearch} /> : undefined}
            />
          </div>
          <Button variant="secondary" className="shrink-0 max-sm:px-0" onClick={state.refresh} aria-busy={state.loading || undefined} aria-label="Refresh repositories" title="Refresh repositories">
            <RefreshCw aria-hidden="true" className="size-4 shrink-0" />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>

        <div className="flex min-w-0 flex-wrap items-center gap-x-4">
          {state.data && <p role="status" className="text-meta font-medium text-fg-secondary md:text-meta-wide">
            {query ? `${count} of ${state.data.length} repositories` : `${count} ${count === 1 ? 'repository' : 'repositories'}`}
          </p>}
          <ScopedRefreshStatus sources={[{ ...state, label: 'Repositories', hasData: !!state.data }]} />
        </div>
      </div>

      {state.data?.length === 0 && (
        <SectionCard className="space-y-1">
          <h2 className="text-row-title text-fg">No accessible repositories</h2>
          <p className="text-support text-fg-muted">Update GitHub App access, then refresh this list.</p>
        </SectionCard>
      )}

      {!!state.data?.length && count === 0 && (
        <SectionCard className="space-y-2">
          <h2 className="text-row-title text-fg">No repositories match your search</h2>
          <Button variant="secondary" size="sm" onClick={clearSearch}>Clear search</Button>
        </SectionCard>
      )}

      {count > 0 && (
        <ul aria-label="Repositories" className="min-w-0 divide-y divide-divider rounded-xl border border-divider bg-panel">
          {filtered?.map(repository => (
            <li key={repository.id}><RepositoryRow repository={repository} installationId={installationId} /></li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RepoListPage() {
  const { user, loginWithGitHub } = useAuth();
  const { selected, installations } = useInstallation();
  const installUrl = appInstallUrl(import.meta.env.VITE_GITHUB_APP_SLUG || selected?.app_slug);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-x-5 gap-y-1 border-b border-divider pb-3">
        <div>
          <h1 className="text-page tracking-tight text-fg md:text-page-wide">Connected Repositories</h1>
          <p className="mt-1 text-support text-fg-muted">Repositories connected through your GitHub App.</p>
        </div>
        {installUrl && (
          <a
            className="control-target control-focus inline-flex max-w-full items-center gap-2 rounded-lg text-control text-link underline-offset-4 transition-colors hover:text-fg hover:underline md:text-control-wide"
            href={installUrl}
          >
            Update GitHub App access
            <ExternalLink aria-hidden="true" className="size-4 shrink-0" />
          </a>
        )}
      </header>

      <InstallationPicker showReviewMode showSettingsLink />

      {installations?.length === 0 && (
        <OnboardingEmptyState onContinue={() => void loginWithGitHub('/repos')} />
      )}
      {!!installations?.length && !selected && (
        <p className="text-support text-fg-muted">Choose an installation to see its repositories.</p>
      )}
      {user && selected && !selected.suspended && (
        <RepositoryList key={`${user.id}:${selected.id}`} installationId={selected.id} userId={user.id} />
      )}
    </div>
  );
}
