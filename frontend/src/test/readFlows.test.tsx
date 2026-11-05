import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';
import { clearResources } from '../api/resources';
import { backend, review } from './fixtures';
import { parseReview, ContractError, type AgentCoverage } from '../api/contracts';
import { AgentRunCard } from '../components/reviews/ReviewPresentation';
import { AgentOutcomeChart } from '../components/dashboard/AgentOutcomeChart';
beforeEach(() => { sessionStorage.clear(); vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(backend(url)))); });
afterEach(() => { cleanup(); clearResources(); vi.unstubAllGlobals(); });
describe('read-only application flows', () => {
  it('displays partial coverage and saved counts independently of execution', () => {
    const coverage: AgentCoverage = { execution: 'completed', status: 'partial', enrichment: 'skipped',
      eligible_files: ['app.py'], analyzed_files: ['app.py'], excluded_files: [{path:'schema.json',reason:'Non-source artifact'}],
      batches: {completed:6,failed:0,reused:0},findings:21,scanners:[] };
    const detail = review();
    detail.agent_runs[1] = {...detail.agent_runs[1], recorded:true,outcome:'degraded',finding_count:21,coverage};
    const parsed = parseReview(detail);
    render(<AgentRunCard run={parsed.agent_runs[1]} />);
    expect(screen.getByText('21 findings reported')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();
    expect(screen.getByText(/Coverage partial/)).toBeInTheDocument();
    expect(screen.getByText('schema.json — Non-source artifact')).toBeInTheDocument();
    expect(screen.queryByText(/could not run/)).not.toBeInTheDocument();
    parsed.agent_runs[1].outcome = 'ok';
    render(<AgentOutcomeChart reviews={[parsed]} unavailable={0} />);
    expect(screen.queryByText(/completed without limitations/)).not.toBeInTheDocument();
    expect(screen.getAllByText(/recorded with outcome OK/).length).toBe(4);
  });
  it('uses real installation/repository identity and opens canonical review detail', async () => {
    render(<MemoryRouter initialEntries={['/repos']}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByText('View pull requests →'));
    fireEvent.click(await screen.findByText('Review #9 · Completed'));
    expect(await screen.findByText('Review #9 · owner/httpx PR #1')).toBeInTheDocument();
    expect(screen.getAllByText('Coverage not recorded').length).toBeGreaterThan(0);
    expect(screen.getByText('GitHub temporarily unavailable')).toBeInTheDocument();
    expect(screen.getAllByText(/Not recorded/).length).toBeGreaterThan(0);
  });
  it('shows analytics with a single point and both coverage limitations', async () => {
    render(<MemoryRouter initialEntries={['/repos/owner/httpx?installation_id=7&tab=analytics']}><App /></MemoryRouter>);
    expect(await screen.findByText('Degraded/failed: security')).toBeInTheDocument();
    expect(screen.getByText('Unrecorded: quality, test_gap, documentation')).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
  });
  it('accepts historical nullable data but rejects unfamiliar persisted statuses', () => {
    expect(parseReview(review()).agent_runs[1].raw_findings).toBeUndefined();
    expect(() => parseReview({ ...review(), status: 'magically_clean' })).toThrow(ContractError);
  });
  it('renders a completed review with null scanner summaries from non-security agents', async () => {
    const completed = review();
    completed.agent_runs = completed.agent_runs.map(run => ({ ...run, recorded: true, outcome: 'ok', failure_reason: null, scanner_info: null, scanner_statuses: [], raw_findings: [] }));
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/reviews/9') ? new Response(JSON.stringify(completed)) : backend(url))));
    render(<MemoryRouter initialEntries={['/reviews/9']}><App /></MemoryRouter>);
    expect((await screen.findAllByText('Coverage not recorded')).length).toBeGreaterThan(0);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
  it('does not present a queued review as a zero-finding result', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve(url.endsWith('/reviews/9') ? new Response(JSON.stringify(review({ status: 'pending' }))) : backend(url))));
    render(<MemoryRouter initialEntries={['/reviews/9']}><App /></MemoryRouter>);
    expect(await screen.findByText('Findings and agent results are not available yet.')).toBeInTheDocument();
    expect(screen.queryByText('0 findings reported')).not.toBeInTheDocument();
    expect(screen.queryByText(/coverage incomplete or unrecorded/)).not.toBeInTheDocument();
  });
});
