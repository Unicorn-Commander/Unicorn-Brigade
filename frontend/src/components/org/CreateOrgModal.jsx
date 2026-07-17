import { useState } from 'react';
import { Building2, Loader2 } from 'lucide-react';
import Modal from '../ui/Modal';
import Button from '../ui/Button';
import notify from '../../utils/notify';
import useOrg from '../../stores/useOrg';

/**
 * Create a new team organization. On success the store switches into the new
 * org and navigates to its management page, so this modal doesn't self-close on
 * success (the app reloads). Errors keep it open with an inline message.
 */
export default function CreateOrgModal({ isOpen, onClose }) {
  const createOrg = useOrg((s) => s.createOrg);
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const trimmed = name.trim();
  const valid = trimmed.length >= 2 && trimmed.length <= 120;

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await createOrg({ name: trimmed });
      notify.success('Organization created');
      // createOrg navigates to /organization on success; nothing else to do.
    } catch (err) {
      const msg = err?.message || 'Failed to create organization';
      setError(msg);
      notify.error(msg);
      setSubmitting(false);
    }
  };

  const close = () => {
    if (submitting) return;
    setName('');
    setError(null);
    onClose?.();
  };

  return (
    <Modal isOpen={isOpen} onClose={close} title="Create organization" size="md">
      <form onSubmit={handleSubmit} className="p-6 space-y-5">
        <p className="text-sm text-muted">
          Spin up a shared workspace you can invite teammates into. You'll be its
          owner. A URL slug is generated from the name automatically.
        </p>

        <div>
          <label htmlFor="new-org-name" className="block text-sm font-medium text-fg mb-1.5">
            Organization name
          </label>
          <div className="relative">
            <Building2 className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              id="new-org-name"
              data-autofocus
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Robotics"
              maxLength={120}
              className="w-full pl-9 pr-3 py-2.5 bg-card/60 border border-border/60 rounded-lg text-sm text-fg placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500/50 focus:border-unicorn-500/50"
            />
          </div>
          <p className="mt-1.5 text-xs text-muted">At least 2 characters.</p>
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
                Creating…
              </>
            ) : (
              'Create organization'
            )}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
