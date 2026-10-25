import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Lock, ArrowRight, ExternalLink, Check } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { Button, Card, LoadingState, Modal } from '../ui';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';
import { billingService } from '../../services/billingService';

const FALLBACK_URL = 'https://unicorncommander.ai/plans.html';

/**
 * UpgradePrompt — shown when the user lacks a permission, tier or role. Inline
 * (a compact card) or as a dialog. Requirements come from the backend
 * (/billing/upgrade-requirements) with sensible defaults if it is unreachable.
 *
 *   <UpgradePrompt feature="create_agents" inline />
 *   <UpgradePrompt feature="publish_agents" isOpen={open} onClose={close} />
 */
const UpgradePrompt = ({ feature, requiredTier, requiredRole, inline = false, isOpen = true, onClose, className = '' }) => {
  const { user } = useAuth();
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    billingService
      .getUpgradeRequirements(feature)
      .then((data) => {
        if (cancelled) return;
        setInfo({
          feature: data.feature || feature,
          requiredTier: data.requiredTier || requiredTier || 'professional',
          requiredRole,
          benefits: data.benefits || [],
          upgradeUrl: data.upgradeUrl || data.opsCenterUrl || FALLBACK_URL,
        });
      })
      .catch(() => {
        if (cancelled) return;
        setInfo({ feature, requiredTier: requiredTier || 'professional', requiredRole, benefits: [], upgradeUrl: FALLBACK_URL });
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [feature, requiredTier, requiredRole]);

  const upgrade = () => window.open(info?.upgradeUrl || FALLBACK_URL, '_blank', 'noopener');

  if (loading) return <LoadingState variant="text" count={2} label="Checking what this needs" className="max-w-sm" />;
  if (!info) return null;

  const required = (
    <span className="inline-flex flex-wrap items-center gap-1.5 align-middle">
      {info.requiredTier && <TierBadge tier={info.requiredTier} size="small" />}
      {info.requiredRole && <RoleBadge role={info.requiredRole} size="small" />}
    </span>
  );

  if (inline) {
    return (
      <Card variant="elevated" padding="sm" className={`flex flex-wrap items-center gap-3 ${className}`}>
        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-accent/10 text-accent">
          <Lock className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-body font-medium text-fg">Upgrade required</span>
          <span className="mt-0.5 flex flex-wrap items-center gap-1.5 text-body-sm text-muted">This feature needs {required}</span>
        </span>
        <Button size="sm" iconRight={ArrowRight} onClick={upgrade}>
          Upgrade
        </Button>
      </Card>
    );
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="md"
      title="Unlock this feature"
      description="Your current plan doesn’t include it. Upgrading takes a minute in the Ops Center."
      footer={
        <>
          {onClose && (
            <Button variant="ghost" onClick={onClose}>
              Maybe later
            </Button>
          )}
          <Button iconRight={ExternalLink} onClick={upgrade}>
            Upgrade now
          </Button>
        </>
      }
    >
      <dl className="space-y-3">
        <div className="flex flex-wrap items-center gap-2 text-body-sm">
          <dt className="text-muted">Required:</dt>
          <dd>{required}</dd>
        </div>
        {user && (user.tier || user.role) && (
          <div className="flex flex-wrap items-center gap-2 text-body-sm">
            <dt className="text-muted">Your plan:</dt>
            <dd className="inline-flex flex-wrap items-center gap-1.5">
              {user.tier && <TierBadge tier={user.tier} size="small" />}
              {user.role && <RoleBadge role={user.role} size="small" />}
            </dd>
          </div>
        )}
      </dl>
      {info.benefits.length > 0 && (
        <div className="mt-4">
          <p className="mb-2 text-body-sm font-medium text-fg">What you get</p>
          <ul className="space-y-1.5">
            {info.benefits.map((b) => (
              <li key={b} className="flex items-start gap-2 text-body-sm text-muted">
                <Check aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Modal>
  );
};

UpgradePrompt.propTypes = {
  /** Feature name that requires upgrade */
  feature: PropTypes.string,
  /** Required subscription tier */
  requiredTier: PropTypes.oneOf(['trial', 'starter', 'professional', 'enterprise', 'founders']),
  /** Required user role */
  requiredRole: PropTypes.oneOf(['brigade-user', 'brigade-builder', 'brigade-power-builder', 'brigade-org-admin', 'brigade-platform-admin']),
  /** Show as inline banner instead of modal */
  inline: PropTypes.bool,
  /** Whether modal is open (for modal mode) */
  isOpen: PropTypes.bool,
  /** Callback when modal is closed */
  onClose: PropTypes.func,
  /** Additional CSS classes */
  className: PropTypes.string,
};

export default UpgradePrompt;
