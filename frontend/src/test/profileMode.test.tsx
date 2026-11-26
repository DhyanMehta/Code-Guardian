import {cleanup,render,screen,fireEvent,waitFor,within} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {MemoryRouter} from 'react-router-dom';
import App from '../App';
import {backend,json} from './fixtures';
import {clearResources} from '../api/resources';
import {clearWriteStates} from '../api/writes';
afterEach(()=>{cleanup();clearResources();clearWriteStates();vi.unstubAllGlobals();});
const policy=(mode='mixed',version='one')=>({review_mode:mode,version,installations:[{id:7,account_login:'owner',review_mode:mode==='mixed'?'auto':mode},{id:8,account_login:'team',review_mode:mode==='mixed'?'manual':mode}]});
it('saves one policy for every administered installation and confirms the server result',async()=>{
  let current=policy();
  const fetch=vi.fn((url:string,init?:RequestInit)=>{
    if(url.endsWith('/profile/review-mode')){
      if(init?.method==='PATCH') {expect(JSON.parse(init.body as string)).toEqual({review_mode:'manual',version:'one'});current=policy('manual','two');}
      return Promise.resolve(json(current));
    }
    return Promise.resolve(backend(url));
  });vi.stubGlobal('fetch',fetch);
  render(<MemoryRouter initialEntries={['/profile']}><App/></MemoryRouter>);
  const draft = await screen.findByLabelText('Review mode');
  const apply = screen.getByRole('button',{name:'Apply to 2 installations'});
  expect(draft).toHaveValue('');
  expect(apply).toBeDisabled();
  const affected = within(screen.getByRole('list', { name: 'Affected installations' }));
  expect(affected.getByText('owner')).toBeVisible();
  expect(affected.getByText('team')).toBeVisible();
  fireEvent.change(draft,{target:{value:'manual'}});
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(0);
  fireEvent.click(apply);
  expect(await screen.findByText('Saved Manual for 2 administered installations.')).toBeInTheDocument();
  await waitFor(() => expect(draft).toHaveValue('manual'));
  expect(apply).toBeDisabled();
  fireEvent.change(draft,{target:{value:'auto'}});
  expect(screen.queryByText('Saved Manual for 2 administered installations.')).toBeNull();
  expect(fetch.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1);
});
it('shows a policy conflict without claiming the change was saved',async()=>{
  vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>Promise.resolve(url.endsWith('/profile/review-mode')?init?.method==='PATCH'?json({detail:'Review policy changed. Refresh before applying again.'},409):json(policy()):backend(url))));
  render(<MemoryRouter initialEntries={['/profile']}><App/></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Review mode'),{target:{value:'manual'}});
  fireEvent.click(screen.getByRole('button',{name:'Apply to 2 installations'}));
  expect(await screen.findByText(/Review policy changed/)).toBeInTheDocument();
  expect(screen.getByRole('button',{name:'Apply to 2 installations'})).toBeDisabled();
  expect(screen.queryByText(/Saved Manual/)).not.toBeInTheDocument();
});

it('explains missing administered installations without exposing an Apply action', async () => {
  const read = vi.fn((url: string, _options?: RequestInit) => Promise.resolve(url.endsWith('/profile/review-mode')
    ? json({ installations: [], review_mode: null, version: 'empty' }) : backend(url)));
  vi.stubGlobal('fetch', read);
  render(<MemoryRouter initialEntries={['/profile?installation_id=7']}><App/></MemoryRouter>);
  expect(await screen.findByText(/You do not administer any active installations/)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Apply to/ })).toBeNull();
  expect(read.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
});
