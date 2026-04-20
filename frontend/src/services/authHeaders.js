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

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
const JWT_KEY = 'brigade_jwt';
const JWT_EXPIRES_AT_KEY = 'brigade_jwt_expires_at';
const LEGACY_API_KEY = 'apiKey';

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
