/**
 * Usage & billing — BR-3.7
 *
 * Per-org spend this billing period, the effective monthly cap, and the most
 * recent metered events. Data: GET /api/v1/billing/usage (RLS-scoped to the
 * caller's own org) + GET /api/v1/billing/upgrade-requirements.
 *
 * Honesty rules on this page: a value the server does not record says why
 * (admin accounts are not metered; credits apply only to prepaid plans) instead
 * of a bare dash, and the activity table reads the fields the API actually
 * sends (see billingService.normalizeUsageEvent).
 */
import { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, ArrowRight, Cpu, DollarSign, ExternalLink, RefreshCw, Wallet, CreditCard } from 'lucide-react';
import { humanize } from '../utils/errors';
import { billingService } from '../services/billingService';
import { openPaymentRequired } from '../components/billing/PaymentRequiredModal';
import {
  Button,
  Card,
  CardHeader,
  Chip,
  DataTable,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  Page,
  PageHeader,
  StatCard,
  Tooltip,
} from '../components/ui';

const PLANS_URL = 'https://unicorncommander.ai/plans.html';

const fmtCost = (c) => `$${Number(c || 0).toFixed(4)}`;
const fmtNum = (n) => Number(n || 0).toLocaleString();
const fmtDate = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};
const fmtDateTime = (iso) => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toLocaleString();
};
function timeAgo(iso) {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return null;
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 45) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.round(h / 24);
  if (d < 14) return `${d} day${d === 1 ? '' : 's'} ago`;
  return fmtDate(iso);
}

// One tone per source and one label per event type, everywhere on the page.
const SOURCE = {
  agent_chat: { label: 'Chat', tone: 'accent' },
  workflow: { label: 'Workflow', tone: 'info' },
  scheduled_run: { label: 'Scheduled run', tone: 'live' },
  a2a: { label: 'A2A', tone: 'warn' },
  api: { label: 'API', tone: 'neutral' },
};
const EVENT_TYPE = {
  'llm.completion': 'Completion',
  'tool.call': 'Tool call',
  ai_api_call: 'API call',
  embedding: 'Embedding',
};
const sourceMeta = (s) => SOURCE[s] || { label: s ? String(s).replace(/_/g, ' ') : 'Unknown', tone: 'neutral' };
const eventLabel = (t) => EVENT_TYPE[t] || (t ? String(t).replace(/[._]/g, ' ') : null);

