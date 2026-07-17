import { Crown, Shield, User } from 'lucide-react';

/**
 * Per-org role pill (owner | admin | member) — the BR-2.1 tenancy role axis,
 * distinct from the global brigade-* roles shown by components/auth/RoleBadge.
 * Owner wears the one unicorn accent; admin/member stay neutral so the accent
 * isn't diluted.
 */
const ROLE_CONFIG = {
  owner: {
    label: 'Owner',
    icon: Crown,
    className: 'bg-unicorn-500/15 text-unicorn-300 border-unicorn-500/40',
  },
  admin: {
    label: 'Admin',
    icon: Shield,
    className: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  },
  member: {
    label: 'Member',
    icon: User,
    className: 'bg-slate-500/15 text-muted border-slate-500/40',
  },
};

const SIZES = {
  sm: 'text-[11px] px-2 py-0.5 gap-1',
  md: 'text-xs px-2.5 py-1 gap-1.5',
};

export default function OrgRoleBadge({ role, size = 'md', className = '' }) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.member;
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${config.className} ${
        SIZES[size] || SIZES.md
      } ${className}`}
    >
      <Icon className={size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5'} aria-hidden="true" />
      {config.label}
    </span>
  );
}
