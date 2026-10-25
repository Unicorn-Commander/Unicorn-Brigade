import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, ChevronsUpDown, Check, Plus, Settings2, RefreshCw } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import useOrg, { useActiveOrg } from '../../stores/useOrg';
import { Menu } from '../ui';
import OrgRoleBadge from './OrgRoleBadge';
import CreateOrgModal from './CreateOrgModal';

/**
 * Active-organization switcher for the sidebar: a ui Menu listing the user's
 * orgs (each with its role chip), the active one checked. Picking another org
 * persists it (sent as X-Org-Id by the API client) and reloads; picking the
 * active one is a no-op. Also links to management and creates a new org.
 */
export default function OrgSwitcher({ className = '' }) {
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { orgs, activeOrgId, loading, loaded, error, loadOrgs, setActiveOrg } = useOrg();
  const activeOrg = useActiveOrg();
  const [showCreate, setShowCreate] = useState(false);
  const navigate = useNavigate();

  // Load once the session resolves; never fire /orgs before it does.
  useEffect(() => {
    if (isAuthenticated && !loaded) loadOrgs();
  }, [isAuthenticated, loaded, loadOrgs]);

  if (loading && !loaded) {
    return <div aria-hidden="true" className={`h-12 animate-pulse rounded-control border border-border bg-elevated/50 ${className}`} />;
  }

  const name = activeOrg?.name || (error ? 'Organizations unavailable' : 'No organization');

  const items = [
    ...orgs.map((org) => ({
      id: org.id,
      icon: org.id === activeOrgId ? Check : Building2,
      label: (
        <span className="flex min-w-0 items-center gap-2">
          <span className="min-w-0 truncate">{org.name}</span>
          {org?.metadata?.personal && <span className="shrink-0 text-micro text-subtle">Personal</span>}
          <OrgRoleBadge role={org.role} size="sm" className="ml-auto" />
        </span>
      ),
      onSelect: () => setActiveOrg(org.id),
    })),
    ...(error && orgs.length === 0
      ? [{ id: 'retry', icon: RefreshCw, label: 'Couldn’t load organizations — retry', onSelect: () => loadOrgs() }]
      : []),
    ...(!error && orgs.length === 0 ? [{ id: 'none', label: 'You’re not in an organization yet', disabled: true }] : []),
    { type: 'separator' },
    { id: 'manage', icon: Settings2, label: 'Manage organization', onSelect: () => navigate('/organization') },
    { id: 'create', icon: Plus, label: 'Create organization', onSelect: () => setShowCreate(true) },
  ];

  return (
    <div className={className}>
      <Menu
        className="w-full"
        align="start"
        items={items}
        trigger={({ props }) => (
          <button
            type="button"
            {...props}
            aria-label={`Organization: ${name}. Switch organization`}
            className="flex min-h-12 w-full items-center gap-3 rounded-control border border-border bg-elevated/40 px-2.5 py-1.5 text-left transition-colors duration-fast hover:border-border-strong hover:bg-elevated/70"
          >
            <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-accent/10 text-accent">
              <Building2 className="h-4 w-4" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-micro font-semibold uppercase tracking-wider text-muted">Organization</span>
              <span className="flex items-center gap-1.5">
                <span className="min-w-0 truncate text-body-sm font-semibold text-fg">{name}</span>
                {activeOrg?.role && <OrgRoleBadge role={activeOrg.role} size="sm" />}
              </span>
            </span>
            <ChevronsUpDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
          </button>
        )}
      />
      <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
