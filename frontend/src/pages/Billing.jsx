import React, { useEffect, useState } from 'react';
import { DollarSign, Cpu, Activity, Wallet, ArrowRight, AlertTriangle, RefreshCw } from 'lucide-react';
import StatCard from '../components/ui/StatCard';
import Card from '../components/ui/Card';
import { billingService } from '../services/billingService';

const fmtCost = (c) => `$${Number(c || 0).toFixed(4)}`;
const fmtNum = (n) => Number(n || 0).toLocaleString();
const fmtDate = (iso) => {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
};

/**
 * Billing.jsx — BR-3.7
 * Per-org usage / spend page: this period's cost, tokens, events, credits, the
 * effective monthly cap (with a progress bar + over-cap warning), and the most
 * recent metered events. Data comes from GET /api/v1/billing/usage (RLS-scoped
 * to the caller's own org).
 */
export default function Billing() {
  const [usage, setUsage] = useState(null);
  const [upgrade, setUpgrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, up] = await Promise.all([
        billingService.getUsage(50),
        billingService.getUpgradeRequirements().catch(() => null),
      ]);
      setUsage(u);
      setUpgrade(up);
    } catch (e) {
      setError('Could not load usage. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const period = usage?.period || {};
  const cap = usage?.cap || {};
  const billing = usage?.billing || {};
  const recent = usage?.recent || [];
  const overCap = usage?.over_cap;

  const tokenCap = cap.monthly_token_cap;
  const costCap = cap.monthly_cost_cap;
  const tokenPct = tokenCap ? Math.min(100, (Number(period.tokens || 0) / tokenCap) * 100) : null;
  const costPct = costCap ? Math.min(100, (Number(period.cost || 0) / costCap) * 100) : null;

  const upgradeUrl = upgrade?.upgradeUrl || 'https://unicorncommander.ai/plans.html';
  const credits = billing.credits_remaining;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-fg">Usage &amp; Billing</h1>
          <p className="text-sm text-muted mt-1">
            Your organization's spend this billing period.
            {usage?.period?.since && (
              <span className="ml-1">Since {fmtDate(usage.period.since)}.</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2.5 py-1 rounded-full bg-elevated border border-border text-fg capitalize">
            {billing.subscription_tier || 'Free'} plan
          </span>
          <button
            onClick={load}
            className="p-2 rounded-lg border border-border text-muted hover:text-fg hover:bg-elevated transition-colors"
            aria-label="Refresh usage"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <Card className="p-4 border-red-500/40">
          <p className="text-sm text-red-300">{error}</p>
        </Card>
      )}

      {overCap && (
        <Card className="p-4 border-amber-500/50 bg-amber-500/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <div className="flex-1">
              <p className="text-sm font-medium text-fg">Monthly cap reached</p>
              <p className="text-sm text-muted mt-1">{usage?.over_cap_reason || 'Your organization is over its monthly usage ceiling.'}</p>
            </div>
            <a href={upgradeUrl} target="_blank" rel="noopener noreferrer"
               className="flex-shrink-0 inline-flex items-center gap-1 px-4 py-2 bg-unicorn-600 text-white text-sm font-medium rounded-lg hover:bg-unicorn-500 transition-colors">
              Upgrade <ArrowRight size={14} />
            </a>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard icon={DollarSign} label="Spend this period" value={fmtCost(period.cost)} />
        <StatCard icon={Cpu} label="Tokens used" value={fmtNum(period.tokens)} />
        <StatCard icon={Activity} label="Metered events" value={fmtNum(period.events)} />
        <StatCard
          icon={Wallet}
          label="Credits remaining"
          value={credits === null || credits === undefined ? '—' : fmtNum(credits)}
          tone={credits !== null && credits !== undefined && Number(credits) <= 0 ? 'bad' : 'neutral'}
        />
      </div>

      {(tokenCap || costCap) ? (
        <Card className="p-6 space-y-4">
          <h2 className="text-lg font-semibold text-fg">Monthly limit</h2>
          {tokenCap && (
            <CapBar label="Tokens" used={period.tokens} cap={tokenCap} pct={tokenPct} fmt={fmtNum} />
          )}
          {costCap && (
            <CapBar label="Cost" used={period.cost} cap={costCap} pct={costPct} fmt={fmtCost} />
          )}
          <p className="text-xs text-muted">
            Cap source: {cap.source === 'config' ? 'organization configuration' : 'default'}.
            {cap.hard_stop === false && ' Soft limit (not enforced).'}
          </p>
        </Card>
      ) : (
        <Card className="p-6">
          <p className="text-sm text-muted">No monthly usage cap is set for your organization.</p>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="p-6 pb-3">
          <h2 className="text-lg font-semibold text-fg">Recent activity</h2>
          <p className="text-sm text-muted mt-1">The latest metered events for your organization.</p>
        </div>
        <div className="overflow-x-auto">
          {loading ? (
            <div className="p-6 text-sm text-muted">Loading…</div>
          ) : recent.length === 0 ? (
            <div className="p-6 text-sm text-muted">No usage recorded yet this period.</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted border-b border-border">
                  <th className="font-medium px-6 py-3">When</th>
                  <th className="font-medium px-6 py-3">Source</th>
                  <th className="font-medium px-6 py-3">Type</th>
                  <th className="font-medium px-6 py-3">Model</th>
                  <th className="font-medium px-6 py-3 text-right">Tokens</th>
                  <th className="font-medium px-6 py-3 text-right">Cost</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r) => (
                  <tr key={r.id} className="border-b border-border/50 hover:bg-elevated/50">
                    <td className="px-6 py-3 text-muted whitespace-nowrap">{fmtDate(r.created_at)}</td>
                    <td className="px-6 py-3 text-fg">{r.source || '—'}</td>
                    <td className="px-6 py-3 text-muted">{r.event_type || '—'}</td>
                    <td className="px-6 py-3 text-muted truncate max-w-[16rem]">{r.model || '—'}</td>
                    <td className="px-6 py-3 text-right text-fg">{fmtNum(r.tokens)}</td>
                    <td className="px-6 py-3 text-right text-fg">{fmtCost(r.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>
    </div>
  );
}

function CapBar({ label, used, cap, pct, fmt }) {
  const danger = pct >= 100;
  const warn = pct >= 80 && pct < 100;
  const barColor = danger ? 'bg-red-500' : warn ? 'bg-amber-500' : 'bg-unicorn-500';
  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1.5">
        <span className="text-muted">{label}</span>
        <span className="text-fg">{fmt(used)} <span className="text-muted">/ {fmt(cap)}</span></span>
      </div>
      <div className="h-2.5 rounded-full bg-elevated overflow-hidden" role="progressbar"
           aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={`${label} usage`}>
        <div className={`h-full ${barColor} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
