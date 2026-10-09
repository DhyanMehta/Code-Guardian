import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OnboardingEmptyState } from '../components/common/OnboardingEmptyState';

describe('OnboardingEmptyState', () => {
  it('renders the heading', () => {
    render(<OnboardingEmptyState />);
    expect(
      screen.getByText('Install the CodeGuardian GitHub App')
    ).toBeTruthy();
  });

  it('uses the real configured slug', () => {
    render(<OnboardingEmptyState slug="guardian-test" />);
    expect(screen.getByRole('link')).toHaveAttribute('href', 'https://github.com/apps/guardian-test/installations/new');
  });

  it('explains missing configuration without a fake link', () => {
    render(<OnboardingEmptyState />);
    expect(
      screen.getByText(/VITE_GITHUB_APP_SLUG is not configured/i)
    ).toBeTruthy();
  });
});
