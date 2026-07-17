/**
 * Shared auth helpers for fetch-based services.
 *
 * Centralizes the auth strategy so api.js, mcpService.js and traceService.js all
 * behave identically:
 *   - Prefer JWT Bearer (brigade_jwt) issued by the OIDC callback.
 *   - Include cookies (credentials: 'include') so the backend session cookie is
 *     always sent.
 *   - Attach X-API-Key as a fallback for the legacy native-auth flow.
 *   - On 401 for a protected endpoint, redirect to the OIDC login route so the
 *     user is bounced through Keycloak.
 */

import { API_BASE } from './apiBase';
const API_URL = API_BASE;
const JWT_KEY = 'brigade_jwt';
const JWT_EXPIRES_AT_KEY = 'brigade_jwt_expires_at';
const LEGACY_API_KEY = 'apiKey';
// BR-2.2: the active organization the user is acting under. The backend honors
// X-Org-Id to bind the RLS org context; when unset it falls back to the user's
// default home org. Persisted here so every request through the unified client
// (http.js apiFetch/apiJson + api.js) is tenant-scoped uniformly.
export const ACTIVE_ORG_KEY = 'brigade_active_org';

/** The active org id the user is acting under, or null. */
export function getActiveOrgId() {
  try {
    return localStorage.getItem(ACTIVE_ORG_KEY) || null;
  } catch {
    return null;
  }
}

function jwtIsValid() {
  const token = localStorage.getItem(JWT_KEY);
  if (!token) return null;
  const expiresAt = Number(localStorage.getItem(JWT_EXPIRES_AT_KEY) || 0);
  if (expiresAt && Date.now() >= expiresAt) {
    localStorage.removeItem(JWT_KEY);
    localStorage.removeItem(JWT_EXPIRES_AT_KEY);
    return null;
  }
  return token;
}

export function buildAuthHeaders(extraHeaders = {}) {
  const headers = { ...extraHeaders };
  const jwt = jwtIsValid();
  if (jwt) headers.Authorization = `Bearer ${jwt}`;
  const apiKey = localStorage.getItem(LEGACY_API_KEY);
  if (apiKey && !headers['X-API-Key']) headers['X-API-Key'] = apiKey;
  // BR-2.2: bind the active org so tenant-scoped reads/writes hit the right org.
  // A caller may override by passing its own X-Org-Id (e.g. managing a specific
  // org); otherwise we attach the persisted active org when one is selected.
  const orgId = getActiveOrgId();
  if (orgId && !headers['X-Org-Id']) headers['X-Org-Id'] = orgId;
  return headers;
}

/**
 * Called by services when a request returns 401.
 * Skips the redirect on public pages so the login screen itself still works.
 */
export function handleUnauthorized() {
  localStorage.removeItem(JWT_KEY);
  localStorage.removeItem(JWT_EXPIRES_AT_KEY);
  const path = window.location.pathname;
  const publicPaths = ['/', '/login', '/register', '/auth/callback'];
  if (!publicPaths.includes(path)) {
    window.location.href = `${API_URL}/auth/oidc/login`;
  }
}

export const AUTH_API_URL = API_URL;
