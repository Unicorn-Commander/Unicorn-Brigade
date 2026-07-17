/**
 * Brigade Authentication Hook (Zustand)
 * Manages authentication state and provides permission checking utilities
 */

import { create } from 'zustand';
import authService from '../services/authService';

const TIER_HIERARCHY = ['trial', 'starter', 'professional', 'enterprise', 'founders'];

const DEV_MODE = import.meta.env.VITE_DEV_MODE === 'true';

const DEV_USER = {
  id: 'dev-user-001',
  name: 'Dev User',
  username: 'devuser',
  email: 'dev@unicorncommander.ai',
  tier: 'founders',
  roles: ['brigade-platform-admin'],
  permissions: ['*'],
  avatar: null,
};

let refreshIntervalId = null;

// Exported BOTH as a named and a default binding: the auth components
// (RoleGate/PermissionGate/UpgradePrompt/FeatureLock) import `{ useAuth }` while
// the rest of the app imports it as default. Keeping both keeps every call site working.
export const useAuth = create((set, get) => ({
  // State
  user: null,
  isAuthenticated: false,
  isLoading: true,


  error: null,

  /**
   * Load user on app start
   * Called from App.jsx useEffect
   * Tries API key auth first, then falls back to OIDC
   */
  loadUser: async () => {
    set({ isLoading: true, error: null });

    // Dev mode: skip auth and auto-authenticate
    if (DEV_MODE) {
      set({
        user: DEV_USER,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      get().startSessionRefresh();
      return;
    }

    // Prefer OIDC session (cookie or JWT) — this is the primary auth path.
    try {
      const user = await authService.getCurrentUser();
      if (user) {
        set({
          user,
          isAuthenticated: true,
          isLoading: false,
          error: null
        });
        get().startSessionRefresh();
        return;
      }
    } catch (error) {
      console.log('[useAuth] OIDC session check failed, trying API key:', error?.message);
    }

    // Fallback: legacy native-auth API key
    if (authService.hasApiKey()) {
      try {
        const user = await authService.getCurrentUserByApiKey();
        if (user) {
          set({
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null
          });
          get().startSessionRefresh();
          return;
        }
      } catch (error) {
        console.log('[useAuth] API key auth failed:', error?.message);
        authService.clearApiKey();
      }
    }

    // Not authenticated — render login UI, do not redirect.
    set({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null
    });
    get().stopSessionRefresh();
  },

  /**
   * Refresh active session to prevent expiry.
   * For API key auth, re-fetch the user profile.
   * For SSO, re-validate the OIDC session.
   */
  refreshSession: async () => {
    if (DEV_MODE) {
      return;
    }

    try {
      // Try OIDC session first
      const oidcUser = await authService.getCurrentUser();
      if (oidcUser) {
        set({ user: oidcUser, isAuthenticated: true });
        return;
      }

      // Fall back to API key
      if (authService.hasApiKey()) {
        const apiKeyUser = await authService.getCurrentUserByApiKey();
        if (apiKeyUser) {
          set({ user: apiKeyUser, isAuthenticated: true });
          return;
        }
      }

      throw new Error('Session expired');
    } catch (error) {
      await get().logout();
    }
  },

  /**
   * Start periodic session refresh (every 15 minutes).
   */
  startSessionRefresh: () => {
    if (refreshIntervalId) {
      return;
    }

    refreshIntervalId = setInterval(() => {
      get().refreshSession();
    }, 15 * 60 * 1000);
  },

  /**
   * Stop periodic session refresh.
   */
  stopSessionRefresh: () => {
    if (refreshIntervalId) {
      clearInterval(refreshIntervalId);
      refreshIntervalId = null;
    }
  },

  /**
   * Check if user has a specific permission
   * @param {string} permission - Permission to check
   * @returns {boolean} True if user has permission
   */
  hasPermission: (permission) => {
    const { user } = get();

    if (!user || !user.permissions) {
      return false;
    }

    return user.permissions.includes(permission);
  },

  /**
   * Check if user has a specific role.
   *
   * Recognizes every shape the backend hands us, so gates like
   * <RoleGate role="admin"> work regardless of auth method:
   *   - user.role       — the canonical backend role ('admin'|'operator'|'viewer'),
   *                       returned by /auth/me. Authoritative.
   *   - user.roles       — legacy brigade-* UI role list (present in dev / some flows).
   *   - user.permissions — Keycloak realm/client roles + API-key scopes; an admin
   *                        carries 'admin' here. '*' is the dev/superuser wildcard.
   *
   * @param {string} role - Role to check
   * @returns {boolean} True if user has role
   */
  hasRole: (role) => {
    const { user } = get();
    if (!user) return false;

    if (user.role === role) return true;
    if (Array.isArray(user.roles) && user.roles.includes(role)) return true;
    if (Array.isArray(user.permissions) &&
        (user.permissions.includes(role) || user.permissions.includes('*'))) {
      return true;
    }
    return false;
  },

  /**
   * Check if user has a tier or higher
   * Uses tier hierarchy: trial < starter < professional < enterprise < founders
   * @param {string} tier - Minimum tier required
   * @returns {boolean} True if user has tier or higher
   */
  hasTier: (tier) => {
    const { user } = get();

    if (!user || !user.tier) {
      return false;
    }

    const userTierIndex = TIER_HIERARCHY.indexOf(user.tier);
    const requiredTierIndex = TIER_HIERARCHY.indexOf(tier);

    // If tier not found in hierarchy, deny access
    if (userTierIndex === -1 || requiredTierIndex === -1) {
      return false;
    }

    return userTierIndex >= requiredTierIndex;
  },

  /**
   * Check if user can use a specific tool
   * @param {string} tool - Tool identifier
   * @returns {Promise<boolean>} True if user can access tool
   */
  canUseTool: async (tool) => {
    try {
      const result = await authService.checkToolAccess(tool);
      return result.allowed || false;
    } catch (error) {
      console.error('Tool access check failed:', error);
      return false;
    }
  },

  /**
   * Get upgrade information for a feature
   * @param {string} feature - Feature identifier
   * @returns {Promise<Object|null>} Upgrade info or null
   */
  getUpgradeInfo: async (feature) => {
    try {
      return await authService.getUpgradeInfo(feature);
    } catch (error) {
      console.error('Failed to get upgrade info:', error);
      return null;
    }
  },

  /**
   * Check if user is in a specific tier (exact match)
   * @param {string} tier - Tier to check
   * @returns {boolean} True if exact match
   */
  isTier: (tier) => {
    const { user } = get();
    return user?.tier === tier;
  },

  /**
   * Get user's display name
   * @returns {string} Display name
   */
  getDisplayName: () => {
    const { user } = get();
    return user?.name || user?.username || user?.email || 'User';
  },

  /**
   * Get user's tier badge color
   * @returns {string} Tailwind color class
   */
  getTierColor: () => {
    const { user } = get();

    if (!user?.tier) {
      return 'bg-gray-100 text-gray-800 border-gray-200';
    }

    const tierColors = {
      trial: 'bg-slate-100 text-slate-800 border-slate-200',
      starter: 'bg-blue-100 text-blue-800 border-blue-200',
      professional: 'bg-unicorn-100 text-unicorn-800 border-unicorn-200',
      enterprise: 'bg-amber-100 text-amber-800 border-amber-200',
      founders: 'bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white border-unicorn-300'
    };

    return tierColors[user.tier] || 'bg-gray-100 text-gray-800 border-gray-200';
  },

  /**
   * Initiate OIDC login flow (SSO)
   */
  login: async () => {
    try {
      await authService.login();
    } catch (error) {
      set({ error: error.message });
      throw error;
    }
  },

  /**
   * Login with email and password (native auth)
   * @param {string} email - User email
   * @param {string} password - User password
   */
  loginWithPassword: async (email, password) => {
    set({ isLoading: true, error: null });
    try {
      const data = await authService.loginWithPassword(email, password);
      set({
        user: data.user || data,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      get().startSessionRefresh();
      return data;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message
      });
      throw error;
    }
  },

  /**
   * Register a new user with email and password
   * @param {string} email - User email
   * @param {string} password - User password
   * @param {string} name - User display name
   */
  register: async (email, password, name) => {
    set({ isLoading: true, error: null });
    try {
      const data = await authService.registerUser(email, password, name);
      set({
        user: data.user || data,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      get().startSessionRefresh();
      return data;
    } catch (error) {
      set({
        isLoading: false,
        error: error.message
      });
      throw error;
    }
  },

  /**
   * Logout from Brigade
   */
  logout: async () => {
    try {
      // Clear API key first
      authService.clearApiKey();
      await authService.logout();
      set({
        user: null,
        isAuthenticated: false,
        error: null
      });
      get().stopSessionRefresh();
    } catch (error) {
      console.error('Logout failed:', error);
      // Clear state anyway
      authService.clearApiKey();
      set({
        user: null,
        isAuthenticated: false,
        error: null
      });
      get().stopSessionRefresh();
    }
  },

  /**
   * Clear error state
   */
  clearError: () => {
    set({ error: null });
  }
}));

export default useAuth;
