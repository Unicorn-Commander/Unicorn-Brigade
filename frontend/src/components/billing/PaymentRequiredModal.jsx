import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, Wallet, BarChart3 } from 'lucide-react';
import Modal from '../ui/Modal';
import { billingService } from '../../services/billingService';

/**
 * PaymentRequiredModal — BR-3.7
 *
 * Mounted once at the app root. Listens for the global `brigade:payment-required`
 * event that api.js dispatches on any 402 response, and turns the backend's
 * credits_remaining + subscription_tier payload into an upgrade path (deep-link
 * into Ops-Center checkout) instead of a dead-end error toast.
 */
export default function PaymentRequiredModal() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState(null);
  const [upgradeUrl, setUpgradeUrl] = useState('https://unicorncommander.ai/plans.html');

  useEffect(() => {
    const onPaymentRequired = (e) => {
      setDetail(e.detail || {});
      setOpen(true);
      // Fetch the real checkout deep-link (best-effort; falls back to plans page).
      billingService
        .getUpgradeRequirements()
        .then((info) => {
          if (info?.upgradeUrl) setUpgradeUrl(info.upgradeUrl);
        })
        .catch(() => {});
    };
    window.addEventListener('brigade:payment-required', onPaymentRequired);
    return () => window.removeEventListener('brigade:payment-required', onPaymentRequired);
  }, []);

  if (!open || !detail) return null;

  const credits = detail.credits_remaining;
  const tier = detail.subscription_tier;
  const message =
    detail.message ||
    "You're out of credits. Upgrade or add credits to keep going.";

  const handleUpgrade = () => {
    window.open(upgradeUrl, '_blank', 'noopener');
  };

  const handleViewUsage = () => {
    setOpen(false);
    navigate('/billing');
  };

  return (
    <Modal
      isOpen={open}
      onClose={() => setOpen(false)}
      ariaLabel="Upgrade required"
      showClose={false}
      panelClassName="relative bg-card border border-border rounded-2xl shadow-2xl max-w-md w-full focus:outline-none"
    >
      <div className="bg-gradient-to-r from-unicorn-600 to-unicorn-500 p-6 rounded-t-2xl text-white">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-white/20 rounded-full">
            <Sparkles size={24} aria-hidden="true" />
          </div>
          <div>
            <h3 className="text-xl font-bold">Out of credits</h3>
            <p className="text-unicorn-100 text-sm mt-1">Upgrade to keep going</p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-4">
        <p className="text-sm text-fg">{message}</p>

        <div className="rounded-lg bg-elevated border border-border p-4 space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-2 text-muted">
              <Wallet size={16} aria-hidden="true" /> Credits remaining
            </span>
            <span className="font-semibold text-fg">
              {credits === null || credits === undefined ? '—' : Number(credits).toLocaleString()}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted">Current plan</span>
            <span className="font-semibold text-fg capitalize">{tier || 'Free'}</span>
          </div>
        </div>
      </div>

      <div className="p-6 pt-0 flex gap-3">
        <button
          onClick={handleViewUsage}
          className="flex-1 px-4 py-2 border border-border text-fg font-medium rounded-lg hover:bg-elevated transition-colors flex items-center justify-center gap-2"
        >
          <BarChart3 size={16} aria-hidden="true" /> View usage
        </button>
        <button
          onClick={handleUpgrade}
          className="flex-1 px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white font-medium rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-all flex items-center justify-center gap-2"
        >
          Upgrade <ArrowRight size={16} aria-hidden="true" />
        </button>
      </div>
    </Modal>
  );
}
