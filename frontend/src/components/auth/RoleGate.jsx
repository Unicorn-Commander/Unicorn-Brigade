import PropTypes from 'prop-types';
import { useAuth } from '../../hooks/useAuth';
import { LoadingState } from '../ui';
import UpgradePrompt from './UpgradePrompt';

const ROLE_HIERARCHY = {
  'brigade-user': 0,
  'brigade-builder': 1,
  'brigade-power-builder': 2,
  'brigade-org-admin': 3,
  'brigade-platform-admin': 4,
};

/**
 * RoleGate — renders children only when the user has the role (or any of
 * `roles`, or at least `minRole` in the hierarchy); otherwise an inline upgrade
 * prompt (or your fallback).
 *
 *   <RoleGate role="admin" showUpgradePrompt={false}>…</RoleGate>
 *   <RoleGate roles={["brigade-builder", "brigade-power-builder"]}>…</RoleGate>
 *   <RoleGate minRole="brigade-power-builder">…</RoleGate>
 */
const RoleGate = ({ role, roles, minRole, fallback = null, showUpgradePrompt = true, children }) => {
  const { user, hasRole, loading } = useAuth();

  if (loading) return <LoadingState variant="text" count={1} label="Checking access" className="max-w-xs" />;

  let allowed = true;
  let required = null;
  if (minRole) {
    allowed = (ROLE_HIERARCHY[user?.role] || 0) >= (ROLE_HIERARCHY[minRole] || 0);
    required = minRole;
  } else if (role) {
    allowed = hasRole(role);
    required = role;
  } else if (Array.isArray(roles)) {
    allowed = roles.some((r) => hasRole(r));
    required = roles[0];
  }

  if (!allowed) return showUpgradePrompt ? <UpgradePrompt requiredRole={required} inline /> : fallback;
  return <>{children}</>;
};

RoleGate.propTypes = {
  /** Single role to check */
  role: PropTypes.string,
  /** Array of roles to check (OR logic) */
  roles: PropTypes.arrayOf(PropTypes.string),
  /** Minimum role level required (hierarchical check) */
  minRole: PropTypes.oneOf(['brigade-user', 'brigade-builder', 'brigade-power-builder', 'brigade-org-admin', 'brigade-platform-admin']),
  /** Custom fallback to show when role denied */
  fallback: PropTypes.node,
  /** Whether to show upgrade prompt when role denied */
  showUpgradePrompt: PropTypes.bool,
  /** Content to render when role granted */
  children: PropTypes.node.isRequired,
};

export default RoleGate;
