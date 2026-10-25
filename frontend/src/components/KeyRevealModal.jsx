import { useState } from 'react';
import { Check, Copy, ShieldAlert } from 'lucide-react';
import notify from '../utils/notify';
import { Button, Chip, IconButton, Modal } from './ui';

/**
 * KeyRevealModal — the one time a freshly minted key is shown in full.
 * Copy is one click; the dialog does not close on a backdrop click so a stray
 * tap can’t lose the value.
 *
 *   <KeyRevealModal apiKey={created} onClose={…} />
 */
export default function KeyRevealModal({ apiKey, onClose }) {
  const [copied, setCopied] = useState(false);
  const value = apiKey?.key || '';
  const perms = Array.isArray(apiKey?.permissions) ? apiKey.permissions : [];
  const masked = value ? `${value.slice(0, 12)}…` : '';

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      notify.success('Key copied');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access. Select the key and copy it by hand.');
    }
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      closeOnBackdrop={false}
      size="lg"
      title="Save this key now"
      description="This is the only time the full key is shown. Put it in your password manager or secrets store before you close this."
      footer={
        <Button icon={Check} onClick={onClose}>
          I’ve saved it
        </Button>
      }
    >
      <div className="space-y-4">
        <div>
          <p className="mb-1 text-caption text-muted">Key name</p>
          <p className="text-body font-medium text-fg-strong">{apiKey?.name}</p>
        </div>

        <div>
          <p className="mb-1.5 text-caption text-muted">API key</p>
          <div className="flex items-start gap-2 rounded-control border border-border bg-surface p-3">
            <code className="min-w-0 flex-1 break-all font-mono text-body-sm text-accent">{value}</code>
            <IconButton icon={copied ? Check : Copy} label={copied ? 'Copied' : 'Copy key'} size="sm" variant="secondary" onClick={copy} />
          </div>
        </div>

        <dl className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-control border border-border bg-surface/60 p-3">
            <dt className="mb-1 text-caption text-muted">Permissions</dt>
            <dd className="flex flex-wrap gap-1">
              {perms.length ? perms.map((p) => <Chip key={p} size="xs" tone="info">{p}</Chip>) : <span className="text-body-sm text-fg">—</span>}
            </dd>
          </div>
          <div className="rounded-control border border-border bg-surface/60 p-3">
            <dt className="mb-1 text-caption text-muted">Rate limit</dt>
            <dd className="text-body-sm text-fg">{typeof apiKey?.rateLimit === 'number' ? `${apiKey.rateLimit} requests/min` : 'Not set'}</dd>
          </div>
          <div className="rounded-control border border-border bg-surface/60 p-3">
            <dt className="mb-1 text-caption text-muted">Expires</dt>
            <dd className="text-body-sm text-fg">{apiKey?.expiresAt ? new Date(apiKey.expiresAt).toLocaleDateString() : 'Never'}</dd>
          </div>
        </dl>

        <div className="flex items-start gap-2 rounded-control border border-warn/30 bg-warn/10 p-3 text-body-sm text-fg">
          <ShieldAlert aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
          <p>Keep it out of source control and chat. Use an environment variable, and revoke it from the API keys tab if it ever leaks.</p>
        </div>

        <div>
          <p className="mb-1.5 text-caption text-muted">Usage</p>
          <pre className="overflow-x-auto rounded-control border border-border bg-surface p-3 font-mono text-body-sm text-fg">
            {`curl -X POST ${window.location.origin}/api/v1/agents/${apiKey?.agentId || '<agent-id>'}/chat \\
  -H "X-API-Key: ${masked}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Status report"}'`}
          </pre>
        </div>
      </div>
    </Modal>
  );
}
