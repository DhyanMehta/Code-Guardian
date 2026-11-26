import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { request } from '../../api/client';
import { parseAccepted, type PullRequest, type ReviewItem, type ReviewMode } from '../../api/contracts';
import { repoPath } from '../../api/endpoints';
import { useWrite } from '../../api/writes';
import { invalidateResources } from '../../api/resources';
import { classifyPrActions, type HistoryState } from '../dashboard/prActions';
import { PullRequestRow } from '../dashboard/PullRequestRow';

interface Props {
  userId: number;
  installation: number;
  repo: string;
  pr: PullRequest;
  latest?: ReviewItem;
  review?: ReviewItem;
  history: HistoryState;
  mode: ReviewMode;
  refreshHistory: () => void;
  loadOlder: () => void;
}

export function TriggerReview({ userId, installation, repo, pr, latest, review, history, mode, refreshHistory, loadOlder }: Props) {
  const write = useWrite(`u:${userId}:trigger:${installation}:${repo}:${pr.number}`);
  const navigate = useNavigate();
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; };
  }, []);
  const previous = useRef<number | null | undefined>(undefined);
  useEffect(() => {
    if (history === 'ready' || history === 'bounded') {
      if (latest && previous.current !== undefined && latest.id !== previous.current) write.reconcile();
      if (latest || history === 'ready') previous.current = latest?.id ?? null;
    }
  }, [latest, history, write.reconcile]);

  const actions = classifyPrActions({ history, review, mode, head: pr.head_sha,
    busy: write.busy, uncertain: write.uncertain, writeDenied: write.errorStatus === 403 });

  async function submit() {
    if (!actions.mutation || actions.disabled) return;
    const result = await write.run(
      () => request(`${repoPath(installation, repo)}/pulls/${pr.number}/review`, parseAccepted, { method: 'POST' }),
      () => invalidateResources(`u:${userId}:i:${installation}:repo:${repo}:`),
    );
    if (result && alive.current) navigate(`/reviews/${result.review_id}`);
  }
  return <PullRequestRow pr={pr} repo={repo} review={review} actions={actions} feedback={write}
    onSubmit={() => void submit()} onRecover={actions.primary === 'older' ? loadOlder : refreshHistory} />;
}
