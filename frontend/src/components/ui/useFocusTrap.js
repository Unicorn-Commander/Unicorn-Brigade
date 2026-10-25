import { useEffect, useRef } from 'react';

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Focus management shared by Modal and Sheet:
 *   - moves focus into the panel when it OPENS (initialFocusRef → [data-autofocus] → first control → panel)
 *   - traps Tab / Shift+Tab inside the panel
 *   - Escape calls onClose
 *   - locks body scroll while open
 *   - restores focus to the previously focused element when it CLOSES
 *
 * The effect depends on `isOpen` ONLY. `onClose` and `initialFocusRef` are read
 * through refs, so a parent that passes a new inline handler on every render
 * (`onClose={() => setForm(null)}` — most dialogs) does not re-run the effect.
 * It used to: every keystroke re-rendered the parent, the effect's cleanup
 * restored focus and its body moved focus back to the FIRST field, so typing
 * "abcdef" into a dialog's second field put "a" there and "bcdef" in the first
 * (found 2026-10-24 on the Missions dialog).
 *
 * Returns the ref to put on the panel element.
 */
export default function useFocusTrap({ isOpen, onClose, initialFocusRef }) {
  const panelRef = useRef(null);
  const previouslyFocused = useRef(null);
  const onCloseRef = useRef(onClose);
  const initialFocusRefRef = useRef(initialFocusRef);
  onCloseRef.current = onClose;
  initialFocusRefRef.current = initialFocusRef;

  useEffect(() => {
    if (!isOpen) return undefined;
    previouslyFocused.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const focusFirst = () => {
      const panel = panelRef.current;
      if (!panel) return;
      // Something inside already has focus (e.g. an autoFocus field): leave it.
      if (panel.contains(document.activeElement)) return;
      const target =
        initialFocusRefRef.current?.current ||
        panel.querySelector('[data-autofocus]') ||
        panel.querySelector(FOCUSABLE) ||
        panel;
      target?.focus?.({ preventScroll: true });
    };
    const raf = requestAnimationFrame(focusFirst);

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onCloseRef.current?.();
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
      previouslyFocused.current?.focus?.({ preventScroll: true });
    };
  }, [isOpen]);

  return panelRef;
}
