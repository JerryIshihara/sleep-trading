import { useEffect, useState } from 'react';
import './nasdaq-ticker.css';
import {
  useNasdaqTicker,
  type Tick,
  type TickDirection,
  type TickerMode,
} from '../hooks/useNasdaqTicker';

const STATUS_LABEL: Record<TickerMode, string> = {
  connecting: 'Connecting',
  live: 'Live',
  sim: 'Simulated',
};

function formatPercent(value: number): string {
  const abs = Math.abs(value).toFixed(2);
  return value >= 0 ? `+${abs}%` : `-${abs}%`;
}

function TickerCell({ tick }: { tick: Tick }) {
  const [flash, setFlash] = useState<TickDirection | null>(null);

  useEffect(() => {
    if (tick.direction === 'flat') return;
    setFlash(tick.direction);
    const id = setTimeout(() => setFlash(null), 320);
    return () => clearTimeout(id);
  }, [tick.ts, tick.direction]);

  const up = tick.percentChange >= 0;
  return (
    <div className="nasdaq-ticker__cell" role="listitem" data-flash={flash ?? undefined}>
      <span className="nasdaq-ticker__symbol">{tick.symbol}</span>
      <span className="nasdaq-ticker__price">{tick.price.toFixed(2)}</span>
      <span className={`nasdaq-ticker__chg nasdaq-ticker__chg--${up ? 'up' : 'down'}`}>
        <span className="nasdaq-ticker__arrow" aria-hidden>
          {up ? '▲' : '▼'}
        </span>
        {formatPercent(tick.percentChange)}
      </span>
    </div>
  );
}

export function NasdaqTicker() {
  const { ticks, order, mode } = useNasdaqTicker();

  return (
    <section
      className="market__section nasdaq-ticker"
      id="nasdaq-ticker"
      aria-label="Nasdaq realtime ticker"
    >
      <header className="market__section-head">
        <div className="nasdaq-ticker__head">
          <h2>Nasdaq</h2>
          <span className={`nasdaq-ticker__status nasdaq-ticker__status--${mode}`}>
            <span className="nasdaq-ticker__dot" aria-hidden />
            {STATUS_LABEL[mode]}
          </span>
        </div>
      </header>
      <div className="nasdaq-ticker__tape" role="list">
        {order.map((symbol) => {
          const tick = ticks[symbol];
          return tick ? <TickerCell key={symbol} tick={tick} /> : null;
        })}
      </div>
    </section>
  );
}
