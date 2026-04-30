/**
 * Single source of truth for the Brigade API base URL.
 *
 * Why this exists: VITE_API_URL is set at build time and has historically
 * been a moving target — sometimes "", sometimes "/api/v1", sometimes
 * "https://brigade.magicunicorn.dev" (without the /api/v1 suffix). Any
 * page concatenating `${VITE_API_URL}/foo` with the bare-host form ended
 * up calling `https://brigade.magicunicorn.dev/foo`, which Traefik routed
 * to the SPA shell instead of the backend — the table-stays-empty bug.
 *
 * `apiBase()` always returns a URL that ends in `/api/v1`, regardless of
 * which of those values the build used.
 *
 * `apiUrl(path)` builds a full request URL and tolerates either a leading
 * "/" on the path or a trailing "/" on the base.
 */

function normalize(raw) {
  let s = (raw || '').replace(/\/+$/, '');
  if (!s) s = '/api/v1';
  if (!s.endsWith('/api/v1')) s = s + '/api/v1';
  return s;
}

export const API_BASE = normalize(import.meta.env.VITE_API_URL);

export function apiUrl(path) {
  if (!path) return API_BASE;
  return path.startsWith('/') ? `${API_BASE}${path}` : `${API_BASE}/${path}`;
}

/** Bare host (no /api/v1) — only used by ApiDocs/MCPDocs for displayed curl examples. */
export function bareHost() {
  return API_BASE.replace(/\/api\/v1$/, '');
}
