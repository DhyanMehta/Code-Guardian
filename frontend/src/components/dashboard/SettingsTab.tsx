import { useRef, useState } from 'react';
import { ApiError, errorMessage, request } from '../../api/client';
import { ContractError, parseStandardsUpload, parseStandardsReset } from '../../api/contracts';
import { endpoints } from '../../api/endpoints';
import { invalidateResources, useResource } from '../../api/resources';
import { useWrite } from '../../api/writes';
import { useInstallation } from '../../context/InstallationContext';
import { Button } from '../common/Button';
import { ConfirmationDialog } from '../common/ConfirmationDialog';
import { FriendlyTimestamp } from '../common/FriendlyTimestamp';
import { ScopedRefreshStatus } from '../common/ScopedRefreshStatus';
import { SectionCard } from '../common/SectionCard';
import { WriteFeedback } from '../common/WriteFeedback';
import { diagnosticError, diagnosticText } from '../reviews/diagnosticText';

export async function validateStandards(file: File) {
  if (!file.name.toLowerCase().endsWith('.md')) throw new Error('Choose a Markdown (.md) file.');
  if (file.size > 512 * 1024) throw new Error('Standards must be at most 512 KiB.');
  const bytes = await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(new Error('Unable to read standards file.'));
    reader.readAsArrayBuffer(file);
  });
  try { new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
  catch { throw new Error('Standards must contain valid UTF-8 text.'); }
}

