import { Building2, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';
import { installationSettingsUrl } from '../../api/identity';
import { useInstallation } from '../../context/InstallationContext';
import { AsyncState } from './AsyncState';

export function InstallationPicker({ showReviewMode = false, showSettingsLink = false }: { showReviewMode?: boolean; showSettingsLink?: boolean }) {
  const { installations, selected, select, loading, error, invalid, refresh } = useInstallation();
  const mode = selected?.review_mode === 'auto' ? 'Automatic' : selected?.review_mode === 'manual' ? 'Manual' : null;
  return (
    <div className="min-w-0 space-y-2">
      <AsyncState loading={loading} error={error} hasData={!!installations} refresh={refresh} />

      {invalid && (
        <div className="bg-risk-medium-bg border border-risk-medium/35 rounded-lg p-3 text-support text-risk-medium">
          <p role="alert">This installation is unavailable. Select an accessible installation.</p>
        </div>
      )}

      {!!installations?.length && (
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <label className="flex min-w-0 max-w-full flex-wrap items-center gap-x-2 gap-y-1 text-control md:text-control-wide text-fg-secondary">
            <span className="flex shrink-0 items-center gap-2">
              <Building2 aria-hidden="true" className="size-4 text-link" />
              Installation
            </span>
            <select
              className="control-target control-focus w-auto min-w-0 max-w-full rounded-lg border border-control-border bg-panel-inset px-2.5 py-1.5 text-control md:max-w-64 md:text-control-wide text-fg hover:border-link cursor-pointer transition-colors duration-100"
              value={selected?.id ?? ''}
              onChange={e => select(Number(e.target.value))}
            >
              <option value="" disabled>Select installation</option>
              {installations.map(i => (
                <option key={i.id} value={i.id}>
                  {i.account_login}{i.suspended ? ' (suspended)' : ''}
                </option>
              ))}
            </select>
          </label>
          {showReviewMode && mode && !selected?.suspended && (
            <p className="rounded-md bg-panel-raised px-2 py-1 text-meta md:text-meta-wide text-fg-secondary">
              Review mode <span className={showSettingsLink ? 'font-semibold text-fg max-[420px]:block' : 'font-semibold text-fg'}>{mode}</span>
            </p>
          )}
          {showSettingsLink && selected && !selected.suspended && (
            <Link to={installationSettingsUrl(selected.id)} className="control-target control-focus inline-flex items-center gap-2 rounded-lg bg-panel-raised px-3 text-control text-link hover:bg-action-secondary-hover max-[420px]:px-2 md:text-control-wide">
              <Settings aria-hidden="true" className="size-4 shrink-0 max-[420px]:hidden" />
              Installation Settings
            </Link>
          )}
        </div>
      )}

      {selected?.suspended && (
        <div className="bg-risk-critical-bg border border-risk-critical/35 rounded-lg p-3 text-support text-risk-critical">
          <p role="alert">This installation is suspended. Restore access on GitHub before continuing.</p>
        </div>
      )}
    </div>
  );
}
