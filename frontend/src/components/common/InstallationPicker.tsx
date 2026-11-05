import { Building2 } from 'lucide-react';
import { useInstallation } from '../../context/InstallationContext';
import { AsyncState } from './AsyncState';

export function InstallationPicker() {
  const { installations, selected, select, loading, error, invalid, refresh } = useInstallation();
  return (
    <div className="space-y-3">
      <AsyncState loading={loading} error={error} hasData={!!installations} refresh={refresh} />

      {invalid && (
        <div className="bg-severity-medium-bg border border-severity-medium-border rounded-lg p-3 text-sm text-severity-medium font-medium">
          <p role="alert">This installation is unavailable. Select an accessible installation.</p>
        </div>
      )}

      {!!installations?.length && (
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <label className="flex items-center gap-3 text-sm font-medium text-neutral-300">
            <span className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-primary-400" />
              Installation
            </span>
            <select
              aria-label="Installation"
              className="bg-neutral-900 border border-neutral-700/80 hover:border-neutral-600 rounded-lg py-2 px-3 text-sm text-neutral-100 font-sans focus:outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-400/20 cursor-pointer transition-all duration-150"
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
        </div>
      )}

      {selected?.suspended && (
        <div className="bg-severity-critical-bg border border-severity-critical-border rounded-lg p-3 text-sm text-severity-critical-text font-medium">
          <p role="alert">This installation is suspended. Restore access on GitHub before continuing.</p>
        </div>
      )}
    </div>
  );
}
