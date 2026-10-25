import PropTypes from 'prop-types';
import { User, Wrench, Zap, Shield, Crown } from 'lucide-react';
import { Chip, Tooltip } from '../ui';

/**
 * RoleBadge — the global brigade-* role as a Chip, with what it allows in a
 * tooltip (hover and keyboard focus through the one TooltipHost).
 *
 *   <RoleBadge role="brigade-builder" />
 *   <RoleBadge role="brigade-platform-admin" size="large" />
 */
export const ROLE_CONFIG = {
  'brigade-user': {
    label: 'User',
    tone: 'neutral',
    icon: User,
    description: 'Basic access',
    permissions: ['View public agents', 'Use agents', 'View documentation'],
  },
  'brigade-builder': {
    label: 'Builder',
    tone: 'info',
    icon: Wrench,
    description: 'Create and manage personal agents',
    permissions: ['Create agents', 'Edit own agents', 'Use all tools', 'Access the agent builder'],
  },
  'brigade-power-builder': {
    label: 'Power Builder',
    tone: 'info',
    icon: Zap,
    description: 'Advanced agent creation and publishing',
    permissions: ['All Builder permissions', 'Publish agents', 'Advanced configurations', 'Custom integrations'],
  },
  'brigade-org-admin': {
    label: 'Org Admin',
    tone: 'accent',
    icon: Shield,
    description: 'Manage the organization and its teams',
    permissions: ['All Power Builder permissions', 'Manage team members', 'Organization settings', 'Billing management'],
  },
  'brigade-platform-admin': {
    label: 'Platform Admin',
    tone: 'accent',
    solid: true,
    icon: Crown,
    description: 'Full platform administration',
    permissions: ['All permissions', 'Manage all users', 'System configuration', 'Platform settings'],
  },
};

const SIZE = { small: 'xs', medium: 'sm', large: 'md' };

const RoleBadge = ({ role, size = 'medium', showIcon = true, className = '' }) => {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG['brigade-user'];
  return (
    <Tooltip content={`${config.label} — ${config.description}. ${config.permissions.join(' · ')}`}>
      <Chip tone={config.tone} solid={config.solid} size={SIZE[size] || 'sm'} icon={showIcon ? config.icon : undefined} className={className}>
        {config.label}
      </Chip>
    </Tooltip>
  );
};

RoleBadge.propTypes = {
  /** User role */
  role: PropTypes.oneOf(['brigade-user', 'brigade-builder', 'brigade-power-builder', 'brigade-org-admin', 'brigade-platform-admin']).isRequired,
  /** Badge size */
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  /** Whether to show the role icon */
  showIcon: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string,
};

export default RoleBadge;
