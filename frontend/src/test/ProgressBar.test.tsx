import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressBar } from '../components/common/ProgressBar';

describe('ProgressBar component', () => {
  it('renders single value progress bar with accessible role and attributes', () => {
    render(<ProgressBar value={40} max={100} aria-label="Review progress" />);
    const bar = screen.getByRole('progressbar', { name: /review progress/i });
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute('aria-valuenow', '40');
    expect(bar).toHaveAttribute('aria-valuemax', '100');
  });

  it('renders multi-color segment variant with proportional widths', () => {
    const segments = [
      { key: 'high', value: 1, colorClass: 'bg-severity-high', label: 'High' },
      { key: 'medium', value: 2, colorClass: 'bg-severity-medium', label: 'Medium' },
      { key: 'low', value: 1, colorClass: 'bg-severity-low', label: 'Low' },
    ];

    render(<ProgressBar segments={segments} aria-label="Severity distribution" />);
    const bar = screen.getByRole('progressbar', { name: /severity distribution/i });
    expect(bar).toBeInTheDocument();
    expect(bar).toHaveAttribute('aria-valuenow', '4');

    // Total = 4. High is 1/4 = 25%
    const highSegment = screen.getByTitle('High: 1');
    expect(highSegment).toBeInTheDocument();
    expect(highSegment).toHaveStyle({ width: '25%' });
  });
});
