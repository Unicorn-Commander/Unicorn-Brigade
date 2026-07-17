/**
 * User preferences — the single source of truth for the `brigade-preferences`
 * localStorage blob. Both the Settings page (which writes it) and the runtime
 * consumers (chat model/streaming, toast gating) read from here so a toggle in
 * Settings actually changes behavior instead of being a placebo.
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
