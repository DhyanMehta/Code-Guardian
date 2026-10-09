export const agents = ['security', 'quality', 'test_gap', 'documentation'] as const;
export type AgentName = typeof agents[number];
export const severities = ['critical', 'high', 'medium', 'low', 'info', 'unknown'] as const;
export type SeverityLevel = typeof severities[number];
export type ReviewStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
export type AutofixStatus = 'creating' | 'pending_approval' | 'approved' | 'rejected' | 'failed' | null;
export type DeliveryStatus = 'pending' | 'posted' | 'failed' | null;
export type AgentOutcome = 'ok' | 'degraded' | 'failed' | 'unknown' | null;
export type ReviewMode = 'auto' | 'manual';
export interface ProgressEvent { id: number; attempt: number; stage: 'checkout' | 'analysis' | 'agent' | 'aggregation'; agent: AgentName | null; status: 'started' | 'ok' | 'degraded' | 'failed'; created_at: string }
export interface ProfileMode { installations: {id: number; account_login: string; review_mode: ReviewMode}[]; review_mode: ReviewMode | 'mixed' | null; version: string }
export type SeverityCounts = Record<SeverityLevel, number>;
export type AgentCounts = Record<AgentName, number>;
export interface UserInstallation { id: number; account_login: string; account_type: string; target_type: string; role: 'admin' | 'member'; suspended: boolean }
export interface Installation extends UserInstallation { app_slug: string; review_mode: ReviewMode; created_at: string | null }
export interface UserProfile { id: number; github_user_id: number; github_login: string; avatar_url: string | null; installations: UserInstallation[] }
export interface Repository { id: number; name: string; full_name: string; private: boolean; html_url: string; default_branch: string; open_issues_count: number }
export interface PullRequest { number: number; title: string; state: 'open' | 'closed'; head_sha: string; user: string | null; created_at: string | null; html_url: string }
export interface InstallationSettings { installation_id: number; review_mode: ReviewMode }
export interface Standards { installation_id: number; has_custom_standards: boolean; version: string | null; filename: string | null; chunks: number | null; uploaded_at: string | null }
export interface Finding { id: number; agent: AgentName; severity: SeverityLevel; title: string; detail: string | null; file_path: string | null; line: number | null; fixable: boolean; fix_data: Record<string, unknown> | null; evidence: Record<string, unknown> | null; rank: number }
export interface ScannerStatus { scanner: string; ok: boolean; finding_count: number; error: string | null; error_type: string | null }
export interface RawFinding { fingerprint: string; scanner: string; rule_id: string; severity: SeverityLevel; file_path: string | null; line: number | null; message: string }
export interface AgentRun { agent: AgentName; outcome: AgentOutcome; recorded: boolean; finding_count: number; failure_reason: string | null; notes: string[]; scanner_statuses?: ScannerStatus[]; scanner_info?: string | null; raw_findings?: RawFinding[] }
export interface SkippedFix { reason: string; target?: string; target_file?: string; target_function?: string }
export interface AutofixDetail { status: AutofixStatus; branch: string | null; approved_by: string | null; approved_at: string | null; applied_count: number | null; commit_sha: string | null; error: string | null; skipped_fixes: SkippedFix[] }
export interface ReviewBase { id: number; installation_id: number | null; repo_full_name: string; pr_number: number; commit_sha: string | null; status: ReviewStatus; delivery_status: DeliveryStatus; started_at: string | null; summary: string | null; is_fork: boolean; created_at: string | null; completed_at: string | null; finding_count: number; severity_counts: SeverityCounts; agent_counts: AgentCounts; fixable_count: number; autofix_status: AutofixStatus; autofix_branch: string | null }
export interface ReviewItem extends ReviewBase { degraded_agents: string[] }
export interface ReviewEnvelope { items: ReviewItem[]; total: number; limit: number; offset: number }
export interface ReviewDetail extends ReviewBase { attempt: number; heartbeat_at: string | null; progress: ProgressEvent[]; delivery_error: string | null; comment_id: string | null; standards_version: string | null; autofix_approved_by: string | null; autofix_approved_at: string | null; findings: Finding[]; findings_by_agent: Partial<Record<AgentName, Finding[]>>; agent_runs: AgentRun[]; autofix: AutofixDetail }
export interface ReviewReport { review_id: number; markdown: string }
export interface TrendPoint { review_id: number; repo_full_name: string; pr_number: number; commit_sha: string | null; status: ReviewStatus; is_fork: boolean; created_at: string | null; total_findings: number; severity_counts: SeverityCounts; agent_counts: AgentCounts; weighted_index: number; degraded_agents: string[]; unrecorded_agents: string[]; coverage_recorded: boolean; coverage_complete: boolean }
export interface TrendsResponse { range: { since: string | null; until: string | null; review_count: number; requested_limit: number; repo: string | null }; repos: string[]; points: TrendPoint[]; totals: { reviews: number; completed: number; failed: number; skipped: number; findings: number; severity_counts: SeverityCounts; agent_counts: AgentCounts; autofix: { created: number; approved: number; rejected: number }; weights_used: Record<string, number>; coverage_recorded_reviews: number; coverage_complete_reviews: number; reviews_with_coverage_gap: number } }
export interface CreateAutofixResponse { status: 'created'; branch: string; applied_fixes: number; skipped_fixes: { target: string; reason: string }[] }

