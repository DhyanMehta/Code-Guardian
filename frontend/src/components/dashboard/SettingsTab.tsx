import { Link } from 'react-router-dom';
import { useState } from 'react';
import { endpoints } from '../../api/endpoints';
import { invalidateResources, useResource } from '../../api/resources';
import { useWrite } from '../../api/writes';
import { request, errorMessage } from '../../api/client';
import { parseStandardsUpload, parseStandardsReset } from '../../api/contracts';
import { useInstallation } from '../../context/InstallationContext';
import { AsyncState } from '../common/AsyncState';
import { WriteFeedback } from '../common/WriteFeedback';
import { Button } from '../common/Button';
import { panelClass } from '../reviews/ReviewPresentation';
export async function validateStandards(file: File) {
  if (!file.name.toLowerCase().endsWith('.md')) throw new Error('Choose a Markdown (.md) file.');
  if (file.size > 512 * 1024) throw new Error('Standards must be at most 512 KiB.');
  const bytes = await new Promise<ArrayBuffer>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result as ArrayBuffer); reader.onerror = () => reject(new Error('Unable to read standards file.')); reader.readAsArrayBuffer(file); });
  try { new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { throw new Error('Standards must contain valid UTF-8 text.'); }
}
export function SettingsTab({ userId, installation }: { userId: number; installation: number }) {
  const scope = `u:${userId}:i:${installation}`; const { selected } = useInstallation();
  const settings = useResource(`${scope}:settings`, s => endpoints.settings(installation, s));
  const standards = useResource(`${scope}:standards`, s => endpoints.standards(installation, s));
  const write = useWrite(`${scope}:settings-write`);
  const [file, setFile] = useState<File | null>(null), [validation, setValidation] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const admin = selected?.id === installation && selected.role === 'admin';
  const disabled = !admin || write.busy || write.uncertain;
  const refresh = () => { invalidateResources(`${scope}:`); invalidateResources(`u:${userId}:installations`); };
  const upload = async () => {
    if (!file) return; setValidation(null);
    try { await validateStandards(file); } catch (e) { setValidation(errorMessage(e)); return; }
    const body = new FormData(); body.append('file', file);
    await write.run(() => request(`/installations/${installation}/standards`, parseStandardsUpload, { method: 'POST', body }), refresh);
  };
  return <div className={panelClass}><h2 className="font-semibold">Installation settings</h2><p className="text-sm text-neutral-400">These settings apply to every repository under this installation.</p>
    {!admin && <p className="text-sm text-neutral-400">Installation administrators can change these settings. Server permission checks remain authoritative.</p>}
    <button className="text-primary-400 underline" onClick={refresh}>Refresh installation settings</button><AsyncState {...settings} hasData={!!settings.data} /><AsyncState {...standards} hasData={!!standards.data} />
    <p>Review automation is managed in <Link className="underline text-primary-400" to="/profile">Profile settings</Link> across all installations you administer.</p>
    {standards.data && <div className="text-sm space-y-2"><p>{standards.data.has_custom_standards ? `Custom standards: ${standards.data.filename}` : 'Default standards'}</p><p>Version: {standards.data.version ?? 'Default / not recorded'}</p><p>Chunks: {standards.data.chunks ?? 'Not recorded'}</p><p>Uploaded: {standards.data.uploaded_at ?? 'Not recorded'}</p><p className="text-neutral-400">Historical reviews retain the standards version used for their analysis.</p></div>}
    <label className="block text-sm space-y-2"><span>Custom coding standards (.md, UTF-8, at most 512 KiB)</span><input className="block" type="file" accept=".md" aria-label="Custom coding standards" disabled={disabled} onChange={e => { setFile(e.target.files?.[0] ?? null); setValidation(null); }} /></label>
    {validation && <p role="alert" className="text-severity-medium">{validation}</p>}
    <div className="flex gap-3"><Button disabled={disabled || !file} onClick={() => void upload()}>Upload standards</Button><Button variant="secondary" disabled={disabled || !standards.data?.has_custom_standards} onClick={() => setConfirmReset(true)}>Reset to defaults</Button></div>
    {confirmReset && <div role="group" aria-label="Confirm reset" className="space-y-2"><p>Reset custom standards for all repositories in this installation? Historical versions remain available to earlier reviews.</p><Button disabled={disabled} onClick={() => { setConfirmReset(false); void write.run(() => request(`/installations/${installation}/standards`, parseStandardsReset, { method: 'DELETE' }), refresh); }}>Confirm reset</Button><button className="ml-3 underline" onClick={() => setConfirmReset(false)}>Cancel</button></div>}
    {write.busy && <p role="status">Saving installation settings…</p>}<WriteFeedback {...write} />
  </div>;
}
