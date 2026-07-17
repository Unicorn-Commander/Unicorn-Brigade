/**
 * Card primitive — the glass panel used all over the app, on semantic tokens
 * (bg-card / border-border) so it re-themes centrally. Matches the existing
 * `backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl`
 * look. Adopt incrementally.
 */
export default function Card({ as: Comp = 'div', className = '', children, ...props }) {
  return (
    <Comp
      className={`rounded-xl border border-border/50 bg-card/50 backdrop-blur-xl ${className}`}
      {...props}
    >
      {children}
    </Comp>
  );
}
