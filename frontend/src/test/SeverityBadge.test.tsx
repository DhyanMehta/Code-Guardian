import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '../components/common/SeverityBadge';

describe('SeverityBadge component', () => {
  it('renders critical severity with label and icon for accessibility', () => {
    const { container } = render(<SeverityBadge severity="critical" />);
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    expect(screen.getByRole('status', { name: /severity: critical/i })).toBeInTheDocument();
    // Verify an svg icon is rendered inside (shape encoding)
    expect(container.querySelector('svg')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('bg-severity-critical-bg');
  });

  it('renders high, medium, and low severities', () => {
    const { rerender } = render(<SeverityBadge severity="high" />);
    expect(screen.getByText('HIGH')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('bg-severity-high-bg');

    rerender(<SeverityBadge severity="medium" />);
    expect(screen.getByText('MEDIUM')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('bg-severity-medium-bg');

    rerender(<SeverityBadge severity="low" />);
    expect(screen.getByText('LOW')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveClass('bg-severity-low-bg');
  });

  it('handles unknown or fallback severity gracefully', () => {
    render(<SeverityBadge severity="unknown" />);
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
  });
});
