/**
 * Theme runtime — the single place that turns a user's theme *choices*
 * (mode 'system' | 'light' | 'dark' in brigade-preferences.theme, and family
 * 'brigade' | 'business' | 'graphite' in brigade-preferences.themeFamily) into
 * the DOM state the token layer reads: `data-theme` + the `dark` class, and
 * `data-theme-family`, on <html>.
 *
 * A tiny inline script in index.html applies the same result before first paint
 * (no flash); this module re-applies at startup and keeps 'system' in sync with
 * the OS while the app is open. tokens.css defines what each family × mode cell
 * looks like — this file only flips the switches.
 */
import { getPreferences } from './preferences';

export const THEME_CHOICES = ['system', 'light', 'dark'];

/** The theme families tokens.css defines. 'brigade' is the default (no attribute). */
export const THEME_FAMILIES = [
  { id: 'brigade', label: 'Brigade', blurb: 'Unicorn Commander magenta, deep navy, the aurora' },
  { id: 'business', label: 'Business', blurb: 'Neutral surfaces, indigo accent. The one to show a bank.' },
  { id: 'graphite', label: 'Graphite', blurb: 'Monochrome. Black, white, and the work.' },
];

const FAMILY_IDS = THEME_FAMILIES.map((f) => f.id);

export function normalizeFamily(id) {
  return FAMILY_IDS.includes(id) ? id : 'brigade';
}

export function systemPrefersDark() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );
}

/** Resolve a stored mode choice into the concrete mode to render. */
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

function applyFamily(id) {
  const root = document.documentElement;
  const family = normalizeFamily(id);
  if (family === 'brigade') root.removeAttribute('data-theme-family');
  else root.setAttribute('data-theme-family', family);
}

/** Apply a theme family ('brigade' | 'business' | 'graphite') to the document. */
export function applyThemeFamily(id) {
  applyFamily(id);
}

/**
 * Apply a mode choice ('system' | 'light' | 'dark') to the document, together
 * with a family (defaults to the saved preference so a mode change never drops
 * the family).
 */
export function applyTheme(choice, family) {
  applyResolved(resolveTheme(choice));
  applyFamily(family ?? getPreferences().themeFamily);
}

/**
 * Apply the saved choices at startup and keep 'system' following the OS while
 * the app is open. Returns a cleanup function.
 */
export function initTheme() {
  const apply = () => {
    const prefs = getPreferences();
    applyTheme(prefs.theme, prefs.themeFamily);
  };
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
