# Dashboard — plan

## Context

`src/dashboard/` hosts the web UI: Vite + React 19 + TypeScript, grayscale neon theme with YAML-customizable tokens, side panel with rail-mode collapse, lucide-react icons. The app is a shell — most pages are placeholders, dummy data drives the indices table, and `useMarketStatus` fetches direction best-effort from Yahoo Finance with a graceful fallback. No backend connection yet. The dashboard will eventually subscribe to the data layer (see [`data.md`](./data.md)) for live events.

## Design goals

1. **Feels fast.** Sub-frame updates on streaming data, no layout thrash.
2. **Offline-tolerant.** Backend disconnects degrade gracefully — cached last-known values, explicit "stale" markers.
3. **Consistent visual grammar.** Session state (open / pre-open / closed) and direction (up / down) share one encoding across every widget.
4. **Customizable without a rebuild.** Theme tokens — and eventually watchlists, layouts — live in the YAML config persisted client-side.
5. **Route-level laziness.** Heavy pages (charts, maps) never block initial paint.

## Current state

- Routes: `/` Overview, `/market`, `/portfolio`, `/strategies`, `/orders`, `/settings`.
- Market page: 7-city clock strip (TZ offset + session status + direction indicators). Flashing magenta halo for open sessions, yellow for pre-open / post-close, dim grey for closed.
- Indices table with dummy data, up/down semantic coloring.
- Settings: Light/Dark toggle + YAML editor wired to CSS custom properties via `<style id="user-config-style">` injection.
- `useMarketStatus` hook computes session locally from trading hours; best-effort Yahoo Finance fetch for direction.

## Components to add (roughly in order)

### Near-term
- **`DataClient` (TypeScript)** — thin WebSocket + REST wrapper around the data service at `src/data/`. Typed events mirror the Python `Event` union. This is the single module widgets depend on — no raw `fetch` / `WebSocket` in pages.
- **Live indices table** — replace dummy data. Subscribes via `DataClient`. Batch stream updates via `requestAnimationFrame` to avoid React thrash on high-rate symbols.
- **`Sparkline`** — inline SVG, ~200 LOC, grayscale-neon friendly, used in metric cards and table rows.
- **Overview hero** — three metric cards at the top of `/` matching the crypto-dashboard aesthetic we explored: asset icon, label, big % number, mini sparkline, session-state dot.

### Medium-term
- **`/portfolio`** — positions table (symbol, qty, entry, mark, unrealized PnL %), total value card, PnL-over-time chart.
- **Candle chart** — TradingView Lightweight Charts on a drill-in route (`/market/:symbol`). Subscribes to the bar feed.
- **`/strategies`** — live list: state (armed / paused / errored), last signal time, P&L contribution. Kill-switch per strategy.
- **`/orders`** — history table with filters, per-order timeline (sent → accepted → filled), global kill-switch.

### Longer-term
- **Backtest viewer** — upload a backtest run, show equity curve, trades overlaid on a candle chart, metrics panel (Sharpe, max drawdown, hit rate).
- **Structured config editor** — form UI over the YAML for non-theme keys (watchlist, layout, strategy params).
- **Auth** — only if/when the dashboard gets exposed beyond `localhost` / Tailscale.

## Architecture seams

- **`DataClient`** is the single consumer-facing module. Routes and widgets depend on it, not on raw transports. Swappable with an in-memory fake for Storybook and unit tests.
- **Theme / config** live in React context (`ThemeContext`, `ConfigContext`). A page never branches on deployment mode.
- **Route-level code splitting** — every major page behind `React.lazy` + `<Suspense>`. Keeps landing bundle small as charts land.
- **Feature flags** — simple boolean context hydrated from `settings.features` in the YAML config. Lets us ship unfinished pages hidden.

## File layout (proposed, incremental)

```
src/dashboard/src/
  App.tsx
  main.tsx
  routes.tsx                # route table, mostly lazy
  market-types.ts           # shared event/status types (mirrors Python)
  pages/
    overview/
    market/                 # Market.tsx moves here when it grows
    portfolio/
    strategies/
    orders/
    settings/
  components/
    SidePanel.tsx
    WorldClock.tsx
    Sparkline.tsx           # new
    MetricCard.tsx          # new
    CandleChart.tsx         # new, lazy
  data/                     # NEW — client-side data access
    client.ts               # WebSocket + REST DataClient
    useStream.ts            # hook wrapping a subscription
    useHistory.ts           # hook for historical queries
    fakes.ts                # in-memory DataClient for Storybook/tests
  hooks/
    useTheme.tsx
    useConfig.tsx
    useMarketStatus.ts      # eventually: replaced by useStream(...)
  styles.css
```

## Execution order

1. Stand up the `DataClient` skeleton — typed wrapper around the `src/data/` `/ws` endpoint. Auto-reconnect, JSON message dispatch.
2. `Sparkline` component, rendered with dummy data in a Storybook-style scratch page.
3. `MetricCard` composing `Sparkline` + session dot. Three of them on `/` Overview with dummy data.
4. Replace the Market indices table's dummy data with a `useStream` subscription. Real fallbacks for offline / disconnected state.
5. Candle chart on `/market/:symbol` (lazy), subscribing to bars.
6. Portfolio, Strategies, Orders pages as features in the Python engine arrive to back them.
7. Backtest viewer, structured config editor — later phases.

## Verification

- `npm run build` clean after every change.
- Manual walkthrough per route: no console errors, no layout thrash, graceful backend-down state.
- Storybook (TBD) for `Sparkline`, `MetricCard`, `CandleChart` — render with fake `DataClient`, visual snapshot.
- Playwright (TBD) for a handful of golden-path flows: navigate routes, toggle theme, edit + apply YAML.
- Bundle-size budget: initial route chunk under 200 KB gzipped; `CandleChart` isolated in its own chunk.

## Out of scope (this plan)

- The data layer itself (see [`data.md`](./data.md)).
- Authentication and multi-user.
- Mobile layout beyond "it doesn't crash" — dashboard is desktop-first.
- Real-time alerting UI.
