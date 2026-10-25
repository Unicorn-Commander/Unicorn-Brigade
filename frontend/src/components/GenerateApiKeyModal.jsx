import { useState } from 'react';
import { Key } from 'lucide-react';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import { Button, Field, Input, Modal, Select } from './ui';

const PERMISSIONS = [
  { id: 'read', label: 'Read agent details', description: 'View configuration and status' },
  { id: 'invoke', label: 'Invoke agent', description: 'Send messages and run tasks' },
  { id: 'modify', label: 'Modify agent', description: 'Change configuration and settings' },
];

const EXPIRY = [
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
  { value: '365', label: '1 year' },
  { value: '', label: 'Never (not recommended)' },
];

/**
 * GenerateApiKeyModal — mint a key for one agent. Validates inline, posts to
 * /agents/:id/api-keys and hands the created key (with its one-time value)
 * to onSuccess, where KeyRevealModal shows it.
 */
export default function GenerateApiKeyModal({ agentId, onSuccess, onClose }) {
  const [form, setForm] = useState({ name: '', permissions: ['read', 'invoke'], rateLimit: 100, expiresInDays: '90' });
  const [errors, setErrors] = useState({});
  const [submitError, setSubmitError] = useState(null);
  const [loading, setLoading] = useState(false);

  const set = (patch) => {
    setForm((f) => ({ ...f, ...patch }));
    setErrors((e) => ({ ...e, ...Object.fromEntries(Object.keys(patch).map((k) => [k, undefined])) }));
  };

  const validate = () => {
    const next = {};
    if (!form.name.trim()) next.name = 'Give the key a name so you can tell it apart later.';
    if (!form.permissions.length) next.permissions = 'Pick at least one permission.';
    if (!form.rateLimit || form.rateLimit < 1) next.rateLimit = 'At least 1 request per minute.';
    setErrors(next);
    return !Object.keys(next).length;
  };

  const submit = async (e) => {
    e?.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setSubmitError(null);
    try {
      const days = form.expiresInDays ? parseInt(form.expiresInDays, 10) : null;
      const expiresAt = days ? new Date(Date.now() + days * 86400000).toISOString() : null;
      const data = await apiJson(`/agents/${agentId}/api-keys`, {
        method: 'POST',
        body: JSON.stringify({
          name: form.name.trim(),
          permissions: form.permissions,
          rateLimit: form.rateLimit,
          expiresAt,
          expiresInDays: days,
        }),
      });
      onSuccess?.(data);
    } catch (err) {
      setSubmitError(humanize(err, { what: 'generating the key' }));
    } finally {
      setLoading(false);
    }
  };

  const togglePermission = (id) =>
    set({ permissions: form.permissions.includes(id) ? form.permissions.filter((p) => p !== id) : [...form.permissions, id] });

  return (
    <Modal
      isOpen
      onClose={loading ? undefined : onClose}
      closeOnBackdrop={false}
      title="Generate an API key"
      description="Credentials for an external system to call this agent. The full key is shown once, after it is created."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button icon={Key} loading={loading} onClick={submit} disabled={!form.name.trim()}>
            Generate key
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-5">
        <Field label="Key name" required error={errors.name} help="Where it will be used, e.g. “Stable bridge” or “Zapier”.">
          <Input value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="Production integration" autoFocus disabled={loading} />
        </Field>

        <fieldset>
          <legend className="mb-1.5 text-body-sm font-medium text-fg">
            Permissions
            <span aria-hidden="true" className="ml-0.5 text-danger">
              *
            </span>
          </legend>
          <ul className="space-y-2">
            {PERMISSIONS.map((perm) => (
              <li key={perm.id}>
                <label className="flex min-h-touch cursor-pointer items-start gap-3 rounded-control border border-border bg-surface/60 p-3 transition-colors duration-fast hover:border-border-strong">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
                    checked={form.permissions.includes(perm.id)}
                    onChange={() => togglePermission(perm.id)}
                    disabled={loading}
                  />
                  <span>
                    <span className="block text-body font-medium text-fg">{perm.label}</span>
                    <span className="block text-caption text-muted">{perm.description}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {errors.permissions && (
            <p role="alert" className="mt-1.5 text-caption text-danger">
              {errors.permissions}
            </p>
          )}
        </fieldset>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Rate limit" help="Requests per minute" error={errors.rateLimit}>
            <Input
              type="number"
              min={1}
              value={form.rateLimit}
              onChange={(e) => set({ rateLimit: parseInt(e.target.value, 10) || 0 })}
              disabled={loading}
            />
          </Field>
          <Field label="Expires" help="You can revoke it at any time.">
            <Select value={form.expiresInDays} onChange={(e) => set({ expiresInDays: e.target.value })} disabled={loading}>
              {EXPIRY.map((o) => (
                <option key={o.value || 'never'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </Field>
        </div>

        {submitError && (
          <p role="alert" className="text-body-sm text-danger">
            {submitError}
          </p>
        )}
        <button type="submit" className="sr-only" tabIndex={-1} aria-hidden="true">
          Submit
        </button>
      </form>
    </Modal>
  );
}
