import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SeverityBadge } from '../components/common/SeverityBadge';

describe('SeverityBadge component', () => {
  it.each([
    ['critical', 'Critical'],
    ['high', 'High'],
    ['medium', 'Medium'],
    ['low', 'Low'],
    ['info', 'Info'],
    ['unknown', 'Unknown'],
  ])('shows %s as a static text label with a decorative icon', (severity, label) => {
    const { container } = render(<SeverityBadge severity={severity} />);
    expect(screen.getByText(label).parentElement).toHaveClass(`bg-risk-${severity}-bg`);
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('normalizes case and preserves the unknown fallback', () => {
    const { rerender } = render(<SeverityBadge severity="HIGH" />);
    expect(screen.getByText('High')).toBeInTheDocument();
    rerender(<SeverityBadge severity="constructor" />);
    expect(screen.getByText('Unknown')).toBeInTheDocument();
  });

  it('keeps text available in icon-only mode', () => {
    render(<SeverityBadge severity="critical" showLabel={false} />);
    expect(screen.getByText('Critical')).toHaveClass('sr-only');
  });
});
