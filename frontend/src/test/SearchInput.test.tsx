import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchInput } from '../components/common/SearchInput';

describe('SearchInput component', () => {
  it('renders input with placeholder and search type', () => {
    render(<SearchInput placeholder="Filter PRs..." id="test-search" />);
    const input = screen.getByPlaceholderText('Filter PRs...');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'search');
  });

  it('updates value and calls onChange', () => {
    const handleChange = vi.fn();
    render(<SearchInput placeholder="Search" onChange={handleChange} />);
    const input = screen.getByPlaceholderText('Search');
    fireEvent.change(input, { target: { value: 'httpx' } });
    expect(handleChange).toHaveBeenCalled();
  });
});
