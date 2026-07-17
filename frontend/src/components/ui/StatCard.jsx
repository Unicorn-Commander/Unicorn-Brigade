/**
 * StatCard primitive — a labelled metric tile.
 *
 * Deliberately has NO built-in "trend arrow": the app had hardcoded up-arrows
 * with no real delta source (a fabrication). If a caller has a real change
 * value, it passes `change` text plus a `tone` ('ok' | 'warn' | 'bad' |
 * default neutral) to color it — no directional arrow is implied.
 */
const TONE = {
  ok: 'text-emerald-400',
  warn: 'text-orange-400',
  bad: 'text-red-400',
  neutral: 'text-muted',
};

export default function StatCard({ icon: Icon, label, value, change, tone = 'neutral', className = '' }) {
  return (
    <div
      className={`rounded-xl border border-border/50 bg-card/50 backdrop-blur-xl p-6 ${className}`}
    >
      <div className="flex items-center justify-between mb-4">
        {Icon ? <Icon className="w-8 h-8 text-unicorn-400" /> : <span />}
      </div>
      <p className="text-3xl font-bold text-fg mb-1">{value}</p>
      <p className="text-sm text-muted">{label}</p>
      {change != null && change !== '' && (
        <p className={`text-xs mt-2 ${TONE[tone] || TONE.neutral}`}>{change}</p>
      )}
    </div>
  );
}
