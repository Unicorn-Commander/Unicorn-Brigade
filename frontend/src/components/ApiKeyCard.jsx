import { useState } from 'react';
import { Key, Trash2 } from 'lucide-react';
import { Button, Card, Chip, Modal } from './ui';

const fmtDate = (s) => (s ? new Date(s).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }) : null);
const fmtAgo = (s) => {
  if (!s) return 'never';
  const mins = Math.floor((Date.now() - new Date(s).getTime()) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} d ago`;
  return fmtDate(s);
};

/**
 * ApiKeyCard — one issued key: name, prefix, status, when it was used, what it
 * may do. The full value is never shown here (only KeyRevealModal, once).
 * Revoking asks in a danger dialog that spells out the consequence.
 *
 *   <ApiKeyCard apiKey={key} onRevoke={async (key) => …} />
 */
export default function ApiKeyCard({ apiKey, onRevoke }) {
  const [confirming, setConfirming] = useState(false);
  const [revoking, setRevoking] = useState(false);

  const expired = Boolean(apiKey.expiresAt) && new Date(apiKey.expiresAt) < new Date();
  const active = (apiKey.isActive ?? true) && !expired;
  const statusLabel = active ? 'Active' : expired ? 'Expired' : 'Revoked';
  const perms = Array.isArray(apiKey.permissions) ? apiKey.permissions : [];

  const confirm = async () => {
    setRevoking(true);
    try {
      await onRevoke?.(apiKey);
      setConfirming(false);
    } finally {
      setRevoking(false);
    }
  };

  return (
    <Card padding="sm">
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-elevated text-muted">
          <Key className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="truncate text-body font-semibold text-fg-strong">{apiKey.name}</h4>
            <Chip tone={active ? 'ok' : 'neutral'} size="xs" dot>
              {statusLabel}
            </Chip>
          </div>
          <code className="mt-0.5 block font-mono text-body-sm text-muted">{apiKey.keyPrefix || '····'}…</code>
          <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-caption text-muted">
            {apiKey.createdAt && (
              <div>
                <dt className="inline">Created </dt>
                <dd className="inline text-fg">{fmtDate(apiKey.createdAt)}</dd>
              </div>
            )}
            <div>
              <dt className="inline">Last used </dt>
              <dd className="inline text-fg">{fmtAgo(apiKey.lastUsedAt)}</dd>
            </div>
            {apiKey.expiresAt && (
              <div>
                <dt className="inline">{expired ? 'Expired ' : 'Expires '}</dt>
                <dd className={`inline ${expired ? 'text-danger' : 'text-fg'}`}>{fmtDate(apiKey.expiresAt)}</dd>
              </div>
            )}
            {typeof apiKey.rateLimit === 'number' && (
              <div>
                <dt className="inline">Rate limit </dt>
                <dd className="inline text-fg">{apiKey.rateLimit}/min</dd>
              </div>
            )}
            {typeof apiKey.usageCount === 'number' && (
              <div>
                <dt className="inline">Calls </dt>
                <dd className="inline text-fg tabular-nums">{apiKey.usageCount.toLocaleString()}</dd>
              </div>
            )}
          </dl>
          {perms.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1" aria-label="Permissions">
              {perms.map((perm) => (
                <li key={perm}>
                  <Chip size="xs" tone="info">
                    {perm}
                  </Chip>
                </li>
              ))}
            </ul>
          )}
        </div>
        {onRevoke && active && (
          <Button variant="ghost" size="sm" icon={Trash2} onClick={() => setConfirming(true)}>
            Revoke
          </Button>
        )}
      </div>

      <Modal
        isOpen={confirming}
        onClose={() => !revoking && setConfirming(false)}
        tone="danger"
        size="sm"
        title={`Revoke “${apiKey.name}”?`}
        description="Anything still calling with this key stops working immediately. This can’t be undone."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirming(false)} disabled={revoking}>
              Keep it
            </Button>
            <Button variant="danger" icon={Trash2} loading={revoking} onClick={confirm}>
              Revoke key
            </Button>
          </>
        }
      />
    </Card>
  );
}
