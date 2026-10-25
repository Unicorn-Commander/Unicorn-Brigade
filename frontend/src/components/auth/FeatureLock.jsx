import { useState } from 'react';
import PropTypes from 'prop-types';
import { Lock, Sparkles } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button } from '../ui';
import UpgradePrompt from './UpgradePrompt';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';

const BLUR = { light: 'blur-sm', medium: 'blur', heavy: 'blur-md' };

/**
 * FeatureLock — blurs locked content and overlays what it needs and an Upgrade
 * button that opens the UpgradePrompt dialog. No decoration animation: the
 * overlay simply appears.
 *
 *   <FeatureLock feature="publish_agents"><PublishButton /></FeatureLock>
 *   <FeatureLock feature="team_management" requiredTier="enterprise" blurStrength="heavy">…</FeatureLock>
 */
const FeatureLock = ({ feature, requiredTier, requiredRole, blurStrength = 'medium', children, className = '' }) => {
  const { hasPermission } = useAuth();
  const [showUpgrade, setShowUpgrade] = useState(false);

  if (feature && hasPermission(feature)) return <>{children}</>;

  return (
    <div className={`relative overflow-hidden rounded-card ${className}`}>
      <div className={`${BLUR[blurStrength] || BLUR.medium} pointer-events-none select-none`} aria-hidden="true">
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-surface/70 backdrop-blur-sm animate-fade-in">
        <div role="status" className="flex max-w-sm flex-col items-center gap-3 px-6 py-8 text-center">
          <span aria-hidden="true" className="flex h-12 w-12 items-center justify-center rounded-pane border border-accent/25 bg-accent/10 text-accent">
            <Lock className="h-6 w-6" />
          </span>
          <div>
            <p className="text-heading text-fg-strong">Feature locked</p>
            <p className="mt-1 text-body-sm text-muted">Upgrade to unlock it.</p>
          </div>
          {(requiredTier || requiredRole) && (
            <div className="flex flex-wrap items-center justify-center gap-1.5">
              {requiredTier && <TierBadge tier={requiredTier} />}
              {requiredRole && <RoleBadge role={requiredRole} />}
            </div>
          )}
          <Button icon={Sparkles} onClick={() => setShowUpgrade(true)}>
            Upgrade now
          </Button>
        </div>
      </div>
      {showUpgrade && (
        <UpgradePrompt feature={feature} requiredTier={requiredTier} requiredRole={requiredRole} isOpen onClose={() => setShowUpgrade(false)} />
      )}
    </div>
  );
};

FeatureLock.propTypes = {
  /** Feature name to check permission for */
  feature: PropTypes.string.isRequired,
  /** Required subscription tier */
  requiredTier: PropTypes.oneOf(['trial', 'starter', 'professional', 'enterprise', 'founders']),
  /** Required user role */
  requiredRole: PropTypes.oneOf(['brigade-user', 'brigade-builder', 'brigade-power-builder', 'brigade-org-admin', 'brigade-platform-admin']),
  /** Blur strength for locked content */
  blurStrength: PropTypes.oneOf(['light', 'medium', 'heavy']),
  /** Kept for API compatibility; the overlay no longer animates decoratively */
  showAnimation: PropTypes.bool,
  /** Content to lock */
  children: PropTypes.node.isRequired,
  /** Additional CSS classes */
  className: PropTypes.string,
};

export default FeatureLock;
