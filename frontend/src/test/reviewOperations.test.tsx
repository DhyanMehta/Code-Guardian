import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AgentTimeline } from '../components/reviews/AgentTimeline';
import { ReviewDelivery } from '../components/reviews/ReviewDelivery';
import { AutofixActions } from '../components/reviews/AutofixActions';
import { clearResources } from '../api/resources';
import { clearWriteStates } from '../api/writes';
import type { DeliveryStatus, ProgressEvent, ReviewDetail } from '../api/contracts';
import { json, review } from './fixtures';

afterEach(() => { cleanup(); clearResources(); clearWriteStates(); vi.unstubAllGlobals(); });

it('preserves concurrent checkpoints and earlier attempt failures in recorded order', () => {
  const event: ProgressEvent = { id: 1, attempt: 1, agent: 'security', stage: 'agent', status: 'failed', created_at: '2026-10-01T10:00:00.123456Z' };
  const events: ProgressEvent[] = [event,
    {...event,id:2,attempt:2,status:'started',stage:'provider_token',agent:'quality'},
    {...event,id:3,attempt:2,status:'reused',agent:'security',created_at:'unknown-time'}];
  const view = render(<AgentTimeline review={review({ attempt:2,status:'running',progress:events })} />);
  expect(screen.getByText('Waiting for token allowance')).toBeVisible();
  expect(screen.queryByRole('progressbar')).toBeNull();
  expect(within(screen.getByRole('article',{name:'Attempt 1'})).getByText('Failed', {selector:'strong'})).toBeVisible();
  const current = screen.getByRole('article',{name:'Attempt 2'});
  fireEvent.click(within(current).getByText('Execution history · attempt 2'));
  const rows = within(current).getAllByRole('listitem');
  expect(rows[0]).toHaveTextContent('Quality · Token allowance');
  expect(rows[1]).toHaveTextContent('Security · Agent checkpointReused');
  expect(rows[1]).toHaveTextContent('Time unavailable');
  const control = rows[0].querySelector('summary')!;
  fireEvent.click(control); control.focus();
  expect(rows[0]).toHaveTextContent(event.created_at);
  view.rerender(<AgentTimeline review={review({attempt:2,status:'running',progress:[...events]})}/>);
  expect(control).toHaveFocus();
  expect(control.parentElement).toHaveAttribute('open');
});

it.each([
  ['posted','68','Posted',true], ['posted','../6','Posted',false], ['posted',null,'Posted',false],
  ['pending','68','Pending',false], ['failed','68','Failed',false], [null,null,'Not recorded',false],
] as const)('uses only recorded delivery %s and comment %s', (state, comment, label, link) => {
  render(<ReviewDelivery review={review({delivery_status:state as DeliveryStatus,comment_id:comment})} userId={1}/>);
  expect(screen.getByText(label)).toBeVisible();
  const destination = screen.queryByRole('link',{name:'View GitHub Report'});
  if (link) expect(destination).toHaveAttribute('href','https://github.com/owner/httpx/pull/1#issuecomment-68');
  else expect(destination).toBeNull();
});

it('keeps report retrieval explicit, retries a failed read and handles missing text', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(json({detail:'Report unavailable'},404))
    .mockResolvedValueOnce(json({review_id:9,markdown:''}));
  vi.stubGlobal('fetch',fetch);
  render(<ReviewDelivery userId={1} review={review({delivery_error:'Authorization: Bearer private-fixture-value'})}/>);
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.queryByText(/private-fixture-value/)).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Saved / rendered report'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Report unavailable');
  fireEvent.click(screen.getByRole('button',{name:'Retry'}));
  expect(await screen.findByText(/Report text is unavailable/)).toBeVisible();
  expect(fetch.mock.calls.map(([url,init]) => [new URL(url).pathname,init.method])).toEqual([['/reviews/9/report','GET'],['/reviews/9/report','GET']]);
});

function actions(r: ReviewDetail, head: string | null = 'head-1') {
  return <MemoryRouter><AutofixActions key={r.id} userId={1} review={r} head={{data:head,loading:false,refresh:vi.fn()}} /></MemoryRouter>;
}

