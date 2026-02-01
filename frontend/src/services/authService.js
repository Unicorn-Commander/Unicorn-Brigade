/**
 * Brigade OIDC Authentication Service
 * Handles Keycloak authentication flow and user session management
 * Also supports API key authentication via X-API-Key header
 */

import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

class AuthService {
  constructor() {
    // Configure axios to send cookies with every request
    axios.defaults.withCredentials = true;

    // Set up axios interceptor to add X-API-Key header when available
    this.setupAxiosInterceptor();
  }

  /**
   * Set up axios interceptor to automatically add X-API-Key header
   */
  setupAxiosInterceptor() {
    axios.interceptors.request.use(
      (config) => {
        const apiKey = localStorage.getItem('apiKey');
        if (apiKey) {
          config.headers['X-API-Key'] = apiKey;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );
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
      // Clear API key from localStorage
      localStorage.removeItem('apiKey');

      await axios.post(`${API_URL}/auth/oidc/logout`, {}, {
        withCredentials: true
      });

      // Redirect to login page
      window.location.href = '/login';
    } catch (error) {
      console.error('Logout failed:', error);
      // Clear API key even on error
      localStorage.removeItem('apiKey');
      // Force redirect even on error
      window.location.href = '/login';
    }
  }

  // ==========================================
  // Native Email/Password Authentication
  // ==========================================

  /**
   * Register a new user with email and password
   * @param {string} email - User email
   * @param {string} password - User password (min 8 chars, must have letters and numbers)
   * @param {string} name - User display name
   * @returns {Promise<Object>} User object with apiKey
   */
  async registerUser(email, password, name) {
    try {
      const { data } = await axios.post(`${API_URL}/users/register`, {
        email,
        password,
        name
      });

      // Store the API key for subsequent requests
      if (data.apiKey) {
        localStorage.setItem('apiKey', data.apiKey);
      }

      return data;
    } catch (error) {
      console.error('[AuthService] Registration failed:', error);
      throw new Error(error.response?.data?.detail || error.response?.data?.error || 'Registration failed');
    }
  }

  /**
   * Login with email and password
   * @param {string} email - User email
   * @param {string} password - User password
   * @returns {Promise<Object>} User object with apiKey
   */
  async loginWithPassword(email, password) {
    try {
      const { data } = await axios.post(`${API_URL}/users/login`, {
        email,
        password
      });

      // Store the API key for subsequent requests
      if (data.apiKey) {
        localStorage.setItem('apiKey', data.apiKey);
      }

      return data;
    } catch (error) {
      console.error('[AuthService] Login failed:', error);
      throw new Error(error.response?.data?.detail || error.response?.data?.error || 'Login failed');
    }
  }

  /**
   * Get current user via API key (for native auth)
   * @returns {Promise<Object|null>} User object or null if not authenticated
   */
  async getCurrentUserByApiKey() {
    const apiKey = localStorage.getItem('apiKey');
    if (!apiKey) {
      return null;
    }

    try {
      const { data } = await axios.get(`${API_URL}/users/me`);
      return data;
    } catch (error) {
      console.error('[AuthService] Failed to get user by API key:', error);
      // Clear invalid API key
      if (error.response?.status === 401) {
        localStorage.removeItem('apiKey');
      }
      return null;
    }
  }

  /**
   * Check if user has an API key stored
   * @returns {boolean} True if API key exists
   */
  hasApiKey() {
    return !!localStorage.getItem('apiKey');
  }

  /**
   * Clear stored API key (logout for native auth)
   */
  clearApiKey() {
    localStorage.removeItem('apiKey');
  }
}

// Export singleton instance
const authService = new AuthService();
export default authService;
