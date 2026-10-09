import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { AgentHistoryDots } from '../components/common/AgentHistoryDots';

describe('AgentHistoryDots', () => {
  it('uses distinct tooltip IDs and Escape dismisses unknown outcomes', () => {
    const unknown = [{ reviewId: 1, outcome: 'unknown' as const, failureReason: null }];
    render(<><AgentHistoryDots dots={unknown} /><AgentHistoryDots dots={unknown} /></>);
    const buttons = screen.getAllByRole('button'); fireEvent.focus(buttons[0]); fireEvent.focus(buttons[1]);
    const ids = screen.getAllByRole('tooltip').map(el => el.id); expect(new Set(ids).size).toBe(2);
    fireEvent.keyDown(buttons[0], { key: 'Escape' }); expect(screen.getAllByRole('tooltip')).toHaveLength(1);
  });
  const dots = [
    { reviewId: 34, outcome: 'ok' as const, failureReason: null },
    {
      reviewId: 35,
      outcome: 'degraded' as const,
      failureReason: 'LLM triage failed (LLMRateLimitError); 1 scanner finding(s) left untriaged.',
    },
    { reviewId: 36, outcome: 'ok' as const, failureReason: null },
  ];

  it('renders one button per dot', () => {
    render(<AgentHistoryDots dots={dots} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(3);
  });

  it('renders empty state when no dots', () => {
    render(<AgentHistoryDots dots={[]} />);
    expect(screen.getByText(/No history/i)).toBeTruthy();
  });

  it('aria-label includes outcome and failure reason', () => {
    render(<AgentHistoryDots dots={dots} />);
    const degradedBtn = screen.getByRole('button', {
      name: /Review #35.*Degraded.*LLMRateLimitError/i,
    });
    expect(degradedBtn).toBeTruthy();
  });

  it('shows tooltip on focus', () => {
    render(<AgentHistoryDots dots={dots} />);
    const degradedBtn = screen.getByRole('button', {
      name: /Review #35/i,
    });
    fireEvent.focus(degradedBtn);
    // Tooltip renders review ID on focus
    expect(screen.getByText('Review #35')).toBeTruthy();
  });

  it('hides tooltip on blur', () => {
    render(<AgentHistoryDots dots={dots} />);
    const degradedBtn = screen.getByRole('button', {
      name: /Review #35/i,
    });
    fireEvent.focus(degradedBtn);
    expect(screen.getByText('Review #35')).toBeTruthy();
    fireEvent.blur(degradedBtn);
    expect(screen.queryByText('Review #35')).toBeNull();
  });
});
