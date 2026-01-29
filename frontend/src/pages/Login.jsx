/**
 * Brigade Login Page
 * SSO authentication via Keycloak (Google, GitHub, Microsoft)
 */

import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import { LogIn, Sparkles, Shield, Zap } from 'lucide-react';
import { BrigadeLogo } from '../components/UnicornBrigadeLogo';

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, isAuthenticated, isLoading } = useAuth();

  const error = searchParams.get('error');

  const handleLogin = async () => {
    try {
      await login();
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Auto-redirect to Keycloak SSO on page load (skip the login page)
  useEffect(() => {
    if (!isAuthenticated && !isLoading && !error) {
      // Automatically initiate login flow
      handleLogin();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, isLoading, error]);

  // Show loading screen while redirecting to Keycloak
  if (!error && (!isAuthenticated && !isLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-900 via-slate-900 to-blue-900">
        <div className="text-center">
          <div className="mb-6 flex justify-center">
            <BrigadeLogo size={80} className="shadow-lg shadow-purple-500/30" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">🦄 Unicorn Brigade</h2>
          <p className="text-purple-300 mb-6">Redirecting to Unicorn Commander SSO...</p>
          <div className="flex justify-center space-x-2">
            <div className="w-3 h-3 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
            <div className="w-3 h-3 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
            <div className="w-3 h-3 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-900 via-slate-900 to-blue-900 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Login Card - Only shown if there's an error */}
      <div className="relative z-10 w-full max-w-md mx-4">
        <div className="glass border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {/* Logo & Title */}
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <BrigadeLogo size={80} className="shadow-lg shadow-purple-500/30" />
            </div>

            <h1 className="text-4xl font-bold mb-2">
              <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-blue-400 bg-clip-text text-transparent">
                🦄 Unicorn Brigade
              </span>
            </h1>

            <p className="text-slate-400 text-sm">
              AI Agent Infrastructure Platform
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <div className="flex items-start space-x-3">
                <Shield className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-red-400 text-sm font-medium">
                    Authentication Failed
                  </p>
                  <p className="text-red-300/80 text-xs mt-1">
                    {decodeURIComponent(error)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* SSO Login Button */}
          <button
            onClick={handleLogin}
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-bold py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 active:scale-95 shadow-lg hover:shadow-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
          >
            <div className="flex items-center justify-center space-x-3">
              <LogIn className="w-5 h-5" />
              <span>Login with SSO</span>
            </div>
          </button>

          {/* SSO Providers */}
          <div className="mt-6 text-center">
            <p className="text-slate-500 text-sm mb-3">Sign in with</p>
            <div className="flex items-center justify-center space-x-4 text-slate-400">
              <div className="flex items-center space-x-1">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span className="text-xs">Google</span>
              </div>
              <div className="flex items-center space-x-1">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                </svg>
                <span className="text-xs">GitHub</span>
              </div>
              <div className="flex items-center space-x-1">
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.4 24H0V8.6h11.4V24zM24 24H12.6V0H24v24z"/>
                </svg>
                <span className="text-xs">Microsoft</span>
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="my-8 border-t border-slate-700/50"></div>

          {/* Features */}
          <div className="space-y-3">
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Sparkles className="w-4 h-4 text-purple-400" />
              <span>Build custom AI agents with conversational interface</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Zap className="w-4 h-4 text-blue-400" />
              <span>Access 400+ MCP tools and integrations</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Shield className="w-4 h-4 text-green-400" />
              <span>Enterprise-grade security and authentication</span>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-8 pt-6 border-t border-slate-700/50 text-center">
            <p className="text-slate-500 text-xs">
              Part of{' '}
              <span className="text-purple-400 font-semibold">
                Unicorn Commander Ecosystem
              </span>
            </p>
            <p className="text-slate-600 text-xs mt-1">
              Powered by Keycloak SSO
            </p>
          </div>
        </div>

        {/* Platform Info */}
        <div className="mt-6 text-center text-slate-500 text-xs">
          <p>🦄 Magic Unicorn Unconventional Technology & Stuff Inc</p>
          <p className="mt-1">
            <a href="https://unicorncommander.com" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 transition">
              unicorncommander.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
