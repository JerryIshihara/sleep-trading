import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { parse as parseYaml } from 'yaml';

const STORAGE_KEY = 'dashboard-config-yaml';
const STYLE_ELEMENT_ID = 'user-config-style';

const TOKEN_KEYS = [
  'bg',
  'bg-elevated',
  'bg-hover',
  'fg',
  'fg-muted',
  'border',
  'accent',
] as const;

export const DEFAULT_CONFIG_YAML = `# Dashboard config — edit and press Apply.
# Values map to CSS custom properties used across the UI.
# Inspired by Ghostty-style flat key/value configuration.

theme:
  dark:
    bg: "#0a0a0a"
    bg-elevated: "#131313"
    bg-hover: "#1c1c1c"
    fg: "#ededed"
    fg-muted: "#8e8e8e"
    border: "#262626"
    accent: "#d9d9d9"

  light:
    bg: "#ffffff"
    bg-elevated: "#f5f5f5"
    bg-hover: "#eaeaea"
    fg: "#131313"
    fg-muted: "#6c6c6c"
    border: "#dedede"
    accent: "#2a2a2a"
`;

type ApplyResult = { ok: true } | { ok: false; error: string };

type ConfigContextValue = {
  source: string;
  setSource: (s: string) => void;
  apply: (s?: string) => ApplyResult;
  reset: () => void;
  error: string | null;
};

const ConfigContext = createContext<ConfigContextValue | null>(null);

function injectStyle(css: string) {
  let el = document.getElementById(STYLE_ELEMENT_ID) as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement('style');
    el.id = STYLE_ELEMENT_ID;
    document.head.appendChild(el);
  }
  el.textContent = css;
}

function clearStyle() {
  document.getElementById(STYLE_ELEMENT_ID)?.remove();
}

function buildCss(config: unknown): string {
  if (!config || typeof config !== 'object') return '';
  const theme = (config as { theme?: unknown }).theme;
  if (!theme || typeof theme !== 'object') return '';
  const sections = theme as Record<string, unknown>;
  let out = '';
  for (const [mode, selector] of [
    ['dark', ':root, [data-theme="dark"]'],
    ['light', '[data-theme="light"]'],
  ] as const) {
    const values = sections[mode];
    if (!values || typeof values !== 'object') continue;
    const entries = Object.entries(values as Record<string, unknown>).filter(
      ([k, v]) => typeof v === 'string' && (TOKEN_KEYS as readonly string[]).includes(k),
    );
    if (entries.length === 0) continue;
    out += `${selector} {\n`;
    for (const [k, v] of entries) out += `  --${k}: ${v as string};\n`;
    out += `}\n`;
  }
  return out;
}

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [source, setSource] = useState<string>(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) ?? DEFAULT_CONFIG_YAML;
    } catch {
      return DEFAULT_CONFIG_YAML;
    }
  });
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback(
    (input?: string): ApplyResult => {
      const yaml = input ?? source;
      try {
        const parsed = parseYaml(yaml);
        const css = buildCss(parsed);
        if (css) injectStyle(css);
        else clearStyle();
        try {
          window.localStorage.setItem(STORAGE_KEY, yaml);
        } catch {
          /* best-effort persistence */
        }
        setError(null);
        return { ok: true };
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        return { ok: false, error: msg };
      }
    },
    [source],
  );

  const reset = useCallback(() => {
    setSource(DEFAULT_CONFIG_YAML);
    clearStyle();
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* best-effort */
    }
    setError(null);
  }, []);

  const appliedOnce = useRef(false);
  useEffect(() => {
    if (appliedOnce.current) return;
    appliedOnce.current = true;
    apply(source);
  }, [apply, source]);

  const value = useMemo(
    () => ({ source, setSource, apply, reset, error }),
    [source, apply, reset, error],
  );

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useConfig(): ConfigContextValue {
  const ctx = useContext(ConfigContext);
  if (!ctx) throw new Error('useConfig must be used inside <ConfigProvider>');
  return ctx;
}