export function SettingsTab({ userId, installation }: { userId: number; installation: number }) {
  const scope = `u:${userId}:i:${installation}`;
  const { selected } = useInstallation();
  const settings = useResource(`${scope}:settings`, signal => endpoints.settings(installation, signal));
  const standards = useResource(`${scope}:standards`, signal => endpoints.standards(installation, signal));
  const write = useWrite(`${scope}:settings-write`);
  const [file, setFile] = useState<File | null>(null);
  const [validation, setValidation] = useState<{ pending: boolean; error?: string }>({ pending: false });
  const [confirmReset, setConfirmReset] = useState(false);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [operation, setOperation] = useState<'upload' | 'reset'>('upload');
  const fileInput = useRef<HTMLInputElement>(null);
  const resetTrigger = useRef<HTMLDivElement>(null);
  const statusHeading = useRef<HTMLHeadingElement>(null);
  const generation = useRef(0);

  const accessError = [settings.error, standards.error].find(error => error instanceof ApiError && [400, 403, 404].includes(error.status));
  const admin = selected?.id === installation && selected.role === 'admin';
  const disabled = !admin || write.busy || write.uncertain;
  const refresh = () => {
    invalidateResources(`${scope}:`);
    invalidateResources(`u:${userId}:installations`);
  };
  const selectFile = async (next: File | null) => {
    const attempt = ++generation.current;
    setFile(next);
    setReceipt(null);
    setValidation({ pending: !!next });
    if (!next) return;
    let error: string | undefined;
    try { await validateStandards(next); }
    catch (e) { error = errorMessage(e); }
    if (fileInput.current && attempt === generation.current) setValidation({ pending: false, error });
  };
  const clearFile = () => {
    if (fileInput.current) fileInput.current.value = '';
    void selectFile(null);
  };
  const upload = async () => {
    if (!file || disabled || validation.pending || validation.error || fileInput.current?.files?.[0] !== file) return;
    const input = fileInput.current;
    setReceipt(null);
    setOperation('upload');
    const body = new FormData();
    body.append('file', file);
    const result = await write.run(async () => {
      const saved = await request(`/installations/${installation}/standards`, parseStandardsUpload, { method: 'POST', body });
      if (saved.installation_id !== installation) throw new ContractError('Unexpected installation in the upload response.');
      return saved;
    }, refresh);
    if (result && fileInput.current === input) {
      clearFile();
      setReceipt(`Uploaded custom standards${result.filename ? ` · ${result.filename}` : ''}${result.version ? ` · version ${result.version}` : ''}.`);
      input?.focus();
    }
  };
  const reset = async () => {
    if (disabled || !standards.data?.has_custom_standards) return;
    setConfirmReset(false);
    setReceipt(null);
    setOperation('reset');
    const heading = statusHeading.current;
    const result = await write.run(async () => {
      const saved = await request(`/installations/${installation}/standards`, parseStandardsReset, { method: 'DELETE' });
      if (saved.installation_id !== installation) throw new ContractError('Unexpected installation in the reset response.');
      return saved;
    }, refresh);
    if (result && heading && statusHeading.current === heading) setReceipt('Reset confirmed. Default standards apply to subsequent reviews.');
  };
  const active = standards.data;
  const refreshStatus = <ScopedRefreshStatus sources={[
    { ...settings, label: 'Installation settings', hasData: !!settings.data, error: diagnosticError(settings.error) },
    { ...standards, label: 'Coding standards', hasData: !!standards.data, error: diagnosticError(standards.error) },
  ]} />;

  return <section className="min-w-0 space-y-4 text-fg" aria-labelledby="standards-heading">
    <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div>
        <h2 id="standards-heading" className="text-section md:text-section-wide">Coding standards</h2>
        {refreshStatus}
      </div>
      <Button variant="secondary" onClick={refresh}>Refresh installation settings</Button>
    </header>
    {!accessError && <>
      {!admin && <p className="rounded-lg border border-divider bg-panel-inset p-3 text-support text-fg-secondary">
        You have read-only access. An installation administrator can upload or reset standards.
      </p>}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <SectionCard className="space-y-3 [overflow-wrap:anywhere]">
          <h3 ref={statusHeading} tabIndex={-1} className="control-focus text-row-title">Active standards</h3>
          {active ? <>
            <p className="text-body font-semibold">
              {active.has_custom_standards ? active.filename ? `Custom standards: ${active.filename}` : 'Custom standards' : 'Default standards'}
            </p>
            {active.has_custom_standards && <FriendlyTimestamp kind="event" value={active.uploaded_at} label="Uploaded" />}
            <details>
              <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">Technical details</summary>
              <div className="space-y-1 text-support text-fg-secondary">
                {active.version !== null && <p>Version: {active.version}</p>}
                {active.chunks !== null && <p>Chunks: {active.chunks}</p>}
                {active.has_custom_standards && (active.filename === null || active.version === null || active.chunks === null) && <p>Some custom standards metadata is unavailable.</p>}
                <p>Historical reviews retain their recorded standards version. Running reviews keep their selected version.</p>
              </div>
            </details>
          </> : <p className="text-support text-fg-muted">{standards.loading ? 'Checking active standards…' : 'Active standards are unavailable.'}</p>}
          {active?.has_custom_standards && <div ref={resetTrigger} className="border-t border-divider pt-3">
            <Button variant="destructive" disabled={disabled} onClick={() => setConfirmReset(true)}>Reset to defaults</Button>
          </div>}
        </SectionCard>
        <SectionCard className="space-y-3">
          <h3 className="text-row-title">Upload custom standards</h3>
          <label htmlFor="standards-file" className="block text-control">Custom coding standards</label>
          <p id="standards-help" className="text-support text-fg-muted">Markdown (.md) · UTF-8 · up to 512 KiB</p>
          <input type="file" id="standards-file" ref={fileInput} accept=".md" disabled={disabled}
            aria-invalid={!!validation.error || undefined}
            aria-describedby={`standards-help${validation.error ? ' standards-error' : ''}`}
            className="control-focus block w-full min-w-0 rounded-lg border border-control-border bg-panel-inset p-1 text-control text-fg-secondary file:mr-2 file:min-h-11 file:rounded-md file:border-0 file:bg-action-secondary file:px-2 file:text-fg md:file:min-h-10 disabled:opacity-65"
            onChange={event => void selectFile(event.target.files?.[0] ?? null)} />
          {file && <div className="flex flex-wrap items-center gap-x-3 text-support">
            <p className="min-w-0 [overflow-wrap:anywhere]"><strong>{file.name}</strong> · {file.size.toLocaleString()} bytes</p>
            <Button variant="quiet" size="sm" disabled={disabled} onClick={() => { clearFile(); fileInput.current?.focus(); }}>Clear file</Button>
          </div>}
          {validation.pending && <p role="status" className="text-support text-fg-muted">Checking file…</p>}
          {validation.error && <p id="standards-error" role="alert" className="text-support text-risk-medium">{validation.error}</p>}
          <Button disabled={disabled || !file || validation.pending || !!validation.error} onClick={() => void upload()}>Upload standards</Button>
        </SectionCard>
      </div>
      {confirmReset && <ConfirmationDialog title="Reset coding standards?" confirmLabel="Confirm reset" disabled={disabled}
        onCancel={() => setConfirmReset(false)} onConfirm={() => void reset()}
        returnFocus={() => {
          const trigger = resetTrigger.current?.querySelector('button');
          if (trigger?.isConnected && !trigger.disabled) trigger.focus();
          else statusHeading.current?.focus();
        }}>
        <p>Resetting standards for <strong>{selected?.account_login}</strong> selects the defaults for subsequent reviews in every repository in this installation. Earlier and running reviews retain their recorded versions.</p>
      </ConfirmationDialog>}
      <WriteFeedback {...write} error={write.error && diagnosticText(write.error)}
        canReconcile={!!standards.data && !!standards.updatedAt && !standards.loading && !standards.error}
        success={receipt} busyMessage={operation === 'upload' ? 'Uploading coding standards…' : 'Resetting coding standards…'} />
    </>}
  </section>;
}
