import { Area, AreaChart, ResponsiveContainer } from 'recharts';

type SparkPoint = {
  value: number;
};

type Props = {
  symbol: string;
  percentChange: number;
  /** Real intraday series; when provided (length > 1) it drives the chart
   *  instead of the deterministic fallback shape. */
  series?: number[];
};

function buildSparkline(symbol: string, percentChange: number): SparkPoint[] {
  const seed = [...symbol].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const direction = percentChange >= 0 ? 1 : -1;
  const slope = Math.min(Math.abs(percentChange), 8) * 0.42 * direction;
  return Array.from({ length: 18 }, (_, i) => {
    const wave = Math.sin((i + seed) * 0.78) * 1.8;
    const chop = Math.cos((i * 1.9 + seed) * 0.31) * 0.8;
    const trend = (i / 17 - 0.5) * slope;
    return { value: 50 + wave + chop + trend };
  });
}

export default function QuoteSparkline({ symbol, percentChange, series }: Props) {
  const color = percentChange >= 0 ? 'var(--up)' : 'var(--down)';
  const data =
    series && series.length > 1
      ? series.map((value) => ({ value }))
      : buildSparkline(symbol, percentChange);

  return (
    <div className="market__spark" aria-label={`${symbol} 1 day mini chart`}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 3, right: 0, bottom: 3, left: 0 }}
        >
          <Area
            dataKey="value"
            type="monotone"
            stroke={color}
            strokeWidth={1.7}
            fill={color}
            fillOpacity={0.13}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
