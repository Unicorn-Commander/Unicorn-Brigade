/**
 * Read design tokens at runtime — for the few places that cannot take a class:
 * canvas / WebGL / xyflow edge styles / chart libraries. Everything else uses
 * the Tailwind token classes.
 *
 *   tokenHsl('--accent')          → 'hsl(329 86% 70%)'
 *   tokenHsl('--ok', 0.4)         → 'hsl(158 64% 52% / 0.4)'
 *   tokenRaw('--shadow-e3')       → the raw value
 *
 * Values re-resolve on every call, so a theme flip is picked up on the next
 * render; cache per theme in hot loops (e.g. in a useMemo keyed on theme).
 */
export function tokenRaw(name) {
  if (typeof window === 'undefined') return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function tokenHsl(name, alpha) {
  const raw = tokenRaw(name);
  if (!raw) return alpha == null ? 'transparent' : 'transparent';
  return alpha == null ? `hsl(${raw})` : `hsl(${raw} / ${alpha})`;
}

/** The current resolved theme: 'dark' | 'light'. */
export function currentTheme() {
  if (typeof document === 'undefined') return 'dark';
  return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
}

/** Status colours for graph/canvas code, resolved from the same tokens the UI uses. */
export function statusColors(alpha) {
  return {
    idle: tokenHsl('--subtle', alpha),
    thinking: tokenHsl('--warn', alpha),
    tool: tokenHsl('--live', alpha),
    responding: tokenHsl('--ok', alpha),
    error: tokenHsl('--danger', alpha),
    accent: tokenHsl('--accent', alpha),
    info: tokenHsl('--info', alpha),
    edge: tokenHsl('--border-strong', alpha),
    text: tokenHsl('--fg', alpha),
    muted: tokenHsl('--muted', alpha),
    surface: tokenHsl('--surface', alpha),
  };
}
