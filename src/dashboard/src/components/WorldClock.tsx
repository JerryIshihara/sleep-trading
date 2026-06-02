import { useEffect, useState } from 'react';
import type { MarketDirection, MarketSessionStatus, MarketStatusMap } from '../market-types';
import './world-clock.css';

type City = {
  label: string;
  timeZone: string;
  exchange: string;
};

const CITIES: City[] = [
  { label: 'New York', timeZone: 'America/New_York', exchange: 'NYSE' },
  { label: 'London', timeZone: 'Europe/London', exchange: 'LSE' },
  { label: 'Hong Kong', timeZone: 'Asia/Hong_Kong', exchange: 'HKEX' },
  { label: 'Tokyo', timeZone: 'Asia/Tokyo', exchange: 'TSE' },
];

type Props = {
  status?: MarketStatusMap;
};

function formatTime(date: Date, timeZone: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

function formatTzOffset(date: Date, timeZone: string): string {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone,
    timeZoneName: 'shortOffset',
  }).formatToParts(date);
  const raw = parts.find((p) => p.type === 'timeZoneName')?.value ?? '';
  return raw || 'UTC';
}

function formatChangePercent(value: number): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function directionArrow(direction: MarketDirection | null): string {
  if (direction === 'up') return '↑';
  if (direction === 'down') return '↓';
  if (direction === 'flat') return '—';
  return '';
}

function sessionLabel(session: MarketSessionStatus | undefined): string {
  switch (session) {
    case 'open':
      return 'Open';
    case 'closed':
      return 'Closed';
    case 'pre-open':
      return 'Pre-open';
    case 'post-close':
      return 'Post-close';
    default:
      return '—';
  }
}

export function WorldClock({ status }: Props) {
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <ul className="world-clock" role="group" aria-label="World clocks">
      {CITIES.map((city) => {
        const info = status?.[city.exchange];
        const session = info?.status;
        const direction = info?.direction ?? null;
        const changePercent = info?.changePercent ?? null;

        const dotState =
          !info
            ? 'unknown'
            : session === 'closed'
              ? 'closed'
              : session === 'pre-open' || session === 'post-close'
                ? 'warn'
                : session === 'open'
                  ? (direction ?? 'flat')
                  : 'unknown';

        const showArrow = session === 'open' && direction !== null;

        return (
          <li
            key={city.exchange}
            className="world-clock__item"
            data-session={session ?? 'unknown'}
            aria-label={`${city.label}, ${sessionLabel(session)}, ${formatTime(now, city.timeZone)}`}
          >
            <span
              className="world-clock__dot"
              data-state={dotState}
              aria-hidden="true"
            />
            <span className="world-clock__top">
              <span className="world-clock__label" data-state={dotState}>
                {city.label}
              </span>
              <span className="world-clock__tz">{formatTzOffset(now, city.timeZone)}</span>
            </span>
            <span className="world-clock__main">
              <span className="world-clock__time" data-state={dotState}>
                {formatTime(now, city.timeZone)}
              </span>
              {showArrow && (
                <span
                  className="world-clock__arrow"
                  data-direction={direction ?? 'flat'}
                  aria-hidden="true"
                >
                  {directionArrow(direction)}
                </span>
              )}
              {changePercent !== null && session === 'open' && (
                <span
                  className="world-clock__change"
                  data-direction={direction ?? 'flat'}
                >
                  {formatChangePercent(changePercent)}
                </span>
              )}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
