import { useId } from 'react';
import { X } from 'lucide-react';
import useFocusTrap from './useFocusTrap';

/**
 * Sheet — a drawer for phones and for side panels: slides in from the bottom
 * (default) or the right. Same accessibility contract as Modal (dialog
 * semantics, focus trap + restore, Escape, scroll lock, backdrop close).
 *
 *   <Sheet isOpen={open} onClose={close} side="bottom" title="Filters">…</Sheet>
 *
 * Use a Sheet for: the mobile navigation, filter panels, the dock on a phone,
 * any secondary task that should not take the whole screen on desktop.
 */
export default function Sheet({
  isOpen = false,
  onClose,
  title,
  ariaLabel,
  side = 'bottom',
  children,
  footer,
  initialFocusRef,
  className = '',
}) {
  const panelRef = useFocusTrap({ isOpen, onClose, initialFocusRef });
  const titleId = useId();
  if (!isOpen) return null;
  const right = side === 'right';
  return (
    <div
      className={`fixed inset-0 z-modal flex bg-bg/70 backdrop-blur-sm animate-fade-in ${right ? 'justify-end' : 'items-end'}`}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={!title ? ariaLabel : undefined}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className={[
          'flex flex-col border-border bg-overlay shadow-e4 focus:outline-none',
          right
            ? 'h-full w-full max-w-md border-l animate-fade-in'
            : 'max-h-[92dvh] w-full rounded-t-pane border-t animate-slide-up',
          className,
        ].join(' ')}
      >
        {!right && (
          <div aria-hidden="true" className="mx-auto mt-2 h-1 w-10 shrink-0 rounded-full bg-border-strong/70" />
        )}
        {(title || true) && (
          <div className="flex items-center gap-3 px-4 pb-2 pt-3 sm:px-5">
            {title && (
              <h2 id={titleId} className="min-w-0 flex-1 truncate text-heading text-fg-strong">
                {title}
              </h2>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-muted transition-colors hover:bg-elevated hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 sm:px-5">{children}</div>
        {footer && <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3 sm:px-5">{footer}</div>}
      </div>
    </div>
  );
}
