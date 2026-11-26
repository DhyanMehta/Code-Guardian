type TimestampSource =
  | { kind: 'fetch'; value?: number | null }
  | { kind: 'event'; value?: string | null };

type FriendlyTimestampProps = TimestampSource & {
  label: string;
  locale?: string;
  timeZone?: string;
  inline?: boolean;
};

const zonedTimestamp = /^(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/;

function parseEvent(value: string) {
  const match = zonedTimestamp.exec(value);
  if (!match) return NaN;
  const [, year, month, day] = match.map(Number);
  // Date.parse can normalize impossible dates such as February 30.
  const calendar = new Date(0);
  calendar.setUTCFullYear(year, month - 1, day);
  if (year === 0 || calendar.getUTCMonth() !== month - 1 || calendar.getUTCDate() !== day || value.slice(11, 13) === '24') return NaN;
  return Date.parse(value);
}

export function FriendlyTimestamp({ label, kind, value, locale, timeZone, inline }: FriendlyTimestampProps) {
  const instant = typeof value === 'string' ? parseEvent(value) : value ?? NaN;
  const date = new Date(instant);
  const valid = Number.isFinite(date.getTime()) && date.getUTCFullYear() > 0 && date.getUTCFullYear() <= 9999;
  const iso = valid ? date.toISOString() : undefined;
  const exact = kind === 'event' ? value : iso;
  const display = valid ? new Intl.DateTimeFormat(locale, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'shortOffset',
    timeZone,
  }).format(date) : 'Time unavailable';

  const reading = <>{label} <span className="tabular-nums">{iso ? <time dateTime={iso}>{display}</time> : display}</span></>;
  const textClass = 'text-meta md:text-meta-wide text-fg-muted';
  if (inline) return <span className={textClass}>{reading}</span>;
  if (exact == null || exact === '') return <p className={textClass}>{reading}</p>;

  return (
    <details className={textClass}>
      <summary className="control-focus w-fit max-w-full min-h-11 content-center cursor-pointer rounded-md py-1.5 pr-2 hover:text-fg md:min-h-10">
        {reading}
      </summary>
      <p className="mt-1">
        {kind === 'fetch' ? 'Exact fetch time' : 'Source timestamp'}{' '}
        <code className="font-mono text-code text-fg-secondary [overflow-wrap:anywhere]">{exact}</code>
      </p>
    </details>
  );
}
