/**
 * Organization — the active org: name, your role, members, invitations and
 * joining by token. Management actions appear only where the API supports them
 * (rename, invite, revoke, invite again); the backend has no member role change
 * or removal yet, so the members table has no action menu.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Building2, Users, RefreshCw, Pencil, Trash2, UserPlus, Ticket, LogIn, Mail, RotateCw } from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import OrgRoleBadge from '../components/org/OrgRoleBadge';
import InviteMemberModal from '../components/org/InviteMemberModal';
import CreateOrgModal from '../components/org/CreateOrgModal';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import useOrg, { useActiveOrg } from '../stores/useOrg';
import { listMembers, listInvitations, revokeInvitation, updateOrg, acceptInvitation, canManageOrg } from '../services/orgService';
import {
  Button,
  Card,
  Chip,
  DataTable,
  Field,
  IconButton,
  Input,
  Modal,
  Page,
  PageHeader,
  SectionHeader,
  EmptyState,
  ErrorState,
  LoadingState,
} from '../components/ui';

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

const INVITE_CHIP = {
  pending: { tone: 'warn', label: 'Pending' },
  accepted: { tone: 'ok', label: 'Accepted' },
  revoked: { tone: 'neutral', label: 'Revoked' },
  expired: { tone: 'danger', label: 'Expired' },
};

export default function Organization() {
  const { orgs, loaded, loading: orgsLoading, error: orgsError, activeOrgId, loadOrgs, setActiveOrg } = useOrg();
  const activeOrg = useActiveOrg();
  const canManage = canManageOrg(activeOrg?.role);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (!loaded) loadOrgs();
  }, [loaded, loadOrgs]);

  // ── members ──────────────────────────────────────────────────────────────
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError] = useState(null);

  const loadMembers = useCallback(async () => {
    if (!activeOrgId) return;
    setMembersLoading(true);
    setMembersError(null);
    try {
      setMembers(await listMembers(activeOrgId));
    } catch (err) {
      setMembers([]);
      setMembersError(err);
    } finally {
      setMembersLoading(false);
    }
  }, [activeOrgId]);

  // ── invitations (owner/admin only) ───────────────────────────────────────
  const [invites, setInvites] = useState([]);
  const [invitesLoading, setInvitesLoading] = useState(false);
  const [invitesError, setInvitesError] = useState(null);

  const loadInvites = useCallback(async () => {
    if (!activeOrgId || !canManage) return;
    setInvitesLoading(true);
    setInvitesError(null);
    try {
      setInvites(await listInvitations(activeOrgId));
    } catch (err) {
      setInvites([]);
      setInvitesError(err);
    } finally {
      setInvitesLoading(false);
    }
  }, [activeOrgId, canManage]);

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  useEffect(() => {
    if (canManage) loadInvites();
    else {
      setInvites([]);
      setInvitesError(null);
    }
  }, [canManage, loadInvites]);

  // ── rename ───────────────────────────────────────────────────────────────
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [nameError, setNameError] = useState(null);
  const [savingName, setSavingName] = useState(false);
  const nameValid = nameDraft.trim().length >= 2 && nameDraft.trim().length <= 120;

  const openRename = () => {
    setNameDraft(activeOrg?.name || '');
    setNameError(null);
    setRenaming(true);
  };
  const saveName = async (e) => {
    e?.preventDefault?.();
    const name = nameDraft.trim();
    if (!nameValid || savingName) return;
    if (name === activeOrg?.name) {
      setRenaming(false);
      return;
    }
    setSavingName(true);
    setNameError(null);
    try {
      await updateOrg(activeOrgId, { name });
      await loadOrgs();
      notify.success('Organization renamed');
      setRenaming(false);
    } catch (err) {
      setNameError(humanize(err, { what: 'renaming the organization' }));
    } finally {
      setSavingName(false);
    }
  };

  // ── invite / invite again / revoke ───────────────────────────────────────
  const [invite, setInvite] = useState(null); // { email, role } while the invite modal is open
  const [revoking, setRevoking] = useState(null); // the invitation awaiting confirmation
  const [revokeBusy, setRevokeBusy] = useState(false);

  const confirmRevoke = async () => {
    if (!revoking) return;
    setRevokeBusy(true);
    try {
      await revokeInvitation(activeOrgId, revoking.id);
      notify.success(`Invitation for ${revoking.email} revoked`);
      setInvites((prev) => prev.map((i) => (i.id === revoking.id ? { ...i, status: 'revoked' } : i)));
      setRevoking(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'revoking the invitation' }));
    } finally {
      setRevokeBusy(false);
    }
  };

  // ── accept an invite token ───────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams();
  const [acceptToken, setAcceptToken] = useState('');
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState(null);

  useEffect(() => {
    const t = searchParams.get('invite');
    if (t) {
      setAcceptToken(t);
      // Clear it from the URL so a refresh doesn't re-trigger or leak the token.
      const next = new URLSearchParams(searchParams);
      next.delete('invite');
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const accept = async (e) => {
    e?.preventDefault?.();
    const token = acceptToken.trim();
    if (!token || accepting) return;
    setAccepting(true);
    setAcceptError(null);
    try {
      const res = await acceptInvitation(token);
      notify.success('Joined the organization');
      setAcceptToken('');
      if (res?.orgId && res.orgId !== activeOrgId) setActiveOrg(res.orgId);
      else {
        await loadOrgs();
        await loadMembers();
      }
    } catch (err) {
      setAcceptError(humanize(err, { what: 'accepting the invitation' }));
    } finally {
      setAccepting(false);
    }
  };

  const refreshAll = () => {
    loadMembers();
    if (canManage) loadInvites();
  };

  const pendingCount = useMemo(() => invites.filter((i) => i.status === 'pending').length, [invites]);

  const memberColumns = [
    {
      key: 'member',
      label: 'Member',
      render: (m) => (
        <span className="flex items-center gap-3">
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-elevated text-caption font-semibold text-fg">
            {initials(m.name || m.email)}
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium text-fg">{m.name || m.email}</span>
            {m.name && <span className="block truncate text-caption text-muted">{m.email}</span>}
          </span>
        </span>
      ),
    },
    { key: 'role', label: 'Role', render: (m) => <OrgRoleBadge role={m.role} /> },
    { key: 'joinedAt', label: 'Joined', render: (m) => formatDate(m.joinedAt), align: 'right' },
  ];

  const inviteColumns = [
    {
      key: 'email',
      label: 'Invitee',
      render: (inv) => (
        <span className="flex items-center gap-3">
          <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-elevated text-muted">
            <Mail className="h-4 w-4" />
          </span>
          <span className="min-w-0">
            <span className="block truncate font-medium text-fg">{inv.email}</span>
            <span className="block text-caption text-muted">
              Invited {formatDate(inv.createdAt)}
              {inv.status === 'pending' && inv.expiresAt ? ` · expires ${formatDate(inv.expiresAt)}` : ''}
            </span>
          </span>
        </span>
      ),
    },
    { key: 'role', label: 'Role', render: (inv) => <OrgRoleBadge role={inv.role} size="sm" /> },
    {
      key: 'status',
      label: 'Status',
      render: (inv) => {
        const c = INVITE_CHIP[inv.status] || INVITE_CHIP.revoked;
        return (
          <Chip tone={c.tone} size="xs" dot>
            {c.label}
          </Chip>
        );
      },
    },
    {
      key: 'actions',
      label: 'Actions',
      align: 'right',
      render: (inv) =>
        inv.status === 'pending' ? (
          <IconButton icon={Trash2} label={`Revoke the invitation for ${inv.email}`} size="sm" onClick={() => setRevoking(inv)} />
        ) : inv.status === 'accepted' ? (
          <span className="text-caption text-subtle">Joined</span>
        ) : (
          <Button variant="ghost" size="xs" icon={RotateCw} onClick={() => setInvite({ email: inv.email, role: inv.role })}>
            Invite again
          </Button>
        ),
    },
  ];

  // ── states: loading orgs, no org, the org ────────────────────────────────
  if (!loaded || (orgsLoading && !orgs.length)) {
    return (
      <Page width="wide">
        <PageHeader breadcrumbs={<Breadcrumbs />} eyebrow="System" title="Organization" description="Members, roles and invitations" />
        <LoadingState variant="table" label="Loading organization" />
      </Page>
    );
  }

  if (orgs.length === 0 && orgsError) {
    return (
      <Page width="wide">
        <PageHeader breadcrumbs={<Breadcrumbs />} eyebrow="System" title="Organization" description="Members, roles and invitations" />
        <ErrorState title="Couldn’t load your organizations" detail={humanize(orgsError, { what: 'loading your organizations' })} onRetry={() => loadOrgs()} />
      </Page>
    );
  }

  if (orgs.length === 0) {
    return (
      <Page width="wide">
        <PageHeader breadcrumbs={<Breadcrumbs />} eyebrow="System" title="Organization" description="Members, roles and invitations" />
        <EmptyState
          icon={Building2}
          title="No organization yet"
          description="Create one to invite teammates and share your Brigade."
          action={
            <Button icon={Building2} onClick={() => setShowCreate(true)}>
              Create organization
            </Button>
          }
        />
        <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
      </Page>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="System"
        icon={Building2}
        title={
          <span className="inline-flex flex-wrap items-center gap-2">
            {activeOrg?.name || 'Organization'}
            {activeOrg?.role && <OrgRoleBadge role={activeOrg.role} />}
          </span>
        }
        description={[
          activeOrg?.slug ? activeOrg.slug : null,
          activeOrg?.planTier ? `${activeOrg.planTier} plan` : null,
          `${members.length} member${members.length === 1 ? '' : 's'}`,
        ]
          .filter(Boolean)
          .join(' · ')}
        actions={
          <>
            <IconButton icon={RefreshCw} label="Refresh" variant="secondary" loading={membersLoading || invitesLoading} onClick={refreshAll} />
            {canManage && (
              <Button variant="outline" icon={Pencil} onClick={openRename}>
                Edit
              </Button>
            )}
            {canManage && (
              <Button icon={UserPlus} onClick={() => setInvite({ email: '', role: 'member' })}>
                Invite
              </Button>
            )}
          </>
        }
      />

      <div className="space-y-8">
        <section>
          <SectionHeader
            title={`Members${members.length ? ` (${members.length})` : ''}`}
            description={canManage ? 'Owners and admins can invite; roles are set when inviting.' : 'You have view access to this organization.'}
          />
          <DataTable
            columns={memberColumns}
            rows={members}
            rowKey="userId"
            caption="Members"
            loading={membersLoading}
            error={membersError && { title: 'Couldn’t load members', detail: humanize(membersError, { what: 'loading members' }), onRetry: loadMembers }}
            empty={{ icon: Users, title: 'No members yet', description: canManage ? 'Invite a teammate and they appear here once they accept.' : 'Members appear here once they join.' }}
          />
        </section>

        {canManage && (
          <section>
            <SectionHeader
              title={`Invitations${pendingCount ? ` (${pendingCount} pending)` : ''}`}
              description="Email delivery isn’t wired yet: hand the link or token to the invitee."
              actions={
                <Button variant="secondary" size="sm" icon={Mail} onClick={() => setInvite({ email: '', role: 'member' })}>
                  Invite by email
                </Button>
              }
            />
            <DataTable
              columns={inviteColumns}
              rows={invites}
              rowKey="id"
              caption="Invitations"
              loading={invitesLoading}
              error={invitesError && { title: 'Couldn’t load invitations', detail: humanize(invitesError, { what: 'loading invitations' }), onRetry: loadInvites }}
              empty={{
                icon: Ticket,
                title: 'No invitations yet',
                description: 'Invite a teammate by email and the invitation shows up here.',
                action: (
                  <Button size="sm" icon={UserPlus} onClick={() => setInvite({ email: '', role: 'member' })}>
                    Invite a teammate
                  </Button>
                ),
              }}
            />
          </section>
        )}

        <section>
          <SectionHeader title="Join an organization" description="Have an invite link or token? Paste the token to join; you’ll switch into that organization." />
          <Card>
            <form onSubmit={accept} className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Invite token" error={acceptError} className="flex-1">
                <Input value={acceptToken} onChange={(e) => setAcceptToken(e.target.value)} placeholder="inv_…" autoComplete="off" spellCheck={false} />
              </Field>
              <Button type="submit" icon={LogIn} loading={accepting} disabled={!acceptToken.trim()}>
                Join
              </Button>
            </form>
          </Card>
        </section>
      </div>

      {/* Rename */}
      <Modal
        isOpen={renaming}
        onClose={() => !savingName && setRenaming(false)}
        size="md"
        title="Rename organization"
        description="The URL slug stays the same."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRenaming(false)} disabled={savingName}>
              Cancel
            </Button>
            <Button type="submit" form="rename-org-form" loading={savingName} disabled={!nameValid}>
              Save
            </Button>
          </>
        }
      >
        <form id="rename-org-form" onSubmit={saveName} noValidate>
          <Field label="Organization name" help="2 to 120 characters" error={nameError} required>
            <Input data-autofocus value={nameDraft} onChange={(e) => setNameDraft(e.target.value)} maxLength={120} />
          </Field>
        </form>
      </Modal>

      {/* Revoke — destructive, so it confirms */}
      <Modal
        isOpen={Boolean(revoking)}
        onClose={() => !revokeBusy && setRevoking(null)}
        size="sm"
        tone="danger"
        title="Revoke this invitation?"
        description={revoking ? `${revoking.email} won’t be able to join with this link. You can invite them again later.` : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRevoking(null)} disabled={revokeBusy}>
              Keep it
            </Button>
            <Button variant="danger" icon={Trash2} loading={revokeBusy} onClick={confirmRevoke}>
              Revoke
            </Button>
          </>
        }
      />

      {activeOrgId && (
        <InviteMemberModal
          isOpen={Boolean(invite)}
          onClose={() => setInvite(null)}
          orgId={activeOrgId}
          onCreated={loadInvites}
          initialEmail={invite?.email || ''}
          initialRole={invite?.role || 'member'}
        />
      )}
      <CreateOrgModal isOpen={showCreate} onClose={() => setShowCreate(false)} />
    </Page>
  );
}
