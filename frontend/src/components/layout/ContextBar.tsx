import React from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, GitFork, Sliders } from 'lucide-react';
import { ReviewMode } from '../../types';

export interface ContextBarProps {
  owner: string;
  repo: string;
  reviewMode?: ReviewMode;
  defaultBranch?: string;
  pullNumber?: number;
  installationId?: number;
}

export const ContextBar: React.FC<ContextBarProps> = ({
  owner,
  repo,
  reviewMode,
  defaultBranch,
  pullNumber,
  installationId,
}) => {
  const repoFullName = `${owner}/${repo}`;

  return (
    <div
      id="repo-context-bar"
      className="w-full bg-neutral-900/60 border-b border-neutral-800 text-xs py-2 px-4 sm:px-6"
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        {/* Breadcrumb */}
        <nav aria-label="Repository Breadcrumb" className="flex items-center gap-1.5 font-mono">
          <Link
            to="/repos"
            className="text-neutral-400 hover:text-neutral-200 transition-colors"
          >
            repos
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-neutral-600" aria-hidden="true" />
          <Link
            to={`/repos/${owner}/${repo}${installationId ? `?installation_id=${installationId}` : ''}`}
            className="text-neutral-200 hover:text-white font-medium transition-colors"
          >
            {repoFullName}
          </Link>
          {pullNumber && (
            <>
              <ChevronRight className="w-3.5 h-3.5 text-neutral-600" aria-hidden="true" />
              <span className="text-primary-400 font-semibold">
                pulls #{pullNumber}
              </span>
            </>
          )}
        </nav>

        {/* Real Status Chips Only (No fabricated badges) */}
        <div className="flex items-center gap-2">
          {defaultBranch && (
            <span
              title="Default branch"
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-neutral-800/80 border border-neutral-700/60 text-neutral-300 font-mono text-[11px]"
            >
              <GitFork className="w-3 h-3 text-neutral-400" aria-hidden="true" />
              <span>{defaultBranch}</span>
            </span>
          )}

          {reviewMode && (
            <span
              title="Review execution mode"
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-neutral-800/80 border border-neutral-700/60 text-neutral-300 font-mono text-[11px]"
            >
              <Sliders className="w-3 h-3 text-neutral-400" aria-hidden="true" />
              <span>mode: {reviewMode}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
