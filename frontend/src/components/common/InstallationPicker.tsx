import { useInstallation } from '../../context/InstallationContext';
import { AsyncState } from './AsyncState';
export function InstallationPicker() {
  const { installations, selected, select, loading, error, invalid, refresh } = useInstallation();
  return <div className="space-y-2"><AsyncState loading={loading} error={error} hasData={!!installations} refresh={refresh} />
    {invalid && <p role="alert">This installation is unavailable. Select an accessible installation.</p>}
    {!!installations?.length && <label className="flex items-center gap-3 text-sm text-neutral-300">Installation<select aria-label="Installation" className="bg-neutral-900 border border-neutral-700 rounded-md p-2" value={selected?.id ?? ''} onChange={e => select(Number(e.target.value))}><option value="" disabled>Select installation</option>{installations.map(i => <option key={i.id} value={i.id}>{i.account_login}{i.suspended ? ' (suspended)' : ''}</option>)}</select></label>}
    {selected?.suspended && <p role="alert">This installation is suspended. Restore access on GitHub before continuing.</p>}
  </div>;
}
