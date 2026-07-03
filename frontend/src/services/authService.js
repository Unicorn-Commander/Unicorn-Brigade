/**
 * Brigade OIDC Authentication Service
 * Handles Keycloak authentication flow and user session management.
 *
 * Auth precedence (highest to lowest):
 *   1) JWT Bearer token (localStorage: brigade_jwt) — issued by /auth/oidc/callback
 *   2) Session cookie (sent automatically with credentials: include)
 *   3) API key (localStorage: apiKey) — legacy/native flow
 *
 * Team Lead A backend endpoints:
 *   GET /api/v1/auth/oidc/login     — initiates SSO flow (returns authUrl)
 *   GET /api/v1/auth/oidc/callback  — handles return from Keycloak
 *   GET /api/v1/auth/oidc/logout    — logs out
 *   GET /api/v1/auth/me             — returns current user
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

// localStorage keys
const JWT_KEY = 'brigade_jwt';
const JWT_EXPIRES_AT_KEY = 'brigade_jwt_expires_at';
const REFRESH_TOKEN_KEY = 'brigade_refresh_token';
const LEGACY_API_KEY = 'apiKey';

class AuthService {
  constructor() {
    // Send cookies with every axios request (session cookie from backend)
    axios.defaults.withCredentials = true;

    this.setupAxiosInterceptor();
  }

  /**
   * Axios request interceptor:
   *   - Attach Authorization: Bearer <jwt> if we have one
   *   - Fall back to X-API-Key for legacy native-auth routes
   *
   * Axios response interceptor:
   *   - On 401 to a Brigade API URL, clear tokens and redirect to SSO login
   */
  setupAxiosInterceptor() {
    axios.interceptors.request.use(
      (config) => {
        const jwt = this.getJwt();
        if (jwt) {
          config.headers.Authorization = `Bearer ${jwt}`;
        }
        const apiKey = localStorage.getItem(LEGACY_API_KEY);
        if (apiKey && !config.headers['X-API-Key']) {
          config.headers['X-API-Key'] = apiKey;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    axios.interceptors.response.use(
      (response) => response,
      (error) => {
        const status = error?.response?.status;
        const url = error?.config?.url || '';
        const isAuthEndpoint = url.includes('/auth/');
        const isBrigadeApi = url.startsWith(API_URL) || url.startsWith('/api/');

        if (status === 401 && isBrigadeApi && !isAuthEndpoint) {
          // Clear local auth material; backend session cookie is already invalid.
          this.clearJwt();
          // Allow current app-level handlers (useAuth.loadUser) to decide what to
          // render (login button vs redirect). Only force redirect if we're
          // already past a protected page — skip redirect on landing / login pages.
          const path = window.location.pathname;
          const publicPaths = ['/', '/login', '/register', '/auth/callback'];
          if (!publicPaths.includes(path)) {
            window.location.href = `${API_URL}/auth/oidc/login`;
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // ==========================================
  // JWT management
  // ==========================================

  getJwt() {
    const token = localStorage.getItem(JWT_KEY);
    if (!token) return null;

    const expiresAt = Number(localStorage.getItem(JWT_EXPIRES_AT_KEY) || 0);
    if (expiresAt && Date.now() >= expiresAt) {
      // Proactively clear expired JWTs so we fall back to cookie/API key.
      this.clearJwt();
      return null;
    }
    return token;
  }

  setJwt(token, expiresIn) {
    if (!token) return;
    localStorage.setItem(JWT_KEY, token);
    if (expiresIn) {
      const expiresAt = Date.now() + Number(expiresIn) * 1000;
      localStorage.setItem(JWT_EXPIRES_AT_KEY, String(expiresAt));
    }
  }

  setRefreshToken(token) {
    if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
  }

  clearJwt() {
    localStorage.removeItem(JWT_KEY);
    localStorage.removeItem(JWT_EXPIRES_AT_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }

  isJwtNearExpiry(marginSeconds = 60) {
    const expiresAt = Number(localStorage.getItem(JWT_EXPIRES_AT_KEY) || 0);
    if (!expiresAt) return false;
    return Date.now() + marginSeconds * 1000 >= expiresAt;
  }

  /**
   * Initiate OIDC login flow.
   * Backend endpoint returns { authUrl } — or, if the client prefers, it can
   * just navigate directly to the login endpoint (backend will 302 to Keycloak).
   * We try the JSON path first, then fall back to a direct navigation.
   */
  async login() {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/login`, {
        withCredentials: true,
        // Accept a redirect response as well — if backend returns 302, axios will
        // follow; if it returns JSON, we use authUrl below.
        headers: { Accept: 'application/json' }
      });

      if (data && data.authUrl) {
        window.location.href = data.authUrl;
        return;
      }
      // Fallback: just navigate to the endpoint and let the browser follow
      // the backend's 302 redirect to Keycloak.
      window.location.href = `${API_URL}/auth/oidc/login`;
    } catch (error) {
      // If axios fails (CORS, 302 not followed, etc.), do a plain navigation
      // so the browser handles the redirect chain.
      console.warn('[AuthService] login JSON fetch failed, using direct navigation', error?.message);
      window.location.href = `${API_URL}/auth/oidc/login`;
    }
  }

  /**
   * Fetch the currently-authenticated user.
   * Returns null when the user is not authenticated (401) rather than throwing —
   * callers like AuthContext/useAuth treat null as "logged out".
   */
  async getCurrentUser() {
    try {
      const { data } = await axios.get(`${API_URL}/auth/me`, {
        withCredentials: true
      });
      return data;
    } catch (error) {
      if (error?.response?.status === 401) {
        // Access token lapsed but the HttpOnly refresh cookie may still be
        // good — renew the session silently before declaring logged-out.
        try {
          await this.refreshToken();
          const { data } = await axios.get(`${API_URL}/auth/me`, {
            withCredentials: true
          });
          return data;
        } catch {
          return null;
        }
      }
      throw error;
    }
  }

  /**
   * Back-compat alias for the old endpoint name used by useAuth.loadUser().
   */
  async getCurrentUserOIDC() {
    return this.getCurrentUser();
  }

  /**
   * Refresh access token. Uses the refresh token we saved at callback time
   * if available; the backend may also support cookie-based refresh.
   */
  async refreshToken() {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    try {
      const { data } = await axios.post(
        `${API_URL}/auth/oidc/refresh`,
        refreshToken ? { refresh_token: refreshToken } : {},
        { withCredentials: true }
      );
      if (data?.access_token) {
        this.setJwt(data.access_token, data.expires_in);
      }
      if (data?.refresh_token) {
        this.setRefreshToken(data.refresh_token);
      }
      return data;
    } catch (error) {
      console.error('[AuthService] Token refresh failed:', error);
      this.clearJwt();
      throw error;
    }
  }

  /**
   * Logout — clear local tokens and hit the backend logout endpoint which
   * will clear the session cookie and redirect through Keycloak RP-initiated
   * logout. We use a hard navigation because the backend returns a 302.
   */
  logout() {
    this.clearJwt();
    localStorage.removeItem(LEGACY_API_KEY);
    localStorage.removeItem('user');
    window.location.href = `${API_URL}/auth/oidc/logout`;
  }

  // ==========================================
  // Permission helpers (unchanged endpoints, if backend still supports them)
  // These are best-effort — callers already handle failures.
  // ==========================================

  async checkPermission(permission) {
    try {
      const { data } = await axios.post(
        `${API_URL}/auth/oidc/check-permission`,
        { permission },
        { withCredentials: true }
      );
      return data.allowed || false;
    } catch {
      return false;
    }
  }

  async getPermissions() {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/permissions`, {
        withCredentials: true
      });
      return data;
    } catch {
      return [];
    }
  }

  async checkToolAccess(tool) {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/tool-access`, {
        params: { tool },
        withCredentials: true
      });
      return data;
    } catch {
      return { allowed: false };
    }
  }

  async getUpgradeInfo(feature) {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/upgrade-info`, {
        params: { feature },
        withCredentials: true
      });
      return data;
    } catch {
      return null;
    }
  }

  // ==========================================
  // Native email/password auth (legacy API-key flow — kept for back-compat)
  // ==========================================

  async registerUser(email, password, name) {
    try {
      const { data } = await axios.post(`${API_URL}/users/register`, {
        email, password, name
      }, { withCredentials: true });
      if (data.apiKey) localStorage.setItem(LEGACY_API_KEY, data.apiKey);
      return data;
    } catch (error) {
      throw new Error(
        error.response?.data?.detail || error.response?.data?.error || 'Registration failed'
      );
    }
  }

  async loginWithPassword(email, password) {
    try {
      const { data } = await axios.post(
        `${API_URL}/users/login`,
        { email, password },
        { withCredentials: true }
      );
      if (data.apiKey) localStorage.setItem(LEGACY_API_KEY, data.apiKey);
      return data;
    } catch (error) {
      throw new Error(
        error.response?.data?.detail || error.response?.data?.error || 'Login failed'
      );
    }
  }

  async getCurrentUserByApiKey() {
    const apiKey = localStorage.getItem(LEGACY_API_KEY);
    if (!apiKey) return null;
    try {
      const { data } = await axios.get(`${API_URL}/users/me`, { withCredentials: true });
      return data;
    } catch (error) {
      if (error.response?.status === 401) {
        localStorage.removeItem(LEGACY_API_KEY);
      }
      return null;
    }
  }

  hasApiKey() {
    return !!localStorage.getItem(LEGACY_API_KEY);
  }

  clearApiKey() {
    localStorage.removeItem(LEGACY_API_KEY);
  }
}

const authService = new AuthService();
export default authService;
