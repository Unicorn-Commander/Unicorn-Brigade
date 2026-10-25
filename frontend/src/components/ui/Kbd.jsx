/**
 * Kbd — a keycap. Use it wherever a shortcut is mentioned so shortcuts are
 * discoverable: palette rows, tooltips, empty states.
 *
 *   <Kbd>⌘</Kbd><Kbd>K</Kbd>   or   <Kbd keys="⌘K" />
 */
export default function Kbd({ keys, children, className = '' }) {
  const parts = keys ? String(keys).split('') : null;
  const cap = (k, i) => (
    <kbd
      key={i}
      className={`inline-flex h-5 min-w-[20px] items-center justify-center rounded-chip border border-border-strong/70 bg-elevated px-1 font-sans text-micro font-medium text-muted shadow-e1 ${className}`}
    >
      {k}
    </kbd>
  );
  if (parts) return <span className="inline-flex items-center gap-0.5">{parts.map(cap)}</span>;
  return cap(children, 0);
}
