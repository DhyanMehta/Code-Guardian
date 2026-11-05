import { useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { GitPullRequest, Activity, Cpu, Sliders, FolderGit2, GitBranch, ArrowLeft } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { endpoints } from '../api/endpoints';
import { useResource } from '../api/resources';
import { ContextBar } from '../components/layout/ContextBar';
import { Tabs } from '../components/common/Tabs';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { AsyncState } from '../components/common/AsyncState';
import { PullsTab } from '../components/dashboard/PullsTab';
import { AnalyticsTab } from '../components/dashboard/AnalyticsTab';
import { AgentsTab } from '../components/dashboard/AgentsTab';
import { SettingsTab } from '../components/dashboard/SettingsTab';

const tabs = [
  { id: 'pulls', label: 'Pull Requests', icon: <GitPullRequest className="w-4 h-4 shrink-0" /> },
  { id: 'analytics', label: 'Code Health Analytics', icon: <Activity className="w-4 h-4 shrink-0" /> },
  { id: 'agents', label: 'Agent Fleet', icon: <Cpu className="w-4 h-4 shrink-0" /> },
  { id: 'settings', label: 'Settings', icon: <Sliders className="w-4 h-4 shrink-0" /> },
];

export function RepoDashboardPage() {
  const { owner = '', repo = '' } = useParams(); const [params, setParams] = useSearchParams();
  const { user } = useAuth(); const { selected } = useInstallation();
  const full = `${owner}/${repo}`;
  const active = tabs.some(t => t.id === params.get('tab')) ? params.get('tab')! : 'pulls';
  useEffect(() => {
    if ((params.has('tab') && params.get('tab') !== active) || (selected && !params.has('installation_id'))) setParams(previous => { const next = new URLSearchParams(previous); next.set('tab', active); if (selected) next.set('installation_id', String(selected.id)); return next; }, { replace: true });
  }, [active, selected, params, setParams]);
  const state = useResource(user && selected && !selected.suspended ? `u:${user.id}:i:${selected.id}:repos` : null, s => endpoints.repos(selected!.id, s));
  const repository = state.data?.find(r => r.full_name.toLowerCase() === full.toLowerCase());
  const scope = `u:${user?.id}:i:${selected?.id}:repo:${full}`;
  return (
    <div className="space-y-6">
      <div className="bg-neutral-900/60 border border-neutral-800/80 rounded-xl p-4 sm:p-5">
        <InstallationPicker />
      </div>

      {selected && !selected.suspended && (
        <div className="space-y-5">
          <AsyncState {...state} hasData={!!state.data} />

          {state.data && !repository && (
            <div className="p-4 rounded-xl bg-severity-medium-bg border border-severity-medium-border text-sm text-severity-medium font-medium">
              <p role="alert">Repository not found or access unavailable for this installation.</p>
            </div>
          )}

          {repository && user && (
            <div className="space-y-6">
              <ContextBar
                owner={owner}
                repo={repo}
                installationId={selected.id}
                defaultBranch={repository.default_branch}
                reviewMode={selected.review_mode}
              />

              <div className="flex flex-col lg:flex-row gap-6 items-start">
                {/* Repository Contextual Navigation Sidebar (Desktop) / Header (Mobile) */}
                <aside className="w-full lg:w-64 shrink-0 space-y-4">
                  {/* Repository Identity Card */}
                  <div className="rounded-xl border border-neutral-800/90 bg-neutral-900/80 p-4 space-y-3">
                    <div className="flex items-center gap-2 text-neutral-400 text-xs font-mono">
                      <FolderGit2 className="w-4 h-4 text-primary-400 shrink-0" />
                      <span className="truncate">{owner}</span>
                    </div>
                    <h1 className="text-lg font-bold font-mono text-neutral-100 break-all leading-tight">
                      {repo}
                    </h1>
                    <div className="flex flex-wrap items-center gap-2 pt-1">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-neutral-950 border border-neutral-800 text-[11px] font-mono text-neutral-300">
                        <GitBranch className="w-3 h-3 text-neutral-400" />
                        {repository.default_branch}
                      </span>
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-neutral-950 border border-neutral-800 text-[11px] font-mono text-neutral-300">
                        Mode: {selected.review_mode}
                      </span>
                    </div>
                  </div>

                  {/* Contextual Navigation (Tabs in Responsive Sidebar Mode) */}
                  <div className="rounded-xl border border-neutral-800/80 bg-neutral-900/40 p-2 lg:p-3">
                    <div className="hidden lg:block px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider text-neutral-400">
                      Repository Navigation
                    </div>
                    <Tabs
                      id="repository-tabs"
                      tabs={tabs}
                      activeTab={active}
                      variant="responsive"
                      onChange={tab =>
                        setParams(previous => {
                          const next = new URLSearchParams(previous);
                          next.set('tab', tab);
                          return next;
                        })
                      }
                    />
                  </div>

                  {/* Global Scope Shortcuts in Sidebar */}
                  <div className="hidden lg:block rounded-xl border border-neutral-800/60 bg-neutral-950/40 p-3 space-y-1 text-xs">
                    <div className="px-2 py-1 text-[11px] font-mono uppercase tracking-wider text-neutral-400">
                      Global Scope
                    </div>
                    <Link
                      to="/repos"
                      className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50 transition-colors"
                    >
                      <ArrowLeft className="w-3.5 h-3.5" />
                      <span>All Repositories</span>
                    </Link>
                    <Link
                      to="/profile"
                      className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50 transition-colors"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      <span>Profile & Policies</span>
                    </Link>
                  </div>
                </aside>

                {/* Main Tab Panel Area */}
                <div
                  role="tabpanel"
                  id={`repository-tabs-panel-${active}`}
                  aria-labelledby={`repository-tabs-tab-${active}`}
                  key={`${scope}:${active}`}
                  className="flex-1 min-w-0 w-full"
                >
                  {active === 'pulls' && <PullsTab scope={scope} installation={selected.id} repo={full} />}
                  {active === 'analytics' && <AnalyticsTab scope={scope} installation={selected.id} repo={full} />}
                  {active === 'agents' && <AgentsTab scope={scope} installation={selected.id} repo={full} />}
                  {active === 'settings' && <SettingsTab userId={user.id} installation={selected.id} />}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
