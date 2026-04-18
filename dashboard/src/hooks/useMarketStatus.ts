import { useEffect, useRef, useState } from 'react';
import type {
  MarketDirection,
  MarketInfo,
  MarketSessionStatus,
  MarketStatusMap,
} from '../market-types';

// NOTE: Yahoo Finance's public chart endpoint (query1.finance.yahoo.com) is not
// an officially supported browser API. It sometimes works from browsers and
// sometimes gets blocked by CORS or upstream changes. In production this hook
// should be pointed at a backend proxy that fetches server-side and re-serves
// the same JSON shape. Current behavior: if fetch fails across the board, the
// UI simply shows `status`-only without direction arrows. Graceful degradation.

type ExchangeConfig = {
  /** Exchange code used as the map key. */
  code: string;
  /** IANA timezone for session computation. */
  timeZone: string;
  /** Market open, minutes from local midnight. */
  openMin: number;
  /** Market close, minutes from local midnight. */
  closeMin: number;
  /** Yahoo Finance chart symbol used for direction / change. */
  yahooSymbol: string;
};

const toMin = (h: number, m: number): number => h * 60 + m;

const EXCHANGES: ExchangeConfig[] = [
  { code: 'NYSE', timeZone: 'America/New_York', openMin: toMin(9, 30), closeMin: toMin(16, 0), yahooSymbol: '^GSPC' },
  { code: 'NASDAQ', timeZone: 'America/New_York', openMin: toMin(9, 30), closeMin: toMin(16, 0), yahooSymbol: '^IXIC' },
  { code: 'TSX', timeZone: 'America/Toronto', openMin: toMin(9, 30), closeMin: toMin(16, 0), yahooSymbol: '^GSPTSE' },
  { code: 'B3', timeZone: 'America/Sao_Paulo', openMin: toMin(10, 0), closeMin: toMin(17, 30), yahooSymbol: '^BVSP' },
  { code: 'LSE', timeZone: 'Europe/London', openMin: toMin(8, 0), closeMin: toMin(16, 30), yahooSymbol: '^FTSE' },
  { code: 'XETRA', timeZone: 'Europe/Berlin', openMin: toMin(9, 0), closeMin: toMin(17, 30), yahooSymbol: '^GDAXI' },
  { code: 'SGX', timeZone: 'Asia/Singapore', openMin: toMin(9, 0), closeMin: toMin(17, 0), yahooSymbol: '^STI' },
  { code: 'HKEX', timeZone: 'Asia/Hong_Kong', openMin: toMin(9, 30), closeMin: toMin(16, 0), yahooSymbol: '^HSI' },
  { code: 'SSE', timeZone: 'Asia/Shanghai', openMin: toMin(9, 30), closeMin: toMin(15, 0), yahooSymbol: '000001.SS' },
  { code: 'SZSE', timeZone: 'Asia/Shanghai', openMin: toMin(9, 30), closeMin: toMin(15, 0), yahooSymbol: '399001.SZ' },
  // TSE: Tokyo has a lunch break ~11:30-12:30; per spec we ignore it and treat
  // the whole 09:00-15:00 window as "open".
  { code: 'TSE', timeZone: 'Asia/Tokyo', openMin: toMin(9, 0), closeMin: toMin(15, 0), yahooSymbol: '^N225' },
  { code: 'ASX', timeZone: 'Australia/Sydney', openMin: toMin(10, 0), closeMin: toMin(16, 0), yahooSymbol: '^AXJO' },
];

const STATUS_REFRESH_MS = 15_000;
const FETCH_REFRESH_MS = 60_000;
const FETCH_TIMEOUT_MS = 5_000;

const WEEKEND = new Set(['Sat', 'Sun']);

/**
 * Returns the local weekday short name and minute-of-day for the given IANA
 * timezone, using Intl.DateTimeFormat. Falls back safely if parsing fails.
 */
function getLocalParts(now: Date, timeZone: string): { weekday: string; minuteOfDay: number } {
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }).formatToParts(now);

    let weekday = '';
    let hour = 0;
    let minute = 0;
    for (const p of parts) {
      if (p.type === 'weekday') weekday = p.value;
      else if (p.type === 'hour') hour = parseInt(p.value, 10) || 0;
      else if (p.type === 'minute') minute = parseInt(p.value, 10) || 0;
    }
    // en-GB can emit '24' for midnight in some engines; normalize.
    if (hour === 24) hour = 0;
    return { weekday, minuteOfDay: hour * 60 + minute };
  } catch {
    return { weekday: '', minuteOfDay: 0 };
  }
}

