import { useId } from 'react';
import { X, AlertTriangle } from 'lucide-react';
import useFocusTrap from './useFocusTrap';

/**
 * Modal — the one dialog.
 *
 * Accessibility is built in: role=dialog + aria-modal, labelled by its title,
 * Escape closes, focus is trapped and restored, body scroll is locked, the
 * backdrop closes it (unless closeOnBackdrop={false}).
 *
 *   <Modal isOpen={open} onClose={close} title="Delete agent" tone="danger"
 *          description="This removes Sgt. Scribe and every conversation with it."
 *          footer={<><Button variant="ghost" onClick={close}>Cancel</Button>
 *                   <Button variant="danger" onClick={confirm}>Delete</Button></>}>
 *     …body…
 *   </Modal>
 *
 * Sizes: sm · md (default) · lg · xl · 2xl · 3xl. On phones every size is a
 * full-width sheet pinned to the bottom with a 44px close target.
 * `panelClassName` is the legacy escape hatch for callers that draw their own
 * frame; prefer title/description/footer.
 */
const SIZE = {
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-md',
  lg: 'sm:max-w-lg',
  xl: 'sm:max-w-xl',
  '2xl': 'sm:max-w-2xl',
  '3xl': 'sm:max-w-3xl',
};

export default function Modal({
  isOpen = true,
  onClose,
  title,
  description,
  ariaLabel,
  tone = 'default',
  children,
  footer,
  size = 'md',
  panelClassName,
  bodyClassName = '',
  showClose = true,
  closeOnBackdrop = true,
  initialFocusRef,
}) {
  const panelRef = useFocusTrap({ isOpen, onClose, initialFocusRef });
  const titleId = useId();
  const descId = useId();
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-modal flex items-end justify-center bg-bg/70 p-0 backdrop-blur-sm animate-fade-in sm:items-center sm:p-4"
      onMouseDown={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={!title ? ariaLabel : undefined}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
        className={
          panelClassName ||
          `flex max-h-[92dvh] w-full flex-col rounded-t-pane border border-border bg-overlay shadow-e4 animate-slide-up focus:outline-none sm:max-h-[85vh] sm:rounded-pane ${
            SIZE[size] || SIZE.md
          }`
        }
      >
        {(title || showClose) && (
          <div className="flex items-start gap-3 px-5 pb-3 pt-5 sm:px-6">
            {tone === 'danger' && (
              <span aria-hidden="true" className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-danger/10 text-danger">
                <AlertTriangle className="h-5 w-5" />
              </span>
            )}
            <div className="min-w-0 flex-1">
              {title && (
                <h2 id={titleId} className="text-heading text-fg-strong">
                  {title}
                </h2>
              )}
              {description && (
                <p id={descId} className="mt-1 text-body text-muted">
                  {description}
                </p>
              )}
            </div>
            {showClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close dialog"
                className="-mr-2 -mt-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-control text-muted transition-colors hover:bg-elevated hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>
        )}
        <div className={`min-h-0 flex-1 overflow-y-auto px-5 pb-5 sm:px-6 ${bodyClassName}`}>{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border px-5 py-3 sm:px-6">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
