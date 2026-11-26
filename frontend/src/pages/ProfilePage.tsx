import { useState } from 'react';
import { request } from '../api/client';
import { parseProfileMode, type ReviewMode, type UserProfile } from '../api/contracts';
import { endpoints } from '../api/endpoints';
import { invalidateResources, useResource } from '../api/resources';
import { useWrite } from '../api/writes';
import { Button } from '../components/common/Button';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';
import { SectionCard } from '../components/common/SectionCard';
import { WriteFeedback } from '../components/common/WriteFeedback';
import { diagnosticError, diagnosticText } from '../components/reviews/diagnosticText';
import { useAuth } from '../context/AuthContext';

const modeLabels = { auto: 'Automatic', manual: 'Manual', mixed: 'Mixed' } as const;

function PolicyEditor({ user }: { user: UserProfile }) {
  const state = useResource(`u:${user.id}:profile-mode`, endpoints.profileMode);
  const write = useWrite(`u:${user.id}:profile-mode-write`);
  const [draft, setDraft] = useState<{ mode: ReviewMode; version: string } | null>(null);
  const [receipt, setReceipt] = useState<{ previousVersion: string; savedVersion: string; message: string } | null>(null);
  const current = state.data;
  const persisted = current?.review_mode;
  const mode = draft && draft.version === current?.version ? draft.mode : persisted === 'auto' || persisted === 'manual' ? persisted : '';
  const count = current?.installations.length ?? 0;
  const canApply = !!(current && count && mode && mode !== persisted && !write.busy && !write.uncertain && !state.loading && !state.error);
  const saved = receipt && current && [receipt.previousVersion, receipt.savedVersion].includes(current.version) ? receipt.message : null;

  const save = async () => {
    if (!canApply || !current || !mode) return;
    setReceipt(null);
    const result = await write.run(() => request('/profile/review-mode', parseProfileMode, {
      method: 'PATCH', body: { review_mode: mode, version: current.version },
    }), () => invalidateResources(`u:${user.id}:`));
    setDraft(null);
    if (result?.review_mode === 'auto' || result?.review_mode === 'manual') {
      const total = result.installations.length;
      setReceipt({
        previousVersion: current.version, savedVersion: result.version,
        message: `Saved ${modeLabels[result.review_mode]} for ${total} administered installation${total === 1 ? '' : 's'}.`,
      });
    }
  };

  const list = current?.installations ?? [];
  const installationRow = (item: typeof list[number]) => <li key={item.id} className="flex flex-wrap justify-between gap-x-3 border-b border-divider py-2 text-support">
    <span className="min-w-0 font-semibold [overflow-wrap:anywhere]">{item.account_login}</span>
    <span className="text-fg-muted">{modeLabels[item.review_mode]}</span>
  </li>;
  return <section aria-labelledby="shared-automation" className="space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
      <div>
        <h2 id="shared-automation" className="text-section md:text-section-wide">Review automation</h2>
        <p className="mt-1 text-support text-fg-muted">Shared policy for active GitHub installations you administer.</p>
        <ScopedRefreshStatus sources={[{ ...state, label: 'Review policy', hasData: !!current, error: diagnosticError(state.error) }]} />
      </div>
      <Button variant="secondary" aria-busy={state.loading || undefined} onClick={state.refresh}>Refresh review policy</Button>
    </header>

    {current && (count ? <>
      <div className="grid items-start gap-4 lg:grid-cols-[7fr_5fr]">
        <SectionCard className="space-y-3">
          <h3 className="text-row-title">Shared policy</h3>
          <p className="text-support">Current policy <strong>{persisted ? modeLabels[persisted] : 'Unavailable'}</strong></p>
          {persisted === 'mixed' && <p className="text-support text-status-degraded">Your installations currently use different modes. Choose one to apply across the list.</p>}
          <label htmlFor="draft-review-mode" className="block text-control">Review mode</label>
          <select id="draft-review-mode" aria-describedby="review-mode-help" disabled={write.busy || write.uncertain}
            value={mode} className="control-target control-focus w-full rounded-lg border border-control-border bg-panel-inset px-3 text-control sm:max-w-xs"
            onChange={event => {
              setReceipt(null);
              if (write.error) write.reconcile();
              setDraft({ mode: event.target.value as ReviewMode, version: current.version });
            }}>
            <option value="" disabled>Choose a mode</option>
            <option value="auto">Automatic</option>
            <option value="manual">Manual</option>
          </select>
          <div id="review-mode-help" className="space-y-1 text-support text-fg-secondary">
            <p><strong>Automatic</strong> queues a review for eligible new PR events.</p>
            <p><strong>Manual</strong> lets authorized users start a review from a pull request.</p>
          </div>
        </SectionCard>
        <SectionCard className="space-y-2">
          <h3 className="text-row-title">Affected installations ({count})</h3>
          <p className="text-support text-fg-muted">Current mode for each administered installation.</p>
          <ul aria-label="Affected installations">{list.slice(0, 5).map(installationRow)}</ul>
          {count > 5 && <details>
            <summary className="control-target control-focus w-fit cursor-pointer content-center rounded text-control text-link">Show {count - 5} more installations</summary>
            <ul aria-label="Additional affected installations">{list.slice(5).map(installationRow)}</ul>
          </details>}
        </SectionCard>
      </div>
      <SectionCard className="space-y-3">
        <p className="max-w-prose text-support text-fg-secondary">Applying this policy affects other users and all selected repositories in these installations. Queued reviews still finish. Newly connected installations keep their own policy until a later apply.</p>
        {mode && mode === persisted && <p className="text-support text-fg-muted">This mode is already applied to every affected installation.</p>}
        <Button disabled={!canApply} aria-busy={write.busy || undefined} onClick={() => void save()}>
          Apply to {count} {count === 1 ? 'installation' : 'installations'}
        </Button>
      </SectionCard>
    </> : <SectionCard><p className="text-support">You do not administer any active installations. Their administrators control review automation.</p></SectionCard>)}

    <WriteFeedback {...write} error={write.error && diagnosticText(write.error)} success={saved}
      canReconcile={!!current && !!state.updatedAt && !state.loading && !state.error} busyMessage="Saving shared policy…" />
  </section>;
}

export function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;
  return <div className="space-y-6 text-fg">
    <h1 className="text-page md:text-page-wide">Profile settings</h1>
    <SectionCard className="flex items-center gap-4">
      {user.avatar_url && <img src={user.avatar_url} alt="" className="size-12 shrink-0 rounded-full" />}
      <div className="min-w-0 [overflow-wrap:anywhere]">
        <h2 className="text-row-title">{user.github_login}</h2>
        <p className="text-support text-fg-muted">Signed in with GitHub</p>
      </div>
    </SectionCard>
    <PolicyEditor key={user.id} user={user} />
  </div>;
}
