import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Building2,
  Users,
  RefreshCw,
  Pencil,
  Check,
  X as XIcon,
  Trash2,
  Loader2,
  UserPlus,
  Ticket,
  LogIn,
  Eye,
  Mail,
} from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import ListSkeleton from '../components/skeletons/ListSkeleton';
import Button from '../components/ui/Button';
import OrgRoleBadge from '../components/org/OrgRoleBadge';
import InviteMemberModal from '../components/org/InviteMemberModal';
import CreateOrgModal from '../components/org/CreateOrgModal';
import notify from '../utils/notify';
import useOrg, { useActiveOrg } from '../stores/useOrg';
import {
  listMembers,
  listInvitations,
  revokeInvitation,
  updateOrg,
  acceptInvitation,
  canManageOrg,
} from '../services/orgService';

function initials(nameOrEmail = '') {
  const s = String(nameOrEmail).trim();
  if (!s) return '?';
  const parts = s.split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return s.slice(0, 2).toUpperCase();
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString();
}

const INVITE_STATUS = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/40',
  accepted: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40',
  revoked: 'bg-slate-500/15 text-muted border-slate-500/40',
  expired: 'bg-red-500/15 text-red-300 border-red-500/40',
};

/** Small section shell matching the app's glass-panel card look. */
function Panel({ children, className = '' }) {
  return (
    <div
      className={`backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6 ${className}`}
    >
      {children}
    </div>
  );
}

