import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { request } from '../../api/client';
import { parseAccepted, type ReviewItem } from '../../api/contracts';
import { repoPath } from '../../api/endpoints';
import { activeReview } from '../../api/identity';
import { useWrite } from '../../api/writes';
import { invalidateResources } from '../../api/resources';
import { Button } from '../common/Button';
import { WriteFeedback } from '../common/WriteFeedback';
export function TriggerReview({ userId, installation, repo, number, latest }: { userId: number; installation: number; repo: string; number: number; latest?: ReviewItem }) {
  const write = useWrite(`u:${userId}:trigger:${installation}:${repo}:${number}`), navigate = useNavigate();
  const alive = useRef(true); useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const previous = useRef(latest?.id);
  useEffect(() => { if (latest?.id !== previous.current) { previous.current = latest?.id; write.reconcile(); } }, [latest?.id, write.reconcile]);
  const submit = async () => {
    const result = await write.run(() => request(`${repoPath(installation, repo)}/pulls/${number}/review`, parseAccepted, { method: 'POST' }), () => invalidateResources(`u:${userId}:i:${installation}:repo:${repo}:`));
    if (result && alive.current) navigate(`/reviews/${result.review_id}`);
  };
  return <div className="space-y-2"><Button size="sm" disabled={write.busy || write.uncertain || !!latest && activeReview(latest.status)} onClick={() => void submit()}>{write.busy ? 'Requesting review…' : latest ? 'Run a new review' : 'Review pull request'}</Button><WriteFeedback {...write} /></div>;
}
