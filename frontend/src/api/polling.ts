import type { ReviewDetail } from './contracts';
import { activeReview } from './identity';
export function reviewPolling() {
  let deliveryStart: number | undefined, previousElapsed = 0;
  return (review: ReviewDetail, visibleMs: number): number | false => {
    if (visibleMs < previousElapsed) deliveryStart = undefined; // Explicit refresh starts a new monitoring budget.
    previousElapsed = visibleMs;
    if (activeReview(review.status) || review.autofix.status === 'creating') return 5_000;
    if (review.delivery_status === 'pending' || review.delivery_status === 'failed') {
      deliveryStart ??= visibleMs;
      return visibleMs - deliveryStart < 180_000 ? 15_000 : false;
    }
    return false;
  };
}
