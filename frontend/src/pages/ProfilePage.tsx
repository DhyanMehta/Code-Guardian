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
  return <div className="max-w-3xl space-y-6"><header><h1 className="text-2xl font-bold">Profile settings</h1><p className="text-neutral-400">Signed in as {user?.github_login}</p></header>
    <section className="rounded-xl border border-neutral-800 bg-neutral-900 p-6 space-y-4"><h2 className="text-lg font-semibold">Review automation</h2>
      <p>Apply one mode to all active installations you administer. This policy is shared with their other users and applies to every selected repository.</p>
      <button className="underline" onClick={state.refresh}>Refresh review policy</button><AsyncState {...state} hasData={!!state.data}/>
      {state.data && <>{state.data.installations.length ? <><ul className="space-y-2">{state.data.installations.map(i=><li key={i.id}>{i.account_login} · {i.review_mode === 'auto' ? 'Automatic' : 'Manual'}</li>)}</ul>
        {state.data.review_mode === 'mixed' && <p role="status">Installations currently use different modes. Choose a mode to align them.</p>}
        <label className="block">Review mode <select aria-label="Review mode" className="bg-neutral-950 border border-neutral-700 rounded p-2" value={mode} disabled={write.busy||write.uncertain} onChange={e=>setMode(e.target.value as ReviewMode)}><option value="" disabled>Choose a mode</option><option value="auto">Automatic</option><option value="manual">Manual</option></select></label>
        <p className="text-sm text-neutral-400">Automatic: new eligible PR events queue a review. Manual: use the review button on a PR. Existing queued reviews still finish. Newly connected installations retain their current policy until you apply this setting again.</p>
        <Button disabled={!mode || mode === state.data.review_mode || write.busy || write.uncertain || state.loading} onClick={()=>void save()}>{write.busy ? 'Saving shared policy…' : 'Apply to all administered installations'}</Button>
        </> : <p>You do not administer any active installations. Their administrators control review automation.</p>}</>}
      <WriteFeedback {...write}/>
      {saved && <p role="status" className="text-tertiary-400">{saved}</p>}
    </section></div>;
}
