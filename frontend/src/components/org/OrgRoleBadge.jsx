import { Crown, Shield, User } from 'lucide-react';
import { Chip } from '../ui';

/**
 * Per-org role chip (owner | admin | member) — the tenancy role axis, distinct
 * from the global brigade-* roles in components/auth/RoleBadge. Owner wears the
 * accent; admin is info; member stays neutral so the accent isn't diluted.
 *
 *   size  sm (18px) | md (22px, default)
 */
const ROLES = {
  owner: { label: 'Owner', icon: Crown, tone: 'accent' },
  admin: { label: 'Admin', icon: Shield, tone: 'info' },
  member: { label: 'Member', icon: User, tone: 'neutral' },
};

export default function OrgRoleBadge({ role, size = 'md', className = '' }) {
  const r = ROLES[role] || ROLES.member;
  return (
    <Chip tone={r.tone} size={size === 'sm' ? 'xs' : 'sm'} icon={r.icon} className={className}>
      {r.label}
    </Chip>
  );
}
