import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Tabs } from '../components/common/Tabs';

describe('Tabs component', () => {
  it('supports arrow and end navigation with scoped panel IDs', () => {
    const onChange = vi.fn();
    render(<Tabs id="repo" tabs={[{ id: 'pulls', label: 'Pulls' }, { id: 'settings', label: 'Settings' }]} activeTab="pulls" onChange={onChange} />);
    const pulls = screen.getByRole('tab', { name: 'Pulls' }), settings = screen.getByRole('tab', { name: 'Settings' });
    expect(pulls).toHaveAttribute('tabindex', '0'); expect(settings).toHaveAttribute('tabindex', '-1');
    fireEvent.keyDown(pulls, { key: 'ArrowRight' }); expect(onChange).toHaveBeenCalledWith('settings'); expect(settings).toHaveFocus();
    expect(settings).toHaveAttribute('aria-controls', 'repo-panel-settings');
  });
  const sampleTabs = [
    { id: 'pulls', label: 'Pulls', count: 3 },
    { id: 'analytics', label: 'Analytics' },
    { id: 'settings', label: 'Settings' },
  ];

  it('renders the tab list with the active link color and selected surface', () => {
    const handleChange = vi.fn();
    render(
      <Tabs
        tabs={sampleTabs}
        activeTab="pulls"
        onChange={handleChange}
      />
    );

    const pullsTab = screen.getByRole('tab', { name: /pulls/i });
    expect(pullsTab).toBeInTheDocument();
    expect(pullsTab).toHaveAttribute('aria-selected', 'true');
    expect(pullsTab).toHaveClass('text-link', 'bg-panel-raised');
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('fires onChange when another tab is clicked', () => {
    const handleChange = vi.fn();
    render(
      <Tabs
        tabs={sampleTabs}
        activeTab="pulls"
        onChange={handleChange}
      />
    );

    const settingsTab = screen.getByRole('tab', { name: /settings/i });
    fireEvent.click(settingsTab);
    expect(handleChange).toHaveBeenCalledWith('settings');
  });
});
