import { useState } from 'react';
import { endpoints } from '../../api/endpoints';
import { repositoryDestination, statusLabel } from '../../api/identity';
import { useResource } from '../../api/resources';
import type { ReviewDetail } from '../../api/contracts';
import { AsyncState } from '../common/AsyncState';
import { Button } from '../common/Button';
import { diagnosticError, diagnosticText } from './diagnosticText';

export function ReviewDelivery({ review, userId }: { review: ReviewDetail; userId: number }) {
  const [open, setOpen] = useState(false);
  const supported = review.status === 'completed' || review.status === 'failed';
  const report = useResource(open && supported ? `u:${userId}:report:${review.id}` : null, s => endpoints.report(review.id, s));
  const repo = repositoryDestination(review.repo_full_name);
  const comment = review.comment_id;
  const destination = review.delivery_status === 'posted' && repo && comment && /^[1-9]\d*$/.test(comment)
    && Number.isSafeInteger(review.pr_number) && review.pr_number > 0 ? `${repo}/pull/${review.pr_number}#issuecomment-${comment}` : null;
  const state = review.delivery_status;
  return <section id="delivery" aria-labelledby="delivery-title" tabIndex={-1} className="scroll-mt-20 space-y-3">
    <h2 id="delivery-title" className="text-section">GitHub delivery</h2>
    <div className="space-y-3 rounded-lg border border-divider bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-meta text-fg-muted">Pull request comment</p>
          <p className={`text-row-title ${state === 'failed' ? 'text-status-failed' : state === 'posted' ? 'text-status-ok' : 'text-fg'}`}>{state === 'pending' ? 'Pending' : state ? statusLabel(state) : 'Not recorded'}</p></div>
        {destination && <a className="control-focus control-target inline-flex items-center rounded-lg border border-control-border px-3 text-control text-link" href={destination} target="_blank" rel="noreferrer">View GitHub Report</a>}
      </div>
      {destination && <p className="text-meta text-fg-muted">Comment #{comment}</p>}
      {state === 'posted' && !destination && <p className="text-support text-fg-secondary">The recorded delivery has no usable comment destination.</p>}
      {state === 'pending' && <p className="text-support text-fg-secondary">GitHub publication is awaiting confirmation.</p>}
      {state === 'failed' && <p className="text-support text-fg-secondary">The recorded delivery attempt failed.</p>}
      {review.delivery_error && <p className="text-support text-status-degraded">{diagnosticText(review.delivery_error)}</p>}
      {supported && <div className="space-y-3 border-t border-divider pt-3">
        <Button variant="secondary" aria-expanded={open} aria-controls="review-report" onClick={() => setOpen(value => !value)}>Saved / rendered report</Button>
        <div id="review-report" hidden={!open}>{open && <>
          <AsyncState loading={report.loading} error={diagnosticError(report.error)} refresh={report.refresh} hasData={!!report.data} />
          {report.data && (report.data.review_id === review.id && report.data.markdown.trim()
            ? <pre tabIndex={0} aria-label="Review report Markdown" className="control-focus max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-code p-4 font-mono text-sm leading-relaxed text-fg-secondary">{report.data.markdown}</pre>
            : <p className="text-support text-fg-muted">Report text is unavailable for this review.</p>)}
        </>}</div>
      </div>}
      {review.standards_version && <p className="text-meta text-fg-muted">Historical standards version · <code>{review.standards_version}</code></p>}
    </div>
  </section>;
}
