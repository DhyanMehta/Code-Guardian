import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { endpoints } from '../../api/endpoints';
import { agents, type ReviewDetail } from '../../api/contracts';
import { useResource } from '../../api/resources';
import { AsyncState } from '../common/AsyncState';
import { AgentRunCard, agentLabels, panelClass } from '../reviews/ReviewPresentation';
import { errorMessage } from '../../api/client';
import { AgentOutcomeChart } from './AgentOutcomeChart';
export type AgentHistoryCache = Map<number, { detail: ReviewDetail; fetched: number }>;
export async function agentHistory(installation: number, repo: string, count: number, signal: AbortSignal, cache: AgentHistoryCache = new Map()) {
  const list = await endpoints.reviews(installation, repo, signal, count);
  const results: { id: number; detail?: ReviewDetail; error?: string }[] = new Array(list.items.length);
  let cursor = 0;
  await Promise.all([0, 1].map(async () => {
    while (cursor < list.items.length && !signal.aborted) {
      const index = cursor++, id = list.items[index].id;
      try {
        const cached = cache.get(id);
        const active = cached && ['pending','running'].includes(cached.detail.status);
        const detail = cached && cached.detail.status === list.items[index].status && Date.now() - cached.fetched < (active ? 5_000 : 30_000) ? cached.detail : await endpoints.review(id, signal);
        if (!cached || cached.detail !== detail) cache.set(id, { detail, fetched: Date.now() });
        results[index] = { id, detail };
      }
      catch (e) { if (signal.aborted) throw e; results[index] = { id, error: errorMessage(e) }; }
    }
  }));
  return { results, total: list.total };
}
export function AgentsTab({ scope, installation, repo }: { scope: string; installation: number; repo: string }) {
  const [count, setCount] = useState(5);
  const cache = useRef<AgentHistoryCache>(new Map());
  const state = useResource(`${scope}:agents:${count}`, s => agentHistory(installation, repo, count, s, cache.current), data => data.results.some(r=>r.detail && ['pending','running'].includes(r.detail.status)) ? 5_000 : 30_000);
  return <div className="space-y-4"><button onClick={() => { cache.current.clear(); state.refresh(); }} className="text-primary-400 underline">Refresh agent history</button><AsyncState {...state} hasData={!!state.data} />
    {state.data && <><AgentOutcomeChart reviews={state.data.results.flatMap(r => r.detail ? [r.detail] : [])} unavailable={state.data.results.filter(r => !r.detail).length}/><div className="grid sm:grid-cols-2 gap-3">{agents.map(a => { const failed = state.data?.results.find(r => r.detail?.agent_runs.some(run => run.agent === a && ['failed', 'degraded'].includes(run.outcome ?? ''))); return <div key={a} className={panelClass}><h3>{agentLabels[a]}</h3><p className="text-sm text-neutral-400">Latest recorded issue in loaded history: {failed ? <Link className="text-primary-400" to={`/reviews/${failed.id}`}>review #{failed.id}</Link> : 'None found; missing history does not establish complete coverage.'}</p></div>; })}</div>
    {!state.data.results.length && <p>No review history yet.</p>}{state.data.results.map(r => <section key={r.id} className="space-y-3"><h3><Link className="text-primary-400" to={`/reviews/${r.id}`}>Review #{r.id}</Link></h3>{r.error ? <p role="alert">Detail unavailable: {r.error}</p> : <div className="grid sm:grid-cols-2 gap-3">{r.detail?.agent_runs.map(run => <AgentRunCard key={run.agent} run={run} />)}</div>}</section>)}
    {state.data.total > count && count < 200 && <button className="underline" onClick={() => setCount(n => Math.min(n + 5, 200))}>Load more agent history</button>}{count === 200 && state.data.total > count && <p>Showing the latest 200 reviews.</p>}</>}
  </div>;
}
