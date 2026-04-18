import { useEffect, useState } from 'react';
import { Check, Moon, RotateCcw, Sun } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { DEFAULT_CONFIG_YAML, useConfig } from '../hooks/useConfig';

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { source, setSource, apply, reset, error } = useConfig();
  const [draft, setDraft] = useState(source);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    setDraft(source);
  }, [source]);

  const showFeedback = (msg: string) => {
    setFeedback(msg);
    window.setTimeout(() => setFeedback(null), 1800);
  };

  const handleApply = () => {
    setSource(draft);
    const result = apply(draft);
    if (result.ok) showFeedback('Applied.');
  };

  const handleReset = () => {
    reset();
    setDraft(DEFAULT_CONFIG_YAML);
    showFeedback('Reset to defaults.');
  };

  const dirty = draft !== source;

  return (
    <div className="settings">
      <section className="settings__card">
        <header className="settings__card-head">
          <h2 className="settings__title">Theme</h2>
          <p className="settings__hint">Switch between light and dark presentation.</p>
        </header>
        <div className="settings__row">
          <button
            type="button"
            className={`button${theme === 'light' ? ' button--primary' : ''}`}
            aria-pressed={theme === 'light'}
            onClick={() => setTheme('light')}
          >
            <Sun size={14} aria-hidden />
            Light
          </button>
          <button
            type="button"
            className={`button${theme === 'dark' ? ' button--primary' : ''}`}
            aria-pressed={theme === 'dark'}
            onClick={() => setTheme('dark')}
          >
            <Moon size={14} aria-hidden />
            Dark
          </button>
        </div>
      </section>

      <section className="settings__card settings__card--grow">
        <header className="settings__card-head">
          <h2 className="settings__title">Custom tokens</h2>
          <p className="settings__hint">
            YAML mapped to CSS custom properties. Persisted locally.
          </p>
        </header>
        <textarea
          className="settings__editor"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          aria-label="YAML configuration"
        />
        <div className="settings__footer">
          <button
            type="button"
            className="button button--primary"
            onClick={handleApply}
            disabled={!dirty && !error}
          >
            <Check size={14} aria-hidden />
            Apply
          </button>
          <button type="button" className="button" onClick={handleReset}>
            <RotateCcw size={14} aria-hidden />
            Reset
          </button>
          {error ? (
            <span className="settings__error" role="alert">
              {error}
            </span>
          ) : feedback ? (
            <span className="settings__feedback">{feedback}</span>
          ) : (
            <span className="settings__feedback settings__feedback--muted">
              {dirty ? 'Unsaved changes.' : 'Up to date.'}
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