export default function Organization() {
  const { orgs, loaded, loading: orgsLoading, activeOrgId, loadOrgs, setActiveOrg } = useOrg();
  const activeOrg = useActiveOrg();
  const [showCreate, setShowCreate] = useState(false);
  const canManage = canManageOrg(activeOrg?.role);

  // ── org load bootstrap ─────────────────────────────────────────────
  useEffect(() => {
    if (!loaded) loadOrgs();
  }, [loaded, loadOrgs]);

  // ── members ────────────────────────────────────────────────────────
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [membersError, setMembersError] = useState(null);

  const loadMembersList = useCallback(async () => {
    if (!activeOrgId) return;
    setMembersLoading(true);
    setMembersError(null);
    try {
      setMembers(await listMembers(activeOrgId));
    } catch (err) {
      setMembers([]);
      setMembersError(err?.message || 'Failed to load members');
    } finally {
      setMembersLoading(false);
    }
  }, [activeOrgId]);

  // ── invitations (manager-only endpoint) ────────────────────────────
  const [invites, setInvites] = useState([]);
  const [invitesLoading, setInvitesLoading] = useState(false);
  const [invitesError, setInvitesError] = useState(null);

  const loadInvitesList = useCallback(async () => {
    if (!activeOrgId || !canManage) return;
    setInvitesLoading(true);
    setInvitesError(null);
    try {
      setInvites(await listInvitations(activeOrgId));
    } catch (err) {
      setInvites([]);
      setInvitesError(err?.message || 'Failed to load invitations');
    } finally {
      setInvitesLoading(false);
    }
  }, [activeOrgId, canManage]);

  useEffect(() => {
    loadMembersList();
  }, [loadMembersList]);

  useEffect(() => {
    if (canManage) loadInvitesList();
    else {
      setInvites([]);
      setInvitesError(null);
    }
  }, [canManage, loadInvitesList]);

  // ── rename (owner/admin) ───────────────────────────────────────────
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [savingName, setSavingName] = useState(false);

  const startRename = () => {
    setNameDraft(activeOrg?.name || '');
    setRenaming(true);
  };

  const saveName = async () => {
    const name = nameDraft.trim();
    if (name.length < 2 || name.length > 120 || name === activeOrg?.name) {
      setRenaming(false);
      return;
    }
    setSavingName(true);
    try {
      await updateOrg(activeOrgId, { name });
      await loadOrgs();
      notify.success('Organization renamed');
      setRenaming(false);
    } catch (err) {
      notify.error(err?.message || 'Failed to rename organization');
    } finally {
      setSavingName(false);
    }
  };

  // ── invite modal + revoke ──────────────────────────────────────────
  const [showInvite, setShowInvite] = useState(false);
  const [revokingId, setRevokingId] = useState(null);

  const handleRevoke = async (inv) => {
    setRevokingId(inv.id);
    try {
      await revokeInvitation(activeOrgId, inv.id);
      notify.success('Invitation revoked');
      setInvites((prev) =>
        prev.map((i) => (i.id === inv.id ? { ...i, status: 'revoked' } : i))
      );
    } catch (err) {
      notify.error(err?.message || 'Failed to revoke invitation');
    } finally {
      setRevokingId(null);
    }
  };

  // ── accept an invite token (any user) ──────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams();
  const [acceptToken, setAcceptToken] = useState('');
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    const t = searchParams.get('invite');
    if (t) {
      setAcceptToken(t);
      // Clear it from the URL so a refresh doesn't re-trigger / leak the token.
      const next = new URLSearchParams(searchParams);
      next.delete('invite');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAccept = async (e) => {
    e?.preventDefault?.();
    const token = acceptToken.trim();
    if (!token || accepting) return;
    setAccepting(true);
    try {
      const res = await acceptInvitation(token);
      notify.success('Joined organization');
      setAcceptToken('');
      // Land the user inside the org they just joined (persists + reloads).
      if (res?.orgId && res.orgId !== activeOrgId) {
        setActiveOrg(res.orgId);
      } else {
        await loadOrgs();
        await loadMembersList();
      }
    } catch (err) {
      notify.error(err?.message || 'Could not accept this invitation');
    } finally {
      setAccepting(false);
    }
  };

  const refreshAll = () => {
    loadMembersList();
    if (canManage) loadInvitesList();
  };

  const pendingCount = useMemo(
    () => invites.filter((i) => i.status === 'pending').length,
    [invites]
  );

  // ── no-org empty state ─────────────────────────────────────────────
  if (loaded && !orgsLoading && orgs.length === 0) {
    return (
      <div className="min-h-screen p-4 md:p-6 lg:p-8">
        <div className="max-w-4xl mx-auto space-y-6">
          <Breadcrumbs />
          <Panel className="text-center py-16">
            <Building2 className="w-12 h-12 text-unicorn-400 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-fg mb-1">No organization yet</h2>
            <p className="text-muted mb-6">Create one to invite teammates and share your Brigade.</p>
            <div className="flex justify-center">
              <Button variant="primary" onClick={() => setShowCreate(true)}>
                Create organization
              </Button>
            </div>
          </Panel>
        </div>
        <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
      </div>
    );
  }

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <Breadcrumbs />

        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gradient">Organization</h1>
            <p className="text-muted mt-1">Members, roles, and invitations</p>
          </div>
          <button
            onClick={refreshAll}
            disabled={membersLoading || invitesLoading}
            className="px-4 py-2 min-h-[44px] bg-elevated text-muted rounded-lg hover:bg-elevated transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${membersLoading || invitesLoading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Org overview */}
        <Panel>
          <div className="flex items-start gap-4">
            <span className="flex-shrink-0 w-14 h-14 rounded-xl bg-unicorn-500/15 border border-unicorn-500/30 flex items-center justify-center">
              <Building2 className="w-7 h-7 text-unicorn-300" />
            </span>
            <div className="flex-1 min-w-0">
              {renaming ? (
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    value={nameDraft}
                    onChange={(e) => setNameDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveName();
                      if (e.key === 'Escape') setRenaming(false);
                    }}
                    maxLength={120}
                    className="flex-1 min-w-0 px-3 py-1.5 bg-card/60 border border-border/60 rounded-lg text-lg font-bold text-fg focus:outline-none focus:ring-2 focus:ring-unicorn-500/50"
                  />
                  <button
                    onClick={saveName}
                    disabled={savingName}
                    aria-label="Save name"
                    className="p-2 min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg bg-unicorn-600 hover:bg-unicorn-500 text-white transition-colors disabled:opacity-50"
                  >
                    {savingName ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => setRenaming(false)}
                    disabled={savingName}
                    aria-label="Cancel rename"
                    className="p-2 min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg bg-elevated hover:bg-elevated text-muted transition-colors disabled:opacity-50"
                  >
                    <XIcon className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-2xl font-bold text-fg truncate">
                    {activeOrg?.name || 'Organization'}
                  </h2>
                  {activeOrg?.role && <OrgRoleBadge role={activeOrg.role} />}
                  {canManage && activeOrg && (
                    <button
                      onClick={startRename}
                      aria-label="Rename organization"
                      className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-white/5 transition-colors"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                  )}
                </div>
              )}
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                {activeOrg?.slug && (
                  <span>
                    Slug: <code className="text-muted">{activeOrg.slug}</code>
                  </span>
                )}
                {activeOrg?.planTier && (
                  <span className="capitalize">Plan: {activeOrg.planTier}</span>
                )}
                <span>
                  {members.length} member{members.length === 1 ? '' : 's'}
                </span>
              </div>
            </div>
          </div>
        </Panel>

        {/* Members */}
        <Panel>
          <div className="flex items-center justify-between mb-4 gap-4">
            <h2 className="text-xl font-bold text-fg flex items-center gap-2">
              <Users className="w-5 h-5 text-unicorn-400" />
              <span>Members{members.length ? ` (${members.length})` : ''}</span>
            </h2>
            {canManage ? (
              <Button variant="primary" size="sm" onClick={() => setShowInvite(true)}>
                <UserPlus className="w-4 h-4" />
                Invite
              </Button>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs text-muted">
                <Eye className="w-3.5 h-3.5" /> View access
              </span>
            )}
          </div>

          {membersLoading ? (
            <ListSkeleton rows={3} />
          ) : membersError ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-3">{membersError}</p>
              <Button variant="secondary" size="sm" onClick={loadMembersList}>
                Try again
              </Button>
            </div>
          ) : members.length === 0 ? (
            <p className="text-muted text-center py-8">No members yet.</p>
          ) : (
            <ul className="divide-y divide-border/60">
              {members.map((m) => (
                <li key={m.userId} className="flex items-center gap-3 py-3">
                  <span className="flex-shrink-0 w-10 h-10 rounded-full bg-elevated/60 flex items-center justify-center text-sm font-semibold text-fg">
                    {initials(m.name || m.email)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-fg truncate">
                      {m.name || m.email}
                    </p>
                    <p className="text-xs text-muted truncate">
                      {m.name ? m.email : `Joined ${formatDate(m.joinedAt)}`}
                    </p>
                  </div>
                  <OrgRoleBadge role={m.role} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* Invitations — owner/admin only (the list endpoint is manager-gated) */}
        {canManage && (
          <Panel>
            <div className="flex items-center justify-between mb-4 gap-4">
              <h2 className="text-xl font-bold text-fg flex items-center gap-2">
                <Ticket className="w-5 h-5 text-unicorn-400" />
                <span>Invitations{pendingCount ? ` (${pendingCount} pending)` : ''}</span>
              </h2>
              <Button variant="secondary" size="sm" onClick={() => setShowInvite(true)}>
                <Mail className="w-4 h-4" />
                Invite by email
              </Button>
            </div>

            {invitesLoading ? (
              <ListSkeleton rows={2} />
            ) : invitesError ? (
              <div className="text-center py-8">
                <p className="text-red-400 mb-3">{invitesError}</p>
                <Button variant="secondary" size="sm" onClick={loadInvitesList}>
                  Try again
                </Button>
              </div>
            ) : invites.length === 0 ? (
              <p className="text-muted text-center py-8">
                No invitations yet — invite a teammate by email.
              </p>
            ) : (
              <ul className="divide-y divide-border/60">
                {invites.map((inv) => (
                  <li key={inv.id} className="flex items-center gap-3 py-3">
                    <span className="flex-shrink-0 w-10 h-10 rounded-full bg-elevated/60 flex items-center justify-center">
                      <Mail className="w-4 h-4 text-muted" />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-fg truncate">{inv.email}</p>
                      <p className="text-xs text-muted">
                        Invited {formatDate(inv.createdAt)}
                        {inv.status === 'pending' && inv.expiresAt
                          ? ` · expires ${formatDate(inv.expiresAt)}`
                          : ''}
                      </p>
                    </div>
                    <OrgRoleBadge role={inv.role} size="sm" />
                    <span
                      className={`inline-flex items-center rounded-full border text-[11px] px-2 py-0.5 capitalize ${
                        INVITE_STATUS[inv.status] || INVITE_STATUS.revoked
                      }`}
                    >
                      {inv.status}
                    </span>
                    {inv.status === 'pending' && (
                      <button
                        onClick={() => handleRevoke(inv)}
                        disabled={revokingId === inv.id}
                        aria-label={`Revoke invitation for ${inv.email}`}
                        className="p-2 min-h-[40px] min-w-[40px] flex items-center justify-center rounded-lg text-muted hover:text-red-300 hover:bg-red-500/10 transition-colors disabled:opacity-50"
                      >
                        {revokingId === inv.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}

        {/* Join another org by token — available to any user */}
        <Panel>
          <h2 className="text-xl font-bold text-fg flex items-center gap-2 mb-1">
            <LogIn className="w-5 h-5 text-cyan-400" />
            <span>Join an organization</span>
          </h2>
          <p className="text-sm text-muted mb-4">
            Have an invite token or link? Paste the token to join. You'll switch into
            that organization.
          </p>
          <form onSubmit={handleAccept} className="flex flex-col sm:flex-row items-stretch gap-2">
            <input
              type="text"
              value={acceptToken}
              onChange={(e) => setAcceptToken(e.target.value)}
              placeholder="Invite token"
              className="flex-1 min-w-0 px-3 py-2.5 bg-card/60 border border-border/60 rounded-lg text-sm text-fg placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500/50"
            />
            <Button type="submit" variant="primary" disabled={!acceptToken.trim() || accepting}>
              {accepting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Joining…
                </>
              ) : (
                'Join'
              )}
            </Button>
          </form>
        </Panel>
      </div>

      {activeOrgId && (
        <InviteMemberModal
          isOpen={showInvite}
          onClose={() => setShowInvite(false)}
          orgId={activeOrgId}
          onCreated={loadInvitesList}
        />
      )}
      <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
    </div>
  );
}