function computeStatus(cfg: ExchangeConfig, now: Date): MarketSessionStatus {
  const { weekday, minuteOfDay } = getLocalParts(now, cfg.timeZone);
  if (WEEKEND.has(weekday)) return 'closed';

  const { openMin, closeMin } = cfg;
  if (minuteOfDay >= openMin - 30 && minuteOfDay < openMin) return 'pre-open';
  if (minuteOfDay >= openMin && minuteOfDay < closeMin) return 'open';
  if (minuteOfDay >= closeMin && minuteOfDay < closeMin + 30) return 'post-close';
  return 'closed';
}

function directionFromChange(changePercent: number): MarketDirection {
  if (changePercent > 0.05) return 'up';
  if (changePercent < -0.05) return 'down';
  return 'flat';
}

type YahooChartResponse = {
  chart?: {
    result?: Array<{
      meta?: {
        regularMarketPrice?: number;
        chartPreviousClose?: number;
      };
    }> | null;
    error?: unknown;
  };
};

/** Fetch direction + changePercent for a single exchange. Never throws. */
async function fetchMarketData(
  cfg: ExchangeConfig,
  signal: AbortSignal,
): Promise<{ direction: MarketDirection | null; changePercent: number | null }> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(
    cfg.yahooSymbol,
  )}?interval=1d&range=1d`;
  try {
    const res = await fetch(url, { signal });
    if (!res.ok) return { direction: null, changePercent: null };
    const json = (await res.json()) as YahooChartResponse;
    const meta = json.chart?.result?.[0]?.meta;
    const current = meta?.regularMarketPrice;
    const prev = meta?.chartPreviousClose;
    if (typeof current !== 'number' || typeof prev !== 'number' || !prev) {
      return { direction: null, changePercent: null };
    }
    const changePercent = ((current - prev) / prev) * 100;
    return { direction: directionFromChange(changePercent), changePercent };
  } catch {
    return { direction: null, changePercent: null };
  }
}

function buildInitialMap(now: Date): MarketStatusMap {
  const map: MarketStatusMap = {};
  for (const cfg of EXCHANGES) {
    const info: MarketInfo = {
      exchange: cfg.code,
      status: computeStatus(cfg, now),
      direction: null,
      changePercent: null,
    };
    map[cfg.code] = info;
  }
  return map;
}

/**
 * React hook returning live market status for the 12 tracked equity exchanges.
 * - Session status is computed locally every 15s (no network).
 * - Direction / changePercent are best-effort via Yahoo Finance every 60s.
 * Keys in the returned map are exchange codes (e.g. 'NYSE').
 */
export function useMarketStatus(): MarketStatusMap {
  const [data, setData] = useState<MarketStatusMap>(() => buildInitialMap(new Date()));
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    const refreshStatus = () => {
      if (cancelled) return;
      const now = new Date();
      setData((prev) => {
        const next: MarketStatusMap = { ...prev };
        for (const cfg of EXCHANGES) {
          const existing = prev[cfg.code];
          const status = computeStatus(cfg, now);
          if (!existing) {
            next[cfg.code] = {
              exchange: cfg.code,
              status,
              direction: null,
              changePercent: null,
            };
          } else if (existing.status !== status) {
            next[cfg.code] = { ...existing, status };
          }
        }
        return next;
      });
    };

    const refreshYahoo = async () => {
      // Cancel any in-flight batch before starting a new one.
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

      const results = await Promise.allSettled(
        EXCHANGES.map((cfg) => fetchMarketData(cfg, controller.signal)),
      );

      clearTimeout(timeoutId);
      if (cancelled || controller.signal.aborted) return;

      setData((prev) => {
        const next: MarketStatusMap = { ...prev };
        EXCHANGES.forEach((cfg, i) => {
          const r = results[i];
          const base = prev[cfg.code] ?? {
            exchange: cfg.code,
            status: computeStatus(cfg, new Date()),
            direction: null,
            changePercent: null,
          };
          if (r.status === 'fulfilled') {
            next[cfg.code] = {
              ...base,
              direction: r.value.direction,
              changePercent: r.value.changePercent,
            };
          } else {
            next[cfg.code] = { ...base, direction: null, changePercent: null };
          }
        });
        return next;
      });
    };

    // Kick off immediately so first paint gets real data ASAP.
    refreshStatus();
    void refreshYahoo();

    const statusTimer = setInterval(refreshStatus, STATUS_REFRESH_MS);
    const yahooTimer = setInterval(() => {
      void refreshYahoo();
    }, FETCH_REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(statusTimer);
      clearInterval(yahooTimer);
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  return data;
}
