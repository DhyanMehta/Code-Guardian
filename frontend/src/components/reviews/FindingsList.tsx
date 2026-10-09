import { useState } from 'react';
import { agents, severities, type Finding } from '../../api/contracts';
import { FindingCard, agentLabels } from './ReviewPresentation';
export function FindingsList({findings,reviewId}:{findings:Finding[];reviewId:number}) {
  const [agent,setAgent]=useState('all'),[severity,setSeverity]=useState('all'),[query,setQuery]=useState('');
  const selected=findings.filter(f=>(agent==='all'||f.agent===agent)&&(severity==='all'||f.severity===severity)&&`${f.title} ${f.file_path??''} ${f.detail??''}`.toLowerCase().includes(query.toLowerCase()));
  if (!findings.length) return null;
  return <section className="space-y-3"><div className="flex flex-wrap gap-3"><label>Agent <select aria-label="Filter findings by agent" className="bg-neutral-900 border rounded p-2" value={agent} onChange={e=>setAgent(e.target.value)}><option value="all">All agents</option>{agents.map(a=><option key={a} value={a}>{agentLabels[a]}</option>)}</select></label><label>Severity <select aria-label="Filter findings by severity" className="bg-neutral-900 border rounded p-2" value={severity} onChange={e=>setSeverity(e.target.value)}><option value="all">All severities</option>{severities.map(s=><option key={s}>{s}</option>)}</select></label><input className="min-w-0 bg-neutral-900 border rounded p-2" type="search" aria-label="Search findings" placeholder="Search findings or files…" value={query} onChange={e=>setQuery(e.target.value)}/></div><p className="text-sm text-neutral-400">Showing {selected.length} of {findings.length} findings</p>{!selected.length&&!!findings.length&&<p>No findings match these filters.</p>}{selected.map(f=><FindingCard key={`${reviewId}:${f.id}`} finding={f} initiallyOpen={selected.length<=5}/>)}</section>;
}
