import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Shield } from 'lucide-react';
import { IconButton } from '../components/common/IconButton';

describe('IconButton component', () => {
  it('renders with accessible aria-label and icon', () => {
    render(
      <IconButton
        icon={<Shield data-testid="shield-icon" />}
        aria-label="Security Shield"
      />
    );
    const button = screen.getByRole('button', { name: /security shield/i });
    expect(button).toBeInTheDocument();
    expect(screen.getByTestId('shield-icon')).toBeInTheDocument();
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(
      <IconButton
        icon={<Shield />}
        aria-label="Action"
        onClick={handleClick}
      />
    );
    fireEvent.click(screen.getByRole('button', { name: /action/i }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
