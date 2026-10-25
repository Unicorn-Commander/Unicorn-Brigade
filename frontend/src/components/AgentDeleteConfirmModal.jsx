import { useState } from 'react';
import { Trash2 } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import { Button, Field, Input, Modal } from './ui';

/**
 * AgentDeleteConfirmModal — spells out what goes with the agent and asks for
 * its id back before DELETE /agents/:id. Reports through
 * onDelete(agent, { optimistic }) with the same rollback contract as the edit
 * dialog.
 */
export default function AgentDeleteConfirmModal({ agent, onClose, onDelete }) {
  const [typed, setTyped] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const name = agent?.displayName || agent?.name;
  const matches = typed.trim() === agent?.name;

  const confirm = async (e) => {
    e?.preventDefault();
    if (!matches) return;
    setDeleting(true);
    setDeleteError(null);
    const rollback = onDelete?.(agent, { optimistic: true });
    try {
      await apiJson(`/agents/${agent.id}`, { method: 'DELETE' });
      notify.success(`${name} deleted`);
      onDelete?.(agent, { optimistic: false });
      onClose?.();
    } catch (err) {
      if (typeof rollback === 'function') rollback();
      setDeleteError(humanize(err, { what: 'deleting the agent' }));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Modal
      isOpen
      onClose={deleting ? undefined : onClose}
      closeOnBackdrop={false}
      tone="danger"
      title={`Delete ${name}?`}
      description="This removes the agent from the brigade. It cannot be undone."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" icon={Trash2} loading={deleting} disabled={!matches} onClick={confirm}>
            Delete agent
          </Button>
        </>
      }
    >
      <form onSubmit={confirm} className="space-y-4">
        <div className="rounded-control border border-danger/30 bg-danger/10 p-3 text-body-sm text-fg">
          <p className="mb-1.5 font-medium">Deleting also removes:</p>
          <ul className="list-disc space-y-0.5 pl-5 text-muted">
            <li>its configuration, persona and system prompt</li>
            <li>conversations with it in your history</li>
            <li>API keys issued for it — anything still calling them stops</li>
          </ul>
        </div>
        <Field label={`Type ${agent?.name} to confirm`} required>
          <Input value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={agent?.name} autoFocus disabled={deleting} className="font-mono" autoComplete="off" />
        </Field>
        {deleteError && (
          <p role="alert" className="text-body-sm text-danger">
            {deleteError}
          </p>
        )}
        <button type="submit" className="sr-only" tabIndex={-1} aria-hidden="true">
          Delete
        </button>
      </form>
    </Modal>
  );
}
