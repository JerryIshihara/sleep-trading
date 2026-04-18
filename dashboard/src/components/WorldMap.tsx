import { useEffect, useMemo, useState } from 'react';
import { ComposableMap, Geographies, Geography, Marker } from 'react-simple-maps';
import world from 'world-atlas/countries-110m.json';
import type { MarketDirection, MarketSessionStatus, MarketStatusMap } from '../market-types';
import './world-map.css';

type LabelAnchor = 'right' | 'left' | 'top' | 'bottom';

type Exchange = {
  name: string;
  city: string;
  signature: string;
  lat: number;
  lon: number;
  timeZone: string;
  open: string; // "HH:mm"
  close: string; // "HH:mm"
  // Optional pixel nudge for overlapping markers in the same city
  offset?: [number, number];
  // When two exchanges share a city, only one shows the label. The primary
  // marker's `cityPartner` points at the secondary so its signature can be
  // appended to the combined label.
  cityPartner?: string;
  // Suppress label rendering for the secondary marker in a shared-city pair.
  labelHidden?: boolean;
  // Where the label sits relative to the marker dot.
  labelAnchor?: LabelAnchor;
};

const EXCHANGES: Exchange[] = [
  { name: 'NYSE', city: 'New York', signature: 'SPX', lat: 40.71, lon: -74.01, timeZone: 'America/New_York', open: '09:30', close: '16:00', offset: [-5, 0], cityPartner: 'NASDAQ', labelAnchor: 'bottom' },
  { name: 'NASDAQ', city: 'New York', signature: 'IXIC', lat: 40.76, lon: -73.98, timeZone: 'America/New_York', open: '09:30', close: '16:00', offset: [5, 0], labelHidden: true },
  { name: 'TSX', city: 'Toronto', signature: 'GSPTSE', lat: 43.65, lon: -79.38, timeZone: 'America/Toronto', open: '09:30', close: '16:00', labelAnchor: 'top' },
  { name: 'B3', city: 'São Paulo', signature: 'IBOV', lat: -23.55, lon: -46.63, timeZone: 'America/Sao_Paulo', open: '10:00', close: '17:30', labelAnchor: 'right' },
  { name: 'LSE', city: 'London', signature: 'UKX', lat: 51.51, lon: -0.1, timeZone: 'Europe/London', open: '08:00', close: '16:30', labelAnchor: 'left' },
  { name: 'XETRA', city: 'Frankfurt', signature: 'DAX', lat: 50.11, lon: 8.68, timeZone: 'Europe/Berlin', open: '09:00', close: '17:30', labelAnchor: 'right' },
  { name: 'SGX', city: 'Singapore', signature: 'STI', lat: 1.28, lon: 103.85, timeZone: 'Asia/Singapore', open: '09:00', close: '17:00', labelAnchor: 'right' },
  { name: 'HKEX', city: 'Hong Kong', signature: 'HSI', lat: 22.28, lon: 114.16, timeZone: 'Asia/Hong_Kong', open: '09:30', close: '16:00', labelAnchor: 'bottom' },
  { name: 'SSE', city: 'Shanghai', signature: 'SHCOMP', lat: 31.23, lon: 121.47, timeZone: 'Asia/Shanghai', open: '09:30', close: '15:00', cityPartner: 'SZSE', labelAnchor: 'left' },
  { name: 'SZSE', city: 'Shenzhen', signature: 'SZCOMP', lat: 22.54, lon: 114.06, timeZone: 'Asia/Shanghai', open: '09:30', close: '15:00', offset: [-5, 5], labelHidden: true },
  { name: 'TSE', city: 'Tokyo', signature: 'N225', lat: 35.68, lon: 139.77, timeZone: 'Asia/Tokyo', open: '09:00', close: '15:00', labelAnchor: 'right' },
  { name: 'ASX', city: 'Sydney', signature: 'XJO', lat: -33.87, lon: 151.21, timeZone: 'Australia/Sydney', open: '10:00', close: '16:00', labelAnchor: 'right' },
];

type FallbackStatus = 'open' | 'closed';

type MarkerVariant = 'closed' | 'warn' | 'open-up' | 'open-down' | 'open-flat';

function getTzWeekdayAndTime(date: Date, timeZone: string): { weekday: number; hours: number; minutes: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const weekdayStr = parts.find((p) => p.type === 'weekday')?.value ?? 'Sun';
  const hourStr = parts.find((p) => p.type === 'hour')?.value ?? '00';
  const minuteStr = parts.find((p) => p.type === 'minute')?.value ?? '00';
  const map: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
  const weekday = map[weekdayStr] ?? 0;
  const hRaw = parseInt(hourStr, 10);
  const hours = Number.isFinite(hRaw) ? hRaw % 24 : 0;
  const minutes = parseInt(minuteStr, 10) || 0;
  return { weekday, hours, minutes };
}

function hhmmToMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(':').map((v) => parseInt(v, 10));
  return (h || 0) * 60 + (m || 0);
}

function computeFallbackStatus(exchange: Exchange, now: Date): FallbackStatus {
  const { weekday, hours, minutes } = getTzWeekdayAndTime(now, exchange.timeZone);
  if (weekday === 0 || weekday === 6) return 'closed';
  const nowMin = hours * 60 + minutes;
  const openMin = hhmmToMinutes(exchange.open);
  const closeMin = hhmmToMinutes(exchange.close);
  if (nowMin < openMin || nowMin >= closeMin) return 'closed';
  return 'open';
}

