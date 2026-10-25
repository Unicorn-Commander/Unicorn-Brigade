import PropTypes from 'prop-types';
import { useAuth } from '../../hooks/useAuth';
import { LoadingState } from '../ui';
import UpgradePrompt from './UpgradePrompt';

/**
 * PermissionGate — renders children only when the user has the permission(s);
 * otherwise an inline upgrade prompt (or your fallback).
 *
 *   <PermissionGate permission="create_agents"><CreateAgentButton /></PermissionGate>
 *   <PermissionGate permissions={["create_agents", "publish_agents"]} requireAll>…</PermissionGate>
 *   <PermissionGate permissions={["view_agents", "edit_agents"]}>…</PermissionGate>   // OR
 */
const PermissionGate = ({ permission, permissions, requireAll = false, fallback = null, showUpgradePrompt = true, children }) => {
  const { hasPermission, loading } = useAuth();

  if (loading) return <LoadingState variant="text" count={1} label="Checking access" className="max-w-xs" />;

  let allowed = true;
  let feature = null;
  if (permission) {
    allowed = hasPermission(permission);
    feature = permission;
  } else if (Array.isArray(permissions)) {
    allowed = requireAll ? permissions.every((p) => hasPermission(p)) : permissions.some((p) => hasPermission(p));
    feature = permissions[0];
  }

  if (!allowed) return showUpgradePrompt ? <UpgradePrompt feature={feature} inline /> : fallback;
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
  children: PropTypes.node.isRequired,
};

export default PermissionGate;
