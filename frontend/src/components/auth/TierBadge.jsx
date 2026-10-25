import PropTypes from 'prop-types';
import { Crown, Zap, Sparkles, Building2, Star } from 'lucide-react';
import { Chip, Tooltip } from '../ui';

/**
 * TierBadge — the subscription tier as a Chip, with its benefits in a tooltip.
 *
 *   <TierBadge tier="professional" />
 *   <TierBadge tier="enterprise" size="large" />
 */
export const TIER_CONFIG = {
  trial: { label: 'Trial', tone: 'neutral', icon: Sparkles, benefits: ['100 API calls/day', '7-day trial', 'Basic AI models', 'Community support'] },
  starter: { label: 'Starter', tone: 'info', icon: Zap, benefits: ['1,000 API calls/month', 'All AI models', 'BYOK support', 'Email support'] },
  professional: { label: 'Professional', tone: 'accent', icon: Crown, benefits: ['10,000 API calls/month', 'All services', 'Billing dashboard', 'Priority support'] },
  enterprise: { label: 'Enterprise', tone: 'warn', icon: Building2, benefits: ['Unlimited API calls', 'Team management (5 seats)', 'Custom integrations', '24/7 dedicated support'] },
  founders: { label: 'Founders', tone: 'accent', solid: true, icon: Star, benefits: ['Lifetime unlimited access', 'All future features', 'VIP support', 'Founders perks'] },
};

const SIZE = { small: 'xs', medium: 'sm', large: 'md' };

const TierBadge = ({ tier, size = 'medium', showIcon = true, className = '' }) => {
  const config = TIER_CONFIG[String(tier || '').toLowerCase()] || TIER_CONFIG.trial;
  return (
    <Tooltip content={`${config.label} plan — ${config.benefits.join(' · ')}`}>
      <Chip tone={config.tone} solid={config.solid} size={SIZE[size] || 'sm'} icon={showIcon ? config.icon : undefined} className={className}>
        {config.label}
      </Chip>
    </Tooltip>
  );
};

TierBadge.propTypes = {
  /** Subscription tier name */
  tier: PropTypes.oneOf(['trial', 'starter', 'professional', 'enterprise', 'founders']).isRequired,
  /** Badge size */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Whether to show the tier icon */
  showIcon: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string,
};

export default TierBadge;
