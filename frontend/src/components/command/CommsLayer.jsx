import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCommsStore } from '../../stores/useCommsStore';
import CommsWindow from './CommsWindow';
import AgentAvatar from '../AgentAvatar';

/**
 * Overlay that renders all open comms windows + a tray of minimized ones.
 * pointer-events-none on the layer (so the org chart stays interactive) with
 * pointer-events-auto on the actual windows/tray.
 */
export default function CommsLayer() {
  const navigate = useNavigate();
  const windows = useCommsStore((s) => s.windows);
  const focusWindow = useCommsStore((s) => s.focusWindow);
  const minimize = useCommsStore((s) => s.minimize);
  const close = useCommsStore((s) => s.close);
  const setPos = useCommsStore((s) => s.setPos);

  const open = windows.filter((w) => !w.minimized);
  const min = windows.filter((w) => w.minimized);

  // Stable so the memoized CommsWindow isn't re-rendered just because this
  // callback was recreated on a drag-triggered render.
  const promote = useCallback(
    (id) => {
      close(id);
      navigate(`/chat?agent=${id}`);
    },
    [close, navigate]
  );

  return (
    <div className="pointer-events-none absolute inset-0 z-20 overflow-hidden">
      {open.map((w) => (
        <div key={w.agent.id} className="pointer-events-auto">
          <CommsWindow
            key={`${w.agent.id}:${w.seedKey || 0}`}
            win={w}
            onFocus={focusWindow}
            onMinimize={minimize}
            onClose={close}
            onPromote={promote}
            onDrag={setPos}
          />
        </div>
      ))}

      {min.length > 0 && (
        <div className="pointer-events-auto absolute bottom-3 left-1/2 flex max-w-[80%] -translate-x-1/2 flex-wrap justify-center gap-2">
          {min.map((w) => (
            <button
              key={w.agent.id}
              onClick={() => focusWindow(w.agent.id)}
              title={`Reopen ${w.agent.displayName || w.agent.name}`}
              aria-label={`Reopen ${w.agent.displayName || w.agent.name}`}
              className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900/90 px-2 py-1 shadow-lg hover:border-unicorn-500/60"
            >
              <AgentAvatar agent={w.agent} size={20} rounded="rounded-full" />
              <span className="max-w-[110px] truncate text-xs text-slate-200">
                {w.agent.displayName || w.agent.name}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