it.each([
  ['Create fix branch', null, '/reviews/9/autofix', {status:'created',branch:'fix/9',applied_fixes:1,skipped_fixes:[]}],
  ['Approve fix branch', 'pending_approval', '/reviews/9/autofix/approve', {status:'approved',review_id:'9'}],
  ['Reject fix branch', 'pending_approval', '/reviews/9/autofix/reject', {status:'rejected',review_id:'9'}],
] as const)('submits one bodyless request for %s after an explicit activation', async (name,status,path,response) => {
  const fetch = vi.fn().mockResolvedValue(json(response));
  vi.stubGlobal('fetch',fetch);
  const r = review({fixable_count:1});
  render(actions({...r,autofix:{...r.autofix,status}}));
  fireEvent(window,new Event('resize'));
  expect(fetch).not.toHaveBeenCalled();
  const button = screen.getByRole('button',{name});
  await act(async () => { fireEvent.click(button); fireEvent.click(button); });
  expect(fetch).toHaveBeenCalledTimes(1);
  const [url,init] = fetch.mock.calls[0];
  expect(new URL(url).pathname).toBe(path);
  expect(init.method).toBe('POST');
  expect(init.body).toBeUndefined();
});

it('honors fork and eligible-draft guards and leaves unconfirmed head validation with the server', () => {
  const r = review({fixable_count:1});
  const view = render(actions({...r,is_fork:true}));
  const button = screen.getByRole('button',{name:'Create fix branch'});
  expect(button).toBeDisabled();
  expect(screen.getByText(/unavailable for fork PRs/)).toBeVisible();
  view.rerender(actions({...r,fixable_count:0}));
  expect(button).toBeDisabled();
  expect(screen.getByText('No eligible drafts in this review.')).toBeVisible();
  view.rerender(actions(r,null));
  expect(screen.getByText(/Revision · Current revision unconfirmed/)).toBeVisible();
  expect(screen.getByText(/server verifies the current PR revision/)).toBeVisible();
  view.rerender(actions({...r,autofix:{...r.autofix,status:'pending_approval',branch:'fix/9'}},null));
  expect(screen.getByText(/Refresh the PR head to check whether the reviewed revision is current/)).toBeVisible();
  expect(screen.queryByText(/server verifies the current PR revision/)).toBeNull();
});

it('keeps a denied decision readable and prevents repeated prohibited requests', async () => {
  const fetch = vi.fn().mockResolvedValue(json({detail:'Repository write permission required'},403));
  vi.stubGlobal('fetch',fetch);
  const r = review();
  render(actions({...r,autofix:{...r.autofix,status:'pending_approval',branch:'fix/review-9'}}));
  const reject = screen.getByRole('button',{name:'Reject fix branch'});
  fireEvent.click(reject);
  expect(await screen.findByRole('alert')).toHaveTextContent('Repository write permission required');
  expect(reject).toBeDisabled();
  expect(screen.getByRole('link',{name:'fix/review-9'})).toBeVisible();
  fireEvent.click(reject);
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1]).toMatchObject({method:'POST',body:undefined});
});

it('guards duplicate activation and keeps a late ambiguous write isolated to its review', async () => {
  let settle!: (value: Response) => void;
  const fetch = vi.fn(() => new Promise<Response>(resolve=>{settle=resolve;}));
  vi.stubGlobal('fetch',fetch);
  const r = review({fixable_count:1});
  const view = render(actions(r));
  const create = screen.getByRole('button',{name:'Create fix branch'});
  fireEvent.click(create); fireEvent.click(create);
  expect(create).toHaveAttribute('aria-busy','true');
  view.rerender(actions({...r,id:10}));
  await act(async () => settle(json({detail:'Outcome unavailable'},503)));
  expect(screen.queryByRole('alert')).toBeNull();
  view.rerender(actions(r));
  expect(screen.getByRole('button',{name:'Create fix branch'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button',{name:/I checked the current state/}));
  expect(screen.getByRole('button',{name:'Create fix branch'})).toBeEnabled();
  expect(fetch).toHaveBeenCalledTimes(1);
});
