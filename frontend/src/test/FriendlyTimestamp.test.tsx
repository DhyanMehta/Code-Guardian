import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { FriendlyTimestamp } from '../components/common/FriendlyTimestamp';

const label = 'Review finished';
const locale = 'en-GB';

describe('FriendlyTimestamp', () => {
  it('renders a valid UTC event as a human and machine-readable time', () => {
    const value = '2026-11-24T20:15:00Z';
    const { container } = render(<FriendlyTimestamp kind="event" label={label} value={value} locale={locale} timeZone="UTC" />);
    expect(screen.getByText(/24 Nov 2026.*20:15 GMT/)).toBeInTheDocument();
    expect(container.querySelector('time')).toHaveAttribute('datetime', '2026-11-24T20:15:00.000Z');
  });

  it('converts an offset across a local date boundary and preserves the original precision', () => {
    const value = '2026-11-24T23:45:12.123456-05:00';
    const { container } = render(<FriendlyTimestamp kind="event" label={label} value={value} locale={locale} timeZone="Asia/Kolkata" />);
    expect(screen.getByText(/25 Nov 2026.*10:15 GMT\+5:30/)).toBeInTheDocument();
    expect(container.querySelector('time')).toHaveAttribute('datetime', '2026-11-25T04:45:12.123Z');
    const summary = container.querySelector('summary')!;
    expect(screen.getByText(value)).not.toBeVisible();
    fireEvent.click(summary);
    expect(screen.getByText(value)).toBeVisible();
  });

  it('labels a client fetch separately and discloses the instant at millisecond precision', () => {
    const value = Date.parse('2026-11-24T20:15:00.256Z');
    const { container } = render(<FriendlyTimestamp kind="fetch" label="Last successful fetch" value={value} locale={locale} timeZone="UTC" />);
    expect(container.querySelector('summary')).toHaveTextContent('Last successful fetch');
    expect(screen.getByText('2026-11-24T20:15:00.256Z')).toBeInTheDocument();
    expect(screen.getByText(/Exact fetch time/)).toBeInTheDocument();
  });

  it('states that missing values are unavailable without emitting a timestamp', () => {
    const { container } = render(<FriendlyTimestamp kind="event" label={label} value={null} />);
    expect(screen.getByText('Time unavailable')).toBeInTheDocument();
    expect(container.querySelector('time, details')).toBeNull();
  });

  it.each(['bad time', '2026-11-24T20:15:00', '2026-02-30T20:15:00Z', '2026-11-24T20:15:00+24:00'])(
    'keeps invalid or ambiguous input %s for inspection',
    value => {
      const { container } = render(<FriendlyTimestamp kind="event" label={label} value={value} />);
      expect(screen.getByText('Time unavailable')).toBeInTheDocument();
      expect(container.querySelector('time')).toBeNull();
      expect(screen.getByText(value)).toHaveTextContent(value);
    },
  );
});
