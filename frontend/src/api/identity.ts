import { endpoints } from './endpoints';
import type { ReviewItem } from './contracts';

export function safeReturnPath(value: unknown): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || /[\\\u0000-\u001f]/.test(value)) return '/repos';
  try {
    const url = new URL(value, window.location.origin);
    if (url.origin !== window.location.origin || ['/auth/callback', '/auth/install'].includes(url.pathname)) return '/repos';
    return url.pathname + url.search + url.hash;
  } catch { return '/repos'; }
}
export const positiveId = (value: string | null | undefined) => value && /^\d+$/.test(value) && Number.isSafeInteger(Number(value)) && Number(value) > 0 ? Number(value) : null;
export const repoUrl = (id: number, fullName: string) => `/repos/${fullName.split('/').map(encodeURIComponent).join('/')}?installation_id=${id}`;
export const activeReview = (status: string) => status === 'pending' || status === 'running';
export const terminalReview = (status: string) => ['completed', 'failed', 'skipped'].includes(status);
export const statusLabel = (status: string) => status === 'pending' ? 'Queued' : status.charAt(0).toUpperCase() + status.slice(1).replaceAll('_', ' ');
export function githubUrl(path: string) { return `https://github.com/${path.split('/').map(encodeURIComponent).join('/')}`; }
export function appInstallUrl(slug: string | undefined) { return slug && /^[a-z0-9-]+$/i.test(slug) ? `https://github.com/apps/${slug}/installations/new` : null; }

export interface HistoryLookup { items: ReviewItem[]; latest: Record<number, ReviewItem>; exhausted: boolean; total: number }
export async function lookupHistory(id: number, repo: string, numbers: number[], signal: AbortSignal, pages = 10, scanAll = false): Promise<HistoryLookup> {
  const latest: Record<number, ReviewItem> = {};
  const seen = new Set<number>(); const items: ReviewItem[] = [];
  let exhausted = false, total = 0;
  for (let page = 0; page < pages; page++) {
    const data = await endpoints.reviews(id, repo, signal, 100, page * 100, 0);
    total = data.total;
    for (const item of data.items) {
      if (seen.has(item.id)) continue;
      seen.add(item.id); items.push(item);
      latest[item.pr_number] ??= item;
    }
    exhausted = (page + 1) * 100 >= data.total || !data.items.length;
    if (exhausted || (!scanAll && numbers.length > 0 && numbers.every(n => latest[n]))) break;
  }
  return { items, latest, exhausted, total };
}
