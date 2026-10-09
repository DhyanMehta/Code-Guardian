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
});
