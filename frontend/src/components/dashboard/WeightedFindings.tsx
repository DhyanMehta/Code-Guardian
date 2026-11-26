import type { TrendPoint, TrendsResponse } from '../../api/contracts';
import { severities } from '../../api/contracts';
import { SectionCard } from '../common/SectionCard';

export function hasObservation(point: TrendPoint) {
  return point.status === 'completed' || (point.status === 'failed' && point.total_findings > 0);
}

export function WeightedFindings({ points, totals }: Pick<TrendsResponse, 'points' | 'totals'>) {
  const observed = points.filter(hasObservation);
  const peak = Math.max(0, ...observed.map(p => p.weighted_index));
  const ceiling = Math.max(2, Math.ceil(peak / 2) * 2);
  return (
    <SectionCard>
      <figure aria-labelledby="index-heading">
        <h3 id="index-heading" className="text-section">Weighted findings by review</h3>
        <p className="mt-1 text-support text-fg-muted">Each position represents one review, in the order it was created. Changes in files and execution coverage affect comparisons.</p>
        {observed.length > 0 ? <>
          <div className="mt-5 text-meta text-fg-secondary">Weighted findings index</div>
          <div role="img" aria-label={`Weighted index for ${observed.length} of ${points.length} sampled reviews. Exact values and limitations are in the review history.`} className="relative mt-4 mb-3 ml-10 h-40 sm:h-48">
            {[ceiling, ceiling / 2, 0].map(tick => <div key={tick} style={{ bottom: `${100 * tick / ceiling}%` }} className={`absolute inset-x-0 border-t ${tick === 0 ? 'border-control-border' : 'border-dashed border-divider'}`}>
              <span className="absolute right-full mr-2 w-max -translate-y-1/2 whitespace-nowrap text-meta tabular-nums text-fg-muted">{tick}</span>
            </div>)}
            <div className="absolute inset-0 flex justify-around">
              {points.map(point => <div key={point.review_id} className="relative flex-1 min-w-0">
                {hasObservation(point) && <span data-review={point.review_id} style={{ bottom: `${100 * point.weighted_index / ceiling}%` }} className={`absolute left-1/2 h-2.5 w-2.5 max-w-full -translate-x-1/2 translate-y-1/2 border-2 ${point.coverage_complete && point.status === 'completed' ? 'rounded-full border-link bg-link' : 'border-risk-medium bg-panel'}`} />}
              </div>)}
            </div>
          </div>
          <div className={`ml-10 flex flex-wrap gap-1 text-meta text-fg-muted ${points.length === 1 ? 'justify-center' : 'justify-between'}`}>
            <span>#{points[0].review_id}</span>{points.length > 1 && <span>#{points[points.length - 1].review_id}</span>}
          </div>
          <p className="text-center text-meta text-fg-secondary">Review sequence · oldest to newest</p>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-meta text-fg-secondary">
            <span><i aria-hidden="true" className="inline-block size-2.5 rounded-full bg-link" /> Complete coverage</span>
            <span><i aria-hidden="true" className="inline-block size-2.5 border-2 border-risk-medium" /> Limited evidence</span>
            <span>Gap · no observation</span>
          </div>
        </> : <p className="my-4 text-body">{points.length ? 'No weighted observations available in this sample.' : 'No review history yet.'}</p>}
        <figcaption className="mt-3 border-t border-divider pt-3 text-support text-fg-muted">
          Weights per reported finding: {severities.map(s => `${s} ${totals.weights_used[s]}`).join(' · ')}.
          {points.length > 0 && <a href="#analytics-history" className="control-focus flex min-h-11 w-fit items-center rounded text-link underline underline-offset-4">Inspect exact review values</a>}
        </figcaption>
      </figure>
    </SectionCard>
  );
}
