import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

/**
 * Menu — a dropdown of actions with full keyboard support.
 *
 *   <Menu
 *     trigger={({ open, props }) => <IconButton icon={MoreHorizontal} label="More" {...props} />}
 *     items={[
 *       { id: 'edit', label: 'Edit agent', icon: Pencil, onSelect: … },
 *       { type: 'separator' },
 *       { id: 'del', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: … },
 *     ]}
 *     align="end"
 *   />
 *
 * The popup renders in a PORTAL with fixed positioning measured from the
 * trigger, so it is never clipped by a scrolling table, a card with
 * overflow-hidden or the sidebar. It flips above the trigger when there is no
 * room below, follows scroll/resize, and keeps inside the viewport.
 *
 * Arrow keys move, Home/End jump, Enter/Space select, Escape closes and
 * returns focus to the trigger, Tab closes, click-outside closes.
 * role=menu / menuitem.
 */
const GAP = 4;
const EDGE = 8;

export default function Menu({ trigger, items = [], align = 'start', side = 'bottom', className = '', minWidth = 192 }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [pos, setPos] = useState(null);
  const rootRef = useRef(null);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);
  const itemRefs = useRef([]);
  const id = useId();
  const enabled = items.map((it, i) => ({ it, i })).filter(({ it }) => it.type !== 'separator' && !it.disabled);

  const place = useCallback(() => {
    const t = triggerRef.current;
    const m = menuRef.current;
    if (!t) return;
    const r = t.getBoundingClientRect();
    const mw = Math.max(minWidth, m?.offsetWidth || minWidth);
    const mh = m?.offsetHeight || 0;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const roomBelow = vh - r.bottom - GAP - EDGE;
    const above = side === 'top' || (mh && roomBelow < mh && r.top > roomBelow);
    let left = align === 'end' ? r.right - mw : r.left;
    left = Math.min(Math.max(EDGE, left), vw - mw - EDGE);
    const top = above ? Math.max(EDGE, r.top - GAP - mh) : Math.min(r.bottom + GAP, vh - EDGE - (mh || 0));
    setPos({ top, left, maxHeight: Math.max(160, (above ? r.top : vh - r.bottom) - GAP - EDGE) });
  }, [align, side, minWidth]);

  useLayoutEffect(() => {
    if (!open) return undefined;
    place();
    // Second pass once the menu has measured itself.
    const raf = requestAnimationFrame(place);
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, place]);

  useEffect(() => {
    if (!open) return undefined;
    const first = enabled[0]?.i ?? 0;
    setActive(first);
    const raf = requestAnimationFrame(() => itemRefs.current[first]?.focus({ preventScroll: true }));
    const onDoc = (e) => {
      if (rootRef.current?.contains(e.target) || menuRef.current?.contains(e.target)) return;
      setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('touchstart', onDoc, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('touchstart', onDoc);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const close = (restore = true) => {
    setOpen(false);
    if (restore) triggerRef.current?.focus({ preventScroll: true });
  };

  const focusItem = (i) => {
    setActive(i);
    itemRefs.current[i]?.focus({ preventScroll: true });
  };

  const move = (dir) => {
    const idx = enabled.findIndex(({ i }) => i === active);
    const next = enabled[(idx + dir + enabled.length) % enabled.length];
    if (next) focusItem(next.i);
  };

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Home') { e.preventDefault(); if (enabled[0]) focusItem(enabled[0].i); }
    else if (e.key === 'End') { e.preventDefault(); const l = enabled[enabled.length - 1]; if (l) focusItem(l.i); }
    else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === 'Tab') { close(false); }
  };

  const triggerProps = {
    ref: triggerRef,
    'aria-haspopup': 'menu',
    'aria-expanded': open,
    'aria-controls': open ? id : undefined,
    onClick: () => setOpen((o) => !o),
    onKeyDown: (e) => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        setOpen(true);
      }
    },
  };

  const popup =
    open && typeof document !== 'undefined'
      ? createPortal(
          <div
            ref={menuRef}
            id={id}
            role="menu"
            onKeyDown={onKeyDown}
            style={{
              position: 'fixed',
              top: pos?.top ?? -9999,
              left: pos?.left ?? -9999,
              minWidth,
              maxHeight: pos?.maxHeight,
              visibility: pos ? 'visible' : 'hidden',
            }}
            className="z-popover overflow-y-auto rounded-card border border-border bg-overlay p-1 shadow-e3 animate-scale-in"
          >
            {items.map((it, i) =>
              it.type === 'separator' ? (
                <div key={`sep-${i}`} role="separator" className="my-1 h-px bg-border" />
              ) : (
                <button
                  key={it.id || i}
                  ref={(el) => (itemRefs.current[i] = el)}
                  role="menuitem"
                  type="button"
                  disabled={it.disabled}
                  tabIndex={active === i ? 0 : -1}
                  onMouseEnter={() => !it.disabled && setActive(i)}
                  onClick={() => {
                    close();
                    it.onSelect?.();
                  }}
                  className={[
                    'flex min-h-[36px] w-full items-center gap-2.5 rounded-control px-2.5 py-2 text-left text-body transition-colors duration-fast',
                    'focus-visible:bg-elevated focus-visible:outline-none [@media(pointer:coarse)]:min-h-touch',
                    it.tone === 'danger' ? 'text-danger hover:bg-danger/10' : 'text-fg hover:bg-elevated',
                    it.disabled ? 'cursor-not-allowed opacity-50' : '',
                  ].join(' ')}
                >
                  {it.icon && <it.icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />}
                  <span className="min-w-0 flex-1 truncate">{it.label}</span>
                  {it.shortcut && <span className="text-micro text-subtle">{it.shortcut}</span>}
                </button>
              )
            )}
          </div>,
          document.body
        )
      : null;

  return (
    <div ref={rootRef} className={`relative inline-block ${className}`}>
      {trigger({ open, props: triggerProps })}
      {popup}
    </div>
  );
}
