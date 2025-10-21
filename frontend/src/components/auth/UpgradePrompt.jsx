import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Lock, ArrowRight, Sparkles } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';

/**
 * UpgradePrompt Component
 *
 * Displays an upgrade prompt when user lacks required permissions.
 * Can be shown inline or as a modal.
 *
 * @component
 * @example
 * // Inline prompt
 * <UpgradePrompt feature="create_agents" inline />
 *
 * @example
 * // Modal prompt
 * <UpgradePrompt
 *   feature="publish_agents"
 *   isOpen={showPrompt}
 *   onClose={() => setShowPrompt(false)}
 * />
 */
const UpgradePrompt = ({
  feature,
  requiredTier,
  requiredRole,
  inline = false,
  isOpen = true,
  onClose,
  className = ''
}) => {
  const { user } = useAuth();
  const [upgradeInfo, setUpgradeInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch upgrade requirements from API
    const fetchUpgradeInfo = async () => {
      setLoading(true);
      try {
        // TODO: Replace with actual API call when backend is ready
        // const response = await fetch(`/api/v1/brigade/upgrade-requirements?feature=${feature}`);
        // const data = await response.json();

        // Mock data for development
        const mockData = {
          feature,
          requiredTier: requiredTier || 'professional',
          requiredRole: requiredRole || 'brigade-builder',
          benefits: [
            'Access to advanced agent builder',
            'Unlimited agent creation',
            'Publishing to marketplace',
            'Priority support'
          ],
          upgradeUrl: `${window.location.origin}/upgrade?plan=professional`,
          opsCenterUrl: 'https://unicorncommander.ai/plans.html'
        };

        setUpgradeInfo(mockData);
      } catch (error) {
        console.error('Failed to fetch upgrade info:', error);
      } finally {
        setLoading(false);
      }
    };

    if (feature || requiredTier || requiredRole) {
      fetchUpgradeInfo();
    }
  }, [feature, requiredTier, requiredRole]);

  const handleUpgrade = () => {
    // Redirect to Ops Center billing page
    const opsCenterUrl = upgradeInfo?.opsCenterUrl || 'https://unicorncommander.ai/plans.html';
    window.open(opsCenterUrl, '_blank');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  if (!upgradeInfo) return null;

  // Inline version (compact banner)
  if (inline) {
    return (
      <div className={`bg-gradient-to-r from-purple-50 to-pink-50 border border-purple-200 rounded-lg p-4 ${className}`}>
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 mt-0.5">
            <Lock className="h-5 w-5 text-purple-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900">
              Upgrade Required
            </p>
            <p className="text-sm text-gray-600 mt-1">
              This feature requires {upgradeInfo.requiredTier && (
                <TierBadge tier={upgradeInfo.requiredTier} size="small" className="mx-1" />
              )}
              {upgradeInfo.requiredRole && (
                <RoleBadge role={upgradeInfo.requiredRole} size="small" className="mx-1" />
              )}
            </p>
          </div>
          <button
            onClick={handleUpgrade}
            className="flex-shrink-0 inline-flex items-center gap-1 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors"
          >
            Upgrade
            <ArrowRight size={14} />
          </button>
        </div>
      </div>
    );
  }

  // Modal version (full featured)
  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            className={`relative bg-white rounded-2xl shadow-2xl max-w-md w-full ${className}`}
          >
            {/* Close button */}
            {onClose && (
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X size={20} />
              </button>
            )}

            {/* Header */}
            <div className="bg-gradient-to-r from-purple-600 to-pink-600 p-6 rounded-t-2xl text-white">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-white/20 rounded-full">
                  <Sparkles size={24} />
                </div>
                <div>
                  <h3 className="text-xl font-bold">Unlock Premium Features</h3>
                  <p className="text-purple-100 text-sm mt-1">
                    Upgrade to access this feature
                  </p>
                </div>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              {/* Required tier/role */}
              <div className="flex items-center gap-2 text-sm">
                <span className="text-gray-600">Required:</span>
                {upgradeInfo.requiredTier && (
                  <TierBadge tier={upgradeInfo.requiredTier} />
                )}
                {upgradeInfo.requiredRole && (
                  <RoleBadge role={upgradeInfo.requiredRole} />
                )}
              </div>

              {/* Current tier/role */}
              {user && (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-gray-600">Your plan:</span>
                  {user.tier && <TierBadge tier={user.tier} />}
                  {user.role && <RoleBadge role={user.role} />}
                </div>
              )}

              {/* Benefits */}
              {upgradeInfo.benefits && upgradeInfo.benefits.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-900 mb-2">
                    What you'll get:
                  </p>
                  <ul className="space-y-2">
                    {upgradeInfo.benefits.map((benefit, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-sm text-gray-600">
                        <span className="text-green-500 flex-shrink-0 mt-0.5">✓</span>
                        <span>{benefit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 pt-0 flex gap-3">
              {onClose && (
                <button
                  onClick={onClose}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Maybe Later
                </button>
              )}
              <button
                onClick={handleUpgrade}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-purple-600 to-pink-600 text-white font-medium rounded-lg hover:from-purple-700 hover:to-pink-700 transition-all flex items-center justify-center gap-2"
              >
                Upgrade Now
                <ArrowRight size={16} />
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

UpgradePrompt.propTypes = {
  /** Feature name that requires upgrade */
  feature: PropTypes.string,
  /** Required subscription tier */
  requiredTier: PropTypes.oneOf(['trial', 'starter', 'professional', 'enterprise', 'founders']),
  /** Required user role */
  requiredRole: PropTypes.oneOf([
    'brigade-user',
    'brigade-builder',
    'brigade-power-builder',
    'brigade-org-admin',
    'brigade-platform-admin'
  ]),
  /** Show as inline banner instead of modal */
  inline: PropTypes.bool,
  /** Whether modal is open (for modal mode) */
  isOpen: PropTypes.bool,
  /** Callback when modal is closed */
  onClose: PropTypes.func,
  /** Additional CSS classes */
  className: PropTypes.string
};

export default UpgradePrompt;
