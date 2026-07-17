/**
 * Horizontal category bar list — magnitude by category (e.g. agents per domain).
 *
 * Dependency-free. One sequential accent hue (identity comes from the row
 * label, not color), bars sorted descending, each directly labelled with its
 * value + share. Bars are anchored to a common baseline and scaled to the max,
 * so lengths are comparable at a glance. Replaces the ad-hoc CSS bars.
 *
 * @param {{label:string,value:number,icon?:React.ReactNode,onClick?:Function}[]} items
 * @param {(item)=>string} [renderValue]  right-aligned value label
 */
export default function BarList({ items = [], renderValue, className = '' }) {
  const rows = [...items].sort((a, b) => (b.value || 0) - (a.value || 0));
  const max = Math.max(1, ...rows.map((r) => r.value || 0));
  const total = rows.reduce((s, r) => s + (r.value || 0), 0);

  if (rows.length === 0) {
    return <p className="text-center text-sm text-muted py-6">No data to display</p>;
  }

  return (
    <ul className={`space-y-2.5 ${className}`}>
      {rows.map((item, idx) => {
        const pct = max ? Math.round((item.value / max) * 100) : 0;
        const share = total ? Math.round((item.value / total) * 100) : 0;
        const Row = item.onClick ? 'button' : 'div';
        return (
          <li key={item.key || item.label || idx}>
            <Row
              type={item.onClick ? 'button' : undefined}
              onClick={item.onClick}
              className={`group relative block w-full overflow-hidden rounded-lg border border-border/40 bg-slate-800/40 px-3 py-2 text-left transition-colors ${
                item.onClick ? 'hover:border-unicorn-500/40 hover:bg-slate-800/70' : ''
              }`}
            >
              {/* Bar fill (anchored left, scaled to the max value) */}
              <span
                aria-hidden="true"
                className="absolute inset-y-0 left-0 bg-gradient-to-r from-unicorn-500/25 to-unicorn-500/5"
                style={{ width: `${Math.max(pct, 6)}%` }}
              />
              <span className="relative flex items-center justify-between gap-3">
                <span className="flex items-center gap-2.5 min-w-0">
                  {item.icon && <span className="flex-shrink-0 text-muted">{item.icon}</span>}
                  <span className="truncate font-medium text-white capitalize">{item.label}</span>
                </span>
                <span
                  className="flex-shrink-0 text-sm text-slate-300"
                  style={{ fontVariantNumeric: 'tabular-nums' }}
                >
                  {renderValue ? renderValue(item) : item.value}
                  <span className="ml-2 text-xs text-muted">{share}%</span>
                </span>
              </span>
            </Row>
          </li>
        );
      })}
    </ul>
  );
}
