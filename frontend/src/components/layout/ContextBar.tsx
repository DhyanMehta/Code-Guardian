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
      className="w-full bg-neutral-950/70 border-b border-neutral-800/80 text-xs py-2.5 px-4 sm:px-6 backdrop-blur-xs"
    >
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3">
        {/* Breadcrumb */}
        <nav aria-label="Repository Breadcrumb" className="flex items-center gap-2 font-mono">
          <Link
            to="/repos"
            className="text-neutral-400 hover:text-primary-400 transition-colors flex items-center gap-1 hover:underline"
          >
            repos
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-neutral-600 shrink-0" aria-hidden="true" />
          <Link
            to={`/repos/${owner}/${repo}${installationId ? `?installation_id=${installationId}` : ''}`}
            className="text-neutral-100 hover:text-white font-semibold tracking-tight transition-colors"
          >
            {repoFullName}
          </Link>
          {pullNumber && (
            <>
              <ChevronRight className="w-3.5 h-3.5 text-neutral-600 shrink-0" aria-hidden="true" />
              <span className="text-primary-400 font-semibold px-1.5 py-0.5 rounded bg-primary-500/15 border border-primary-500/30">
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
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-neutral-900 border border-neutral-700/70 text-neutral-200 font-mono text-[11px] shadow-2xs"
            >
              <GitFork className="w-3 h-3 text-neutral-400" aria-hidden="true" />
              <span>{defaultBranch}</span>
            </span>
          )}

          {reviewMode && (
            <span
              title="Review execution mode"
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-primary-950/40 border border-primary-500/30 text-primary-300 font-mono text-[11px] shadow-2xs"
            >
              <Sliders className="w-3 h-3 text-primary-400" aria-hidden="true" />
              <span>mode: {reviewMode}</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
