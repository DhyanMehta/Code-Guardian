import { ArrowLeft, GitBranch } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { Repository } from '../../api/contracts';
import { InstallationPicker } from '../common/InstallationPicker';

interface ContextBarProps {
  repositoriesTo: string;
  repository?: Pick<Repository, 'full_name' | 'default_branch'>;
}

export function ContextBar({ repositoriesTo, repository }: ContextBarProps) {
  return (
    <section aria-label="Repository context" className="min-w-0 space-y-2">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <Link
          to={repositoriesTo}
          className="control-target control-focus inline-flex items-center gap-2 rounded-lg pr-2 text-control md:text-control-wide text-link hover:text-fg"
        >
          <ArrowLeft aria-hidden="true" className="size-4 shrink-0" />
          All repositories
        </Link>
        <InstallationPicker showReviewMode showSettingsLink={!!repository} />
      </div>
      {repository && (
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="min-w-0 text-page md:text-page-wide tracking-tight text-fg [overflow-wrap:anywhere]">
            {repository.full_name}
          </h1>
          {repository.default_branch && (
            <p className="flex min-w-0 max-w-full items-center gap-1.5 text-meta md:text-meta-wide text-fg-muted">
              <GitBranch aria-hidden="true" className="size-4 shrink-0" />
              <span className="min-w-0 [overflow-wrap:anywhere]">Default branch <code className="font-mono text-fg-secondary">{repository.default_branch}</code></span>
            </p>
          )}
        </div>
      )}
    </section>
  );
}
