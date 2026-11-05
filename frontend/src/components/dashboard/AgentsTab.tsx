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
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-neutral-800/60">
        <div>
          <h2 className="text-base font-semibold text-neutral-100">Specialist Agent Fleet</h2>
          <p className="text-xs text-neutral-400">Autonomous multi-agent execution statistics, health metrics, and history.</p>
        </div>
        <button
          type="button"
          onClick={() => { cache.current.clear(); state.refresh(); }}
          className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer self-start sm:self-auto"
        >
          Refresh agent history
        </button>
      </div>

      <AsyncState {...state} hasData={!!state.data} />

      {state.data && (
        <div className="space-y-6">
          <AgentOutcomeChart
            reviews={state.data.results.flatMap(r => r.detail ? [r.detail] : [])}
            unavailable={state.data.results.filter(r => !r.detail).length}
          />

          <div className="grid sm:grid-cols-2 gap-3">
            {agents.map(a => {
              const failed = state.data?.results.find(r =>
                r.detail?.agent_runs.some(run => run.agent === a && (run.coverage?.status === 'partial' || ['failed', 'degraded'].includes(run.outcome ?? '')))
              );
              return (
                <div key={a} className={panelClass}>
                  <h3 className="font-semibold text-sm text-neutral-100">{agentLabels[a]}</h3>
                  <p className="text-xs font-mono text-neutral-400 mt-1">
                    Latest recorded issue in loaded history:{' '}
                    {failed ? (
                      <Link className="text-primary-400 hover:underline font-semibold" to={`/reviews/${failed.id}`}>
                        review #{failed.id}
                      </Link>
                    ) : (
                      'None found; missing history does not establish complete coverage.'
                    )}
                  </p>
                </div>
              );
            })}
          </div>

          {!state.data.results.length && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
              <p>No review history yet.</p>
            </div>
          )}

          <div className="space-y-4">
            {state.data.results.map(r => (
              <section key={r.id} className="rounded-xl border border-neutral-800/80 bg-neutral-900/50 p-5 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-neutral-800/60">
                  <h3 className="font-mono text-sm font-semibold">
                    <Link className="text-primary-400 hover:text-primary-300 hover:underline" to={`/reviews/${r.id}`}>
                      Review #{r.id}
                    </Link>
                  </h3>
                </div>

                {r.error ? (
                  <p role="alert" className="text-xs text-severity-critical">
                    Detail unavailable: {r.error}
                  </p>
                ) : (
                  <div className="grid sm:grid-cols-2 gap-3">
                    {r.detail?.agent_runs.map(run => (
                      <AgentRunCard key={run.agent} run={run} />
                    ))}
                  </div>
                )}
              </section>
            ))}
          </div>

          {state.data.total > count && count < 200 && (
            <div className="text-center pt-2">
              <button
                type="button"
                className="text-xs font-mono text-primary-400 hover:text-primary-300 underline cursor-pointer"
                onClick={() => setCount(n => Math.min(n + 5, 200))}
              >
                Load more agent history
              </button>
            </div>
          )}

          {count === 200 && state.data.total > count && (
            <p className="text-xs font-mono text-center text-neutral-400">Showing the latest 200 reviews.</p>
          )}
        </div>
      )}
    </div>
  );
}
