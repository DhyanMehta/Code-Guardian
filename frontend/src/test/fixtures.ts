import type { ReviewDetail, ReviewItem, TrendsResponse, UserProfile, Installation, PullRequest, Repository } from '../api/contracts';
export const installation: Installation = { id: 7, account_login: 'owner', account_type: 'User', target_type: 'User', role: 'admin', suspended: false, app_slug: 'guardian-test', review_mode: 'manual', created_at: null };
export const user: UserProfile = { id: 1, github_user_id: 2, github_login: 'owner', avatar_url: null, installations: [installation] };
export const repo: Repository = { id: 5, name: 'httpx', full_name: 'owner/httpx', private: false, html_url: 'https://github.com/owner/httpx', default_branch: 'main', open_issues_count: 1 };
export const pull: PullRequest = { number: 1, title: 'Retry helper', state: 'open', head_sha: 'head-1', user: 'owner', created_at: null, html_url: 'https://github.com/owner/httpx/pull/1' };
export function review(overrides: Partial<ReviewDetail> = {}): ReviewDetail {
  return { attempt: 0, heartbeat_at: null, progress: [], id: 9, installation_id: 7, repo_full_name: 'owner/httpx', pr_number: 1, commit_sha: 'head-1', status: 'completed', delivery_status: 'failed', delivery_error: 'GitHub temporarily unavailable', comment_id: null, standards_version: 'v1', started_at: '2026-10-01T10:00:00Z', created_at: '2026-10-01T10:00:00Z', completed_at: '2026-10-01T10:01:00Z', summary: 'Review finished', is_fork: false, finding_count: 0, fixable_count: 0, severity_counts: { critical: 0, high: 0, medium: 0, low: 0, info: 0, unknown: 0 }, agent_counts: { security: 0, quality: 0, test_gap: 0, documentation: 0 }, autofix_status: null, autofix_branch: null, autofix_approved_at: null, autofix_approved_by: null, findings: [], findings_by_agent: {}, agent_runs: [{ agent: 'security', outcome: 'degraded', recorded: true, finding_count: 0, failure_reason: 'Scanner unavailable', notes: [], raw_findings: [], scanner_statuses: [] }, ...(['quality', 'test_gap', 'documentation'] as const).map(agent => ({ agent, outcome: null, recorded: false, finding_count: 0, failure_reason: null, notes: [] }))], autofix: { status: null, branch: null, approved_at: null, approved_by: null, applied_count: null, commit_sha: null, error: null, skipped_fixes: [] }, ...overrides };
}
export function item(detail = review()): ReviewItem { return { ...detail, degraded_agents: ['security'] }; }
export const trends: TrendsResponse = { range: { since: null, until: null, repo: 'owner/httpx', review_count: 1, requested_limit: 50 }, repos: ['owner/httpx'], points: [{ review_id: 9, repo_full_name: 'owner/httpx', pr_number: 1, commit_sha: 'head-1', status: 'completed', is_fork: false, created_at: null, total_findings: 0, severity_counts: review().severity_counts, agent_counts: review().agent_counts, weighted_index: 0, degraded_agents: ['security'], unrecorded_agents: ['quality', 'test_gap', 'documentation'], coverage_recorded: false, coverage_complete: false }], totals: { reviews: 1, completed: 1, failed: 0, skipped: 0, findings: 0, severity_counts: review().severity_counts, agent_counts: review().agent_counts, autofix: { created: 0, approved: 0, rejected: 0 }, weights_used: { critical: 10, high: 5, medium: 2, low: 1, info: 0, unknown: 0 }, coverage_recorded_reviews: 0, coverage_complete_reviews: 0, reviews_with_coverage_gap: 1 } };
export const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
export function backend(url: string): Response {
  const u = new URL(url);
  if (u.pathname === '/auth/me') return json(user);
  if (u.pathname === '/installations') return json([installation]);
  if (u.pathname === '/installations/7/repos') return json([repo]);
  if (u.pathname.endsWith('/pulls')) return json([pull]);
  if (u.pathname === '/reviews') return json({ items: [item()], limit: 100, offset: 0, total: 1 });
  if (u.pathname === '/reviews/9') return json(review());
  if (u.pathname === '/reviews/9/report') return json({ review_id: 9, markdown: '# Saved report' });
  if (u.pathname === '/metrics/trends') return json(trends);
  if (u.pathname.endsWith('/settings')) return json({ installation_id: 7, review_mode: 'manual' });
  if (u.pathname.endsWith('/standards')) return json({ installation_id: 7, has_custom_standards: false, version: null, filename: null, chunks: null, uploaded_at: null });
  return json({ detail: `Unexpected endpoint: ${u.pathname}` }, 404);
}
