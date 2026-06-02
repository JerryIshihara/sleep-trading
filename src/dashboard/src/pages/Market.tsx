import { lazy, Suspense, useEffect, useRef, useState, type DragEvent } from 'react';
import { Settings } from 'lucide-react';
import './market.css';
import { WorldClock } from '../components/WorldClock';
import { NasdaqTicker } from '../components/NasdaqTicker';
import { useMarketStatus } from '../hooks/useMarketStatus';
import { useWorldIndices } from '../hooks/useWorldIndices';

const QuoteSparkline = lazy(() => import('../components/QuoteSparkline'));

type QuoteRow = {
  symbol: string;
  name: string;
  price: string;
  change: string;
  percentChange: number;
  meta: string;
};

type QuoteGroup = {
  key: string;
  label: string;
  rows: QuoteRow[];
};

type IndicatorMode = 'change' | 'percent';

type SectorRow = {
  name: string;
  marketWeight: string;
  ytdReturn: number;
};

type MiniRow = {
  symbol: string;
  name: string;
  value: string;
  percentChange: number;
};

type IndexRow = {
  region: string;
  flag: string;
  name: string;
  symbol: string;
  last: number;
  change: number;
  percentChange: number;
};

const STOCK_GROUPS: QuoteGroup[] = [
  {
    key: 'trending',
    label: 'Trending',
    rows: [
      { symbol: 'NVDA', name: 'NVIDIA Corporation', price: '143.18', change: '+3.21', percentChange: 2.29, meta: 'Semiconductors' },
      { symbol: 'TSLA', name: 'Tesla, Inc.', price: '342.12', change: '-4.62', percentChange: -1.33, meta: 'Auto manufacturers' },
      { symbol: 'AAPL', name: 'Apple Inc.', price: '203.67', change: '+1.08', percentChange: 0.53, meta: 'Consumer electronics' },
      { symbol: 'PLTR', name: 'Palantir Technologies', price: '126.84', change: '+2.74', percentChange: 2.21, meta: 'Software infrastructure' },
    ],
  },
  {
    key: 'active',
    label: 'Most Active',
    rows: [
      { symbol: 'AMD', name: 'Advanced Micro Devices', price: '165.44', change: '+2.01', percentChange: 1.23, meta: '63.2M volume' },
      { symbol: 'F', name: 'Ford Motor Company', price: '12.06', change: '-0.08', percentChange: -0.66, meta: '57.1M volume' },
      { symbol: 'BAC', name: 'Bank of America', price: '39.78', change: '+0.14', percentChange: 0.35, meta: '45.9M volume' },
      { symbol: 'SOFI', name: 'SoFi Technologies', price: '18.33', change: '+0.41', percentChange: 2.29, meta: '41.5M volume' },
    ],
  },
  {
    key: 'gainers',
    label: 'Top Gainers',
    rows: [
      { symbol: 'MRVL', name: 'Marvell Technology', price: '92.18', change: '+10.72', percentChange: 13.16, meta: 'Earnings reaction' },
      { symbol: 'COHR', name: 'Coherent Corp.', price: '84.44', change: '+7.36', percentChange: 9.55, meta: 'AI optics demand' },
      { symbol: 'CRWD', name: 'CrowdStrike Holdings', price: '456.80', change: '+25.31', percentChange: 5.86, meta: 'Security software' },
      { symbol: 'DELL', name: 'Dell Technologies', price: '148.09', change: '+6.12', percentChange: 4.31, meta: 'Server momentum' },
    ],
  },
  {
    key: 'losers',
    label: 'Top Losers',
    rows: [
      { symbol: 'SNOW', name: 'Snowflake Inc.', price: '183.42', change: '-12.90', percentChange: -6.57, meta: 'Guidance reset' },
      { symbol: 'NKE', name: 'Nike, Inc.', price: '68.11', change: '-3.72', percentChange: -5.18, meta: 'Retail pressure' },
      { symbol: 'PYPL', name: 'PayPal Holdings', price: '72.60', change: '-2.86', percentChange: -3.79, meta: 'Fintech rotation' },
      { symbol: 'INTC', name: 'Intel Corporation', price: '31.54', change: '-0.92', percentChange: -2.83, meta: 'Chip laggard' },
    ],
  },
];

