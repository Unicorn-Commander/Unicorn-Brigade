import { useRef } from 'react';

/**
 * Tabs — an accessible tab strip (role=tablist, arrow-key navigation, Home/End).
 * The panel is the caller's: render whatever `value` selects below the strip
 * and give it role="tabpanel" + aria-labelledby={`${idBase}-${id}`} if you want
 * the relationship announced.
 *
 *   <Tabs
 *     value={view}
 *     onChange={setView}
 *     variant="segmented"           // underline (default) | segmented
 *     tabs={[{ id: 'chart', label: 'Org Chart', icon: Network, count: 57 }]}
 *   />
 *
 * Sizes: sm (28px segmented / 32px underline) · md (default).
 */
export default function Tabs({
  tabs = [],
  value,
  onChange,
  variant = 'underline',
  size = 'md',
  label = 'Views',
  idBase = 'tab',
  className = '',
}) {
  const refs = useRef([]);
  const seg = variant === 'segmented';

  const onKeyDown = (e, i) => {
    const n = tabs.length;
    let next = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % n;
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + n) % n;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = n - 1;
    if (next == null) return;
    e.preventDefault();
    refs.current[next]?.focus();
    onChange?.(tabs[next].id);
  };

  return (
    <div
      role="tablist"
      aria-label={label}
      className={[
        'flex items-center',
        seg
          ? 'gap-0.5 rounded-control border border-border bg-surface/70 p-0.5'
          : 'gap-1 border-b border-border overflow-x-auto',
        className,
      ].join(' ')}
    >
      {tabs.map((t, i) => {
        const selected = t.id === value;
        const Icon = t.icon;
        return (
          <button
            key={t.id}
            ref={(el) => (refs.current[i] = el)}
            id={`${idBase}-${t.id}`}
            role="tab"
            type="button"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange?.(t.id)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={[
              'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap font-medium transition-colors duration-fast',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface',
              seg
                ? `${size === 'sm' ? 'h-7 px-2 text-caption' : 'h-8 px-3 text-body-sm'} rounded-chip ${
                    selected ? 'bg-elevated text-fg-strong shadow-e1' : 'text-muted hover:text-fg'
                  }`
                : `${size === 'sm' ? 'h-8 px-2 text-body-sm' : 'h-10 px-3 text-body'} -mb-px border-b-2 ${
                    selected
                      ? 'border-accent text-fg-strong'
                      : 'border-transparent text-muted hover:border-border-strong hover:text-fg'
                  }`,
            ].join(' ')}
          >
            {Icon && <Icon aria-hidden="true" className="h-4 w-4" />}
            {t.label}
            {t.count != null && (
              <span
                className={`rounded-full px-1.5 text-micro tabular-nums ${
                  selected ? 'bg-accent/15 text-accent' : 'bg-elevated text-muted'
                }`}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
