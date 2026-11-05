import { agents, type ReviewDetail } from '../../api/contracts';
import { agentLabels } from '../reviews/ReviewPresentation';
const categories = ['ok','degraded','failed','unrecorded'] as const;
const colors = {ok:'bg-tertiary-500',degraded:'bg-yellow-500',failed:'bg-red-500',unrecorded:'bg-neutral-600'};
export function AgentOutcomeChart({ reviews, unavailable }: { reviews: ReviewDetail[]; unavailable: number }) {
  const completed = reviews.filter(r => ['completed', 'failed', 'skipped'].includes(r.status));
  return (
    <section className="rounded-xl border border-neutral-800/90 bg-neutral-900/80 p-5 space-y-5 shadow-xs">
      <div className="pb-3 border-b border-neutral-800/60">
        <h2 className="font-semibold text-base text-neutral-100">Agent outcomes in loaded history</h2>
        <p className="text-xs font-mono text-neutral-400 mt-1">
          {completed.length} terminal reviews · {reviews.length - completed.length} active · {unavailable} unavailable. Counts are review outcomes, not execution coverage or a live agent workload.
        </p>
      </div>

      <div className="grid gap-4">
        {agents.map(agent => {
          const counts = { ok: 0, degraded: 0, failed: 0, unrecorded: 0 };
          for (const review of completed) {
            const run = review.agent_runs.find(r => r.agent === agent);
            const outcome =
              run?.recorded && ['ok', 'degraded', 'failed'].includes(run.outcome ?? '')
                ? (run.outcome as 'ok' | 'degraded' | 'failed')
                : 'unrecorded';
            counts[outcome]++;
          }
          return (
            <div key={agent} className="space-y-2 p-3.5 rounded-lg bg-neutral-950/60 border border-neutral-800/60">
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-sm text-neutral-200">{agentLabels[agent]}</h3>
                <span className="text-[11px] font-mono text-neutral-400">
                  {counts.ok}/{completed.length} recorded with outcome OK
                </span>
              </div>
              <div
                role="img"
                aria-label={`${agentLabels[agent]}: ${categories.map(c => `${counts[c]} ${c}`).join(', ')}`}
                className="h-3 flex overflow-hidden rounded-full bg-neutral-800"
              >
                {categories.map(c => (
                  <span
                    key={c}
                    className={`${colors[c]} transition-all duration-300`}
                    style={{ width: `${completed.length ? (counts[c] / completed.length) * 100 : 0}%` }}
                  />
                ))}
              </div>
              <p className="text-xs font-mono text-neutral-400">
                {categories.map(c => `${c === 'ok' ? 'Outcome OK' : c}: ${counts[c]}`).join(' · ')}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
