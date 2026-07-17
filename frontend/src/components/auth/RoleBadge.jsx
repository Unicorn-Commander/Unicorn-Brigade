import React, { useId } from 'react';
import PropTypes from 'prop-types';
import { Tooltip } from 'react-tooltip';
import { User, Wrench, Zap, Shield, Crown, Check } from 'lucide-react';

/**
 * RoleBadge Component
 *
 * Displays a color-coded badge for user roles with tooltip.
 * Uses react-tooltip (the app's single tooltip lib) for rich hover content.
 *
 * @component
 * @example
 * <RoleBadge role="brigade-builder" />
 *
 * @example
 * <RoleBadge role="brigade-platform-admin" size="large" showIcon />
 */
const TOOLTIP_STYLE = {
  backgroundColor: 'rgba(17, 24, 39, 0.98)',
  color: '#ffffff',
  borderRadius: '0.5rem',
  padding: '0.5rem 0.75rem',
  border: '1px solid rgba(100, 116, 139, 0.3)',
};

const RoleBadge = ({
  role,
  size = 'medium',
  showIcon = true,
  className = ''
}) => {
  const roleConfig = {
    'brigade-user': {
      label: 'User',
      color: 'bg-gray-100 text-gray-700 border-gray-300',
      icon: User,
      description: 'Basic user with limited permissions',
      permissions: [
        'View public agents',
        'Use agents',
        'View documentation'
      ]
    },
    'brigade-builder': {
      label: 'Builder',
      color: 'bg-blue-100 text-blue-700 border-blue-300',
      icon: Wrench,
      description: 'Create and manage personal agents',
      permissions: [
        'Create agents',
        'Edit own agents',
        'Use all tools',
        'Access agent builder'
      ]
    },
    'brigade-power-builder': {
      label: 'Power Builder',
      color: 'bg-purple-100 text-purple-700 border-purple-300',
      icon: Zap,
      description: 'Advanced agent creation and publishing',
      permissions: [
        'All Builder permissions',
        'Publish agents',
        'Advanced configurations',
        'Custom integrations'
      ]
    },
    'brigade-org-admin': {
      label: 'Org Admin',
      color: 'bg-orange-100 text-orange-700 border-orange-300',
      icon: Shield,
      description: 'Manage organization and teams',
      permissions: [
        'All Power Builder permissions',
        'Manage team members',
        'Organization settings',
        'Billing management'
      ]
    },
    'brigade-platform-admin': {
      label: 'Platform Admin',
      color: 'bg-red-100 text-red-700 border-red-300',
      icon: Crown,
      description: 'Full platform administration',
      permissions: [
        'All permissions',
        'Manage all users',
        'System configuration',
        'Platform settings'
      ]
    }
  };

  const config = roleConfig[role] || roleConfig['brigade-user'];
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
          <p className="font-semibold">{config.label}</p>
          <p className="text-xs text-gray-300">{config.description}</p>
          <ul className="text-xs space-y-0.5 mt-2">
            {config.permissions.map((perm, idx) => (
              <li key={idx} className="flex items-start gap-1">
                <Check className="w-3 h-3 text-green-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
                <span>{perm}</span>
              </li>
            ))}
          </ul>
        </div>
      </Tooltip>
    </>
  );
};

RoleBadge.propTypes = {
  /** User role */
  role: PropTypes.oneOf([
    'brigade-user',
    'brigade-builder',
    'brigade-power-builder',
    'brigade-org-admin',
    'brigade-platform-admin'
  ]).isRequired,
  /** Badge size */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Whether to show role icon */
  showIcon: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string
};

export default RoleBadge;
