import { EmptyState, LoadingState, ErrorState } from './States';

/**
 * DataTable — a real table on desktop, a card list on phones. One component,
 * all four states.
 *
 *   <DataTable
 *     columns={[
 *       { key: 'name', label: 'Name', render: (r) => <strong>{r.name}</strong> },
 *       { key: 'cron', label: 'Schedule', mono: true, hideOnMobile: true },
 *       { key: 'status', label: 'Status', render: (r) => <Chip tone={…}>{…}</Chip>, align: 'right' },
 *     ]}
 *     rows={runs}
 *     rowKey="id"
 *     loading={loading}
 *     error={error && { title: 'Couldn’t load runs', detail: humanize(error), onRetry: reload }}
 *     empty={{ icon: CalendarClock, title: 'No scheduled runs yet', description: '…', action: <Button … /> }}
 *     onRowClick={(row) => …}
 *     caption="Scheduled runs"
 *   />
 *
 * Mobile: every row becomes a card listing `label: value` for each column not
 * marked hideOnMobile; the first column is the card title.
 */
export default function DataTable({
  columns = [],
  rows = [],
  rowKey = 'id',
  loading = false,
  error = null,
  empty,
  onRowClick,
  caption,
  dense = false,
  className = '',
}) {
  if (loading) return <LoadingState variant="table" count={6} className={className} />;
  if (error) return <ErrorState compact {...error} className={className} />;
  if (!rows.length) return empty ? <EmptyState compact {...empty} className={className} /> : null;

  const keyOf = (r, i) => (typeof rowKey === 'function' ? rowKey(r) : r[rowKey]) ?? i;
  const cell = (c, r) => (c.render ? c.render(r) : r[c.key]);
  const clickable = typeof onRowClick === 'function';
  const [first, ...rest] = columns;

  return (
    <div className={className}>
      {/* ── desktop table ── */}
      <div className="hidden overflow-x-auto rounded-card border border-border bg-card md:block">
        <table className="w-full border-collapse text-body">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr className="border-b border-border">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={`whitespace-nowrap px-4 ${dense ? 'py-2' : 'py-3'} text-micro font-semibold uppercase tracking-wider text-muted ${
                    c.align === 'right' ? 'text-right' : 'text-left'
                  } ${c.width || ''}`}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={keyOf(r, i)}
                onClick={clickable ? () => onRowClick(r) : undefined}
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onRowClick(r);
                        }
                      }
                    : undefined
                }
                tabIndex={clickable ? 0 : undefined}
                className={`border-b border-border/60 last:border-b-0 ${
                  clickable
                    ? 'cursor-pointer transition-colors duration-fast hover:bg-elevated/50 focus:outline-none focus-visible:bg-elevated/60'
                    : ''
                }`}
              >
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-4 ${dense ? 'py-2' : 'py-3'} align-middle text-fg ${c.align === 'right' ? 'text-right' : ''} ${
                      c.mono ? 'font-mono text-body-sm text-muted' : ''
                    } ${c.nowrap !== false ? 'whitespace-nowrap' : ''}`}
                  >
                    {cell(c, r)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── mobile cards ── */}
      <ul className="space-y-2 md:hidden" aria-label={caption}>
        {rows.map((r, i) => {
          const Inner = clickable ? 'button' : 'div';
          return (
            <li key={keyOf(r, i)}>
              <Inner
                type={clickable ? 'button' : undefined}
                onClick={clickable ? () => onRowClick(r) : undefined}
                className={`block w-full rounded-card border border-border bg-card p-4 text-left ${
                  clickable ? 'min-h-touch transition-colors hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring' : ''
                }`}
              >
                {first && <div className="text-body font-semibold text-fg-strong">{cell(first, r)}</div>}
                <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  {rest
                    .filter((c) => !c.hideOnMobile)
                    .map((c) => (
                      <div key={c.key} className="contents">
                        <dt className="text-caption text-muted">{c.label}</dt>
                        <dd className={`text-body-sm text-fg ${c.mono ? 'font-mono text-muted' : ''}`}>{cell(c, r)}</dd>
                      </div>
                    ))}
                </dl>
              </Inner>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
