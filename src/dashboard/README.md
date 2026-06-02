# dashboard

Web dashboard for monitoring live portfolio state, strategy performance, PnL, and orders. Separate subproject (TypeScript/React) that sits alongside the Python engine under `../` (both live inside `src/`).

## Local development

Requires Node.js 18+.

```bash
npm install
npm run dev      # Vite dev server on http://localhost:5173
npm run build    # type-check + production build to dist/
npm run preview  # serve the built bundle locally
```

## Stack

- Vite + React 19 + TypeScript
- Plain CSS with CSS custom properties for light/dark theming (`data-theme` on `<html>`)
- React Router for the side-panel navigation
- No state management library

## Layout

- `src/main.tsx` — entry; wraps `<App />` in router, theme, and config providers
- `src/App.tsx` — side panel + routed main content
- `src/routes.tsx` — route definitions for the side panel and page outlet
- `src/components/` — `SidePanel`, `WorldClock`
- `src/pages/` — `Market`, `Settings`
- `src/hooks/useTheme.tsx` — theme context, persists to `localStorage`, falls back to `prefers-color-scheme`
- `src/hooks/useConfig.tsx` — YAML-backed CSS token customization
- `src/hooks/useMarketStatus.ts` — local session status plus best-effort market direction fetches
- `src/styles.css` — reset + CSS variables for both themes
