/**
 * Unified HTTP client for every Brigade API call.
 *
 * Why this exists: pages historically mixed raw fetch/axios (no auth headers)
 * with the auth-aware api.js. Under enforced auth the header-less calls 401
 * and pages silently render empty ("Failed to load…", empty agent dropdown).
 * Every call site now goes through apiFetch/apiJson so auth is attached
 * uniformly and 401s recover consistently:
 *
 *   1. attach Bearer JWT / X-API-Key (buildAuthHeaders) + session cookie
 *   2. on 401: drop a stale local JWT and retry once (a bad cached token must
 *      never mask a valid session cookie / API key)
 *   3. still 401: hand off to handleUnauthorized() → OIDC login redirect
 */

import { buildAuthHeaders, handleUnauthorized } from './authHeaders';
import { API_BASE } from './apiBase';

const JWT_KEY = 'brigade_jwt';
const JWT_EXPIRES_AT_KEY = 'brigade_jwt_expires_at';

// Single-flight silent session refresh. The refresh token lives in an
// HttpOnly cookie, so renewal is a cookie-authenticated POST the backend
// answers by re-issuing the session cookies. Many parallel requests can 401
// at the same instant when the access token lapses — they all await the one
// refresh instead of stampeding Keycloak.
let refreshInFlight = null;

async function trySilentRefresh() {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${API_BASE}/auth/oidc/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

function buildUrl(path, params) {
  const raw = /^https?:\/\//.test(path)
    ? path
    : `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`;
  const url = new URL(raw, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, String(value));
      }
    });
  }
  return url.toString();
}

export async function apiFetch(path, options = {}) {
  const { params, redirectOn401 = true, ...fetchOptions } = options;
  const url = buildUrl(path, params);

  const isForm = typeof FormData !== 'undefined' && fetchOptions.body instanceof FormData;
  const baseHeaders = fetchOptions.body && !isForm ? { 'Content-Type': 'application/json' } : {};

  const doFetch = () =>
    fetch(url, {
      ...fetchOptions,
      credentials: 'include',
      headers: buildAuthHeaders({ ...baseHeaders, ...fetchOptions.headers }),
    });

  let response = await doFetch();

  if (response.status === 401 && !path.includes('/auth/')) {
    // A stale cached JWT must never mask a valid session cookie.
    if (localStorage.getItem(JWT_KEY)) {
      localStorage.removeItem(JWT_KEY);
      localStorage.removeItem(JWT_EXPIRES_AT_KEY);
    }
    // Access token lapsed — renew the session cookie silently and retry.
    if (await trySilentRefresh()) {
      response = await doFetch();
    }
    if (response.status === 401 && redirectOn401) {
      handleUnauthorized();
    }
  }

  return response;
}

export class ApiError extends Error {
  constructor(status, data, message) {
    super(message || `Request failed with status ${status}`);
    this.status = status;
    this.data = data;
  }
}

export async function apiJson(path, options = {}) {
  const response = await apiFetch(path, options);
  const contentType = response.headers.get('content-type') || '';
  const parse = async () => {
    if (contentType.includes('application/json')) return response.json();
    return response.text();
  };
  const data = await parse().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      (typeof detail === 'string' ? detail : detail?.message) ||
      data?.message ||
      data?.error ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, data, message);
  }
  return data;
}

export { API_BASE };
