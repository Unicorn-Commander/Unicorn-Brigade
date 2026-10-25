import { useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCommsStore } from '../../stores/useCommsStore';
import CommsWindow from './CommsWindow';
import AgentAvatar from '../AgentAvatar';
import { usePhone } from './media';

const inField = (el) => el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);

/**
 * Overlay that renders every open comms window + a tray of minimized ones.
 * pointer-events-none on the layer (so the board stays interactive) with
 * pointer-events-auto on the windows and the tray. On a phone the top window
 * is a full-screen Sheet. Escape anywhere on the board closes the top window.
 */
export default function CommsLayer() {
  const navigate = useNavigate();
  const phone = usePhone();
  const windows = useCommsStore((s) => s.windows);
  const focusWindow = useCommsStore((s) => s.focusWindow);
  const minimize = useCommsStore((s) => s.minimize);
  const close = useCommsStore((s) => s.close);
  const closeTop = useCommsStore((s) => s.closeTop);
  const setPos = useCommsStore((s) => s.setPos);

  const open = windows.filter((w) => !w.minimized);
  const min = windows.filter((w) => w.minimized);
  const topId = open.length ? open.reduce((a, b) => (a.z > b.z ? a : b)).agent.id : null;

  // Stable so the memoized CommsWindow isn't re-rendered just because this
  // callback was recreated on a drag-triggered render.
  const promote = useCallback(
    (id) => {
      close(id);
      navigate(`/chat?agent=${id}`);
    },
    [close, navigate]
  );

  // Escape from the board (not from inside a field) closes the top window.
  // Windows handle their own Escape and stop it; Modal/Sheet traps run first.
  useEffect(() => {
    if (!open.length || phone) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented || inField(e.target)) return;
      if (closeTop()) e.preventDefault();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open.length, phone, closeTop]);

  return (
    <div className="pointer-events-none absolute inset-0 z-dock overflow-hidden">
      {open.map((w) => (
        <div key={w.agent.id} className="pointer-events-auto">
          <CommsWindow
            key={`${w.agent.id}:${w.seedKey || 0}`}
            win={w}
            phone={phone}
            isTop={w.agent.id === topId}
            onFocus={focusWindow}
            onMinimize={minimize}
            onClose={close}
            onPromote={promote}
            onDrag={setPos}
          />
        </div>
      ))}

      {min.length > 0 && (
        <ul aria-label="Minimized comms windows" className="pointer-events-auto absolute bottom-3 left-1/2 flex max-w-[80%] -translate-x-1/2 flex-wrap justify-center gap-2">
          {min.map((w) => {
            const name = w.agent.displayName || w.agent.name;
            return (
              <li key={w.agent.id}>
                <button
                  type="button"
                  onClick={() => focusWindow(w.agent.id)}
                  aria-label={`Reopen comms with ${name}`}
                  className="flex min-h-touch items-center gap-1.5 rounded-full border border-border bg-overlay/95 py-1 pl-1 pr-3 shadow-e3 backdrop-blur-xl transition-colors duration-fast hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-0"
                >
                  <AgentAvatar agent={w.agent} size={24} rounded="rounded-full" />
                  <span className="max-w-[9rem] truncate text-caption text-fg">{name}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
