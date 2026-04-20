import React, { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import { motion, AnimatePresence } from 'framer-motion';
import {
  User,
  Settings,
  CreditCard,
  LogOut,
  ChevronDown,
  Mail
} from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';

/**
 * UserProfile Component
 *
 * Displays user profile information with dropdown menu.
 * Shows username, email, tier, role, and navigation options.
 *
 * @component
 * @example
 * <UserProfile />
 *
 * @example
 * <UserProfile onLogout={handleLogout} />
 */
const UserProfile = ({
  onLogout,
  showBilling = true,
  className = ''
}) => {
  const { user, logout, isLoading: loading } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const handleLogoutClick = async () => {
    setIsOpen(false);
    if (onLogout) {
      await onLogout();
    } else {
      await logout();
    }
  };

  const handleProfileClick = () => {
    setIsOpen(false);
    // Navigate to profile settings
    window.location.href = '/settings/profile';
  };

  const handleBillingClick = () => {
    setIsOpen(false);
    // Navigate to billing dashboard (Ops Center)
    window.open('https://unicorncommander.ai/billing-settings.html', '_blank');
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center gap-2 px-3 py-2">
        <div className="animate-pulse bg-gray-200 rounded-full h-8 w-8"></div>
        <div className="animate-pulse bg-gray-200 rounded h-4 w-24"></div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Get user initials for avatar
  const getInitials = (name) => {
    if (!name) return 'U';
    const parts = name.trim().split(' ');
    if (parts.length === 1) return parts[0][0].toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  };

  const initials = getInitials(user.username || user.name);

  // Determine if billing should be shown (professional tier or higher)
  const canSeeBilling = showBilling && user.tier &&
    ['professional', 'enterprise', 'founders'].includes(user.tier.toLowerCase());

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Profile Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors w-full"
      >
        {/* Avatar */}
        <div className="flex-shrink-0 h-10 w-10 rounded-full bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center text-white font-semibold text-sm">
          {initials}
        </div>

        {/* User Info */}
        <div className="flex-1 min-w-0 text-left">
          <p className="text-sm font-medium text-gray-900 truncate">
            {user.username || user.name || 'User'}
          </p>
          <p className="text-xs text-gray-500 truncate">
            {user.email}
          </p>
        </div>

        {/* Chevron */}
        <ChevronDown
          size={16}
          className={`flex-shrink-0 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown Menu */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 right-0 mt-2 bg-white rounded-lg shadow-xl border border-gray-200 z-50 overflow-hidden"
          >
            {/* User Details */}
            <div className="p-4 border-b border-gray-100 bg-gray-50">
              <p className="text-sm font-medium text-gray-900 mb-1">
                {user.username || user.name}
              </p>
              <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                <Mail size={12} />
                {user.email}
              </div>
              <div className="flex flex-wrap gap-2">
                {user.tier && <TierBadge tier={user.tier} size="small" />}
                {user.role && <RoleBadge role={user.role} size="small" />}
              </div>
            </div>

            {/* Menu Items */}
            <div className="py-1">
              <button
                onClick={handleProfileClick}
                className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                <Settings size={16} />
                Profile Settings
              </button>

              {canSeeBilling && (
                <button
                  onClick={handleBillingClick}
                  className="w-full flex items-center gap-3 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <CreditCard size={16} />
                  Billing Dashboard
                </button>
              )}
            </div>

            {/* Logout */}
            <div className="border-t border-gray-100">
              <button
                onClick={handleLogoutClick}
                className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut size={16} />
                Sign Out
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

UserProfile.propTypes = {
  /** Custom logout handler */
  onLogout: PropTypes.func,
  /** Whether to show billing dashboard option */
  showBilling: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string
};

export default UserProfile;
