import { useEffect, useRef, useState } from 'react';

// Wires the World Indexes table to the data service's /api/indices proxy, which
// fetches each index server-side (no browser CORS) and returns both the quote
// (last / change / %) and the intraday close series that drives the sparkline —
// so the numbers and the chart share one source. If the service is down, the
// map stays empty and the table falls back to its static seed values.

export type IndexQuote = {
  last: number;
  change: number;
  percentChange: number;
  /** Intraday closes for the 1D sparkline. */
  series: number[];
  live: boolean;
};

export type WorldIndexMap = Record<string, IndexQuote>;

export const INDICES_URL = 'http://localhost:8000/api/indices';

const REFRESH_MS = 60_000;
const TIMEOUT_MS = 6_000;

type RawIndex = {
  symbol?: unknown;
  last?: unknown;
  change?: unknown;
  percentChange?: unknown;
  series?: unknown;
};

function toEntry(raw: RawIndex): [string, IndexQuote] | null {
  if (typeof raw.symbol !== 'string' || typeof raw.last !== 'number') return null;
  return [
    raw.symbol,
    {
      last: raw.last,
      change: typeof raw.change === 'number' ? raw.change : 0,
      percentChange: typeof raw.percentChange === 'number' ? raw.percentChange : 0,
      series: Array.isArray(raw.series)
        ? raw.series.filter((v): v is number => typeof v === 'number')
        : [],
      live: true,
    },
  ];
}

/**
 * Live quotes for the tracked world indices, keyed by display symbol (e.g.
 * 'SPX', 'IXIC'). Polls the data service every 60s. Symbols missing from the
 * response are absent from the map; callers fall back to their static values.
 */
export function useWorldIndices(): WorldIndexMap {
  const [data, setData] = useState<WorldIndexMap>({});
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;

    const refresh = async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
      try {
        const res = await fetch(INDICES_URL, { signal: controller.signal });
        if (!res.ok) return;
        const payload: unknown = await res.json();
        if (cancelled || !Array.isArray(payload)) return;
        const next: WorldIndexMap = {};
        for (const item of payload) {
          if (item !== null && typeof item === 'object') {
            const entry = toEntry(item as RawIndex);
            if (entry !== null) next[entry[0]] = entry[1];
          }
        }
        if (Object.keys(next).length > 0) setData(next);
      } catch {
        // service unreachable / aborted — keep prior data, table uses static fallback
      } finally {
        clearTimeout(timeoutId);
      }
    };

    void refresh();
    const timer = setInterval(() => void refresh(), REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  return data;
}