const ETF_GROUPS: QuoteGroup[] = [
  {
    key: 'active',
    label: 'Most Active',
    rows: [
      { symbol: 'SPY', name: 'SPDR S&P 500 ETF Trust', price: '524.73', change: '+1.86', percentChange: 0.36, meta: 'US broad market' },
      { symbol: 'QQQ', name: 'Invesco QQQ Trust', price: '451.92', change: '+2.11', percentChange: 0.47, meta: 'Nasdaq 100' },
      { symbol: 'IWM', name: 'iShares Russell 2000 ETF', price: '207.28', change: '+0.56', percentChange: 0.27, meta: 'Small caps' },
      { symbol: 'TLT', name: 'iShares 20+ Year Treasury Bond ETF', price: '91.08', change: '+0.44', percentChange: 0.49, meta: 'Long bonds' },
    ],
  },
  {
    key: 'gainers',
    label: 'Top Gainers',
    rows: [
      { symbol: 'SMH', name: 'VanEck Semiconductor ETF', price: '279.11', change: '+9.21', percentChange: 3.41, meta: 'Chips' },
      { symbol: 'URA', name: 'Global X Uranium ETF', price: '53.12', change: '+2.58', percentChange: 5.11, meta: 'Uranium' },
      { symbol: 'XSD', name: 'SPDR S&P Semiconductor ETF', price: '632.42', change: '+31.27', percentChange: 5.20, meta: 'Semiconductors' },
      { symbol: 'BOTZ', name: 'Global X Robotics & AI ETF', price: '34.82', change: '+0.91', percentChange: 2.68, meta: 'Automation' },
    ],
  },
  {
    key: 'income',
    label: 'Income',
    rows: [
      { symbol: 'BND', name: 'Vanguard Total Bond Market ETF', price: '72.54', change: '+0.08', percentChange: 0.11, meta: 'Core bonds' },
      { symbol: 'VYM', name: 'Vanguard High Dividend Yield ETF', price: '123.18', change: '+0.31', percentChange: 0.25, meta: 'Dividend equity' },
      { symbol: 'JEPI', name: 'JPMorgan Equity Premium Income ETF', price: '56.43', change: '+0.05', percentChange: 0.09, meta: 'Covered call' },
      { symbol: 'MUB', name: 'iShares National Muni Bond ETF', price: '107.72', change: '+0.13', percentChange: 0.12, meta: 'Municipals' },
    ],
  },
];

const SECTORS: SectorRow[] = [
  { name: 'Technology', marketWeight: '31.4%', ytdReturn: 18.8 },
  { name: 'Financial Services', marketWeight: '13.2%', ytdReturn: 6.4 },
  { name: 'Industrials', marketWeight: '8.9%', ytdReturn: 5.1 },
  { name: 'Health Care', marketWeight: '11.6%', ytdReturn: -1.3 },
  { name: 'Energy', marketWeight: '3.7%', ytdReturn: -4.8 },
];

const FUTURES: MiniRow[] = [
  { symbol: 'ES=F', name: 'S&P Futures', value: '5,268.50', percentChange: 0.16 },
  { symbol: 'NQ=F', name: 'Nasdaq Futures', value: '18,671.75', percentChange: 0.21 },
  { symbol: 'YM=F', name: 'Dow Futures', value: '39,204.00', percentChange: 0.17 },
  { symbol: 'RTY=F', name: 'Russell Futures', value: '2,081.20', percentChange: -0.14 },
];

const BONDS: MiniRow[] = [
  { symbol: '^TNX', name: 'US 10Y Treasury', value: '4.28%', percentChange: -0.09 },
  { symbol: '^FVX', name: 'US 5Y Treasury', value: '4.12%', percentChange: -0.07 },
  { symbol: '^TYX', name: 'US 30Y Treasury', value: '4.47%', percentChange: -0.05 },
  { symbol: 'LQD', name: 'Investment Grade Credit', value: '108.64', percentChange: 0.18 },
];

