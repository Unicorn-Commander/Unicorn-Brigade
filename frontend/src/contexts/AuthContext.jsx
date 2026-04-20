/**
 * AuthContext — React Context wrapper around the Zustand useAuth store.
 *
 * Exists to match the spec shared with Team Lead A's backend work:
 *   { user, loading, isAuthenticated, login, logout }
 *
 * The underlying state lives in src/hooks/useAuth.js (Zustand). This file
 * exposes it as a Context Provider so new components can use either API:
 *
 *   - Existing components: import useAuth from '../hooks/useAuth'
 *   - New components:      import { useAuthContext } from '../contexts/AuthContext'
 *
 * Both read the same underlying store.
 */

import { createContext, useContext, useEffect } from 'react';
import useAuth from '../hooks/useAuth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    loadUser,
    login,
    logout
  } = useAuth();

  // Kick off the initial session check on mount. Safe to call from both the
  // provider and App.jsx — loadUser is idempotent (sets its own loading flag).
  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const value = {
    user,
    // Expose both names so new code can use "loading" per spec while legacy
    // components continue to read "isLoading".
    loading: isLoading,
    isLoading,
    isAuthenticated,
    error,
    login,
    logout
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuthContext() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuthContext must be used within <AuthProvider>');
  }
  return ctx;
}

export default AuthContext;
