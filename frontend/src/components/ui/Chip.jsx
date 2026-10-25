/**
 * Chip — a small label: a tag, a count, a status word, a filter toggle.
 *
 *   tone  neutral | accent | ok | warn | danger | info | live
 *   size  xs (18px) | sm (22px, default) | md (26px)
 *   solid filled (white/dark text) instead of the soft tint
 *   dot   leading status dot in the tone colour
 *   onClick / selected  turns it into a toggle (role=button + aria-pressed)
 *
 * Soft tints are the token at 12% over the surface with the token as text —
 * every tone clears 4.5:1 in both themes (scripts/audit-contrast.mjs).
 */
const SOFT = {
  neutral: 'bg-elevated text-muted border border-border',
  accent: 'bg-accent/10 text-accent border border-accent/25',
  ok: 'bg-ok/10 text-ok border border-ok/25',
  warn: 'bg-warn/10 text-warn border border-warn/25',
  danger: 'bg-danger/10 text-danger border border-danger/25',
  info: 'bg-info/10 text-info border border-info/25',
  live: 'bg-live/10 text-live border border-live/25',
};
const SOLID = {
  neutral: 'bg-elevated text-fg border border-border-strong',
  accent: 'bg-accent-fill text-on-accent',
  ok: 'bg-ok-fill text-white',
  warn: 'bg-warn-fill text-on-warn',
  danger: 'bg-danger-fill text-white',
  info: 'bg-info-fill text-white',
  live: 'bg-live text-on-warn',
};
const DOT = {
  neutral: 'bg-subtle',
  accent: 'bg-accent',
  ok: 'bg-ok',
  warn: 'bg-warn',
  danger: 'bg-danger',
  info: 'bg-info',
  live: 'bg-live',
};
const SIZES = {
  xs: 'h-[18px] px-1.5 text-micro gap-1',
  sm: 'h-[22px] px-2 text-caption gap-1.5',
  md: 'h-[26px] px-2.5 text-body-sm gap-1.5',
};

export default function Chip({
  tone = 'neutral',
  size = 'sm',
  solid = false,
  dot = false,
  pulse = false,
  uppercase = false,
  icon: Icon,
  selected,
  onClick,
  className = '',
  children,
  ...props
}) {
  const interactive = typeof onClick === 'function';
  const Comp = interactive ? 'button' : 'span';
  const palette = (solid || selected ? SOLID : SOFT)[tone] || SOFT.neutral;
  return (
    <Comp
      type={interactive ? 'button' : undefined}
      aria-pressed={interactive && selected != null ? selected : undefined}
      onClick={onClick}
      className={[
        'inline-flex shrink-0 items-center whitespace-nowrap rounded-chip font-medium leading-none',
        uppercase ? 'uppercase tracking-wide' : '',
        SIZES[size] || SIZES.sm,
        palette,
        interactive
          ? 'cursor-pointer transition-colors duration-fast hover:brightness-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface'
          : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {dot && (
        <span
          aria-hidden="true"
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT[tone] || DOT.neutral} ${pulse ? 'animate-pulse' : ''}`}
        />
      )}
      {Icon && <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />}
      {children}
    </Comp>
  );
}
