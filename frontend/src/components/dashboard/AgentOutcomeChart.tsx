import { agents, type ReviewDetail } from '../../api/contracts';
import { agentLabels } from '../reviews/ReviewPresentation';
const categories = ['ok','degraded','failed','unrecorded'] as const;
const colors = {ok:'bg-tertiary-500',degraded:'bg-yellow-500',failed:'bg-red-500',unrecorded:'bg-neutral-600'};
export function AgentOutcomeChart({reviews,unavailable}:{reviews:ReviewDetail[];unavailable:number}) {
  const completed=reviews.filter(r=>['completed','failed','skipped'].includes(r.status));
  return <section className="rounded-xl border border-neutral-800 p-5 space-y-4"><h2 className="font-semibold">Agent outcomes in loaded history</h2><p className="text-sm text-neutral-400">{completed.length} terminal reviews · {reviews.length-completed.length} active · {unavailable} unavailable. Counts are review outcomes, not execution coverage or a live agent workload.</p>{agents.map(agent=>{
    const counts={ok:0,degraded:0,failed:0,unrecorded:0};
    for(const review of completed){const run=review.agent_runs.find(r=>r.agent===agent);const outcome=run?.recorded&&['ok','degraded','failed'].includes(run.outcome??'') ? run.outcome as 'ok'|'degraded'|'failed' : 'unrecorded';counts[outcome]++;}
    return <div key={agent} className="space-y-2"><h3>{agentLabels[agent]}</h3><div role="img" aria-label={`${agentLabels[agent]}: ${categories.map(c=>`${counts[c]} ${c}`).join(', ')}`} className="h-4 flex overflow-hidden rounded bg-neutral-800">{categories.map(c=><span key={c} className={colors[c]} style={{width:`${completed.length?counts[c]/completed.length*100:0}%`}}/>)}</div><p className="text-xs text-neutral-400">{categories.map(c=>`${c === 'ok' ? 'Successful' : c}: ${counts[c]}`).join(' · ')}</p></div>;
  })}</section>;
}
