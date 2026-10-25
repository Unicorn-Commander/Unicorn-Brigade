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
      className={`relative inline-flex h-6 w-11 flex-shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface [@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-2.5 [@media(pointer:coarse)]:after:content-[''] disabled:opacity-50 disabled:cursor-not-allowed ${
        checked ? 'bg-accent-fill' : 'bg-border-strong'
      } ${className}`}
    >
      <span
        className={`inline-block h-5 w-5 transform rounded-full shadow-e1 transition-transform duration-fast ${checked ? 'bg-on-accent' : 'bg-white'} ${
          checked ? 'translate-x-5' : 'translate-x-0.5'
        }`}
      />
    </button>
  );
}