export default function Billing() {
  const [usage, setUsage] = useState(null);
  const [upgrade, setUpgrade] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);

  const load = useCallback(async () => {
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
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  const period = usage?.period || {};
  const cap = usage?.cap || {};
  const billing = usage?.billing || {};
  const recent = usage?.recent || [];
  const overCap = Boolean(usage?.over_cap);

  const tokenCap = cap.monthly_token_cap;
  const costCap = cap.monthly_cost_cap;
  const tokenPct = tokenCap ? Math.min(100, (Number(period.tokens || 0) / tokenCap) * 100) : null;
  const costPct = costCap ? Math.min(100, (Number(period.cost || 0) / costCap) * 100) : null;

  const tier = billing.subscription_tier || null;
  const isAdmin = tier === 'admin';
  const noPlan = !loading && !error && usage && !tier && !billing.paid;
  const upgradeUrl = upgrade?.upgradeUrl || PLANS_URL;
  const plansUrl = upgrade?.opsCenterUrl ? `${upgrade.opsCenterUrl.replace(/\/$/, '')}/plans.html` : upgradeUrl;
  const since = fmtDate(period.since);

  // ── credits: say why a number is missing instead of a bare dash ────────────
  const creditsRaw = billing.credits_remaining;
  let credits;
  if (isAdmin) {
    credits = { value: 'Not metered', note: 'Admin accounts aren’t metered against credits', tip: 'Admin accounts run without a credit balance. Usage is still recorded below.' };
  } else if (billing.lookup === 'unavailable') {
    credits = { value: '—', note: 'Ops-Center didn’t answer', tip: 'The credit balance lives in Ops-Center and couldn’t be fetched just now. Refresh to try again.', tone: 'warn' };
  } else if (creditsRaw === null || creditsRaw === undefined) {
    credits = { value: '—', note: 'Credits apply only to prepaid plans', tip: 'Credits apply only to prepaid plans. This organization is billed by usage.' };
  } else {
    const n = Number(creditsRaw);
    credits = {
      value: fmtNum(n),
      note: tier ? `${tier.charAt(0).toUpperCase()}${tier.slice(1)} plan` : 'No plan',
      tip: 'Prepaid credits left on this plan. Top up in Ops-Center.',
      tone: n <= 0 ? 'bad' : 'neutral',
    };
  }

  const choosePlan = () =>
    openPaymentRequired({
      reason: 'no-plan',
      subscription_tier: tier,
      credits_remaining: creditsRaw,
      message: 'This organization has no plan yet. Pick one in Ops-Center and agents can start running.',
    });

  // ── activity columns ───────────────────────────────────────────────────────
  const columns = [
    {
      key: 'event',
      label: 'Event',
      render: (r) => {
        const s = sourceMeta(r.source);
        const t = eventLabel(r.event_type);
        return (
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <Chip tone={s.tone} size="xs">
              {s.label}
            </Chip>
            {t ? (
              <span className="text-body-sm text-fg">{t}</span>
            ) : (
              <Tooltip content="This event was recorded without a type">
                <span tabIndex={0} className="text-body-sm text-subtle">
                  Untyped
                </span>
              </Tooltip>
            )}
          </span>
        );
      },
    },
    {
      key: 'when',
      label: 'When',
      render: (r) =>
        r.created_at ? (
          <Tooltip content={fmtDateTime(r.created_at)}>
            <span tabIndex={0} className="text-body-sm text-muted">
              {timeAgo(r.created_at)}
            </span>
          </Tooltip>
        ) : (
          <Tooltip content="This event was recorded without a timestamp">
            <span tabIndex={0} className="text-body-sm text-subtle">
              Unknown
            </span>
          </Tooltip>
        ),
    },
    { key: 'model', label: 'Model', mono: true, render: (r) => r.model || <span className="text-subtle">—</span> },
    { key: 'agent_id', label: 'Agent', mono: true, hideOnMobile: true, render: (r) => r.agent_id || <span className="text-subtle">—</span> },
    { key: 'tokens', label: 'Tokens', align: 'right', render: (r) => <span className="tabular-nums">{fmtNum(r.tokens)}</span> },
    { key: 'cost', label: 'Cost', align: 'right', render: (r) => <span className="tabular-nums">{fmtCost(r.cost)}</span> },
  ];

  // ── the four states ────────────────────────────────────────────────────────
  let body;
  if (offline && !usage) {
    body = <OfflineState onRetry={load} />;
  } else if (loading && !usage) {
    body = (
      <div className="space-y-5">
        <LoadingState variant="stats" count={4} label="Loading usage" />
        <LoadingState variant="table" count={6} label="Loading activity" />
      </div>
    );
  } else if (error && !usage) {
    body = <ErrorState title="Couldn’t load usage" detail={humanize(error, { what: 'loading usage' })} onRetry={load} />;
  } else {
    body = (
      <div className="space-y-5">
        {overCap && (
          <Card className="border-warn/40 bg-warn/5" role="alert">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
              <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-warn/15 text-warn">
                <AlertTriangle className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-body font-semibold text-fg-strong">Monthly cap reached</p>
                <p className="mt-0.5 text-body-sm text-muted">
                  {tokenCap && Number(period.tokens || 0) >= tokenCap
                    ? `This organization has used ${fmtNum(period.tokens)} of its ${fmtNum(tokenCap)}-token monthly cap.`
                    : costCap && Number(period.cost || 0) >= costCap
                      ? `This organization has spent ${fmtCost(period.cost)} of its ${fmtCost(costCap)} monthly cap.`
                      : 'This organization is over its monthly usage ceiling.'}{' '}
                  {cap.hard_stop === false ? 'The cap is soft, so agents keep running.' : 'Chats and runs pause until the period resets or the cap is raised.'}
                </p>
              </div>
              <Button as="a" href={upgradeUrl} target="_blank" rel="noopener noreferrer" iconRight={ArrowRight} className="shrink-0">
                Raise the cap
              </Button>
            </div>
          </Card>
        )}

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={DollarSign} label="Spend this period" value={fmtCost(period.cost)} />
          <StatCard icon={Cpu} label="Tokens used" value={fmtNum(period.tokens)} />
          <StatCard icon={Activity} label="Metered events" value={fmtNum(period.events)} />
          <StatCard
            icon={Wallet}
            label="Credits remaining"
            value={
              <Tooltip content={credits.tip}>
                <span tabIndex={0} className="rounded-chip focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  {credits.value}
                </span>
              </Tooltip>
            }
            change={credits.note}
            tone={credits.tone || 'neutral'}
          />
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          {/* Plan */}
          <Card>
            <CardHeader
              icon={CreditCard}
              title="Plan"
              description={since ? `Billing period since ${since}` : 'No billing period has started yet'}
              actions={
                !noPlan && (
                  <Button as="a" href={plansUrl} target="_blank" rel="noopener noreferrer" variant="secondary" size="sm" iconRight={ExternalLink}>
                    Admin plan
                  </Button>
                )
              }
            />
            {noPlan ? (
              <EmptyState
                compact
                icon={CreditCard}
                title="No plan yet"
                description="Pick a plan in Ops-Center and this organization’s agents can start running. Usage shows here as soon as it happens."
                action={
                  <Button icon={CreditCard} onClick={choosePlan}>
                    Choose a plan
                  </Button>
                }
              />
            ) : (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                <div>
                  <dt className="text-caption text-muted">Current plan</dt>
                  <dd className="mt-1">
                    <Chip tone="accent" className="capitalize">
                      {tier || 'Usage-based'}
                    </Chip>
                  </dd>
                </div>
                <div>
                  <dt className="text-caption text-muted">Billing</dt>
                  <dd className="mt-1 text-body text-fg">{billing.paid ? 'Active' : 'Not active'}</dd>
                </div>
                <div>
                  <dt className="text-caption text-muted">Token cap</dt>
                  <dd className="mt-1 text-body tabular-nums text-fg">{tokenCap ? `${fmtNum(tokenCap)} / month` : 'Unlimited'}</dd>
                </div>
                <div>
                  <dt className="text-caption text-muted">Cost cap</dt>
                  <dd className="mt-1 text-body tabular-nums text-fg">{costCap ? `${fmtCost(costCap)} / month` : 'Unlimited'}</dd>
                </div>
              </dl>
            )}
          </Card>

          {/* Monthly limit */}
          <Card>
            <CardHeader
              title="Monthly limit"
              description={
                tokenCap || costCap
                  ? `${cap.source === 'config' ? 'Set in your organization’s billing configuration' : 'Platform default'}${cap.hard_stop === false ? ' · soft limit, not enforced' : ''}`
                  : 'No monthly cap is set for this organization'
              }
            />
            {tokenCap || costCap ? (
              <div className="space-y-4">
                {tokenCap && <CapBar label="Tokens" used={period.tokens} cap={tokenCap} pct={tokenPct} fmt={fmtNum} />}
                {costCap && <CapBar label="Cost" used={period.cost} cap={costCap} pct={costPct} fmt={fmtCost} />}
              </div>
            ) : (
              <p className="text-body-sm text-muted">
                Agents run without a ceiling. An owner can set a token or cost cap per organization; it appears here with a progress bar.
              </p>
            )}
          </Card>
        </div>

        {/* Activity */}
        <section aria-labelledby="billing-activity">
          <div className="mb-3">
            <h2 id="billing-activity" className="text-heading text-fg-strong">
              Recent activity
            </h2>
            <p className="mt-0.5 text-body-sm text-muted">
              {recent.length ? `The latest ${recent.length} metered events for this organization.` : 'Metered events for this organization.'}
            </p>
          </div>
          <DataTable
            caption="Recent metered events"
            columns={columns}
            rows={recent}
            rowKey="id"
            loading={loading && !usage}
            empty={{
              icon: Activity,
              title: 'No usage recorded this period',
              description: 'Every chat, workflow and scheduled run is metered here once it runs.',
            }}
          />
        </section>
      </div>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        eyebrow="System"
        title="Usage & billing"
        description={since ? `Your organization’s spend this billing period, since ${since}.` : 'Your organization’s spend this billing period.'}
        actions={
          <>
            {tier && (
              <Chip tone={isAdmin ? 'neutral' : 'accent'} className="capitalize">
                {tier} plan
              </Chip>
            )}
            <Button variant="secondary" icon={RefreshCw} loading={loading && Boolean(usage)} onClick={load}>
              Refresh
            </Button>
          </>
        }
      />
      {body}
    </Page>
  );
}

function CapBar({ label, used, cap, pct, fmt }) {
  const danger = pct >= 100;
  const warn = pct >= 80 && pct < 100;
  const fill = danger ? 'bg-danger-fill' : warn ? 'bg-warn-fill' : 'bg-accent-fill';
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-body-sm">
        <span className="text-muted">{label}</span>
        <span className="tabular-nums text-fg">
          {fmt(used)} <span className="text-muted">/ {fmt(cap)}</span>
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-elevated"
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${label} used this period`}
      >
        <div className={`h-full ${fill} transition-[width] duration-slow ease-standard`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
