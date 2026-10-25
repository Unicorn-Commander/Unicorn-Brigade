/**
 * StatCard — a labelled metric tile.
 *
 * Deliberately has NO built-in trend arrow: the app once shipped hard-coded
 * up-arrows with no real delta behind them. If a caller has a real change
 * value it passes `change` text plus a `tone` ('ok' | 'warn' | 'bad' |
 * 'neutral') to colour it — no direction is implied.
 *
 *   <StatCard icon={Bot} label="Agents" value={57} change="3 need attention" tone="warn" />
 */
const TONE = {
  ok: 'text-ok',
  warn: 'text-warn',
  bad: 'text-danger',
  danger: 'text-danger',
  neutral: 'text-muted',
};

export default function StatCard({ icon: Icon, label, value, change, tone = 'neutral', className = '' }) {
  return (
    <div className={`flex flex-col rounded-card border border-border bg-card p-5 ${className}`}>
      {Icon && (
        <span
          aria-hidden="true"
          className="mb-4 flex h-9 w-9 items-center justify-center rounded-control border border-border bg-elevated/70 text-accent"
        >
          <Icon className="h-[18px] w-[18px]" />
        </span>
      )}
      <p className="text-display tabular-nums text-fg-strong">{value}</p>
      <p className="mt-1 text-body-sm text-muted">{label}</p>
      {change != null && change !== '' && (
        <p className={`mt-2 text-caption ${TONE[tone] || TONE.neutral}`}>{change}</p>
      )}
    </div>
  );
}
