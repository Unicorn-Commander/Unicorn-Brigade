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

const useAuth = create((set, get) => ({
  // State
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  /**
   * Load user on app start
   * Called from App.jsx useEffect
   */
  loadUser: async () => {
    set({ isLoading: true, error: null });

    // Dev mode: skip Keycloak and auto-authenticate
    if (DEV_MODE) {
      set({
        user: DEV_USER,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
      return;
    }

    try {
      const user = await authService.getCurrentUser();
      set({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null
      });
    } catch (error) {
      // Not authenticated - this is normal for logged out users
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
        error: null
      });
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
   * Check if user has a specific role
   * @param {string} role - Role to check
   * @returns {boolean} True if user has role
   */
  hasRole: (role) => {
    const { user } = get();

    if (!user || !user.roles) {
      return false;
    }

    return user.roles.includes(role);
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
      professional: 'bg-purple-100 text-purple-800 border-purple-200',
      enterprise: 'bg-amber-100 text-amber-800 border-amber-200',
      founders: 'bg-gradient-to-r from-purple-500 to-pink-500 text-white border-purple-300'
    };

    return tierColors[user.tier] || 'bg-gray-100 text-gray-800 border-gray-200';
  },

  /**
   * Initiate login flow
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
   * Logout from Brigade
   */
  logout: async () => {
    try {
      await authService.logout();
      set({
        user: null,
        isAuthenticated: false,
        error: null
      });
    } catch (error) {
      console.error('Logout failed:', error);
      // Clear state anyway
      set({
        user: null,
        isAuthenticated: false,
        error: null
      });
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
