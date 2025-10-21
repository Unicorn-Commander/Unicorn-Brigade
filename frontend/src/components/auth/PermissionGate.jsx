import React from 'react';
import PropTypes from 'prop-types';
import { useAuth } from '../../hooks/useAuth';
import UpgradePrompt from './UpgradePrompt';

/**
 * PermissionGate Component
 *
 * Conditionally renders children based on user permissions.
 * Shows upgrade prompt or custom fallback if user lacks permission.
 *
 * @component
 * @example
 * // Single permission
 * <PermissionGate permission="create_agents">
 *   <CreateAgentButton />
 * </PermissionGate>
 *
 * @example
 * // Multiple permissions with AND logic
 * <PermissionGate permissions={["create_agents", "publish_agents"]} requireAll>
 *   <PublishButton />
 * </PermissionGate>
 *
 * @example
 * // Multiple permissions with OR logic
 * <PermissionGate permissions={["view_agents", "edit_agents"]}>
 *   <AgentList />
 * </PermissionGate>
 */
const PermissionGate = ({
  permission,
  permissions,
  requireAll = false,
  fallback = null,
  showUpgradePrompt = true,
  children
}) => {
  const { user, hasPermission, loading } = useAuth();

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-purple-600"></div>
      </div>
    );
  }

  // Handle single permission check
  if (permission) {
    const allowed = hasPermission(permission);
    if (!allowed) {
      if (showUpgradePrompt) {
        return <UpgradePrompt feature={permission} inline />;
      }
      return fallback;
    }
    return <>{children}</>;
  }

  // Handle multiple permissions check
  if (permissions && Array.isArray(permissions)) {
    let allowed;

    if (requireAll) {
      // AND logic: user must have ALL permissions
      allowed = permissions.every(perm => hasPermission(perm));
    } else {
      // OR logic: user must have AT LEAST ONE permission
      allowed = permissions.some(perm => hasPermission(perm));
    }

    if (!allowed) {
      if (showUpgradePrompt) {
        return <UpgradePrompt feature={permissions[0]} inline />;
      }
      return fallback;
    }
    return <>{children}</>;
  }

  // No permissions specified, show children by default
  return <>{children}</>;
};

PermissionGate.propTypes = {
  /** Single permission to check */
  permission: PropTypes.string,
  /** Array of permissions to check */
  permissions: PropTypes.arrayOf(PropTypes.string),
  /** If true, user must have ALL permissions. If false, user needs ANY permission. */
  requireAll: PropTypes.bool,
  /** Custom fallback to show when permission denied */
  fallback: PropTypes.node,
  /** Whether to show upgrade prompt when permission denied */
  showUpgradePrompt: PropTypes.bool,
  /** Content to render when permission granted */
  children: PropTypes.node.isRequired
};

export default PermissionGate;
