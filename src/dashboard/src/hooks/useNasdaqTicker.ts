import { useEffect, useState } from 'react';

// Listens to a realtime NASDAQ tick stream over WebSocket and exposes the latest
// price per symbol. The stream is expected to emit JSON frames shaped like
// `RawTick` (one object or an array). When the socket is unreachable or silent,
// the hook falls back to a local random-walk simulator so the component always
// ticks — clearly surfaced as `mode: 'sim'`. Point `TICKER_WS_URL` at the data
// service (e.g. a `/ws/ticks` bridge over `data.adapters.MoomooAdapter`).

export type TickDirection = 'up' | 'down' | 'flat';
export type TickerMode = 'connecting' | 'live' | 'sim';

export type Tick = {
  symbol: string;
  name: string;
  price: number;
  prevClose: number;
  change: number;
  percentChange: number;
  /** Direction of the latest print vs the previous one — drives the flash. */
  direction: TickDirection;
  ts: number;
};

export type NasdaqTickerState = {
  ticks: Record<string, Tick>;
  order: string[];
  mode: TickerMode;
};

export const TICKER_WS_URL = 'ws://localhost:8000/ws/ticks';

const SIM_INTERVAL_MS = 550;
const CONNECT_GRACE_MS = 2500;

type Seed = { symbol: string; name: string; price: number };

const SEED: Seed[] = [
  { symbol: 'AAPL', name: 'Apple', price: 314.98 },
  { symbol: 'NVDA', name: 'NVIDIA', price: 225.2 },
  { symbol: 'MSFT', name: 'Microsoft', price: 498.4 },
  { symbol: 'AMZN', name: 'Amazon', price: 232.1 },
  { symbol: 'META', name: 'Meta Platforms', price: 712.55 },
  { symbol: 'GOOGL', name: 'Alphabet', price: 198.33 },
  { symbol: 'AVGO', name: 'Broadcom', price: 268.77 },
  { symbol: 'TSLA', name: 'Tesla', price: 342.12 },
  { symbol: 'QQQ', name: 'Invesco QQQ', price: 745.65 },
];

const round2 = (n: number): number => Math.round(n * 100) / 100;

function seedTick(seed: Seed, ts: number): Tick {
  return {
    symbol: seed.symbol,
    name: seed.name,
    price: seed.price,
    prevClose: seed.price,
    change: 0,
    percentChange: 0,
    direction: 'flat',
    ts,
  };
}

function walk(prev: Tick, ts: number): Tick {
  const step = (Math.random() - 0.5) * Math.max(prev.price * 0.0014, 0.02);
  const price = round2(Math.max(0.01, prev.price + step));
  const change = round2(price - prev.prevClose);
  return {
    ...prev,
    price,
    change,
    percentChange: prev.prevClose ? round2((change / prev.prevClose) * 100) : 0,
    direction: price > prev.price ? 'up' : price < prev.price ? 'down' : 'flat',
    ts,
  };
}

type RawTick = {
  symbol?: unknown;
  name?: unknown;
  price?: unknown;
  prevClose?: unknown;
  percentChange?: unknown;
  ts?: unknown;
};

function normalize(raw: RawTick, prev: Tick | undefined): Tick | null {
  const symbol = typeof raw.symbol === 'string' ? raw.symbol : undefined;
  const price = typeof raw.price === 'number' ? raw.price : undefined;
  if (symbol === undefined || price === undefined) return null;
  const prevClose = typeof raw.prevClose === 'number' ? raw.prevClose : (prev?.prevClose ?? price);
  const change = round2(price - prevClose);
  return {
    symbol,
    name: typeof raw.name === 'string' ? raw.name : (prev?.name ?? symbol),
    price,
    prevClose,
    change,
    percentChange:
      typeof raw.percentChange === 'number'
        ? raw.percentChange
        : prevClose
          ? round2((change / prevClose) * 100)
          : 0,
    direction: prev ? (price > prev.price ? 'up' : price < prev.price ? 'down' : 'flat') : 'flat',
    ts: typeof raw.ts === 'number' ? raw.ts : Date.now(),
  };
}

function initialState(): NasdaqTickerState {
  const now = Date.now();
  const ticks: Record<string, Tick> = {};
  for (const seed of SEED) ticks[seed.symbol] = seedTick(seed, now);
  return { ticks, order: SEED.map((s) => s.symbol), mode: 'connecting' };
}

export function useNasdaqTicker(): NasdaqTickerState {
  const [state, setState] = useState<NasdaqTickerState>(initialState);

  useEffect(() => {
    let cancelled = false;
    let isLive = false;
    let simTimer: ReturnType<typeof setInterval> | null = null;
    let graceTimer: ReturnType<typeof setTimeout> | null = null;
    let ws: WebSocket | null = null;

    const startSim = () => {
      if (cancelled || isLive || simTimer !== null) return;
      setState((prev) => (prev.mode === 'live' ? prev : { ...prev, mode: 'sim' }));
      simTimer = setInterval(() => {
        if (cancelled) return;
        setState((prev) => {
          if (prev.mode === 'live') return prev;
          const pick = prev.order[Math.floor(Math.random() * prev.order.length)];
          const current = prev.ticks[pick];
          if (current === undefined) return prev;
          return { ...prev, ticks: { ...prev.ticks, [pick]: walk(current, Date.now()) } };
        });
      }, SIM_INTERVAL_MS);
    };

    const stopSim = () => {
      if (simTimer !== null) {
        clearInterval(simTimer);
        simTimer = null;
      }
    };

    const goLive = () => {
      isLive = true;
      stopSim();
      if (graceTimer !== null) {
        clearTimeout(graceTimer);
        graceTimer = null;
      }
    };

    const handleFrame = (data: string) => {
      let payload: unknown;
      try {
        payload = JSON.parse(data);
      } catch {
        return;
      }
      const items = Array.isArray(payload) ? payload : [payload];
      const valid = items.filter(
        (item): item is RawTick =>
          item !== null && typeof item === 'object' && 'price' in item,
      );
      if (valid.length === 0) return;
      goLive();
      setState((prev) => {
        let ticks = prev.ticks;
        let order = prev.order;
        for (const raw of valid) {
          const next = normalize(raw, ticks[String(raw.symbol)]);
          if (next === null) continue;
          ticks = { ...ticks, [next.symbol]: next };
          if (!order.includes(next.symbol)) order = [...order, next.symbol];
        }
        return { mode: 'live', order, ticks };
      });
    };

    try {
      ws = new WebSocket(TICKER_WS_URL);
      ws.onmessage = (event: MessageEvent) => {
        if (!cancelled && typeof event.data === 'string') handleFrame(event.data);
      };
      ws.onerror = () => startSim();
      ws.onclose = () => startSim();
    } catch {
      startSim();
    }

    // If the socket never delivers a usable tick, simulate after a short grace.
    graceTimer = setTimeout(startSim, CONNECT_GRACE_MS);

    return () => {
      cancelled = true;
      if (graceTimer !== null) clearTimeout(graceTimer);
      stopSim();
      if (ws !== null) {
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        ws.close();
      }
    };
  }, []);

  return state;
}
