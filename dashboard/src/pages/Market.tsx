import { useEffect, useState } from 'react';
import './market.css';
import { WorldClock } from '../components/WorldClock';
import { WorldMap } from '../components/WorldMap';
import { useMarketStatus } from '../hooks/useMarketStatus';

const WIDE_QUERY = '(min-width: 900px)';

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener('change', handler);
    setMatches(mql.matches);
    return () => mql.removeEventListener('change', handler);
  }, [query]);
  return matches;
}

type IndexRow = {
  region: string;
  name: string;
  symbol: string;
  last: number;
  change: number;
  percentChange: number;
};

const INDICES: IndexRow[] = [
  { region: 'Americas', name: 'S&P 500', symbol: 'SPX', last: 5247.82, change: 18.54, percentChange: 0.35 },
  { region: 'Americas', name: 'Nasdaq Composite', symbol: 'IXIC', last: 16421.36, change: 72.11, percentChange: 0.44 },
  { region: 'Americas', name: 'Dow Jones', symbol: 'DJI', last: 39087.45, change: -42.33, percentChange: -0.11 },
  { region: 'Americas', name: 'Russell 2000', symbol: 'RUT', last: 2072.18, change: 5.62, percentChange: 0.27 },
  { region: 'Americas', name: 'TSX Composite', symbol: 'GSPTSE', last: 21934.07, change: -14.85, percentChange: -0.07 },
  { region: 'Americas', name: 'Bovespa', symbol: 'IBOV', last: 128415.6, change: 311.4, percentChange: 0.24 },
  { region: 'Europe', name: 'FTSE 100', symbol: 'UKX', last: 7748.92, change: -12.07, percentChange: -0.16 },
  { region: 'Europe', name: 'DAX', symbol: 'DAX', last: 17842.54, change: 66.18, percentChange: 0.37 },
  { region: 'Europe', name: 'CAC 40', symbol: 'FCHI', last: 8106.25, change: 22.73, percentChange: 0.28 },
  { region: 'Europe', name: 'STOXX 600', symbol: 'SXXP', last: 503.64, change: -0.91, percentChange: -0.18 },
  { region: 'Asia/Pacific', name: 'Nikkei 225', symbol: 'N225', last: 39523.48, change: 145.2, percentChange: 0.37 },
  { region: 'Asia/Pacific', name: 'Hang Seng', symbol: 'HSI', last: 16512.92, change: -88.61, percentChange: -0.54 },
  { region: 'Asia/Pacific', name: 'Shanghai Composite', symbol: 'SHCOMP', last: 3054.64, change: 8.12, percentChange: 0.27 },
  { region: 'Asia/Pacific', name: 'KOSPI', symbol: 'KS11', last: 2672.33, change: -5.47, percentChange: -0.2 },
  { region: 'Asia/Pacific', name: 'ASX 200', symbol: 'XJO', last: 7768.1, change: 12.45, percentChange: 0.16 },
];

function formatNumber(value: number): string {
  return value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatChange(value: number): string {
  const abs = Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return value >= 0 ? `+${abs}` : `-${abs}`;
}

function formatPercent(value: number): string {
  const abs = Math.abs(value).toFixed(2);
  return value >= 0 ? `+${abs}%` : `-${abs}%`;
}

export function MarketPage() {
  const status = useMarketStatus();
  const wide = useMediaQuery(WIDE_QUERY);

  return (
    <div className="page market">
      <h1>Market</h1>

      <section className="market__overview">
        <div className="market__overview-clocks">
          <WorldClock status={status} orientation={wide ? 'vertical' : 'horizontal'} />
        </div>
        <div className="market__overview-map">
          <WorldMap status={status} />
        </div>
      </section>

      <div className="market__scroll">
        <table className="market__table">
          <thead>
            <tr>
              <th>Region</th>
              <th>Index</th>
              <th>Symbol</th>
              <th className="market__num">Last</th>
              <th className="market__num">Change</th>
              <th className="market__num">% Change</th>
            </tr>
          </thead>
          <tbody>
            {INDICES.map((row) => {
              const up = row.percentChange >= 0;
              const changeClass = up ? 'market__change--up' : 'market__change--down';
              const arrow = up ? '↑' : '↓';
              return (
                <tr key={row.symbol}>
                  <td>{row.region}</td>
                  <td>{row.name}</td>
                  <td className="market__symbol">{row.symbol}</td>
                  <td className="market__num">{formatNumber(row.last)}</td>
                  <td className={`market__num ${changeClass}`}>
                    <span className="market__arrow" aria-hidden>
                      {arrow}
                    </span>
                    {formatChange(row.change)}
                  </td>
                  <td className={`market__num ${changeClass}`}>{formatPercent(row.percentChange)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
