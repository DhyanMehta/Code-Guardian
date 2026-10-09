import { useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
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
const tabs = [{ id: 'pulls', label: 'Pull Requests' }, { id: 'analytics', label: 'Code Health Analytics' }, { id: 'agents', label: 'Agent Fleet' }, { id: 'settings', label: 'Settings' }];
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
  return <div className="space-y-5"><InstallationPicker />{selected && !selected.suspended && <><AsyncState {...state} hasData={!!state.data} />{state.data && !repository && <p role="alert">Repository not found or access unavailable for this installation.</p>}{repository && user && <><ContextBar owner={owner} repo={repo} installationId={selected.id} defaultBranch={repository.default_branch} reviewMode={selected.review_mode} /><h1 className="text-xl font-bold font-mono">{full}</h1><Tabs id="repository-tabs" tabs={tabs} activeTab={active} onChange={tab => setParams(previous => { const next = new URLSearchParams(previous); next.set('tab', tab); return next; })} /><div role="tabpanel" id={`repository-tabs-panel-${active}`} aria-labelledby={`repository-tabs-tab-${active}`} key={`${scope}:${active}`}>
      {active === 'pulls' && <PullsTab scope={scope} installation={selected.id} repo={full} />}
      {active === 'analytics' && <AnalyticsTab scope={scope} installation={selected.id} repo={full} />}
      {active === 'agents' && <AgentsTab scope={scope} installation={selected.id} repo={full} />}
      {active === 'settings' && <SettingsTab userId={user.id} installation={selected.id} />}
    </div></>}</>}</div>;
}
