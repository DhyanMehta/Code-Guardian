import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GitPullRequest } from 'lucide-react';
import { StatCard } from '../components/common/StatCard';

describe('StatCard component', () => {
  it('renders label and large value correctly', () => {
    render(
      <StatCard
        label="Open PRs"
        value={14}
        secondaryText="Active branches"
        icon={<GitPullRequest data-testid="pr-icon" />}
      />
    );

    expect(screen.getByText('Open PRs')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('Active branches')).toBeInTheDocument();
    expect(screen.getByTestId('pr-icon')).toBeInTheDocument();
  });

  it('renders trend text when provided', () => {
    render(
      <StatCard
        label="Reviews"
        value={42}
        trend={{ direction: 'up', text: '+4 from yesterday' }}
      />
    );

    expect(screen.getByText('+4 from yesterday')).toBeInTheDocument();
  });

  it('keeps the value and unit as static, non-focusable content', () => {
    render(<StatCard id="metric" label="Failed / skipped" value="0 / 1" />);
    const value = screen.getByText('0 / 1');
    const card = value.closest('#metric');
    expect(value.tagName).toBe('DD');
    expect(screen.getByText('Failed / skipped').tagName).toBe('DT');
    expect(card).not.toHaveAttribute('tabindex');
    expect(card?.className).not.toMatch(/hover:|cursor-pointer/);
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
