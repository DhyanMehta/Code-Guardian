import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '../components/common/Button';

describe('Button component', () => {
  it('renders children correctly', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('uses distinct styles for existing and new action variants', () => {
    const { rerender } = render(<Button variant="primary">Primary</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-action');

    rerender(<Button variant="secondary">Secondary</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-action-secondary');

    rerender(<Button variant="inverted">Inverted</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-neutral-100');

    rerender(<Button variant="outlined">Outlined</Button>);
    expect(screen.getByRole('button')).toHaveClass('border-control-border');

    rerender(<Button variant="quiet">Quiet</Button>);
    expect(screen.getByRole('button')).toHaveClass('control-target', 'control-focus', 'bg-transparent');

    rerender(<Button variant="destructive">Destructive</Button>);
    expect(screen.getByRole('button')).toHaveClass('bg-action-danger');
  });

  it('handles click events', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Trigger</Button>);
    fireEvent.click(screen.getByRole('button', { name: /trigger/i }));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('disables button when disabled or loading', () => {
    const { rerender } = render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole('button')).toBeDisabled();

    rerender(<Button isLoading>Loading</Button>);
    const loading = screen.getByRole('button', { name: 'Loading' });
    expect(loading).toBeDisabled();
    expect(loading).toHaveAttribute('aria-busy', 'true');
  });
});
