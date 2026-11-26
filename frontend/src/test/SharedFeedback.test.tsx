import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AsyncState } from '../components/common/AsyncState';
import { StatusBadge } from '../components/common/StatusBadge';
import { WriteFeedback } from '../components/common/WriteFeedback';
import { ScopedRefreshStatus } from '../components/common/ScopedRefreshStatus';

it('withholds credential-bearing read and write errors while preserving the scoped recovery actions', () => {
  const message = JSON.stringify({ password: 'fixture-only' });
  const retry = vi.fn();
  const { rerender } = render(<AsyncState error={new Error(message)} refresh={retry} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Diagnostic text withheld');
  expect(screen.getByRole('button', { name: 'Retry' })).toBeEnabled();
  rerender(<ScopedRefreshStatus sources={[{label:'Review',loading:false,hasData:true,error:new Error(message),refresh:retry}]} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Updates delayed. Diagnostic text withheld');
  expect(screen.getByRole('button', {name:'Retry review'})).toBeEnabled();
  rerender(<WriteFeedback error={message} uncertain reconcile={retry} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Diagnostic text withheld');
  expect(screen.getByRole('button', {name:/explicit retry/})).toBeEnabled();
  expect(document.body).not.toHaveTextContent('fixture-only');
});

describe('StatusBadge', () => {
  it.each([
    ['completed', 'Completed'], ['running', 'Running'], ['pending', 'Queued'],
    ['failed', 'Failed'], ['skipped', 'Skipped'], ['degraded', 'Degraded'], ['unknown', 'Unknown'],
  ] as const)('exposes %s as static %s text', (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeVisible();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('AsyncState', () => {
  it('announces initial loading and keeps background refresh and fetch time quiet', () => {
    const { rerender } = render(<AsyncState loading />);
    expect(screen.getByRole('status')).toHaveTextContent('Loading…');
    rerender(<AsyncState loading hasData updatedAt={0} showExactFetchTime />);
    expect(screen.getByText('Refreshing…')).toBeVisible();
    expect(screen.getByText(/Last successful fetch/)).toBeVisible();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('retains a scoped stale-data message and only retries on activation', () => {
    const refresh = vi.fn();
    const { rerender } = render(<AsyncState error={new Error('Repository access unavailable')} hasData updatedAt={0} refresh={refresh} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Updates delayed. Repository access unavailable');
    expect(screen.getByText(/Last updated/)).toBeVisible();
    expect(refresh).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(refresh).toHaveBeenCalledTimes(1);
    rerender(<AsyncState error={new Error('Repository access unavailable')} hasData loading updatedAt={0} refresh={refresh} />);
    expect(screen.getByRole('alert')).toBe(alert);
  });
});

describe('WriteFeedback', () => {
  it('shows operation-specific busy and confirmed text only when supplied', () => {
    const reconcile = vi.fn();
    const { rerender } = render(<WriteFeedback busy busyMessage="Saving installation settings…" success="Old result" uncertain={false} reconcile={reconcile} />);
    expect(screen.getByRole('status')).toHaveTextContent('Saving installation settings…');
    expect(screen.queryByText('Old result')).not.toBeInTheDocument();
    rerender(<WriteFeedback success="Saved Automatic for 1 administered installation." uncertain={false} reconcile={reconcile} />);
    expect(screen.getByRole('status')).toHaveTextContent('Saved Automatic for 1 administered installation.');
    expect(reconcile).not.toHaveBeenCalled();
  });

  it.each(['Choose a Markdown file.', 'Permission denied.', 'Policy version conflict.'])(
    'retains the operation error %s without offering reconciliation',
    error => {
      render(<WriteFeedback error={error} uncertain={false} reconcile={vi.fn()} />);
      expect(screen.getByRole('alert')).toHaveTextContent(error);
      expect(screen.queryByRole('button')).not.toBeInTheDocument();
    },
  );

  it('suppresses success during uncertainty and requires explicit reconciliation', () => {
    const reconcile = vi.fn();
    render(<WriteFeedback error="Network error." success="Saved" uncertain reconcile={reconcile} />);
    expect(screen.getByRole('alert')).toHaveTextContent('The server may have completed this action');
    expect(screen.queryByText('Saved')).not.toBeInTheDocument();
    expect(reconcile).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: /allow an explicit retry/ }));
    expect(reconcile).toHaveBeenCalledTimes(1);
  });
});