const CURRENCIES: MiniRow[] = [
  { symbol: 'EUR/USD', name: 'Euro / US Dollar', value: '1.0842', percentChange: -0.12 },
  { symbol: 'USD/JPY', name: 'US Dollar / Yen', value: '156.91', percentChange: 0.18 },
  { symbol: 'GBP/USD', name: 'Pound / US Dollar', value: '1.2718', percentChange: -0.06 },
  { symbol: 'AUD/USD', name: 'Australian Dollar', value: '0.6634', percentChange: 0.09 },
];

const CRYPTO: MiniRow[] = [
  { symbol: 'BTC-USD', name: 'Bitcoin USD', value: '67,828.40', percentChange: -4.46 },
  { symbol: 'ETH-USD', name: 'Ethereum USD', value: '1,936.48', percentChange: -1.45 },
  { symbol: 'SOL-USD', name: 'Solana USD', value: '77.01', percentChange: -3.11 },
  { symbol: 'USDC-USD', name: 'USD Coin USD', value: '1.00', percentChange: 0.0 },
];

const INDICES: IndexRow[] = [
  { region: 'United States', flag: '🇺🇸', name: 'S&P 500', symbol: 'SPX', last: 5247.82, change: 18.54, percentChange: 0.35 },
  { region: 'United States', flag: '🇺🇸', name: 'Nasdaq Composite', symbol: 'IXIC', last: 16421.36, change: 72.11, percentChange: 0.44 },
  { region: 'United States', flag: '🇺🇸', name: 'Dow Jones', symbol: 'DJI', last: 39087.45, change: -42.33, percentChange: -0.11 },
  { region: 'United States', flag: '🇺🇸', name: 'Russell 2000', symbol: 'RUT', last: 2072.18, change: 5.62, percentChange: 0.27 },
  { region: 'Canada', flag: '🇨🇦', name: 'TSX Composite', symbol: 'GSPTSE', last: 21934.07, change: -14.85, percentChange: -0.07 },
  { region: 'Brazil', flag: '🇧🇷', name: 'Bovespa', symbol: 'IBOV', last: 128415.6, change: 311.4, percentChange: 0.24 },
  { region: 'United Kingdom', flag: '🇬🇧', name: 'FTSE 100', symbol: 'UKX', last: 7748.92, change: -12.07, percentChange: -0.16 },
  { region: 'Germany', flag: '🇩🇪', name: 'DAX', symbol: 'DAX', last: 17842.54, change: 66.18, percentChange: 0.37 },
  { region: 'France', flag: '🇫🇷', name: 'CAC 40', symbol: 'FCHI', last: 8106.25, change: 22.73, percentChange: 0.28 },
  { region: 'Europe', flag: '🇪🇺', name: 'STOXX 600', symbol: 'SXXP', last: 503.64, change: -0.91, percentChange: -0.18 },
  { region: 'Japan', flag: '🇯🇵', name: 'Nikkei 225', symbol: 'N225', last: 39523.48, change: 145.2, percentChange: 0.37 },
  { region: 'Japan', flag: '🇯🇵', name: 'TOPIX', symbol: 'TOPIX', last: 2759.67, change: 8.92, percentChange: 0.32 },
  { region: 'Hong Kong', flag: '🇭🇰', name: 'Hang Seng', symbol: 'HSI', last: 16512.92, change: -88.61, percentChange: -0.54 },
  { region: 'China', flag: '🇨🇳', name: 'Shanghai Composite', symbol: 'SHCOMP', last: 3054.64, change: 8.12, percentChange: 0.27 },
  { region: 'South Korea', flag: '🇰🇷', name: 'KOSPI', symbol: 'KS11', last: 2672.33, change: -5.47, percentChange: -0.2 },
  { region: 'Australia', flag: '🇦🇺', name: 'ASX 200', symbol: 'XJO', last: 7768.1, change: 12.45, percentChange: 0.16 },
];

