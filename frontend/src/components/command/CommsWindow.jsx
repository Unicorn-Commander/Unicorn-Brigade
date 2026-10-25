import { memo, useRef } from 'react';
import { X, Minus, Maximize2, Cpu } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import ChatPanel from '../chat/ChatPanel';
import { useAgentChat } from '../../hooks/useAgentChat';
import { useCommsStore } from '../../stores/useCommsStore';
import { MODEL_OPTIONS } from '../../utils/models';
import { roleLine } from '../../utils/agentClass';
import { Button, IconButton, Select, Sheet, StatusDot, statusMeta } from '../ui';

/**
 * One comms window for a single agent. Mounts its own useAgentChat so each
 * window streams independently. On desktop it is a floating, draggable box
 * (drag via the header → store x/y); on a phone (`phone`) the same window
 * renders as a full-screen Sheet, and only the top one is shown (`isTop`).
 * Carries an optional per-window model override + a seeded conversation
 * (e.g. promoted from a briefing answer). Escape closes it.
 */
function CommsWindow({ win, phone = false, isTop = true, onFocus, onMinimize, onClose, onPromote, onDrag }) {
  const { agent, x, y, z } = win;
  const setModel = useCommsStore((s) => s.setModel);
  const chat = useAgentChat(agent, { model: win.model, initialMessages: win.seed });
  const drag = useRef(null);
  const name = agent.displayName || agent.name;

  const status = chat.isThinking ? 'thinking' : chat.currentTool ? 'tool' : chat.isStreaming ? 'responding' : 'idle';
  const subtitle =
    status === 'tool' ? `Running ${chat.currentTool}…` : status !== 'idle' ? statusMeta(status).label : roleLine(agent);

  const onHeaderPointerDown = (e) => {
    if (e.target.closest('button, select')) return; // not a drag
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

  const modelRow = (
    <div className="flex items-center gap-2 border-b border-border px-2 py-1.5">
      <Cpu aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted" />
      <div className="min-w-0 flex-1">
        <Select size="sm" aria-label="Model for this window" value={win.model || ''} onChange={(e) => setModel(agent.id, e.target.value)}>
          {MODEL_OPTIONS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </Select>
      </div>
    </div>
  );

  const panel = (
    <ChatPanel
      agent={agent}
      messages={chat.messages}
      isThinking={chat.isThinking}
      currentTool={chat.currentTool}
      isStreaming={chat.isStreaming}
      onSend={chat.send}
      onAbort={chat.abort}
    />
  );

  if (phone) {
    return (
      <Sheet
        isOpen={isTop}
        onClose={() => onClose(agent.id)}
        title={name}
        footer={
          <>
            <Button variant="ghost" size="sm" icon={Minus} onClick={() => onMinimize(agent.id)}>
              Minimize
            </Button>
            <Button variant="secondary" size="sm" icon={Maximize2} onClick={() => onPromote(agent.id)}>
              Full chat
            </Button>
          </>
        }
      >
        <div className="flex h-[70dvh] flex-col overflow-hidden rounded-card border border-border bg-card">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <span className="relative shrink-0">
              <AgentAvatar agent={agent} size={32} rounded="rounded-full" status={status} />
              <StatusDot status={status} size="sm" ring className="absolute -bottom-0.5 -right-0.5" />
            </span>
            <span className="truncate text-caption text-muted">{subtitle}</span>
          </div>
          {modelRow}
          <div className="min-h-0 flex-1">{panel}</div>
        </div>
      </Sheet>
    );
  }

  return (
    <div
      onPointerDown={() => onFocus(agent.id)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          onClose(agent.id);
        }
      }}
      role="dialog"
      aria-label={`Comms with ${name}`}
      style={{ position: 'absolute', left: x, top: y, zIndex: z, width: 'min(340px, 92vw)', height: 'min(440px, 80dvh)' }}
      className="flex animate-fade-in flex-col overflow-hidden rounded-pane border border-border bg-overlay/95 shadow-e3 backdrop-blur-xl"
    >
      <div onPointerDown={onHeaderPointerDown} className="flex cursor-grab items-center gap-2 border-b border-border px-2 py-1.5 active:cursor-grabbing">
        <span className="relative shrink-0">
          <AgentAvatar agent={agent} size={28} rounded="rounded-full" status={status} />
          <StatusDot status={status} size="sm" ring className="absolute -bottom-0.5 -right-0.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-body-sm font-semibold leading-tight text-fg-strong">{name}</div>
          <div className={`truncate text-micro leading-tight ${status === 'idle' ? 'text-muted' : 'text-fg'}`}>{subtitle}</div>
        </div>
        <IconButton icon={Maximize2} label="Open full chat" size="xs" onClick={() => onPromote(agent.id)} />
        <IconButton icon={Minus} label="Minimize" size="xs" onClick={() => onMinimize(agent.id)} />
        <IconButton icon={X} label="Close (Esc)" size="xs" onClick={() => onClose(agent.id)} />
      </div>
      {modelRow}
      <div className="min-h-0 flex-1">{panel}</div>
    </div>
  );
}

// Memoized so dragging one window (which only changes that window's object in
// the store) doesn't re-render every other open window and its chat.
export default memo(CommsWindow);