// The backend stores unconstrained strings/JSON. Reject unfamiliar contracts at
// this boundary, never promote an unknown value to a successful UI state.
export class ContractError extends Error { constructor(message: string) { super(`Unsupported API response: ${message}`); this.name = 'ContractError'; } }
type Check = (value: unknown, path: string) => void;
const check = (valid: boolean, path: string) => { if (!valid) throw new ContractError(path); };
export const string: Check = (v, p) => check(typeof v === 'string', p);
export const number: Check = (v, p) => check(typeof v === 'number' && Number.isFinite(v), p);
export const boolean: Check = (v, p) => check(typeof v === 'boolean', p);
export const object: Check = (v, p) => check(!!v && typeof v === 'object' && !Array.isArray(v), p);
export const nullable = (c: Check): Check => (v, p) => { if (v !== null) c(v, p); };
export const optional = (c: Check): Check => (v, p) => { if (v !== undefined) c(v, p); };
export const array = (c: Check): Check => (v, p) => { check(Array.isArray(v), p); (v as unknown[]).forEach((x, i) => c(x, `${p}[${i}]`)); };
export const shape = (fields: Record<string, Check>): Check => (v, p) => { object(v, p); for (const [k, c] of Object.entries(fields)) c((v as Record<string, unknown>)[k], `${p}.${k}`); };
export const values = (...allowed: unknown[]): Check => (v, p) => check(allowed.includes(v), `${p} (${String(v)})`);
export const parse = <T>(c: Check) => (v: unknown): T => { c(v, 'response'); return v as T; };
const ns = nullable(string), nn = nullable(number), strings = array(string);
const reviewStatus = values('pending', 'running', 'completed', 'failed', 'skipped');
const autofixStatus = values(null, 'creating', 'pending_approval', 'approved', 'rejected', 'failed');
const severityCounts = shape(Object.fromEntries(severities.map(s => [s, number])));
const agentCounts = shape(Object.fromEntries(agents.map(s => [s, number])));
const userInstallation = { id: number, account_login: string, account_type: string, target_type: string, role: values('admin', 'member'), suspended: boolean };
export const parseUser = parse<UserProfile>(shape({ id: number, github_user_id: number, github_login: string, avatar_url: ns, installations: array(shape(userInstallation)) }));
export const parseInstallations = parse<Installation[]>(array(shape({ ...userInstallation, app_slug: string, review_mode: values('auto', 'manual'), created_at: ns })));
export const parseRepos = parse<Repository[]>(array(shape({ id: number, name: string, full_name: string, private: boolean, html_url: string, default_branch: string, open_issues_count: number })));
export const parsePulls = parse<PullRequest[]>(array(shape({ number, title: string, state: values('open', 'closed'), head_sha: string, user: ns, created_at: ns, html_url: string })));
export const parseSettings = parse<InstallationSettings>(shape({ installation_id: number, review_mode: values('auto', 'manual') }));
export const parseProfileMode = parse<ProfileMode>(shape({ installations: array(shape({id:number,account_login:string,review_mode:values('auto','manual')})), review_mode:values('auto','manual','mixed',null), version:string }));
export const parseInstallationUrl = parse<{url:string}>(shape({url:string}));
export const parseStandards = parse<Standards>(shape({ installation_id: number, has_custom_standards: boolean, version: ns, filename: ns, chunks: nn, uploaded_at: ns }));
const base = { id: number, installation_id: nn, repo_full_name: string, pr_number: number, commit_sha: ns, status: reviewStatus, delivery_status: values(null, 'pending', 'posted', 'failed'), started_at: ns, summary: ns, is_fork: boolean, created_at: ns, completed_at: ns, finding_count: number, severity_counts: severityCounts, agent_counts: agentCounts, fixable_count: number, autofix_status: autofixStatus, autofix_branch: ns };
export const parseReviews = parse<ReviewEnvelope>(shape({ items: array(shape({ ...base, degraded_agents: strings })), total: number, limit: number, offset: number }));
const finding = shape({ id: number, agent: values(...agents), severity: values(...severities), title: string, detail: ns, file_path: ns, line: nn, fixable: boolean, fix_data: nullable(object), evidence: nullable(object), rank: number });
const run = shape({ agent: values(...agents), outcome: values(null, 'ok', 'degraded', 'failed', 'unknown'), recorded: boolean, finding_count: number, failure_reason: ns, notes: strings, scanner_statuses: optional(array(shape({ scanner: string, ok: boolean, finding_count: number, error: ns, error_type: ns }))), scanner_info: optional(ns), raw_findings: optional(array(shape({ fingerprint: string, scanner: string, rule_id: string, severity: values(...severities), file_path: ns, line: nn, message: string }))) });
export const parseReview = parse<ReviewDetail>(shape({ ...base, attempt: number, heartbeat_at: ns, progress: array(shape({id:number,attempt:number,stage:values('checkout','analysis','agent','aggregation'),agent:nullable(values(...agents)),status:values('started','ok','degraded','failed'),created_at:string})), delivery_error: ns, comment_id: ns, standards_version: ns, autofix_approved_by: ns, autofix_approved_at: ns, findings: array(finding), findings_by_agent: shape(Object.fromEntries(agents.map(a => [a, optional(array(finding))]))), agent_runs: array(run), autofix: shape({ status: autofixStatus, branch: ns, approved_by: ns, approved_at: ns, applied_count: nn, commit_sha: ns, error: ns, skipped_fixes: array(shape({ reason: string, target: optional(string), target_file: optional(string), target_function: optional(string) })) }) }));
export const parseReport = parse<ReviewReport>(shape({ review_id: number, markdown: string }));
export const parseTrends = parse<TrendsResponse>(shape({ range: shape({ since: ns, until: ns, review_count: number, requested_limit: number, repo: ns }), repos: strings, points: array(shape({ review_id: number, repo_full_name: string, pr_number: number, commit_sha: ns, status: reviewStatus, is_fork: boolean, created_at: ns, total_findings: number, severity_counts: severityCounts, agent_counts: agentCounts, weighted_index: number, degraded_agents: strings, unrecorded_agents: strings, coverage_recorded: boolean, coverage_complete: boolean })), totals: shape({ reviews: number, completed: number, failed: number, skipped: number, findings: number, severity_counts: severityCounts, agent_counts: agentCounts, autofix: shape({ created: number, approved: number, rejected: number }), weights_used: severityCounts, coverage_recorded_reviews: number, coverage_complete_reviews: number, reviews_with_coverage_gap: number }) }));
export const parseCreated = parse<CreateAutofixResponse>(shape({ status: values('created'), branch: string, applied_fixes: number, skipped_fixes: array(shape({ target: string, reason: string })) }));
export const parseAccepted = parse<{ status: 'accepted'; review_id: number }>(shape({ status: values('accepted'), review_id: number }));
export const parseDecision = parse<{ status: 'approved' | 'rejected'; review_id: string }>(shape({ status: values('approved', 'rejected'), review_id: string }));
export const parseStandardsUpload = parse<Omit<Standards, 'has_custom_standards'>>(shape({ installation_id: number, version: ns, filename: ns, chunks: nn, uploaded_at: ns }));
export const parseStandardsReset = parse<{ status: 'deleted'; installation_id: number }>(shape({ status: values('deleted'), installation_id: number }));
export const parseLogout = parse<{ status: 'ok' }>(shape({ status: values('ok') }));
export const parseReadiness = parse<{ status: 'ready' | 'not_ready'; checks: Record<'database' | 'chromadb' | 'worker' | 'configuration', 'ok' | 'unavailable'> }>(shape({ status: values('ready', 'not_ready'), checks: shape(Object.fromEntries(['database', 'chromadb', 'worker', 'configuration'].map(name => [name, values('ok', 'unavailable')]))) }));
export const parseCallback = parse<{ user: Omit<UserProfile, 'installations'> }>(shape({ user: shape({ id: number, github_user_id: number, github_login: string, avatar_url: ns }) }));
