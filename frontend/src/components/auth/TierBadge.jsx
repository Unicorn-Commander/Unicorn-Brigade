import React, { useId } from 'react';
import PropTypes from 'prop-types';
import { Tooltip } from 'react-tooltip';
import { Crown, Zap, Sparkles, Building2, Star, Check } from 'lucide-react';

/**
 * TierBadge Component
 *
 * Displays a color-coded badge for subscription tiers with tooltip.
 * Uses react-tooltip (the app's single tooltip lib) for rich hover content.
 *
 * @component
 * @example
 * <TierBadge tier="professional" />
 *
 * @example
 * <TierBadge tier="enterprise" size="large" showIcon />
 */
const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(17, 24, 39, 0.98)',
  color: '#ffffff',
  borderRadius: '0.5rem',
  padding: '0.5rem 0.75rem',
  border: '1px solid rgba(100, 116, 139, 0.3)',
};

const TierBadge = ({
  tier,
  size = 'medium',
  showIcon = true,
  className = ''
}) => {
  const tierConfig = {
    trial: {
      label: 'Trial',
      color: 'bg-gray-100 text-gray-700 border-gray-300',
      icon: Sparkles,
      benefits: [
        '100 API calls/day',
        '7 day trial period',
        'Basic AI models',
        'Community support'
      ]
    },
    starter: {
      label: 'Starter',
      color: 'bg-blue-100 text-blue-700 border-blue-300',
      icon: Zap,
      benefits: [
        '1,000 API calls/month',
        'All AI models',
        'BYOK support',
        'Email support'
      ]
    },
    professional: {
      label: 'Professional',
      color: 'bg-purple-100 text-purple-700 border-purple-300',
      icon: Crown,
      benefits: [
        '10,000 API calls/month',
        'All services access',
        'Billing dashboard',
        'Priority support'
      ]
    },
    enterprise: {
      label: 'Enterprise',
      color: 'bg-yellow-100 text-yellow-700 border-yellow-300',
      icon: Building2,
      benefits: [
        'Unlimited API calls',
        'Team management (5 seats)',
        'Custom integrations',
        '24/7 dedicated support'
      ]
    },
    founders: {
      label: 'Founders',
      color: 'bg-gradient-to-r from-purple-500 via-pink-500 to-yellow-500 text-white border-0',
      icon: Star,
      benefits: [
        'Lifetime unlimited access',
        'All future features',
        'VIP support',
        'Special founders perks'
      ]
    }
  };

  const config = tierConfig[tier?.toLowerCase()] || tierConfig.trial;
  const Icon = config.icon;
  const tooltipId = useId();

  const sizeClasses = {
    small: 'text-xs px-2 py-0.5',
    medium: 'text-sm px-3 py-1',
    large: 'text-base px-4 py-1.5'
  };

  const iconSizes = {
    small: 12,
    medium: 14,
    large: 16
  };

  return (
    <>
      <span
        data-tooltip-id={tooltipId}
        className={`
          inline-flex items-center gap-1.5 rounded-full font-medium border
          ${config.color}
          ${sizeClasses[size]}
          ${className}
          transition-all duration-200 hover:scale-105 cursor-help
        `}
      >
        {showIcon && <Icon size={iconSizes[size]} />}
        {config.label}
      </span>
      <Tooltip id={tooltipId} place="top" className="z-50 max-w-xs" style={TOOLTIP_STYLE}>
        <div className="space-y-1">
          <p className="font-semibold">{config.label} Plan</p>
          <ul className="text-xs space-y-0.5">
            {config.benefits.map((benefit, idx) => (
              <li key={idx} className="flex items-start gap-1">
                <Check className="w-3 h-3 text-green-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span>{benefit}</span>
              </li>
            ))}
          </ul>
        </div>
      </Tooltip>
    </>
  );
};

TierBadge.propTypes = {
  /** Subscription tier name */
  tier: PropTypes.oneOf(['trial', 'starter', 'professional', 'enterprise', 'founders']).isRequired,
  /** Badge size */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Whether to show tier icon */
  showIcon: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string
};

export default TierBadge;
