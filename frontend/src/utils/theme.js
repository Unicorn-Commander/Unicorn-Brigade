/**
 * Theme runtime — the single place that turns a user's theme *choice*
 * ('system' | 'light' | 'dark', stored in brigade-preferences.theme) into the
 * DOM state the token layer reads: `data-theme` + the `dark` class on <html>.
 *
 * A tiny inline script in index.html applies the same result before first paint
 * (no flash); this module re-applies at startup and keeps 'system' in sync with
 * the OS while the app is open. index.css defines what each resolved theme looks
 * like — this file only flips the switch.
 */
import { getPreferences } from './preferences';

export const THEME_CHOICES = ['system', 'light', 'dark'];

export function systemPrefersDark() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

/** Resolve a stored choice into the concrete theme to render. */
export function resolveTheme(choice) {
  if (choice === 'dark') return 'dark';
  if (choice === 'light') return 'light';
  return systemPrefersDark() ? 'dark' : 'light'; // 'system' / unknown
}

function applyResolved(resolved) {
  const root = document.documentElement;
  root.setAttribute('data-theme', resolved);
  root.classList.toggle('dark', resolved === 'dark');
}

/** Apply a user choice ('system' | 'light' | 'dark') to the document. */
export function applyTheme(choice) {
  applyResolved(resolveTheme(choice));
}

/**
 * Apply the saved choice at startup and keep 'system' following the OS while
 * the app is open. Returns a cleanup function.
 */
export function initTheme() {
  const apply = () => applyTheme(getPreferences().theme);
  apply();

  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      if (getPreferences().theme === 'system') apply();
    };
    // addEventListener is the modern API; older Safari used addListener.
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else if (mq.removeListener) mq.removeListener(onChange);
    };
  }
  return () => {};
}
