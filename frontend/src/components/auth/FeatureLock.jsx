import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { motion } from 'framer-motion';
import { Lock, Sparkles } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import UpgradePrompt from './UpgradePrompt';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';

/**
 * FeatureLock Component
 *
 * Overlays locked content with blur effect and upgrade prompt.
 * Shows lock icon and required tier/role.
 *
 * @component
 * @example
 * <FeatureLock feature="publish_agents">
 *   <PublishButton />
 * </FeatureLock>
 *
 * @example
 * <FeatureLock
 *   feature="team_management"
 *   requiredTier="enterprise"
 *   blurStrength="medium"
 * >
 *   <TeamSettings />
 * </FeatureLock>
 */
const FeatureLock = ({
  feature,
  requiredTier,
  requiredRole,
  blurStrength = 'medium',
  showAnimation = true,
  children,
  className = ''
}) => {
  const { hasPermission } = useAuth();
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);

  // Check if user has permission
  const hasAccess = feature ? hasPermission(feature) : false;

  // If user has access, just show children
  if (hasAccess) {
    return <>{children}</>;
  }

  // Blur strength mapping
  const blurClasses = {
    light: 'blur-[2px]',
    medium: 'blur-[4px]',
    heavy: 'blur-[8px]'
  };

  const blurClass = blurClasses[blurStrength] || blurClasses.medium;

  return (
    <div className={`relative ${className}`}>
      {/* Blurred content */}
      <div
        className={`${blurClass} select-none pointer-events-none`}
        aria-hidden="true"
      >
        {children}
      </div>

      {/* Lock overlay */}
      <motion.div
        initial={showAnimation ? { opacity: 0, scale: 0.9 } : { opacity: 1, scale: 1 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.3 }}
        className="absolute inset-0 flex items-center justify-center bg-white/60 backdrop-blur-sm"
      >
        <div className="text-center px-6 py-8 max-w-sm">
          {/* Lock icon with glow effect */}
          <motion.div
            initial={showAnimation ? { scale: 0, rotate: -180 } : { scale: 1, rotate: 0 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{
              type: "spring",
              stiffness: 200,
              damping: 15,
              delay: 0.1
            }}
            className="inline-flex p-4 rounded-full bg-gradient-to-br from-unicorn-100 to-unicorn-100 mb-4 relative"
          >
            <Lock className="h-8 w-8 text-unicorn-600" />

            {/* Animated glow */}
            {showAnimation && (
              <motion.div
                className="absolute inset-0 rounded-full bg-unicorn-400/30"
                animate={{
                  scale: [1, 1.3, 1],
                  opacity: [0.5, 0, 0.5]
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            )}
          </motion.div>

          {/* Feature locked message */}
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Feature Locked
          </h3>

          <p className="text-sm text-gray-600 mb-4">
            Upgrade to unlock this feature
          </p>

          {/* Required tier/role badges */}
          <div className="flex items-center justify-center gap-2 mb-4">
            {requiredTier && <TierBadge tier={requiredTier} />}
            {requiredRole && <RoleBadge role={requiredRole} />}
          </div>

          {/* Upgrade button */}
          <button
            onClick={() => setShowUpgradeModal(true)}
            className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white font-medium rounded-lg hover:from-unicorn-600 hover:to-unicorn-500 transition-all shadow-lg hover:shadow-xl transform hover:scale-105"
          >
            <Sparkles size={16} />
            Upgrade Now
          </button>
        </div>
      </motion.div>

      {/* Upgrade modal */}
      <UpgradePrompt
        feature={feature}
        requiredTier={requiredTier}
        requiredRole={requiredRole}
        isOpen={showUpgradeModal}
        onClose={() => setShowUpgradeModal(false)}
      />
    </div>
  );
};

FeatureLock.propTypes = {
  /** Feature name to check permission for */
  feature: PropTypes.string.isRequired,
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
  /** Blur strength for locked content */
  blurStrength: PropTypes.oneOf(['light', 'medium', 'heavy']),
  /** Whether to show unlock animation */
  showAnimation: PropTypes.bool,
  /** Content to lock */
  children: PropTypes.node.isRequired,
  /** Additional CSS classes */
  className: PropTypes.string
};

export default FeatureLock;
