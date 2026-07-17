import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, ChevronsUpDown, Check, Plus, Settings2, Loader2 } from 'lucide-react';
import useAuth from '../../hooks/useAuth';
import useOrg, { useActiveOrg } from '../../stores/useOrg';
import OrgRoleBadge from './OrgRoleBadge';
import CreateOrgModal from './CreateOrgModal';

/**
 * Active-organization switcher for the sidebar. Lists the user's orgs, sets the
 * active one (persisted → sent as X-Org-Id by the API client), and links into
 * org management. Accessible menu: button with aria-haspopup/expanded, Escape +
 * click-outside to close, 44px targets.
 */
export default function OrgSwitcher() {
  const isAuthenticated = useAuth((s) => s.isAuthenticated);
  const { orgs, activeOrgId, loading, loaded, error, loadOrgs, setActiveOrg } = useOrg();
  const activeOrg = useActiveOrg();
  const [open, setOpen] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const rootRef = useRef(null);
  const navigate = useNavigate();

  // Load once the user is authenticated (Navigation only renders on protected
  // routes, but gate anyway so we never fire /orgs before the session resolves).
  useEffect(() => {
    if (isAuthenticated && !loaded) loadOrgs();
  }, [isAuthenticated, loaded, loadOrgs]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const pick = (id) => {
    setOpen(false);
    setActiveOrg(id); // no-op + no reload when already active
  };

  const goManage = () => {
    setOpen(false);
    navigate('/organization');
  };

  if (loading && !loaded) {
    return (
      <div className="h-[52px] rounded-lg border border-border/50 bg-elevated/40 animate-pulse" aria-hidden="true" />
    );
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Switch organization"
        className="w-full flex items-center gap-3 min-h-[52px] px-3 py-2 rounded-lg border border-border/60 bg-elevated/40 hover:bg-elevated/70 transition-colors text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-unicorn-500/60"
      >
        <span className="flex-shrink-0 w-9 h-9 rounded-lg bg-unicorn-500/15 border border-unicorn-500/30 flex items-center justify-center">
          <Building2 className="w-[18px] h-[18px] text-unicorn-300" />
        </span>
        <span className="flex-1 min-w-0">
          <span className="block text-[10px] uppercase tracking-wider text-muted font-semibold">
            Organization
          </span>
          <span className="block text-sm font-semibold text-fg truncate">
            {activeOrg?.name || (error ? 'Unavailable' : 'No organization')}
          </span>
        </span>
        <ChevronsUpDown className="flex-shrink-0 w-4 h-4 text-muted" aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Organizations"
          className="absolute left-0 right-0 top-full mt-2 z-50 rounded-xl border border-border/60 bg-surface/95 backdrop-blur-xl shadow-2xl overflow-hidden animate-fade-in"
        >
          <div className="max-h-64 overflow-y-auto p-1.5">
            {error && orgs.length === 0 && (
              <div className="px-3 py-3 text-xs text-red-400">
                {error}
                <button
                  type="button"
                  onClick={() => loadOrgs()}
                  className="mt-1 block text-muted underline hover:text-fg"
                >
                  Retry
                </button>
              </div>
            )}

            {!error && orgs.length === 0 && (
              <p className="px-3 py-3 text-xs text-muted">
                You're not in any organization yet.
              </p>
            )}

            {orgs.map((org) => {
              const isActive = org.id === activeOrgId;
              return (
                <button
                  key={org.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={isActive}
                  onClick={() => pick(org.id)}
                  className={`w-full flex items-center gap-2.5 min-h-[44px] px-2.5 py-2 rounded-lg text-left transition-colors ${
                    isActive ? 'bg-unicorn-500/10' : 'hover:bg-white/5'
                  }`}
                >
                  <span className="flex-shrink-0 w-4 flex justify-center">
                    {isActive ? (
                      <Check className="w-4 h-4 text-unicorn-400" aria-hidden="true" />
                    ) : null}
                  </span>
                  <span className="flex-1 min-w-0">
                    <span className="block text-sm text-fg truncate">{org.name}</span>
                    {org?.metadata?.personal && (
                      <span className="block text-[11px] text-muted">Personal</span>
                    )}
                  </span>
                  <OrgRoleBadge role={org.role} size="sm" />
                </button>
              );
            })}
          </div>

          <div className="border-t border-border/50 p-1.5">
            <button
              type="button"
              role="menuitem"
              onClick={goManage}
              className="w-full flex items-center gap-2.5 min-h-[44px] px-2.5 py-2 rounded-lg text-left text-muted hover:bg-white/5 hover:text-fg transition-colors"
            >
              <Settings2 className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span className="text-sm">Manage organization</span>
            </button>
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                setShowCreate(true);
              }}
              className="w-full flex items-center gap-2.5 min-h-[44px] px-2.5 py-2 rounded-lg text-left text-muted hover:bg-white/5 hover:text-fg transition-colors"
            >
              <Plus className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
              <span className="text-sm">Create organization</span>
            </button>
          </div>
        </div>
      )}

      <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
