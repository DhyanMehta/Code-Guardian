import { request } from './client';
import * as c from './contracts';
export const repoPath = (id: number, repo: string) => `/installations/${id}/repos/${repo.split('/').map(encodeURIComponent).join('/')}`;
export const reviewPath = (id: number, repo: string, limit = 100, offset = 0) => `/reviews?${new URLSearchParams({ installation_id: String(id), repo, limit: String(limit), offset: String(offset) })}`;
export const endpoints = {
  profileMode: (signal: AbortSignal) => request('/profile/review-mode', c.parseProfileMode, {signal}),
  installationUrl: (signal: AbortSignal) => request('/auth/installation-url', c.parseInstallationUrl, {signal}),
  readiness: (signal: AbortSignal) => request('/health/ready', c.parseReadiness, { signal, retries: 0, auth: false, acceptedStatuses: [503] }),
  installations: (signal: AbortSignal) => request('/installations', c.parseInstallations, { signal }),
  repos: (id: number, signal: AbortSignal) => request(`/installations/${id}/repos`, c.parseRepos, { signal }),
  pulls: (id: number, repo: string, page: number, signal: AbortSignal, retries = 2, state = 'open') => request(`${repoPath(id, repo)}/pulls?page=${page}&per_page=50&state=${state}`, c.parsePulls, { signal, retries }),
  reviews: (id: number, repo: string, signal: AbortSignal, limit = 100, offset = 0, retries = 2) => request(reviewPath(id, repo, limit, offset), c.parseReviews, { signal, retries }),
  review: (id: number, signal: AbortSignal, retries = 2) => request(`/reviews/${id}`, c.parseReview, { signal, retries }),
  report: (id: number, signal: AbortSignal) => request(`/reviews/${id}/report`, c.parseReport, { signal }),
  settings: (id: number, signal: AbortSignal) => request(`/installations/${id}/settings`, c.parseSettings, { signal }),
  standards: (id: number, signal: AbortSignal) => request(`/installations/${id}/standards`, c.parseStandards, { signal }),
  trends: (id: number, repo: string, signal: AbortSignal) => request(`/metrics/trends?${new URLSearchParams({ installation_id: String(id), repo, limit: '50' })}`, c.parseTrends, { signal }),
};