const IMPORTANT_INDEX_SYMBOLS = ['SPX', 'IXIC', 'N225', 'TOPIX', 'HSI', 'SHCOMP'] as const;
const IMPORTANT_INDEX_COUNT = IMPORTANT_INDEX_SYMBOLS.length;
const INITIAL_INDEX_ORDER = [
  ...IMPORTANT_INDEX_SYMBOLS,
  ...INDICES.map((row) => row.symbol).filter(
    (symbol) => !(IMPORTANT_INDEX_SYMBOLS as readonly string[]).includes(symbol),
  ),
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

function changeClass(value: number): string {
  return value >= 0 ? 'market__change--up' : 'market__change--down';
}

function reorderSymbols(symbols: string[], source: string, target: string): string[] {
  const from = symbols.indexOf(source);
  const to = symbols.indexOf(target);
  if (from < 0 || to < 0 || from === to) return symbols;
  const next = [...symbols];
  const [moved] = next.splice(from, 1);
  next.splice(to, 0, moved);
  return next;
}

function IndicatorToggle({
  mode,
  onChange,
  open,
  onToggleOpen,
  onClose,
}: {
  mode: IndicatorMode;
  onChange: (mode: IndicatorMode) => void;
  open: boolean;
  onToggleOpen: () => void;
  onClose: () => void;
}) {
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) onClose();
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };

    document.addEventListener('pointerdown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [onClose, open]);

  return (
    <div className="market__settings" ref={rootRef}>
      <button
        type="button"
        className="icon-button market__settings-button"
        aria-label="Index display settings"
        aria-expanded={open}
        onClick={onToggleOpen}
      >
        <Settings size={15} aria-hidden="true" />
      </button>
      {open && (
        <div className="market__settings-menu" role="dialog" aria-label="Index display settings">
          <span className="market__settings-label">Indicator</span>
          <div className="market__tabs" role="tablist" aria-label="Price indication">
            <button
              type="button"
              className={`market__tab${mode === 'change' ? ' market__tab--active' : ''}`}
              aria-selected={mode === 'change'}
              role="tab"
              onClick={() => onChange('change')}
            >
              Change
            </button>
            <button
              type="button"
              className={`market__tab${mode === 'percent' ? ' market__tab--active' : ''}`}
              aria-selected={mode === 'percent'}
              role="tab"
              onClick={() => onChange('percent')}
            >
              % Change
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function QuoteTable({
  rows,
  metaLabel,
  indicatorMode,
}: {
  rows: QuoteRow[];
  metaLabel: string;
  indicatorMode: IndicatorMode;
}) {
  return (
    <div className="market__table-wrap">
      <table className="market__quote-table">
        <colgroup>
          <col className="market__col-symbol" />
          <col className="market__col-name" />
          <col className="market__col-chart" />
          <col className="market__col-price" />
          <col className="market__col-indicator" />
          <col className="market__col-meta" />
        </colgroup>
        <thead>
          <tr>
            <th>Symbol</th>
            <th>Name</th>
            <th className="market__chart-head">1D Chart</th>
            <th className="market__num">Price</th>
            <th className="market__num">{indicatorMode === 'change' ? 'Change' : '% Change'}</th>
            <th>{metaLabel}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.symbol}>
              <td className="market__symbol">{row.symbol}</td>
              <td>{row.name}</td>
              <td>
                <Suspense fallback={<span className="market__spark market__spark--loading" aria-hidden="true" />}>
                  <QuoteSparkline symbol={row.symbol} percentChange={row.percentChange} />
                </Suspense>
              </td>
              <td className={`market__num ${changeClass(row.percentChange)}`}>{row.price}</td>
              <td className={`market__num ${changeClass(row.percentChange)}`}>
                {indicatorMode === 'change' ? row.change : formatPercent(row.percentChange)}
              </td>
              <td className="market__meta">{row.meta}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MiniMarketSection({
  id,
  eyebrow,
  rows,
}: {
  id: string;
  eyebrow: string;
  rows: MiniRow[];
}) {
  return (
    <section className="market__section" id={id}>
      <header className="market__section-head">
        <div>
          <h2>{eyebrow}</h2>
        </div>
      </header>
      <div className="market__mini-grid">
        {rows.map((row) => (
          <article key={row.symbol} className="market__mini">
            <div className="market__mini-id">
              <span className="market__symbol">{row.symbol}</span>
              <span>{row.name}</span>
            </div>
            <span className={`market__mini-value ${changeClass(row.percentChange)}`}>{row.value}</span>
            <span className={`market__mini-change ${changeClass(row.percentChange)}`}>
              {formatPercent(row.percentChange)}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}

export function MarketPage() {
  const status = useMarketStatus();
  const indexQuotes = useWorldIndices();
  const [stockGroup, setStockGroup] = useState(STOCK_GROUPS[0].key);
  const [etfGroup, setEtfGroup] = useState(ETF_GROUPS[0].key);
  const [indicatorMode, setIndicatorMode] = useState<IndicatorMode>('percent');
  const [indicatorSettingsOpen, setIndicatorSettingsOpen] = useState(false);
  const [indicesExpanded, setIndicesExpanded] = useState(false);
  const [indexOrder, setIndexOrder] = useState<string[]>(() => [...INITIAL_INDEX_ORDER]);
  const [draggedIndexSymbol, setDraggedIndexSymbol] = useState<string | null>(null);
  const activeStocks = STOCK_GROUPS.find((group) => group.key === stockGroup) ?? STOCK_GROUPS[0];
  const activeEtfs = ETF_GROUPS.find((group) => group.key === etfGroup) ?? ETF_GROUPS[0];
  const orderedIndices = indexOrder
    .map((symbol) => INDICES.find((row) => row.symbol === symbol))
    .filter((row): row is IndexRow => row !== undefined);
  const visibleIndices = indicesExpanded ? orderedIndices : orderedIndices.slice(0, IMPORTANT_INDEX_COUNT);

  const handleIndexDragStart = (event: DragEvent<HTMLTableRowElement>, symbol: string) => {
    setDraggedIndexSymbol(symbol);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', symbol);
  };

  const handleIndexDragOver = (event: DragEvent<HTMLTableRowElement>, symbol: string) => {
    if (draggedIndexSymbol === null || draggedIndexSymbol === symbol) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  };

  const handleIndexDrop = (event: DragEvent<HTMLTableRowElement>, symbol: string) => {
    event.preventDefault();
    const source = event.dataTransfer.getData('text/plain') || draggedIndexSymbol;
    if (!source || source === symbol) return;
    setIndexOrder((current) => reorderSymbols(current, source, symbol));
    setDraggedIndexSymbol(null);
  };

  return (
    <div className="page market">
      <header className="market__top">
        <div className="market__title">
          <h1>Markets</h1>
        </div>
        <div className="market__top-clock">
          <WorldClock status={status} />
        </div>
      </header>

      <NasdaqTicker />

      <section className="market__section" id="world-indexes">
        <header className="market__section-head">
          <div>
            <h2>World Indexes</h2>
          </div>
          <IndicatorToggle
            mode={indicatorMode}
            onChange={setIndicatorMode}
            open={indicatorSettingsOpen}
            onToggleOpen={() => setIndicatorSettingsOpen((open) => !open)}
            onClose={() => setIndicatorSettingsOpen(false)}
          />
        </header>
        <div className="market__scroll">
          <table className="market__table market__index-table">
            <colgroup>
              <col className="market__col-index-name" />
              <col className="market__col-symbol" />
              <col className="market__col-chart" />
              <col className="market__col-price" />
              <col className="market__col-indicator" />
            </colgroup>
            <thead>
              <tr>
                <th>Index</th>
                <th>Symbol</th>
                <th className="market__chart-head">1D Chart</th>
                <th className="market__num">Last</th>
                <th className="market__num">{indicatorMode === 'change' ? 'Change' : '% Change'}</th>
              </tr>
            </thead>
            <tbody>
              {visibleIndices.map((row) => {
                const quote = indexQuotes[row.symbol];
                const last = quote?.last ?? row.last;
                const change = quote?.change ?? row.change;
                const percentChange = quote?.percentChange ?? row.percentChange;
                const up = percentChange >= 0;
                const rowChangeClass = changeClass(percentChange);
                const arrow = up ? '↑' : '↓';
                const draggable = true;
                return (
                  <tr
                    key={row.symbol}
                    className={draggable ? 'market__draggable-row' : undefined}
                    draggable={draggable}
                    data-dragging={draggedIndexSymbol === row.symbol ? 'true' : undefined}
                    onDragStart={(event) => handleIndexDragStart(event, row.symbol)}
                    onDragOver={(event) => handleIndexDragOver(event, row.symbol)}
                    onDrop={(event) => handleIndexDrop(event, row.symbol)}
                    onDragEnd={() => setDraggedIndexSymbol(null)}
                  >
                    <td>
                      <span className="market__index-cell">
                        <span className="market__flag" aria-label={row.region} title={row.region}>
                          {row.flag}
                        </span>
                        <span className="market__index-label">{row.name}</span>
                      </span>
                    </td>
                    <td className="market__symbol">{row.symbol}</td>
                    <td>
                      <Suspense fallback={<span className="market__spark market__spark--loading" aria-hidden="true" />}>
                        <QuoteSparkline symbol={row.symbol} percentChange={percentChange} series={quote?.series} />
                      </Suspense>
                    </td>
                    <td className={`market__num ${rowChangeClass}`}>{formatNumber(last)}</td>
                    <td className={`market__num ${rowChangeClass}`}>
                      <span className="market__arrow" aria-hidden>
                        {arrow}
                      </span>
                      {indicatorMode === 'change' ? formatChange(change) : formatPercent(percentChange)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="market__section-footer">
          <button
            type="button"
            className="market__show-toggle"
            aria-expanded={indicesExpanded}
            onClick={() => setIndicesExpanded((expanded) => !expanded)}
          >
            {indicesExpanded ? 'Show less' : `Show more (${orderedIndices.length - IMPORTANT_INDEX_COUNT})`}
          </button>
        </div>
      </section>

      <section className="market__section" id="stocks">
        <header className="market__section-head">
          <div>
            <h2>Stocks</h2>
          </div>
          <div className="market__tabs" role="tablist" aria-label="Stock lists">
            {STOCK_GROUPS.map((group) => (
              <button
                key={group.key}
                type="button"
                className={`market__tab${stockGroup === group.key ? ' market__tab--active' : ''}`}
                aria-selected={stockGroup === group.key}
                role="tab"
                onClick={() => setStockGroup(group.key)}
              >
                {group.label}
              </button>
            ))}
          </div>
        </header>
        <QuoteTable rows={activeStocks.rows} metaLabel="Context" indicatorMode={indicatorMode} />
      </section>

      <section className="market__section" id="etfs">
        <header className="market__section-head">
          <div>
            <h2>ETFs</h2>
          </div>
          <div className="market__tabs" role="tablist" aria-label="ETF lists">
            {ETF_GROUPS.map((group) => (
              <button
                key={group.key}
                type="button"
                className={`market__tab${etfGroup === group.key ? ' market__tab--active' : ''}`}
                aria-selected={etfGroup === group.key}
                role="tab"
                onClick={() => setEtfGroup(group.key)}
              >
                {group.label}
              </button>
            ))}
          </div>
        </header>
        <QuoteTable rows={activeEtfs.rows} metaLabel="Theme" indicatorMode={indicatorMode} />
      </section>

      <MiniMarketSection
        id="futures"
        eyebrow="Futures"
        rows={FUTURES}
      />

      <MiniMarketSection
        id="bonds"
        eyebrow="Bonds"
        rows={BONDS}
      />

      <MiniMarketSection
        id="currencies"
        eyebrow="Currencies"
        rows={CURRENCIES}
      />

      <MiniMarketSection
        id="crypto"
        eyebrow="Crypto"
        rows={CRYPTO}
      />

      <section className="market__section" id="sectors">
        <header className="market__section-head">
          <div>
            <h2>Sectors</h2>
          </div>
        </header>
        <div className="market__sector-list">
          {SECTORS.map((sector) => (
            <div key={sector.name} className="market__sector-row">
              <span>{sector.name}</span>
              <span className="market__sector-weight">{sector.marketWeight}</span>
              <span className={`market__sector-return ${changeClass(sector.ytdReturn)}`}>
                {formatPercent(sector.ytdReturn)}
              </span>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
}
