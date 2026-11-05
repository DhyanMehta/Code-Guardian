import { Link } from 'react-router-dom';
import { endpoints } from '../../api/endpoints';
import { useResource } from '../../api/resources';
import { AsyncState } from '../common/AsyncState';
import { Counts, panelClass } from '../reviews/ReviewPresentation';
export function AnalyticsTab({ scope, installation, repo }: { scope: string; installation: number; repo: string }) {
  const state = useResource(`${scope}:trends`, s => endpoints.trends(installation, repo, s), () => 30_000);
  const data = state.data;
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2 border-b border-neutral-800/60">
        <div>
          <h2 className="text-base font-semibold text-neutral-100">Repository Analytics & Trends</h2>
          <p className="text-xs text-neutral-400">Aggregated review performance, coverage metrics, and severity distributions.</p>
        </div>
        <button
          type="button"
          className="text-xs font-mono font-medium text-primary-400 hover:text-primary-300 underline underline-offset-2 cursor-pointer self-start sm:self-auto"
          onClick={state.refresh}
        >
          Refresh analytics
        </button>
      </div>

      <AsyncState {...state} hasData={!!data} />

      {data && (
        <div className="space-y-6">
          {/* KPI Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              ['Reviews', data.totals.reviews],
              ['Completed', data.totals.completed],
              ['Failed / skipped', `${data.totals.failed} / ${data.totals.skipped}`],
              ['Coverage recorded', data.totals.coverage_recorded_reviews],
              ['Coverage complete', data.totals.coverage_complete_reviews],
              ['Coverage gaps', data.totals.reviews_with_coverage_gap],
              ['Auto-fix attempts', data.totals.autofix.created],
              ['Approved', data.totals.autofix.approved],
              ['Rejected', data.totals.autofix.rejected],
            ].map(([label, value]) => (
              <div key={label} className={panelClass}>
                <p className="text-xs font-mono uppercase tracking-wider text-neutral-400">{label}</p>
                <p className="text-2xl font-mono font-bold text-neutral-100 mt-1">{value}</p>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <Counts counts={data.totals.severity_counts} />
            <p className="text-xs font-mono text-neutral-400">
              Latest {data.range.review_count} reviews in this range. Weighted index uses server weights: {Object.entries(data.totals.weights_used).map(([s, n]) => `${s}=${n}`).join(', ')}.
            </p>
          </div>

          {!data.points.length ? (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-8 text-center text-neutral-400">
              <p>No review history yet.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Weighted Findings Chart */}
              <div className={panelClass}>
                <div className="flex items-center justify-between pb-2 border-b border-neutral-800/60">
                  <h3 className="font-semibold text-sm text-neutral-100">Weighted findings over time</h3>
                  <span className="text-[11px] font-mono text-neutral-400">Relative finding severity</span>
                </div>

                <div
                  className="flex items-end gap-1.5 h-36 pt-4 pb-2 px-2 bg-neutral-950/60 rounded-xl border border-neutral-800/80"
                  role="img"
                  aria-label="Weighted finding index, oldest to newest; exact values and coverage limitations follow in the table"
                >
                  {data.points.map(p => (
                    <div
                      key={p.review_id}
                      title={`Review ${p.review_id}: ${p.weighted_index}${p.coverage_complete ? '' : ' — incomplete coverage'}`}
                      className={`flex-1 min-w-1.5 rounded-t-sm transition-all duration-150 hover:opacity-80 ${
                        p.coverage_complete
                          ? 'bg-primary-500'
                          : 'bg-neutral-600 border border-dashed border-severity-medium'
                      }`}
                      style={{
                        height: `${Math.max(
                          4,
                          (p.weighted_index / Math.max(1, ...data.points.map(q => q.weighted_index))) * 100
                        )}%`,
                      }}
                    />
                  ))}
                </div>

                <p className="text-xs text-neutral-400 italic">
                  Gray points have incomplete or unknown coverage. Lower counts do not establish an improvement.
                </p>
              </div>

              {/* Data Table */}
              <div className="rounded-xl border border-neutral-800/90 bg-neutral-900/80 overflow-hidden shadow-xs">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm text-left">
                    <thead className="bg-neutral-950/80 text-xs font-mono text-neutral-400 border-b border-neutral-800">
                      <tr>
                        <th className="py-3 px-4 font-medium uppercase tracking-wider">Review</th>
                        <th className="py-3 px-4 font-medium uppercase tracking-wider">Status</th>
                        <th className="py-3 px-4 font-medium uppercase tracking-wider">Findings / index</th>
                        <th className="py-3 px-4 font-medium uppercase tracking-wider">Coverage</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-800/60">
                      {data.points.map(p => (
                        <tr key={p.review_id} className="hover:bg-neutral-850/40 transition-colors">
                          <td className="py-3 px-4 font-mono">
                            <Link to={`/reviews/${p.review_id}`} className="text-primary-400 hover:text-primary-300 font-semibold underline underline-offset-2">
                              #{p.review_id} · PR #{p.pr_number}
                            </Link>
                            <p className="text-xs text-neutral-500 mt-0.5">{p.created_at ?? 'Date not recorded'}</p>
                          </td>
                          <td className="py-3 px-4 font-mono text-xs text-neutral-300 capitalize">
                            {p.status}
                          </td>
                          <td className="py-3 px-4 font-mono text-xs text-neutral-200">
                            {p.total_findings} / {p.weighted_index}
                          </td>
                          <td className="py-3 px-4 text-xs font-mono">
                            {p.coverage_complete ? (
                              <span className="text-tertiary-400 font-semibold">Complete</span>
                            ) : (
                              <div className="space-y-0.5 text-severity-medium">
                                {p.degraded_agents.length > 0 && <p>Degraded/failed: {p.degraded_agents.join(', ')}</p>}
                                {p.unrecorded_agents.length > 0 && <p>Unrecorded: {p.unrecorded_agents.join(', ')}</p>}
                                {!p.degraded_agents.length && !p.unrecorded_agents.length && 'Incomplete'}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
