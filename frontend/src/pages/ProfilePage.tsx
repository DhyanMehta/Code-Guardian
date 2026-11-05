import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { endpoints } from '../api/endpoints';
import { request } from '../api/client';
import { parseProfileMode, type ReviewMode } from '../api/contracts';
import { invalidateResources, useResource } from '../api/resources';
import { useWrite } from '../api/writes';
import { AsyncState } from '../components/common/AsyncState';
import { WriteFeedback } from '../components/common/WriteFeedback';
import { Button } from '../components/common/Button';
export function ProfilePage() {
  const {user} = useAuth();
  const state = useResource(user ? `u:${user.id}:profile-mode` : null, endpoints.profileMode);
  const write = useWrite(`u:${user!.id}:profile-mode-write`);
  const [mode,setMode] = useState<ReviewMode | ''>('');
  const [saved,setSaved] = useState<string | null>(null);
  useEffect(() => { if (state.updatedAt && write.uncertain) write.reconcile(); }, [state.updatedAt]);
  useEffect(() => { setMode(state.data?.review_mode === 'auto' || state.data?.review_mode === 'manual' ? state.data.review_mode : ''); }, [state.data?.version]);
  const save = async () => {
    setSaved(null);
    const result = await write.run(() => request('/profile/review-mode',parseProfileMode,{method:'PATCH',body:{review_mode:mode,version:state.data!.version}}), () => invalidateResources(`u:${user!.id}:`));
    if (result) setSaved(`Saved ${result.review_mode === 'auto' ? 'Automatic' : 'Manual'} for ${result.installations.length} administered installation${result.installations.length === 1 ? '' : 's'}.`);
  };
  return (
    <div className="max-w-3xl space-y-6">
      <header className="border-b border-neutral-800/80 pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-neutral-100">Profile settings</h1>
        <p className="text-sm text-neutral-400 mt-1 font-mono">
          Signed in as <span className="text-neutral-200 font-semibold">{user?.github_login}</span>
        </p>
      </header>

      <section className="rounded-xl border border-neutral-800/90 bg-neutral-900/80 p-6 space-y-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-800/60">
          <div>
            <h2 className="text-lg font-semibold text-neutral-100">Review automation</h2>
            <p className="text-xs text-neutral-400 mt-0.5">
              Apply one mode to all active installations you administer. This policy is shared with their other users and applies to every selected repository.
            </p>
          </div>
          <button
            type="button"
            className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer self-start sm:self-auto"
            onClick={state.refresh}
          >
            Refresh review policy
          </button>
        </div>

        <AsyncState {...state} hasData={!!state.data} />

        {state.data && (
          <>
            {state.data.installations.length ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <p className="text-xs font-mono uppercase tracking-wider text-neutral-400">
                    Administered Installations ({state.data.installations.length})
                  </p>
                  <ul className="space-y-2 font-mono text-xs">
                    {state.data.installations.map(i => (
                      <li
                        key={i.id}
                        className="flex items-center justify-between p-3 rounded-lg bg-neutral-950/60 border border-neutral-800/80"
                      >
                        <span className="font-semibold text-neutral-200">{i.account_login}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                            i.review_mode === 'auto'
                              ? 'bg-primary-500/15 text-primary-300 border border-primary-500/30'
                              : 'bg-neutral-800 text-neutral-300 border border-neutral-700'
                          }`}
                        >
                          {i.review_mode === 'auto' ? 'Automatic' : 'Manual'}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>

                {state.data.review_mode === 'mixed' && (
                  <div className="p-3 rounded-lg bg-severity-medium-bg border border-severity-medium-border text-xs text-severity-medium font-medium">
                    <p role="status">Installations currently use different modes. Choose a mode to align them.</p>
                  </div>
                )}

                <div className="pt-2 border-t border-neutral-800/60 space-y-3">
                  <label className="block text-sm space-y-2">
                    <span className="font-medium text-neutral-200">Review mode</span>
                    <select
                      aria-label="Review mode"
                      className="block w-full sm:w-64 bg-neutral-950 border border-neutral-700/80 hover:border-neutral-600 rounded-lg p-2.5 text-sm text-neutral-100 font-sans focus:outline-none focus:border-primary-400 focus:ring-1 focus:ring-primary-400 cursor-pointer"
                      value={mode}
                      disabled={write.busy || write.uncertain}
                      onChange={e => setMode(e.target.value as ReviewMode)}
                    >
                      <option value="" disabled>Choose a mode</option>
                      <option value="auto">Automatic</option>
                      <option value="manual">Manual</option>
                    </select>
                  </label>

                  <p className="text-xs text-neutral-400 leading-relaxed">
                    Automatic: new eligible PR events queue a review. Manual: use the review button on a PR. Existing queued reviews still finish. Newly connected installations retain their current policy until you apply this setting again.
                  </p>

                  <div className="pt-2">
                    <Button
                      disabled={!mode || mode === state.data.review_mode || write.busy || write.uncertain || state.loading}
                      onClick={() => void save()}
                    >
                      {write.busy ? 'Saving shared policy…' : 'Apply to all administered installations'}
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-neutral-800 bg-neutral-950/40 p-6 text-center text-neutral-400 text-sm">
                <p>You do not administer any active installations. Their administrators control review automation.</p>
              </div>
            )}
          </>
        )}

        <WriteFeedback {...write} />

        {saved && (
          <div className="p-3.5 rounded-lg bg-tertiary-950/40 border border-tertiary-500/40 text-xs font-mono text-tertiary-400">
            <p role="status">{saved}</p>
          </div>
        )}
      </section>
    </div>
  );
}
