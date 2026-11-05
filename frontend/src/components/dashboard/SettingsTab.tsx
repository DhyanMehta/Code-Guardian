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
  return (
    <div className="space-y-6">
      <div className={panelClass}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800/60">
          <div>
            <h2 className="font-semibold text-lg text-neutral-100">Installation settings</h2>
            <p className="text-xs text-neutral-400 mt-1">These settings apply to every repository under this installation.</p>
          </div>
          <button
            type="button"
            className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer self-start sm:self-auto"
            onClick={refresh}
          >
            Refresh installation settings
          </button>
        </div>

        {!admin && (
          <div className="p-3.5 rounded-lg bg-neutral-950/60 border border-neutral-800 text-xs text-neutral-400 leading-relaxed">
            Installation administrators can change these settings. Server permission checks remain authoritative.
          </div>
        )}

        <AsyncState {...settings} hasData={!!settings.data} />
        <AsyncState {...standards} hasData={!!standards.data} />

        <div className="p-3.5 rounded-lg bg-primary-950/20 border border-primary-500/20 text-xs text-neutral-300">
          <p>
            Review automation is managed in{' '}
            <Link className="underline text-primary-400 font-medium hover:text-primary-300" to="/profile">
              Profile settings
            </Link>{' '}
            across all installations you administer.
          </p>
        </div>

        {standards.data && (
          <div className="p-4 rounded-xl bg-neutral-950/60 border border-neutral-800/80 space-y-2 text-xs font-mono">
            <p className="font-semibold text-sm text-neutral-200">
              {standards.data.has_custom_standards ? `Custom standards: ${standards.data.filename}` : 'Default standards'}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-2 border-t border-neutral-800/60 text-neutral-400">
              <p>Version: {standards.data.version ?? 'Default / not recorded'}</p>
              <p>Chunks: {standards.data.chunks ?? 'Not recorded'}</p>
              <p>Uploaded: {standards.data.uploaded_at ?? 'Not recorded'}</p>
            </div>
            <p className="text-[11px] text-neutral-400 font-sans italic pt-1">
              Historical reviews retain the standards version used for their analysis.
            </p>
          </div>
        )}

        {/* File Upload Control */}
        <div className="space-y-3 pt-2">
          <label className="block text-sm space-y-2">
            <span className="font-medium text-neutral-200">
              Custom coding standards (.md, UTF-8, at most 512 KiB)
            </span>
            <input
              className="block w-full text-xs font-mono text-neutral-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border file:border-neutral-700 file:bg-neutral-800 file:text-xs file:font-medium file:text-neutral-200 hover:file:bg-neutral-750 file:cursor-pointer cursor-pointer border border-neutral-800 rounded-lg p-2 bg-neutral-950/40"
              type="file"
              accept=".md"
              aria-label="Custom coding standards"
              disabled={disabled}
              onChange={e => {
                setFile(e.target.files?.[0] ?? null);
                setValidation(null);
              }}
            />
          </label>

          {validation && (
            <div className="p-3 rounded-lg bg-severity-medium-bg border border-severity-medium-border">
              <p role="alert" className="text-xs text-severity-medium font-medium">
                {validation}
              </p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <Button disabled={disabled || !file} onClick={() => void upload()}>
              Upload standards
            </Button>
            <Button
              variant="secondary"
              disabled={disabled || !standards.data?.has_custom_standards}
              onClick={() => setConfirmReset(true)}
            >
              Reset to defaults
            </Button>
          </div>
        </div>

        {/* Confirmation Modal / Block */}
        {confirmReset && (
          <div
            role="group"
            aria-label="Confirm reset"
            className="p-4 rounded-xl bg-neutral-950/80 border border-severity-medium/40 space-y-3"
          >
            <p className="text-sm text-neutral-200 font-medium">
              Reset custom standards for all repositories in this installation? Historical versions remain available to earlier reviews.
            </p>
            <div className="flex items-center gap-3">
              <Button
                disabled={disabled}
                onClick={() => {
                  setConfirmReset(false);
                  void write.run(() => request(`/installations/${installation}/standards`, parseStandardsReset, { method: 'DELETE' }), refresh);
                }}
              >
                Confirm reset
              </Button>
              <button
                type="button"
                className="ml-3 text-xs font-mono text-neutral-400 hover:text-neutral-200 underline cursor-pointer"
                onClick={() => setConfirmReset(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {write.busy && (
          <div className="flex items-center gap-2 text-xs font-mono text-primary-400">
            <span className="w-3.5 h-3.5 border-2 border-primary-400 border-t-transparent rounded-full motion-safe:animate-spin" />
            <p role="status">Saving installation settings…</p>
          </div>
        )}

        <WriteFeedback {...write} />
      </div>
    </div>
  );
}
