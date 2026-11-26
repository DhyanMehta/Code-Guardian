import { Link, Navigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { installationSettingsUrl } from '../api/identity';
import { InstallationPicker } from '../components/common/InstallationPicker';
import { SectionCard } from '../components/common/SectionCard';
import { SettingsTab } from '../components/dashboard/SettingsTab';
import { useAuth } from '../context/AuthContext';
import { useInstallation } from '../context/InstallationContext';

export function InstallationSettingsPage() {
  const { user } = useAuth();
  const { selected, installations, invalid } = useInstallation();
  const [params] = useSearchParams();
  const explicit = params.get('installation_id');
  if (explicit === null && selected) {
    return <Navigate replace to={installationSettingsUrl(selected.id, params)} />;
  }
  const repositoriesTo = explicit === null ? '/repos' : `/repos?${new URLSearchParams({ installation_id: explicit })}`;

  return (
    <div className="space-y-6">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <Link className="control-target control-focus inline-flex items-center gap-2 rounded-lg pr-2 text-control text-link hover:text-fg md:text-control-wide" to={repositoriesTo}>
          <ArrowLeft aria-hidden="true" className="size-4" />
          All repositories
        </Link>
        <InstallationPicker />
      </div>
      <header>
        <h1 className="text-page tracking-tight text-fg md:text-page-wide">Installation Settings</h1>
        <p className="mt-1 text-support text-fg-muted">Configuration applies to every repository in the selected GitHub installation.</p>
      </header>
      {user && selected && !selected.suspended && <>
        <SectionCard className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
          <div className="min-w-0 [overflow-wrap:anywhere]">
            <h2 className="text-row-title">{selected.account_login}</h2>
            <p className="text-support text-fg-secondary">
              {selected.role === 'admin' ? 'Administrator' : 'Member'} · Review mode {selected.review_mode === 'auto' ? 'Automatic' : 'Manual'}
            </p>
          </div>
          <Link className="control-target control-focus inline-flex items-center rounded-lg border border-control-border px-3 text-control text-link hover:bg-panel-raised"
            to={`/profile?installation_id=${selected.id}`}>Shared review automation</Link>
        </SectionCard>
        <SettingsTab key={`${user.id}:${selected.id}`} userId={user.id} installation={selected.id} />
      </>}
      {installations && !selected && !invalid && (
        <p className="text-support text-fg-secondary">
          {installations.length ? 'Select an installation to view its settings.' : 'You have no accessible installations.'}
        </p>
      )}
    </div>
  );
}
