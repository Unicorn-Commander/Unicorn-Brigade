/**
 * Accessible switch primitive.
 *
 * Replaces the hand-rolled `<button>` toggles (which had no role and no state
 * exposed to assistive tech). Renders as role="switch" with aria-checked, is
 * keyboard operable (Space/Enter via native button), and takes an accessible
 * name from `label`/`aria-label`.
 */
export default function Toggle({
  checked = false,
  onChange,
  disabled = false,
  label,
  id,
  className = '',
}) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange?.(!checked)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed ${
        checked ? 'bg-accent' : 'bg-slate-700'
      } ${className}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
          checked ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  );
}
