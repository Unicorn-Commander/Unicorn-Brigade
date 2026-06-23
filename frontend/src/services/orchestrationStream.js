/**
 * Helpers for opening the orchestration SSE stream.
 *
 * A browser EventSource can't send Authorization/X-API-Key headers, so on an
 * authenticated deployment the stream would be rejected. We mint a short-lived,
 * single-use ticket via an authenticated POST and pass it as ?ticket=, which
 * the backend accepts in place of a header (see app/auth/sse_ticket.py).
 */
import { API_BASE } from './apiBase';
import { buildAuthHeaders } from './authHeaders';

/**
 * Mint a single-use SSE ticket. Returns the ticket string, or null if minting
 * isn't possible (not signed in, offline, endpoint unavailable) — callers then
 * open the stream unticketed and let the server's other auth (cookie/bypass)
 * apply, so nothing regresses where headers/cookies already work.
 */
export async function mintOrchestrationTicket() {
  try {
    const res = await fetch(`${API_BASE}/orchestration/events/ticket`, {
      method: 'POST',
      headers: buildAuthHeaders(),
      credentials: 'include',
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data && data.ticket ? data.ticket : null;
  } catch {
    return null;
  }
}

/**
 * Build the SSE URL, attaching a freshly-minted ticket when one is available.
 * Call this for every (re)connection so each uses its own single-use ticket.
 */
export async function orchestrationEventsUrl(extraParams = {}) {
  const params = new URLSearchParams(extraParams);
  const ticket = await mintOrchestrationTicket();
  if (ticket) params.set('ticket', ticket);
  const qs = params.toString();
  return `${API_BASE}/orchestration/events${qs ? `?${qs}` : ''}`;
}
