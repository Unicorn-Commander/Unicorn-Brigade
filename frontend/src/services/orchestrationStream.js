/**
 * Orchestration SSE connection helper.
 *
 * A browser EventSource can't send Authorization/X-API-Key headers, so on an
 * authenticated deployment the live stream would be rejected. We mint a
 * short-lived, single-use ticket via an authenticated POST; the mint also drops
 * the ticket in an HttpOnly cookie scoped to /api/v1/orchestration. We then open
 * the stream COOKIE-FIRST (no ticket in the URL → nothing sensitive in access
 * logs), and only fall back to the ?ticket= query param if a cookie-only attempt
 * fails to open (e.g. a proxy/CDN strips the cookie on the SSE subresource).
 * See app/auth/sse_ticket.py + require_sse_access.
 */
import { API_BASE } from './apiBase';
import { apiFetch } from './http';

/**
 * Mint a single-use SSE ticket. The POST also Set-Cookies it server-side.
 * Returns the ticket string (kept for the URL fallback), or null if minting
 * isn't possible (not signed in, offline, endpoint unavailable) — callers then
 * open the stream relying on whatever auth the server already accepts.
 */
export async function mintOrchestrationTicket() {
  try {
    // Unified client: refreshes a lapsed access token and retries, so the live
    // feed survives the session's token rollover instead of dying with 401.
    const res = await apiFetch('/orchestration/events/ticket', {
      method: 'POST',
      redirectOn401: false,
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data && data.ticket ? data.ticket : null;
  } catch {
    return null;
  }
}

/**
 * Open and maintain the orchestration SSE stream. Handles minting, cookie-first
 * connection with a ?ticket fallback, and reconnect-with-a-fresh-ticket on error
 * (debounced exponential backoff). Returns a controller with `.close()`.
 *
 * @param {object}   opts
 * @param {(ev:any)=>void} opts.onEvent      called with each parsed SSE event
 * @param {()=>void}       [opts.onConnected]
 * @param {()=>void}       [opts.onDisconnected]
 * @param {object}         [opts.params]     extra query params (e.g. { mission_id })
 */
export function connectOrchestrationStream({ onEvent, onConnected, onDisconnected, params = {} } = {}) {
  let es = null;
  let cancelled = false;
  let retryTimer = null;
  let backoff = 1000;
  let preferUrlTicket = false; // flips permanently if a cookie-only attempt won't open
  let opened = false;

  const scheduleReconnect = () => {
    if (cancelled || retryTimer) return;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      backoff = Math.min(backoff * 2, 15000);
      connect();
    }, backoff);
  };

  async function connect() {
    if (cancelled) return;
    opened = false;
    // Fresh single-use ticket per connect; the POST also (re)sets the cookie.
    const ticket = await mintOrchestrationTicket();
    if (cancelled) return;

    const qs = new URLSearchParams(params);
    if (preferUrlTicket && ticket) qs.set('ticket', ticket);
    const q = qs.toString();
    const url = `${API_BASE}/orchestration/events${q ? `?${q}` : ''}`;

    try {
      es = new EventSource(url, { withCredentials: true });
    } catch {
      scheduleReconnect();
      return;
    }
    es.onopen = () => {
      opened = true;
      backoff = 1000;
      if (onConnected) onConnected();
    };
    es.onerror = () => {
      if (onDisconnected) onDisconnected();
      // A cookie-only attempt that never opened → switch to the URL ticket for
      // subsequent attempts (covers a proxy/CDN that drops the cookie). Close
      // first so the browser won't auto-retry with the now-spent ticket.
      if (!opened && !preferUrlTicket && ticket) preferUrlTicket = true;
      if (es) {
        es.close();
        es = null;
      }
      scheduleReconnect();
    };
    es.onmessage = (e) => {
      let ev;
      try {
        ev = JSON.parse(e.data);
      } catch {
        return;
      }
      if (onEvent) onEvent(ev);
    };
  }

  connect();

  return {
    close() {
      cancelled = true;
      if (retryTimer) clearTimeout(retryTimer);
      if (es) {
        es.close();
        es = null;
      }
    },
  };
}