function deriveVariant(
  sessionStatus: MarketSessionStatus,
  direction: MarketDirection | null,
): MarkerVariant {
  if (sessionStatus === 'closed') return 'closed';
  if (sessionStatus === 'pre-open' || sessionStatus === 'post-close') return 'warn';
  if (direction === 'up') return 'open-up';
  if (direction === 'down') return 'open-down';
  return 'open-flat';
}

function formatDirectionLabel(direction: MarketDirection | null, changePercent: number | null): string {
  if (direction === null) return '';
  const arrow = direction === 'up' ? '↑' : direction === 'down' ? '↓' : '→';
  if (changePercent === null || !Number.isFinite(changePercent)) return ` ${arrow}`;
  const sign = changePercent > 0 ? '+' : '';
  return ` ${arrow} ${sign}${changePercent.toFixed(2)}%`;
}

function sessionLabel(s: MarketSessionStatus): string {
  switch (s) {
    case 'open':
      return 'Open';
    case 'closed':
      return 'Closed';
    case 'pre-open':
      return 'Pre-open';
    case 'post-close':
      return 'Post-close';
  }
}

function labelPos(anchor: LabelAnchor) {
  switch (anchor) {
    case 'right':
      return { cityX: 8, cityY: 4, sigX: 8, sigY: 14, textAnchor: 'start' as const };
    case 'left':
      return { cityX: -8, cityY: 4, sigX: -8, sigY: 14, textAnchor: 'end' as const };
    case 'top':
      return { cityX: 0, cityY: -14, sigX: 0, sigY: -4, textAnchor: 'middle' as const };
    case 'bottom':
      return { cityX: 0, cityY: 14, sigX: 0, sigY: 24, textAnchor: 'middle' as const };
  }
}

const GEO_STYLE = {
  default: {
    fill: 'var(--bg-elevated)',
    stroke: 'var(--border)',
    strokeWidth: 0.5,
    outline: 'none',
  },
  hover: {
    fill: 'var(--bg-elevated)',
    stroke: 'var(--border)',
    strokeWidth: 0.5,
    outline: 'none',
  },
  pressed: {
    fill: 'var(--bg-elevated)',
    stroke: 'var(--border)',
    strokeWidth: 0.5,
    outline: 'none',
  },
} as const;

type Props = {
  status?: MarketStatusMap;
};

export function WorldMap({ status }: Props) {
  const [now, setNow] = useState<Date>(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  const markers = useMemo(() => {
    return EXCHANGES.map((ex) => {
      const info = status?.[ex.name];
      const sessionStatus: MarketSessionStatus =
        info?.status ?? (computeFallbackStatus(ex, now) === 'open' ? 'open' : 'closed');
      const direction: MarketDirection | null = info?.direction ?? null;
      const changePercent: number | null = info?.changePercent ?? null;
      const variant = deriveVariant(sessionStatus, direction);
      return { exchange: ex, sessionStatus, direction, changePercent, variant };
    });
  }, [now, status]);

  return (
    <div className="world-map" role="group" aria-label="World stock exchanges">
      <div className="world-map__svg-wrap">
        <ComposableMap
          className="world-map__svg"
          projection="geoEqualEarth"
          projectionConfig={{ scale: 155 }}
          width={900}
          height={440}
          style={{ width: '100%', height: 'auto' }}
        >
          <Geographies geography={world}>
            {({ geographies }) =>
              geographies.map((geo) => (
                <Geography key={geo.rsmKey} geography={geo} style={GEO_STYLE} />
              ))
            }
          </Geographies>

          {markers.map(({ exchange, sessionStatus, direction, changePercent, variant }) => {
            const key = `${exchange.name}-${exchange.city}`;
            const tooltip = `${exchange.name} · ${exchange.city} · ${sessionLabel(sessionStatus)}${formatDirectionLabel(direction, changePercent)}`;
            const [dx, dy] = exchange.offset ?? [0, 0];

            const isOpen = variant === 'open-up' || variant === 'open-down' || variant === 'open-flat';
            const showHalo = isOpen || variant === 'warn';

            let signatureLabel = exchange.signature;
            if (exchange.cityPartner) {
              const partner = EXCHANGES.find((e) => e.name === exchange.cityPartner);
              if (partner) signatureLabel = `${exchange.signature} / ${partner.signature}`;
            }
            const showLabel = !exchange.labelHidden;
            const pos = labelPos(exchange.labelAnchor ?? 'right');

            return (
              <Marker key={key} coordinates={[exchange.lon, exchange.lat]}>
                <g
                  className={`world-map__marker world-map__marker--${variant}`}
                  transform={dx || dy ? `translate(${dx}, ${dy})` : undefined}
                >
                  {showHalo ? (
                    <>
                      <circle r={8} className="world-map__halo" />
                      <circle r={3.5} className="world-map__dot" />
                    </>
                  ) : (
                    <circle r={2.5} className="world-map__dot" />
                  )}
                  {showLabel ? (
                    <g className="world-map__label" aria-hidden>
                      <text x={pos.cityX} y={pos.cityY} className="world-map__label-city" textAnchor={pos.textAnchor}>
                        {exchange.city}
                      </text>
                      <text x={pos.sigX} y={pos.sigY} className="world-map__label-sig" textAnchor={pos.textAnchor}>
                        {signatureLabel}
                      </text>
                    </g>
                  ) : null}
                  <title>{tooltip}</title>
                </g>
              </Marker>
            );
          })}
        </ComposableMap>
      </div>
    </div>
  );
}
