import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowRight, BarChart3, Check } from 'lucide-react';
import { Button, Chip, Modal } from '../ui';
import { billingService } from '../../services/billingService';

/**
 * PaymentRequiredModal — BR-3.7
 *
 * Mounted once at the app root. Listens for the global `brigade:payment-required`
 * event that api.js dispatches on any 402 response (and that Billing dispatches
 * from its "Choose a plan" button), and turns the backend's credits_remaining +
 * subscription_tier payload into an upgrade path (deep-link into Ops-Center
 * checkout) instead of a dead-end error toast.
 */
export const PAYMENT_REQUIRED_EVENT = 'brigade:payment-required';

/** Open the upgrade dialog from anywhere: `openPaymentRequired({ message, subscription_tier, credits_remaining })`. */
export function openPaymentRequired(detail = {}) {
  window.dispatchEvent(new CustomEvent(PAYMENT_REQUIRED_EVENT, { detail }));
}

const PLANS_URL = 'https://unicorncommander.ai/plans.html';

const fmtCredits = (c) => (c === null || c === undefined ? null : Number(c).toLocaleString());

export default function PaymentRequiredModal() {
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [upgrade, setUpgrade] = useState(null);

  useEffect(() => {
    const onPaymentRequired = (e) => {
      setDetail(e.detail || {});
      setOpen(true);
      // Fetch the real checkout deep-link + benefits (best-effort; falls back to the plans page).
      billingService
        .getUpgradeRequirements()
        .then((info) => setUpgrade(info || null))
        .catch(() => {});
    };
    window.addEventListener(PAYMENT_REQUIRED_EVENT, onPaymentRequired);
    return () => window.removeEventListener(PAYMENT_REQUIRED_EVENT, onPaymentRequired);
  }, []);

  if (!open || !detail) return null;

  const credits = fmtCredits(detail.credits_remaining ?? upgrade?.creditsRemaining);
  const tier = detail.subscription_tier || upgrade?.currentTier || null;
  const noPlan = !tier || detail.reason === 'no-plan';
  const upgradeUrl = upgrade?.upgradeUrl || PLANS_URL;
  const benefits = Array.isArray(upgrade?.benefits) ? upgrade.benefits : [];

  const title = noPlan ? 'Choose a plan' : 'Out of credits';
  const message =
    detail.message ||
    (noPlan
      ? 'This organization has no plan yet. Pick one in Ops-Center and agents can start running.'
      : 'You’re out of credits. Upgrade or add credits to keep agents running.');

  const close = () => setOpen(false);
  const viewUsage = () => {
    close();
    if (location.pathname !== '/billing') navigate('/billing');
  };
  const goUpgrade = () => window.open(upgradeUrl, '_blank', 'noopener');

  return (
    <Modal
      isOpen={open}
      onClose={close}
      title={title}
      description={message}
      footer={
        <>
          <Button variant="ghost" icon={BarChart3} onClick={viewUsage}>
            View usage
          </Button>
          <Button iconRight={ArrowRight} onClick={goUpgrade}>
            {noPlan ? 'Choose a plan' : 'Upgrade'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <dl className="grid grid-cols-2 gap-3 rounded-control border border-border bg-elevated/60 p-4">
          <div>
            <dt className="text-caption text-muted">Current plan</dt>
            <dd className="mt-1">
              {tier ? (
                <Chip tone="accent" className="capitalize">
                  {tier}
                </Chip>
              ) : (
                <Chip>No plan</Chip>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-caption text-muted">Credits remaining</dt>
            <dd className="mt-1 text-lead font-semibold tabular-nums text-fg-strong">
              {credits ?? <span className="text-muted">Not metered</span>}
            </dd>
          </div>
        </dl>
        {benefits.length > 0 && (
          <div>
            <p className="mb-2 text-caption text-muted">
              {upgrade?.requiredTier ? `The ${upgrade.requiredTier} plan includes` : 'A paid plan includes'}
            </p>
            <ul className="space-y-1.5">
              {benefits.map((b) => (
                <li key={b} className="flex items-start gap-2 text-body-sm text-fg">
                  <Check aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-ok" />
                  {b}
                </li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-caption text-muted">Checkout opens in Ops-Center in a new tab.</p>
      </div>
    </Modal>
  );
}
