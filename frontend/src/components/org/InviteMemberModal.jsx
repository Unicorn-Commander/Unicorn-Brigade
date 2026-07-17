import { useState } from 'react';
import { Mail, Loader2, Copy, Check, Link2, KeyRound } from 'lucide-react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import notify from '../../utils/notify';
import { createInvitation, ORG_ROLES } from '../../services/orgService';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

async function copyText(text) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to the legacy path */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

function CopyRow({ icon: Icon, label, value }) {
  const [copied, setCopied] = useState(false);
  const onCopy = async () => {
    const ok = await copyText(value);
    if (ok) {
      setCopied(true);
      notify.success(`${label} copied`);
      setTimeout(() => setCopied(false), 1500);
    } else {
      notify.error(`Could not copy ${label.toLowerCase()}`);
    }
  };
  return (
    <div>
      <div className="flex items-center gap-2 text-xs font-medium text-muted mb-1">
        <Icon className="w-3.5 h-3.5" aria-hidden="true" />
        {label}
      </div>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 min-w-0 truncate px-3 py-2 bg-bg/60 border border-border/60 rounded-lg text-xs text-fg font-mono">
          {value}
        </code>
        <button
          type="button"
          onClick={onCopy}
          aria-label={`Copy ${label.toLowerCase()}`}
          className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 min-h-[40px] rounded-lg bg-elevated/60 border border-border/60 text-fg hover:bg-elevated/60 transition-colors text-xs font-medium"
        >
          {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  );
}

/**
 * Invite a teammate by email into the active org. Email delivery is a backend
 * stub in BR-2.1, so on success we surface the one-time invite token + a link
 * for the manager to hand off out-of-band (the invitee accepts it on the
 * Organization page). `onCreated` refreshes the pending-invites list.
 */
export default function InviteMemberModal({ isOpen, onClose, orgId, onCreated }) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState(ORG_ROLES.MEMBER);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null); // the created invitation (incl. token)

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

  const handleSubmit = async (e) => {
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
      const msg = err?.message || 'Failed to create invitation';
      setError(msg);
      notify.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const inviteLink = result?.token
    ? `${window.location.origin}/organization?invite=${result.token}`
    : '';

  return (
    <Modal isOpen={isOpen} onClose={close} title="Invite a teammate" size="lg">
      {!result ? (
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <p className="text-sm text-muted">
            They'll join this organization once they accept. Owners can't be
            invited — an org has a single owner.
          </p>

          <div>
            <label htmlFor="invite-email" className="block text-sm font-medium text-fg mb-1.5">
              Email address
            </label>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
              <input
                id="invite-email"
                data-autofocus
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="teammate@company.com"
                className="w-full pl-9 pr-3 py-2.5 bg-card/60 border border-border/60 rounded-lg text-sm text-fg placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500/50 focus:border-unicorn-500/50"
              />
            </div>
          </div>

          <div>
            <label htmlFor="invite-role" className="block text-sm font-medium text-fg mb-1.5">
              Role
            </label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="w-full px-3 py-2.5 bg-card/60 border border-border/60 rounded-lg text-sm text-fg focus:outline-none focus:ring-2 focus:ring-unicorn-500/50 focus:border-unicorn-500/50"
            >
              <option value={ORG_ROLES.MEMBER}>Member — can view</option>
              <option value={ORG_ROLES.ADMIN}>Admin — can manage members &amp; invites</option>
            </select>
          </div>

          {error && (
            <p className="text-sm text-red-400" role="alert">
              {error}
            </p>
          )}

          <div className="flex items-center justify-end gap-3 pt-1">
            <Button type="button" variant="secondary" onClick={close} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={!valid || submitting}>
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Sending…
                </>
              ) : (
                'Create invite'
              )}
            </Button>
          </div>
        </form>
      ) : (
        <div className="p-6 space-y-5">
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
            Email delivery isn't wired yet — share this invite link or token with{' '}
            <span className="font-medium text-amber-100">{result.email}</span> directly.
            It expires in 7 days.
          </div>

          <CopyRow icon={Link2} label="Invite link" value={inviteLink} />
          <CopyRow icon={KeyRound} label="Invite token" value={result.token} />

          <div className="flex items-center justify-end gap-3 pt-1">
            <Button type="button" variant="secondary" onClick={reset}>
              Invite another
            </Button>
            <Button type="button" variant="primary" onClick={close}>
              Done
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
