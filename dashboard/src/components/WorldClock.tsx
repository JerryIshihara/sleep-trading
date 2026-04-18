import { useEffect, useState } from 'react';
import type { MarketDirection, MarketStatusMap } from '../market-types';
import './world-clock.css';

type City = {
  label: string;
  timeZone: string;
  exchange: string;
};

const CITIES: City[] = [
  { label: 'New York', timeZone: 'America/New_York', exchange: 'NYSE' },
  { label: 'London', timeZone: 'Europe/London', exchange: 'LSE' },
  { label: 'Frankfurt', timeZone: 'Europe/Berlin', exchange: 'XETRA' },
  { label: 'Singapore', timeZone: 'Asia/Singapore', exchange: 'SGX' },
  { label: 'Hong Kong', timeZone: 'Asia/Hong_Kong', exchange: 'HKEX' },
  { label: 'Tokyo', timeZone: 'Asia/Tokyo', exchange: 'TSE' },
  { label: 'Sydney', timeZone: 'Australia/Sydney', exchange: 'ASX' },
];

type Props = {
  status?: MarketStatusMap;
  orientation?: 'horizontal' | 'vertical';
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

export function WorldClock({ status, orientation = 'horizontal' }: Props) {
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <ul
      className="world-clock"
      data-orientation={orientation}
      role="group"
      aria-label="World clocks"
    >
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
                  ? direction ?? 'flat'
                  : 'unknown';

        const showArrow = session === 'open' && direction !== null;
        const arrow = showArrow ? directionArrow(direction) : '';

        return (
          <li
            key={city.exchange}
            className="world-clock__item"
            data-session={session ?? 'unknown'}
          >
            <span
              className="world-clock__dot"
              data-state={dotState}
              aria-hidden="true"
            />
            <span className="world-clock__label">{city.label}</span>
            <span className="world-clock__time">
              {formatTime(now, city.timeZone)}
            </span>
            {showArrow && (
              <span
                className="world-clock__arrow"
                data-direction={direction ?? 'flat'}
                aria-hidden="true"
              >
                {arrow}
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
          </li>
        );
      })}
    </ul>
  );
}
