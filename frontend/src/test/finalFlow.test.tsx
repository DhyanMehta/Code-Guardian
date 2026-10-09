import {cleanup,render,screen,fireEvent} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import App from '../App';
import {backend,json,user,review} from './fixtures';
import {clearResources} from '../api/resources';
import {clearWriteStates} from '../api/writes';
import {navigation} from '../context/AuthContext';
import {AgentTimeline} from '../components/reviews/AgentTimeline';
import {AgentOutcomeChart} from '../components/dashboard/AgentOutcomeChart';
afterEach(()=>{cleanup();clearResources();clearWriteStates();sessionStorage.clear();vi.restoreAllMocks();vi.unstubAllGlobals();});
it('sends a first-time user to the server-owned GitHub installer only once',async()=>{
  const assign=vi.spyOn(navigation,'assign').mockImplementation(()=>{});
  vi.stubGlobal('fetch',vi.fn((url:string)=>Promise.resolve(url.endsWith('/auth/me') || url.endsWith('/auth/installations/refresh')?json({...user,installations:[]}):url.endsWith('/auth/installation-url')?json({url:'https://github.com/apps/guardian/installations/new'}):backend(url))));
  const view=render(<MemoryRouter initialEntries={['/auth/install']}><App/></MemoryRouter>);
  expect(await screen.findByRole('link',{name:'Choose repositories on GitHub'})).toHaveAttribute('href','https://github.com/apps/guardian/installations/new');
  expect(assign).toHaveBeenCalledTimes(1);
  view.unmount();render(<MemoryRouter initialEntries={['/auth/install']}><App/></MemoryRouter>);
  await screen.findByRole('link',{name:'Choose repositories on GitHub'});expect(assign).toHaveBeenCalledTimes(1);
});
it('automatically reconciles installation return without a second OAuth login',async()=>{
  const fetch=vi.fn((url:string)=>Promise.resolve(url.endsWith('/auth/me')?json({...user,installations:[]}):url.endsWith('/auth/installations/refresh')?json(user):url.endsWith('/auth/installation-url')?json({url:'https://github.com/apps/guardian/installations/new'}):backend(url)));
  vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter initialEntries={['/auth/install?installation_id=999&setup_action=install']}><App/></MemoryRouter>);
  expect(await screen.findByText('owner/httpx')).toBeInTheDocument();
  expect(fetch.mock.calls.filter(([u])=>u.endsWith('/auth/installations/refresh'))).toHaveLength(1);
  expect(fetch.mock.calls.some(([u])=>u.endsWith('/auth/github/login'))).toBe(false);
});
it('keeps profile mode read-only without administered installations',async()=>{
  vi.stubGlobal('fetch',vi.fn((url:string)=>Promise.resolve(url.endsWith('/profile/review-mode')?json({installations:[],review_mode:null,version:'empty'}):backend(url))));
  render(<MemoryRouter initialEntries={['/profile']}><App/></MemoryRouter>);
  expect(await screen.findByText(/You do not administer any active installations/)).toBeInTheDocument();
  expect(screen.queryByLabelText('Review mode')).not.toBeInTheDocument();
});
it('shows current-attempt progress and does not claim an interrupted agent succeeded',()=>{
  const r=review({status:'failed',attempt:2,progress:[{id:1,attempt:1,stage:'agent',agent:'security',status:'ok',created_at:'2026-10-09T00:00:00Z'},{id:2,attempt:2,stage:'agent',agent:'security',status:'started',created_at:'2026-10-09T00:01:00Z'}]});
  render(<AgentTimeline review={r}/>);expect(screen.getByText('Interrupted')).toBeInTheDocument();expect(screen.queryByText('Completed')).not.toBeInTheDocument();
});
it('charts terminal coverage separately from active and unavailable reviews',()=>{
  render(<AgentOutcomeChart reviews={[review(),review({status:'running'})]} unavailable={1}/>);
  expect(screen.getByText(/1 terminal reviews · 1 active · 1 unavailable/)).toBeInTheDocument();
  expect(screen.getByRole('img',{name:'Security: 0 ok, 1 degraded, 0 failed, 0 unrecorded'})).toBeInTheDocument();
});
it('filters real findings by severity without changing total findings',async()=>{
  const finding={id:1,agent:'security',severity:'high',title:'SQL construction',detail:null,file_path:'app.py',line:2,fixable:false,fix_data:null,evidence:null,rank:1};
  vi.stubGlobal('fetch',vi.fn((url:string)=>Promise.resolve(url.endsWith('/reviews/9')?json(review({findings:[finding as never],finding_count:1})):backend(url))));
  render(<MemoryRouter initialEntries={['/reviews/9']}><App/></MemoryRouter>);await screen.findByText('SQL construction');
  expect(screen.getByText(/Execution history · attempt/).closest('details')).not.toHaveAttribute('open');
  fireEvent.change(screen.getByLabelText('Filter findings by severity'),{target:{value:'low'}});
  expect(screen.getByText('Showing 0 of 1 findings')).toBeInTheDocument();expect(screen.getByText('1 findings reported')).toBeInTheDocument();
});
