/**
 * humanize(err) — turn any thrown thing into a sentence a person can act on.
 *
 * The UI never shows a raw exception ("Request failed with status code 500",
 * "TypeError: Failed to fetch", a stack). Each branch says what happened and
 * what to do next. Backend `detail` strings are used only when they read as
 * a sentence written for a human (short, no braces, no code).
 */
const LOOKS_HUMAN = (s) =>
  typeof s === 'string' && s.length > 3 && s.length < 160 && !/[{}<>]|traceback|exception|\bat\s+\w+\.\w+/i.test(s);

export function humanize(err, { what = 'that' } = {}) {
  if (!err) return `Couldn’t finish ${what}. Try again.`;
  const status = err.status ?? err.response?.status;
  const detail = err.data?.detail?.message ?? err.data?.detail ?? err.data?.message ?? err.response?.data?.detail;
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false;

  if (offline) return 'You’re offline. Reconnect and try again.';
  if (err.name === 'AbortError') return 'Stopped.';
  if (status === 401) return 'Your session has expired. Sign in again to continue.';
  if (status === 402) return 'This needs an active plan. Open Usage & Billing to add one.';
  if (status === 403) return 'You don’t have access to this. Ask an owner of your organization.';
  if (status === 404) return 'That isn’t here any more. It may have been removed or renamed.';
  if (status === 408 || status === 504) return 'The server took too long to answer. Try again in a moment.';
  if (status === 409) return LOOKS_HUMAN(detail) ? detail : 'That conflicts with something that already exists.';
  if (status === 413) return 'That’s too large to send. Try a smaller file or message.';
  if (status === 422) return LOOKS_HUMAN(detail) ? detail : 'Some of the details aren’t valid. Check the highlighted fields.';
  if (status === 429) return 'Too many requests right now. Wait a few seconds and try again.';
  if (status >= 500) return 'The server hit a problem. Try again; if it keeps happening, check Monitoring.';
  if (/failed to fetch|networkerror|load failed/i.test(err.message || '')) {
    return 'The API isn’t reachable right now. Check Monitoring or try again shortly.';
  }
  if (LOOKS_HUMAN(detail)) return detail;
  if (LOOKS_HUMAN(err.message) && !/status code|HTTP \d{3}/i.test(err.message)) return err.message;
  return `Couldn’t finish ${what}. Try again.`;
}

/** A short title for an error card, by what the person was doing. */
export function errorTitle(action = 'load this') {
  return `Couldn’t ${action}`;
}

export default humanize;
