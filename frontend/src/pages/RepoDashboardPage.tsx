import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Navigate, useParams, useSearchParams } from 'react-router-dom';
import { Activity, Cpu, GitPullRequest } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';
import { endpoints } from '../api/endpoints';
import { useResource } from '../api/resources';
import { ContextBar } from '../components/layout/ContextBar';
import { Tabs } from '../components/common/Tabs';
import { AsyncState } from '../components/common/AsyncState';
import { PullsTab } from '../components/dashboard/PullsTab';
import { AnalyticsTab } from '../components/dashboard/AnalyticsTab';
import { AgentsTab } from '../components/dashboard/AgentsTab';
import { installationSettingsUrl } from '../api/identity';

const tabs = [
  { id: 'pulls', label: 'Pull Requests', icon: <GitPullRequest className="size-4 shrink-0" /> },
  { id: 'analytics', label: 'Analytics', icon: <Activity className="size-4 shrink-0" /> },
  { id: 'agents', label: 'Agent History', icon: <Cpu className="size-4 shrink-0" /> },
];
const navigationId = 'repository-tabs';
const wideNavigationQuery = '(min-width: 48rem)';

function RepositoryViews({ active, onChange, children }: { active: string; onChange: (tab: string) => void; children: ReactNode }) {
  const [wide, setWide] = useState(() => window.matchMedia?.(wideNavigationQuery).matches ?? true);
  const navigation = useRef<HTMLDivElement>(null);
  const restoreFocus = useRef(false);

  useEffect(() => {
    const media = window.matchMedia?.(wideNavigationQuery);
    if (!media) return;
    function resize(event: MediaQueryListEvent) {
      restoreFocus.current = navigation.current?.contains(document.activeElement) ?? false;
      setWide(event.matches);
    }
    media.addEventListener('change', resize);
    return () => media.removeEventListener('change', resize);
  }, []);

  useLayoutEffect(() => {
    if (!restoreFocus.current) return;
    restoreFocus.current = false;
    navigation.current?.querySelector<HTMLElement>('select, [role="tab"][aria-selected="true"]')?.focus({ preventScroll: true });
  }, [wide]);

  return (
    <>
      <div ref={navigation}>
        {wide ? (
          <Tabs id={navigationId} label="Repository views" tabs={tabs} activeTab={active} onChange={onChange} />
        ) : (
          <label className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 border-b border-divider pb-2 text-control text-fg-secondary">
            <span>Repository view</span>
            <select
              className="control-target control-focus min-w-0 max-w-full cursor-pointer rounded-lg border border-control-border bg-panel-inset px-2.5 py-1.5 text-control text-fg hover:border-link"
              value={active}
              aria-controls={`${navigationId}-panel-${active}`}
              onChange={event => onChange(event.target.value)}
            >
              {tabs.map(tab => <option key={tab.id} value={tab.id}>{tab.label}</option>)}
            </select>
          </label>
        )}
      </div>
      {tabs.map(tab => (wide || tab.id === active) && (
        <section
          key={tab.id}
          id={`${navigationId}-panel-${tab.id}`}
          role={wide ? 'tabpanel' : undefined}
          aria-labelledby={wide ? `${navigationId}-tab-${tab.id}` : undefined}
          aria-label={wide ? undefined : tab.label}
          hidden={tab.id !== active}
          tabIndex={wide && tab.id === active ? 0 : undefined}
          className="control-focus min-w-0 rounded-sm"
        >
          {tab.id === active && children}
        </section>
      ))}
    </>
  );
}

export function RepoDashboardPage() {
  const { owner = '', repo = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const { selected } = useInstallation();
  const full = `${owner}/${repo}`;
  const requestedTab = params.get('tab');
  const active = tabs.find(tab => tab.id === requestedTab)?.id ?? 'pulls';
  const installationId = params.get('installation_id') ?? selected?.id.toString();
  const repositoriesTo = installationId === undefined ? '/repos' : `/repos?${new URLSearchParams({ installation_id: installationId })}`;

  useEffect(() => {
    if (requestedTab === 'settings') return;
    if ((requestedTab !== null && requestedTab !== active) || (selected && !params.has('installation_id'))) {
      setParams(previous => {
        const next = new URLSearchParams(previous);
        next.set('tab', active);
        if (selected) next.set('installation_id', String(selected.id));
        return next;
      }, { replace: true });
    }
  }, [active, requestedTab, selected, params, setParams]);

  const state = useResource(user && selected && !selected.suspended ? `u:${user.id}:i:${selected.id}:repos` : null, s => endpoints.repos(selected!.id, s));
  const repository = state.data?.find(r => r.full_name.toLowerCase() === full.toLowerCase());
  const scope = `u:${user?.id}:i:${selected?.id}:repo:${full}`;
  const legacySettings = requestedTab === 'settings';
  const bookmarkScope = legacySettings && user && selected && !selected.suspended ? scope : null;
  const [checkedBookmark, setCheckedBookmark] = useState<string | null>(null);
  const refreshAccess = state.refresh;

  useEffect(() => {
    // A saved bookmark must recheck access even after a recent visit to this repository.
    // The resource coalesces this refresh with an ordinary in-flight repository read.
    if (bookmarkScope) refreshAccess();
    setCheckedBookmark(bookmarkScope);
  }, [bookmarkScope, refreshAccess]);

  function changeTab(tab: string) {
    if (active === tab) return;
    setParams(previous => {
      const next = new URLSearchParams(previous);
      next.set('tab', tab);
      return next;
    });
  }

  if (bookmarkScope && checkedBookmark === bookmarkScope && selected && repository && !state.loading && !state.error) {
    return <Navigate replace to={installationSettingsUrl(selected.id, params)} />;
  }

  return (
    <div className="space-y-2 sm:space-y-4">
      <ContextBar repositoriesTo={repositoriesTo} repository={repository} />

      {selected && !selected.suspended && (
        <AsyncState {...state} hasData={!!state.data} updatedAt={state.error ? state.updatedAt : undefined} />
      )}

      {state.data && !repository && (
        <p role="alert" className="rounded-lg border border-risk-medium/35 bg-risk-medium-bg p-3 text-support text-risk-medium">
          Repository not found or access unavailable for this installation.
        </p>
      )}

      {!legacySettings && repository && selected && user && (
        <RepositoryViews active={active} onChange={changeTab}>
          <div key={scope}>
            {active === 'pulls' && <PullsTab mode={selected.review_mode} scope={scope} installation={selected.id} repo={full} />}
            {active === 'analytics' && <AnalyticsTab scope={scope} installation={selected.id} repo={full} />}
            {active === 'agents' && <AgentsTab scope={scope} installation={selected.id} repo={full} />}
          </div>
        </RepositoryViews>
      )}
    </div>
  );
}
