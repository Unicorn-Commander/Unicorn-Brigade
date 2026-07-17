import React from 'react';
import PropTypes from 'prop-types';
import { useAuth } from '../../hooks/useAuth';
import UpgradePrompt from './UpgradePrompt';

/**
 * RoleGate Component
 *
 * Conditionally renders children based on user role.
 * Shows upgrade prompt or custom fallback if user lacks role.
 *
 * @component
 * @example
 * // Single role
 * <RoleGate role="brigade-builder">
 *   <AdminPanel />
 * </RoleGate>
 *
 * @example
 * // Multiple roles with OR logic
 * <RoleGate roles={["brigade-builder", "brigade-power-builder"]}>
 *   <AdvancedFeatures />
 * </RoleGate>
 *
 * @example
 * // Minimum role level
 * <RoleGate minRole="brigade-power-builder">
 *   <TeamManagement />
 * </RoleGate>
 */
const RoleGate = ({
  role,
  roles,
  minRole,
  fallback = null,
  showUpgradePrompt = true,
  children
}) => {
  const { user, hasRole, loading } = useAuth();

  // Role hierarchy for minRole checks
  const ROLE_HIERARCHY = {
    'brigade-user': 0,
    'brigade-builder': 1,
    'brigade-power-builder': 2,
    'brigade-org-admin': 3,
    'brigade-platform-admin': 4
  };

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-unicorn-600"></div>
      </div>
    );
  }

  // Handle minimum role check (hierarchical)
  if (minRole) {
    const userRoleLevel = ROLE_HIERARCHY[user?.role] || 0;
    const requiredRoleLevel = ROLE_HIERARCHY[minRole] || 0;

    const allowed = userRoleLevel >= requiredRoleLevel;
    if (!allowed) {
      if (showUpgradePrompt) {
        return <UpgradePrompt requiredRole={minRole} inline />;
      }
      return fallback;
    }
    return <>{children}</>;
  }

  // Handle single role check
  if (role) {
    const allowed = hasRole(role);
    if (!allowed) {
      if (showUpgradePrompt) {
        return <UpgradePrompt requiredRole={role} inline />;
      }
      return fallback;
    }
    return <>{children}</>;
  }

  // Handle multiple roles check (OR logic)
  if (roles && Array.isArray(roles)) {
    const allowed = roles.some(r => hasRole(r));
    if (!allowed) {
      if (showUpgradePrompt) {
        return <UpgradePrompt requiredRole={roles[0]} inline />;
      }
      return fallback;
    }
    return <>{children}</>;
  }

  // No roles specified, show children by default
  return <>{children}</>;
};

RoleGate.propTypes = {
  /** Single role to check */
  role: PropTypes.string,
  /** Array of roles to check (OR logic) */
  roles: PropTypes.arrayOf(PropTypes.string),
  /** Minimum role level required (hierarchical check) */
  minRole: PropTypes.oneOf([
    'brigade-user',
    'brigade-builder',
    'brigade-power-builder',
    'brigade-org-admin',
    'brigade-platform-admin'
  ]),
  /** Custom fallback to show when role denied */
  fallback: PropTypes.node,
  /** Whether to show upgrade prompt when role denied */
  showUpgradePrompt: PropTypes.bool,
  /** Content to render when role granted */
  children: PropTypes.node.isRequired
};

export default RoleGate;
