/**
 * Brigade Registration Page
 * Email/password registration for native authentication
 */

import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import useAuth from '../hooks/useAuth';
import { UserPlus, Shield, Sparkles, Zap, Eye, EyeOff, CheckCircle, AlertCircle, LogIn } from 'lucide-react';
import { BrigadeLogo } from '../components/UnicornBrigadeLogo';
import { apiJson } from '../services/http';

export default function Register() {
  const navigate = useNavigate();
  const { register, login, isAuthenticated, isLoading, error, clearError } = useAuth();

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  // Deployment auth flags — when native register is disabled (SSO-managed),
  // the form is replaced with a pointer to SSO login. null until loaded.
  const [authConfig, setAuthConfig] = useState(null);

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Clear errors on mount
  useEffect(() => {
    clearError();
  }, [clearError]);

  // Fetch public deployment auth flags (no auth required, never redirect)
  useEffect(() => {
    let cancelled = false;
    apiJson('/auth/config', { redirectOn401: false })
      .then((config) => {
        if (!cancelled) setAuthConfig(config);
      })
      .catch(() => {
        // Config unavailable — leave the form visible; the backend still
        // enforces the register gate with a 403.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const registerDisabled = authConfig ? authConfig.native_register_enabled === false : false;

  const handleSSOLogin = async () => {
    try {
      await login();
    } catch (err) {
      console.error('SSO login failed:', err);
    }
  };

  // Password validation
  const validatePassword = (password) => {
    const errors = [];
    if (password.length < 8) {
      errors.push('Password must be at least 8 characters');
    }
    if (!/[a-zA-Z]/.test(password)) {
      errors.push('Password must contain letters');
    }
    if (!/[0-9]/.test(password)) {
      errors.push('Password must contain numbers');
    }
    return errors;
  };

  // Email validation
  const validateEmail = (email) => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  // Handle input changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));

    // Clear validation errors as user types
    if (validationErrors[name]) {
      setValidationErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  // Validate form
  const validateForm = () => {
    const errors = {};

    if (!formData.name.trim()) {
      errors.name = 'Name is required';
    }

    if (!formData.email.trim()) {
      errors.email = 'Email is required';
    } else if (!validateEmail(formData.email)) {
      errors.email = 'Please enter a valid email address';
    }

    const passwordErrors = validatePassword(formData.password);
    if (passwordErrors.length > 0) {
      errors.password = passwordErrors;
    }

    if (formData.password !== formData.confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);
    clearError();

    try {
      await register(formData.email, formData.password, formData.name);
      setSuccess(true);
      // Redirect after showing success message
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      console.error('Registration failed:', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Password strength indicator
  const getPasswordStrength = () => {
    const password = formData.password;
    if (!password) return { strength: 0, label: '' };

    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;

    const labels = ['', 'Weak', 'Fair', 'Good', 'Strong', 'Very Strong'];
    const colors = ['', 'bg-red-500', 'bg-orange-500', 'bg-yellow-500', 'bg-green-500', 'bg-emerald-500'];

    return { strength, label: labels[strength], color: colors[strength] };
  };

  const passwordStrength = getPasswordStrength();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 relative overflow-hidden">
      {/* Animated background elements */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-unicorn-500/20 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-cyan-500/20 rounded-full blur-3xl animate-pulse delay-1000"></div>
      </div>

      {/* Registration Card */}
      <div className="relative z-10 w-full max-w-md mx-4">
        <div className="glass border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {/* Logo & Title */}
          <div className="text-center mb-6">
            <div className="flex justify-center mb-4">
              <BrigadeLogo size={64} className="shadow-lg shadow-unicorn-500/30" />
            </div>

            <h1 className="text-3xl font-bold mb-2">
              <span className="text-gradient">
                Join Unicorn Brigade
              </span>
            </h1>

            <p className="text-slate-400 text-sm">
              {registerDisabled
                ? 'Sign in with your organization account'
                : 'Create your account to get started'}
            </p>
          </div>

          {/* SSO-managed deployments: no native signup */}
          {registerDisabled && (
            <div className="space-y-6">
              <div className="bg-unicorn-500/10 border border-unicorn-500/30 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <Shield className="w-5 h-5 text-unicorn-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-unicorn-300 text-sm font-medium">
                      Account creation is managed by your organization's SSO
                    </p>
                    <p className="text-unicorn-300/70 text-xs mt-1">
                      Sign in with your organization account and a Brigade profile
                      will be provisioned for you automatically.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleSSOLogin}
                disabled={isLoading}
                className="w-full bg-gradient-to-r from-unicorn-600 to-unicorn-500 hover:from-unicorn-500 hover:to-unicorn-400 text-white font-bold py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 active:scale-95 shadow-lg hover:shadow-unicorn-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              >
                <div className="flex items-center justify-center space-x-3">
                  <LogIn className="w-5 h-5" />
                  <span>Login with SSO</span>
                </div>
              </button>
            </div>
          )}

          {/* Success Message */}
          {!registerDisabled && success && (
            <div className="mb-6 bg-green-500/10 border border-green-500/30 rounded-lg p-4">
              <div className="flex items-center space-x-3">
                <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0" />
                <div>
                  <p className="text-green-400 text-sm font-medium">
                    Registration Successful!
                  </p>
                  <p className="text-green-300/80 text-xs mt-1">
                    Redirecting to dashboard...
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Error Message */}
          {!registerDisabled && error && (
            <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <div className="flex items-start space-x-3">
                <Shield className="w-5 h-5 text-red-400 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-red-400 text-sm font-medium">
                    Registration Failed
                  </p>
                  <p className="text-red-300/80 text-xs mt-1">
                    {error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Registration Form */}
          {!registerDisabled && (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Name Input */}
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-slate-300 mb-1">
                Full Name
              </label>
              <input
                type="text"
                id="name"
                name="name"
                value={formData.name}
                onChange={handleChange}
                className={`w-full px-4 py-3 bg-slate-800/50 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500 transition ${
                  validationErrors.name ? 'border-red-500' : 'border-slate-600'
                }`}
                placeholder="Enter your name"
                disabled={isSubmitting}
              />
              {validationErrors.name && (
                <p className="mt-1 text-xs text-red-400">{validationErrors.name}</p>
              )}
            </div>

            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1">
                Email Address
              </label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className={`w-full px-4 py-3 bg-slate-800/50 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500 transition ${
                  validationErrors.email ? 'border-red-500' : 'border-slate-600'
                }`}
                placeholder="you@example.com"
                disabled={isSubmitting}
              />
              {validationErrors.email && (
                <p className="mt-1 text-xs text-red-400">{validationErrors.email}</p>
              )}
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-1">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  className={`w-full px-4 py-3 pr-12 bg-slate-800/50 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500 transition ${
                    validationErrors.password ? 'border-red-500' : 'border-slate-600'
                  }`}
                  placeholder="Min 8 chars, letters & numbers"
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {validationErrors.password && (
                <ul className="mt-1 text-xs text-red-400 list-disc list-inside">
                  {validationErrors.password.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              )}
              {/* Password Strength Indicator */}
              {formData.password && (
                <div className="mt-2">
                  <div className="flex items-center space-x-2">
                    <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full ${passwordStrength.color} transition-all duration-300`}
                        style={{ width: `${(passwordStrength.strength / 5) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-slate-400">{passwordStrength.label}</span>
                  </div>
                </div>
              )}
            </div>

            {/* Confirm Password Input */}
            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-300 mb-1">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  type={showConfirmPassword ? 'text' : 'password'}
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className={`w-full px-4 py-3 pr-12 bg-slate-800/50 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500 transition ${
                    validationErrors.confirmPassword ? 'border-red-500' : 'border-slate-600'
                  }`}
                  placeholder="Confirm your password"
                  disabled={isSubmitting}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300"
                >
                  {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              {validationErrors.confirmPassword && (
                <p className="mt-1 text-xs text-red-400">{validationErrors.confirmPassword}</p>
              )}
              {formData.confirmPassword && formData.password === formData.confirmPassword && !validationErrors.confirmPassword && (
                <p className="mt-1 text-xs text-green-400 flex items-center">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Passwords match
                </p>
              )}
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting || isLoading}
              className="w-full bg-gradient-to-r from-unicorn-600 to-unicorn-500 hover:from-unicorn-500 hover:to-unicorn-400 text-white font-bold py-4 px-6 rounded-lg transition-all duration-200 transform hover:scale-105 active:scale-95 shadow-lg hover:shadow-unicorn-500/50 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none mt-6"
            >
              <div className="flex items-center justify-center space-x-3">
                {isSubmitting ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Creating Account...</span>
                  </>
                ) : (
                  <>
                    <UserPlus className="w-5 h-5" />
                    <span>Create Account</span>
                  </>
                )}
              </div>
            </button>
          </form>
          )}

          {/* Login Link */}
          <div className="mt-6 text-center">
            <p className="text-slate-400 text-sm">
              Already have an account?{' '}
              <Link
                to="/login"
                className="text-unicorn-400 hover:text-unicorn-300 font-medium transition"
              >
                Login
              </Link>
            </p>
          </div>

          {/* Divider */}
          <div className="my-6 border-t border-slate-700/50"></div>

          {/* Features */}
          <div className="space-y-3">
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Sparkles className="w-4 h-4 text-unicorn-400" />
              <span>Build custom AI agents with conversational interface</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Zap className="w-4 h-4 text-cyan-400" />
              <span>Connect MCP servers and 20+ built-in tools</span>
            </div>
            <div className="flex items-center space-x-3 text-slate-400 text-sm">
              <Shield className="w-4 h-4 text-green-400" />
              <span>Enterprise-grade security and authentication</span>
            </div>
          </div>

          {/* Footer */}
          <div className="mt-6 pt-6 border-t border-slate-700/50 text-center">
            <p className="text-slate-400 text-xs">
              Part of{' '}
              <span className="text-unicorn-400 font-semibold">
                Unicorn Commander Ecosystem
              </span>
            </p>
          </div>
        </div>

        {/* Platform Info */}
        <div className="mt-6 text-center text-slate-400 text-xs">
          <p>Magic Unicorn Unconventional Technology & Stuff Inc</p>
          <p className="mt-1">
            <a href="https://unicorncommander.com" target="_blank" rel="noopener noreferrer" className="text-unicorn-400 hover:text-unicorn-300 transition">
              unicorncommander.com
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
