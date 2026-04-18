# dashboard

Web dashboard for monitoring live portfolio state, strategy performance, PnL, and orders. Separate subproject (TypeScript/React) from the Python engine in `../src/`.

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
- No state management library, no router — added as scope grows

## Layout

- `src/main.tsx` — entry; wraps `<App />` in `<ThemeProvider>`
- `src/App.tsx` — header + toggable side panel + main content
- `src/components/` — `SidePanel`, `ThemeToggle`
- `src/hooks/useTheme.tsx` — theme context, persists to `localStorage`, falls back to `prefers-color-scheme`
- `src/styles.css` — reset + CSS variables for both themes
