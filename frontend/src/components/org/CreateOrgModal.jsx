import { useState } from 'react';
import { Building2 } from 'lucide-react';
import { Button, Field, Input, Modal } from '../ui';
import notify from '../../utils/notify';
import { humanize } from '../../utils/errors';
import useOrg from '../../stores/useOrg';

/**
 * Create a team organization. On success the store switches into the new org
 * and lands on its management page (a reload), so the modal only closes itself
 * on cancel; an error keeps it open with the reason under the field.
 */
export default function CreateOrgModal({ isOpen, onClose }) {
  const createOrg = useOrg((s) => s.createOrg);
  const [name, setName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const trimmed = name.trim();
  const valid = trimmed.length >= 2 && trimmed.length <= 120;

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!valid || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await createOrg({ name: trimmed });
      notify.success('Organization created');
    } catch (err) {
      setError(humanize(err, { what: 'creating the organization' }));
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
    <Modal
      isOpen={isOpen}
      onClose={close}
      size="md"
      title="Create organization"
      description="A shared workspace you can invite teammates into. You’ll be its owner; the URL slug comes from the name."
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" form="create-org-form" icon={Building2} loading={submitting} disabled={!valid}>
            Create organization
          </Button>
        </>
      }
    >
      <form id="create-org-form" onSubmit={submit} noValidate>
        <Field label="Organization name" help="At least 2 characters" error={error} required>
          <Input
            data-autofocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Acme Robotics"
            maxLength={120}
            autoComplete="organization"
          />
        </Field>
      </form>
    </Modal>
  );
}
