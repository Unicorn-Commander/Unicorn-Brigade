import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Settings, CreditCard, LogOut, ChevronsUpDown } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import { Menu } from '../ui';
import TierBadge from './TierBadge';
import RoleBadge from './RoleBadge';

/**
 * UserProfile — the signed-in person, as a ui Menu in the sidebar footer:
 * initials, name, email, tier and role chips; items for settings, the billing
 * dashboard (paid tiers) and sign-out.
 */
function initialsOf(name) {
  if (!name) return 'U';
  const parts = String(name).trim().split(/\s+/);
  if (parts.length === 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const UserProfile = ({ onLogout, showBilling = true, className = '' }) => {
  const { user, logout, isLoading: loading } = useAuth();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div aria-hidden="true" className={`flex items-center gap-3 px-2 py-2 ${className}`}>
        <div className="h-9 w-9 animate-pulse rounded-full bg-elevated" />
        <div className="flex-1 space-y-1.5">
          <div className="h-3 w-24 animate-pulse rounded-chip bg-elevated" />
          <div className="h-2.5 w-32 animate-pulse rounded-chip bg-elevated" />
        </div>
      </div>
    );
  }
  if (!user) return null;

  const displayName = user.username || user.name || 'User';
  const canSeeBilling =
    showBilling && user.tier && ['professional', 'enterprise', 'founders'].includes(String(user.tier).toLowerCase());

  const items = [
    { id: 'settings', icon: Settings, label: 'Profile settings', onSelect: () => navigate('/settings') },
    ...(canSeeBilling
      ? [
          {
            id: 'billing',
            icon: CreditCard,
            label: 'Billing dashboard',
            onSelect: () => window.open('https://unicorncommander.ai/billing-settings.html', '_blank', 'noopener'),
          },
        ]
      : []),
    { type: 'separator' },
    {
      id: 'signout',
      icon: LogOut,
      label: 'Sign out',
      tone: 'danger',
      onSelect: async () => {
        if (onLogout) await onLogout();
        else await logout();
      },
    },
  ];

  return (
    <Menu
      className={`w-full ${className}`}
      side="top"
      align="start"
      items={items}
      trigger={({ props }) => (
        <button
          type="button"
          {...props}
          aria-label={`Account: ${displayName}, ${user.email || ''}. Open account menu`}
          className="flex w-full items-center gap-3 rounded-control px-2 py-2 text-left transition-colors duration-fast hover:bg-elevated/60"
        >
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-fill text-caption font-semibold text-on-accent">
            {initialsOf(displayName)}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-body-sm font-medium text-fg">{displayName}</span>
            <span className="block truncate text-caption text-muted">{user.email}</span>
            {(user.tier || user.role) && (
              <span className="mt-1 flex flex-wrap gap-1">
                {user.tier && <TierBadge tier={user.tier} size="small" />}
                {user.role && <RoleBadge role={user.role} size="small" />}
              </span>
            )}
          </span>
          <ChevronsUpDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
        </button>
      )}
    />
  );
};

UserProfile.propTypes = {
  /** Custom logout handler */
  onLogout: PropTypes.func,
  /** Whether to show the billing dashboard item (paid tiers only) */
  showBilling: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string,
};

export default UserProfile;
