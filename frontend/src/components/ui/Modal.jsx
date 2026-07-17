import { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

/**
 * Accessible modal dialog primitive.
 *
 * Bakes in the a11y contract that the audit found missing on 24 hand-rolled
 * `fixed inset-0` modals (only CommsWindow had any of it):
 *   - role="dialog" + aria-modal="true"
 *   - labelled by its title (aria-labelledby) or an explicit aria-label
 *   - Escape to close
 *   - focus trap (Tab/Shift+Tab cycle within the panel)
 *   - focus restore to the element that was focused before opening
 *   - backdrop click to close
 *   - background scroll lock while open
 *
 * Visuals are caller-owned via `panelClassName` so existing modals keep their
 * exact look while gaining the semantics. Pass a `title` to get the built-in
 * header + close button, or render your own header inside `children` and pass
 * `ariaLabel` + `showClose={false}`.
 */
const SIZE = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  '3xl': 'max-w-3xl',
};

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Modal({
  isOpen = true,
  onClose,
  title,
  ariaLabel,
  children,
  size = 'md',
  panelClassName,
  showClose = true,
  closeOnBackdrop = true,
  initialFocusRef,
}) {
  const panelRef = useRef(null);
  const previouslyFocused = useRef(null);
  const titleId = useId();

  useEffect(() => {
    if (!isOpen) return undefined;

    previouslyFocused.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    // Move focus into the dialog.
    const focusFirst = () => {
      const panel = panelRef.current;
      if (!panel) return;
      const target =
        initialFocusRef?.current ||
        panel.querySelector('[data-autofocus]') ||
        panel.querySelector(FOCUSABLE) ||
        panel;
      target?.focus?.();
    };
    // rAF so the element exists and layout has settled before focusing.
    const raf = requestAnimationFrame(focusFirst);

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onClose?.();
        return;
      }
      if (e.key !== 'Tab') return;
      const panel = panelRef.current;
      if (!panel) return;
      const items = Array.from(panel.querySelectorAll(FOCUSABLE)).filter(
        (el) => el.offsetParent !== null || el === document.activeElement
      );
      if (items.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', onKeyDown, true);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', onKeyDown, true);
      document.body.style.overflow = prevOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [isOpen, onClose, initialFocusRef]);

  if (!isOpen) return null;

  const labelledBy = title ? titleId : undefined;
  const label = !title ? ariaLabel : undefined;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-label={label}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className={
          panelClassName ||
          `w-full ${SIZE[size] || SIZE.md} rounded-xl border border-border/60 bg-surface/95 backdrop-blur-xl shadow-2xl focus:outline-none`
        }
      >
        {(title || showClose) && (
          <div className="flex items-start justify-between gap-4 p-6 border-b border-border/50">
            {title ? (
              <h2 id={titleId} className="text-xl font-bold text-white">
                {title}
              </h2>
            ) : (
              <span />
            )}
            {showClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                className="p-2 -m-2 rounded-lg text-muted hover:text-white hover:bg-white/5 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
