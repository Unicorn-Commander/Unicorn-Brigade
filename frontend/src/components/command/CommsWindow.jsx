import { useRef } from 'react';
import { X, Minus, Maximize2, Cpu } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import ChatPanel from '../chat/ChatPanel';
import { useAgentChat } from '../../hooks/useAgentChat';
import { useCommsStore } from '../../stores/useCommsStore';
import { MODEL_OPTIONS } from '../../utils/models';

/**
 * One floating, draggable comms window for a single agent. Mounts its own
 * useAgentChat so each window streams independently. Drag via the header
 * (manual pointer drag → store x/y, so it never fights an absolute layout).
 * Carries an optional per-window model override + a seeded conversation (e.g.
 * promoted from a briefing answer).
 */
export default function CommsWindow({ win, onFocus, onMinimize, onClose, onPromote, onDrag }) {
  const { agent, x, y, z } = win;
  const setModel = useCommsStore((s) => s.setModel);
  const chat = useAgentChat(agent, { model: win.model, initialMessages: win.seed });
  const drag = useRef(null);

  const status = chat.isThinking
    ? 'thinking'
    : chat.currentTool
      ? 'tool'
      : chat.isStreaming
        ? 'responding'
        : 'idle';

  const onHeaderPointerDown = (e) => {
    // ignore drags that start on the header buttons
    if (e.target.closest('button')) return;
    onFocus(agent.id);
    drag.current = { sx: e.clientX, sy: e.clientY, ox: x, oy: y };
    const move = (ev) => {
      if (!drag.current) return;
      // Clamp so the title bar always stays grabbable on-screen.
      const maxX = Math.max(0, window.innerWidth - 320);
      const maxY = Math.max(0, window.innerHeight - 80);
      onDrag(
        agent.id,
        Math.min(maxX, Math.max(0, drag.current.ox + (ev.clientX - drag.current.sx))),
        Math.min(maxY, Math.max(0, drag.current.oy + (ev.clientY - drag.current.sy)))
      );
    };
    const up = () => {
      drag.current = null;
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const subtitle = chat.isStreaming
    ? chat.currentTool
      ? `running ${chat.currentTool}…`
      : 'responding…'
    : agent.title || agent.rank;

  return (
    <div
      onPointerDown={() => onFocus(agent.id)}
      style={{ position: 'absolute', left: x, top: y, zIndex: z, width: 'min(340px, 92vw)', height: 'min(440px, 80dvh)' }}
      className="flex animate-[fade-in_0.15s_ease-out] flex-col overflow-hidden rounded-xl border border-slate-700/70 bg-slate-900/95 shadow-2xl shadow-black/60 backdrop-blur-md"
    >
      <div
        onPointerDown={onHeaderPointerDown}
        className="flex cursor-grab items-center gap-2 border-b border-slate-800 px-2 py-1.5 active:cursor-grabbing"
      >
        <div className="relative">
          <AgentAvatar agent={agent} size={26} rounded="rounded-full" status={status} />
          <span
            className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-slate-900 ${
              chat.isStreaming ? 'bg-emerald-400' : 'bg-slate-500'
            }`}
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-semibold leading-tight text-white">
            {agent.displayName || agent.name}
          </div>
          <div className="truncate text-[10px] leading-tight text-slate-400">{subtitle}</div>
        </div>
        <button onClick={() => onPromote(agent.id)} title="Open full chat" className="p-1 text-slate-400 hover:text-white">
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button onClick={() => onMinimize(agent.id)} title="Minimize" className="p-1 text-slate-400 hover:text-white">
          <Minus className="h-3.5 w-3.5" />
        </button>
        <button onClick={() => onClose(agent.id)} title="Close" className="p-1 text-slate-400 hover:text-red-300">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Per-window model override */}
      <div className="flex items-center gap-1.5 border-b border-slate-800 bg-slate-900/50 px-2 py-1">
        <Cpu className="h-3 w-3 shrink-0 text-slate-500" />
        <select
          value={win.model || ''}
          onChange={(e) => setModel(agent.id, e.target.value)}
          onPointerDown={(e) => e.stopPropagation()}
          title="Model for this window"
          className="flex-1 cursor-pointer bg-transparent text-[11px] text-slate-300 focus:outline-none"
        >
          {MODEL_OPTIONS.map((m) => (
            <option key={m.id} value={m.id} className="bg-slate-900 text-slate-200">
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <div className="min-h-0 flex-1">
        <ChatPanel
          agent={agent}
          messages={chat.messages}
          isThinking={chat.isThinking}
          currentTool={chat.currentTool}
          isStreaming={chat.isStreaming}
          onSend={chat.send}
          onAbort={chat.abort}
        />
      </div>
    </div>
  );
}
