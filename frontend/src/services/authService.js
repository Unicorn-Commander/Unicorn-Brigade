/**
 * Brigade OIDC Authentication Service
 * Handles Keycloak authentication flow and user session management
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

class AuthService {
  constructor() {
    // Configure axios to send cookies with every request
    axios.defaults.withCredentials = true;
  }

  /**
   * Initiate OIDC login flow
   * Redirects user to Keycloak login page
   */
  async login() {
    try {
      console.log('[AuthService] Initiating login, API_URL:', API_URL);
      const { data } = await axios.get(`${API_URL}/auth/oidc/login`, {
        withCredentials: true
      });

      console.log('[AuthService] Login response:', data);

      if (data.authUrl) {
        console.log('[AuthService] Redirecting to:', data.authUrl);
        // Redirect to Keycloak login page
        window.location.href = data.authUrl;
      } else {
        throw new Error('No authorization URL received');
      }
    } catch (error) {
      console.error('[AuthService] Login initiation failed:', error);
      console.error('[AuthService] Error details:', error.response?.data, error.message);
      throw new Error(error.response?.data?.error || 'Failed to initiate login');
    }
  }

  /**
   * Get current user information with permissions
   * @returns {Promise<Object>} User object with tier, roles, and permissions
   */
  async getCurrentUser() {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/user`, {
        withCredentials: true
      });

      return data;
    } catch (error) {
      console.error('Failed to get current user:', error);
      throw new Error(error.response?.data?.error || 'Not authenticated');
    }
  }

  /**
   * Check if user has a specific permission
   * @param {string} permission - Permission to check
   * @returns {Promise<boolean>} True if user has permission
   */
  async checkPermission(permission) {
    try {
      const { data } = await axios.post(
        `${API_URL}/auth/oidc/check-permission`,
        { permission },
        { withCredentials: true }
      );

      return data.allowed || false;
    } catch (error) {
      console.error('Permission check failed:', error);
      return false;
    }
  }

  /**
   * Get all user permissions
   * @returns {Promise<Array>} Array of permission strings
   */
  async getPermissions() {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/permissions`, {
        withCredentials: true
      });

      return data;
    } catch (error) {
      console.error('Failed to get permissions:', error);
      return [];
    }
  }

  /**
   * Check if user has access to a specific MCP tool
   * @param {string} tool - Tool identifier
   * @returns {Promise<Object>} Access result with allowed flag
   */
  async checkToolAccess(tool) {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/tool-access`, {
        params: { tool },
        withCredentials: true
      });

      return data;
    } catch (error) {
      console.error('Tool access check failed:', error);
      return { allowed: false };
    }
  }

  /**
   * Get upgrade information for a locked feature
   * @param {string} feature - Feature identifier
   * @returns {Promise<Object>} Upgrade requirements and pricing
   */
  async getUpgradeInfo(feature) {
    try {
      const { data } = await axios.get(`${API_URL}/auth/oidc/upgrade-info`, {
        params: { feature },
        withCredentials: true
      });

      return data;
    } catch (error) {
      console.error('Failed to get upgrade info:', error);
      return null;
    }
  }

  /**
   * Refresh access token using refresh token
   * @param {string} refreshToken - Refresh token
   * @returns {Promise<Object>} New tokens
   */
  async refreshToken(refreshToken) {
    try {
      const { data } = await axios.post(
        `${API_URL}/auth/oidc/refresh`,
        { refresh_token: refreshToken },
        { withCredentials: true }
      );

      return data;
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw new Error(error.response?.data?.error || 'Failed to refresh token');
    }
  }

  /**
   * Logout from Keycloak and clear session
   */
  async logout() {
    try {
      await axios.post(`${API_URL}/auth/oidc/logout`, {}, {
        withCredentials: true
      });

      // Redirect to login page
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout failed:', error);
      // Force redirect even on error
      window.location.href = '/login';
    }
  }
}

// Export singleton instance
const authService = new AuthService();
export default authService;
