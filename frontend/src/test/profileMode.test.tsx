import {cleanup,render,screen,fireEvent} from '@testing-library/react';
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
  fireEvent.change(await screen.findByLabelText('Review mode'),{target:{value:'manual'}});
  fireEvent.click(screen.getByRole('button',{name:'Apply to all administered installations'}));
  expect(await screen.findByText('Saved Manual for 2 administered installations.')).toBeInTheDocument();
});
it('shows a policy conflict without claiming the change was saved',async()=>{
  vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>Promise.resolve(url.endsWith('/profile/review-mode')?init?.method==='PATCH'?json({detail:'Review policy changed. Refresh before applying again.'},409):json(policy()):backend(url))));
  render(<MemoryRouter initialEntries={['/profile']}><App/></MemoryRouter>);
  fireEvent.change(await screen.findByLabelText('Review mode'),{target:{value:'manual'}});
  fireEvent.click(screen.getByRole('button',{name:'Apply to all administered installations'}));
  expect(await screen.findByText(/Review policy changed/)).toBeInTheDocument();
  expect(screen.queryByText(/Saved Manual/)).not.toBeInTheDocument();
});
