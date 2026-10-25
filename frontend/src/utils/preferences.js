/**
 * User preferences — the single source of truth for the `brigade-preferences`
 * localStorage blob. Both the Settings page (which writes it) and the runtime
 * consumers (chat model/streaming, toast gating, the theme) read from here so a
 * toggle in Settings actually changes behavior instead of being a placebo.
 */

export const PREFERENCES_KEY = 'brigade-preferences';

export const DEFAULT_PREFERENCES = {
  // Model id used for new conversations when no per-window override is set.
  // '' = "Auto (server default)".
  defaultModel: '',
  // Show non-error toast notifications.
  notifications: true,
  // Render assistant text token-by-token as it streams (vs. showing it once
  // the full response is ready).
  streamResponses: true,
  // Color mode: 'system' follows the OS, 'light' / 'dark' force one.
  // Consumed by src/utils/theme.js (+ the pre-paint script in index.html).
  theme: 'system',
  // Theme family: 'brigade' (magenta, navy, aurora — the default), 'business'
  // (neutral surfaces, indigo accent) or 'graphite' (monochrome). Selected by
  // data-theme-family on <html>; see src/utils/theme.js THEME_FAMILIES.
  themeFamily: 'brigade',
};

export function getPreferences() {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    return raw ? { ...DEFAULT_PREFERENCES, ...JSON.parse(raw) } : { ...DEFAULT_PREFERENCES };
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

export function savePreferences(prefs) {
  try {
    localStorage.setItem(PREFERENCES_KEY, JSON.stringify(prefs));
  } catch {
    /* storage unavailable — preferences simply won't persist */
  }
}
