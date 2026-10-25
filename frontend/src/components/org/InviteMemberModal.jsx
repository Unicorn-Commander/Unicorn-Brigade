import { useEffect, useState } from 'react';
import { Copy, Check, Link2, KeyRound, UserPlus } from 'lucide-react';
import { Button, Field, IconButton, Input, Modal, Select } from '../ui';
import notify from '../../utils/notify';
import { humanize } from '../../utils/errors';
import { createInvitation, ORG_ROLES } from '../../services/orgService';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function CopyRow({ icon: Icon, label, value }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    if (await copyText(value)) {
      setCopied(true);
      notify.success(`${label} copied`);
      setTimeout(() => setCopied(false), 1500);
    } else {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };
  return (
    <div>
      <p className="mb-1 flex items-center gap-1.5 text-caption font-medium text-muted">
        <Icon aria-hidden="true" className="h-3.5 w-3.5" />
        {label}
      </p>
      <div className="flex items-center gap-2">
        <Input readOnly value={value} aria-label={label} className="font-mono text-body-sm" onFocus={(e) => e.target.select()} />
        <IconButton icon={copied ? Check : Copy} label={`Copy ${label.toLowerCase()}`} variant="secondary" onClick={onCopy} />
      </div>
    </div>
  );
}

/**
 * Invite a teammate by email into the active org. Email delivery is a backend
 * stub, so on success the one-time invite link and token are shown for the
 * manager to hand off; the invitee accepts on the Organization page.
 * `initialEmail` / `initialRole` pre-fill it ("Invite again" on a lapsed invite).
 */
export default function InviteMemberModal({ isOpen, onClose, orgId, onCreated, initialEmail = '', initialRole = ORG_ROLES.MEMBER }) {
  const [email, setEmail] = useState(initialEmail);
  const [role, setRole] = useState(initialRole);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setEmail(initialEmail);
      setRole(initialRole);
      setError(null);
      setResult(null);
    }
  }, [isOpen, initialEmail, initialRole]);

  const valid = EMAIL_RE.test(email.trim());

  const reset = () => {
    setEmail('');
    setRole(ORG_ROLES.MEMBER);
    setError(null);
    setResult(null);
    setSubmitting(false);
  };

  const close = () => {
    if (submitting) return;
    reset();
    onClose?.();
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const invite = await createInvitation(orgId, { email: email.trim().toLowerCase(), role });
      setResult(invite);
      notify.success('Invitation created');
      onCreated?.(invite);
    } catch (err) {
      setError(humanize(err, { what: 'creating the invitation' }));
    } finally {
      setSubmitting(false);
    }
  };

  const inviteLink = result?.token ? `${window.location.origin}/organization?invite=${result.token}` : '';

  return (
    <Modal
      isOpen={isOpen}
      onClose={close}
      size="lg"
      title={result ? 'Invitation ready' : 'Invite a teammate'}
      description={
        result
          ? `Share this with ${result.email}. It expires in 7 days.`
          : 'They join this organization once they accept. An organization has one owner, so invites are member or admin.'
      }
      footer={
        result ? (
          <>
            <Button variant="ghost" onClick={reset}>
              Invite another
            </Button>
            <Button onClick={close}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={close} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" form="invite-form" icon={UserPlus} loading={submitting} disabled={!valid}>
              Create invite
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="space-y-4">
          <p className="rounded-control border border-warn/30 bg-warn/10 p-3 text-body-sm text-fg">
            Email delivery isn’t wired yet — hand the link or token to {result.email} directly.
          </p>
          <CopyRow icon={Link2} label="Invite link" value={inviteLink} />
          <CopyRow icon={KeyRound} label="Invite token" value={result.token || ''} />
        </div>
      ) : (
        <form id="invite-form" onSubmit={submit} noValidate className="space-y-4">
          <Field label="Email address" error={error} required>
            <Input
              data-autofocus
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@company.com"
              autoComplete="email"
            />
          </Field>
          <Field label="Role" help="Members can view; admins can also manage members and invitations.">
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value={ORG_ROLES.MEMBER}>Member</option>
              <option value={ORG_ROLES.ADMIN}>Admin</option>
            </Select>
          </Field>
        </form>
      )}
    </Modal>
  );
}
