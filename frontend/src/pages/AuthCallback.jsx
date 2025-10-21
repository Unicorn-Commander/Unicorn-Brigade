/**
 * Brigade OIDC Callback Handler
 * Processes callback from Keycloak after successful authentication
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';

export default function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('processing'); // processing | success | error
  const [message, setMessage] = useState('Completing authentication...');

  useEffect(() => {
    // Check for success or error in query params
    const loginStatus = searchParams.get('login');
    const error = searchParams.get('error');

    if (loginStatus === 'success') {
      // Login successful
      setStatus('success');
      setMessage('Login successful! Redirecting to dashboard...');

      // Redirect to dashboard after brief delay
      setTimeout(() => {
        navigate('/dashboard', { replace: true });
      }, 1500);
    } else if (error) {
      // Login failed
      setStatus('error');
      setMessage(decodeURIComponent(error));

      // Redirect to login after delay
      setTimeout(() => {
        navigate(`/login?error=${error}`, { replace: true });
      }, 3000);
    } else {
      // Still processing (backend should redirect with ?login=success or ?error=message)
      setStatus('processing');
      setMessage('Processing authentication...');

      // Timeout after 10 seconds
      const timeout = setTimeout(() => {
        setStatus('error');
        setMessage('Authentication timeout. Please try again.');

        setTimeout(() => {
          navigate('/login?error=timeout', { replace: true });
        }, 2000);
      }, 10000);

      return () => clearTimeout(timeout);
    }
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-purple-900 via-slate-900 to-blue-900">
      {/* Animated background */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-blue-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Callback Card */}
      <div className="relative z-10 w-full max-w-md mx-4">
        <div className="glass border border-slate-700/50 rounded-2xl p-12 shadow-2xl">
          <div className="text-center">
            {/* Status Icon */}
            <div className="flex justify-center mb-6">
              {status === 'processing' && (
                <Loader2 className="w-16 h-16 text-purple-400 animate-spin" />
              )}
              {status === 'success' && (
                <CheckCircle className="w-16 h-16 text-green-400 animate-bounce" />
              )}
              {status === 'error' && (
                <XCircle className="w-16 h-16 text-red-400 animate-pulse" />
              )}
            </div>

            {/* Title */}
            <h2 className="text-2xl font-bold mb-3">
              {status === 'processing' && (
                <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">
                  Processing...
                </span>
              )}
              {status === 'success' && (
                <span className="text-green-400">Success!</span>
              )}
              {status === 'error' && (
                <span className="text-red-400">Authentication Failed</span>
              )}
            </h2>

            {/* Message */}
            <p className="text-slate-400 text-sm leading-relaxed">
              {message}
            </p>

            {/* Processing animation */}
            {status === 'processing' && (
              <div className="mt-8 flex justify-center space-x-2">
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
              </div>
            )}

            {/* Error retry button */}
            {status === 'error' && (
              <div className="mt-8">
                <button
                  onClick={() => navigate('/login', { replace: true })}
                  className="px-6 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition text-sm font-medium"
                >
                  Return to Login
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Branding */}
        <div className="mt-6 text-center">
          <p className="text-slate-500 text-xs">
            <span className="text-purple-400 font-semibold">🦄 Unicorn Brigade</span>
            {' '}- AI Agent Infrastructure Platform
          </p>
        </div>
      </div>
    </div>
  );
}
