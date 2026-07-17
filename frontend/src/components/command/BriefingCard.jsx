import { useEffect, useMemo, useRef } from 'react';
import { Maximize2, Loader2, Wrench, RotateCw } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import Markdown from '../chat/Markdown';
import { useAgentChat } from '../../hooks/useAgentChat';

/**
 * One recipient's live answer to a broadcast. Owns its own headless chat, so all
 * cards stream independently and in parallel. Fires once per `round` (the parent
 * bumps `round` when the operator sends a briefing). The card's own chat state
 * drives the avatar expression, so faces visibly react here as each agent works.
 */
export default function BriefingCard({ agent, prompt, round, onPromote, onStatus }) {
  const chat = useAgentChat(agent);
  const fired = useRef(0);

  useEffect(() => {
    if (round > 0 && round !== fired.current && prompt) {
      fired.current = round;
      chat.send(prompt);
    }
    // Fire exactly once per round; chat.send/prompt intentionally excluded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round]);

  // Abort any in-flight stream when this card unmounts (e.g. the operator
  // changes scope or leaves the briefing) so we don't leak open SSE requests.
  useEffect(() => {
    return () => chat.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const assistant = useMemo(
    () => [...chat.messages].reverse().find((m) => m.role === 'assistant'),
    [chat.messages]
  );

  const status = chat.isThinking
    ? 'thinking'
    : chat.currentTool
      ? 'tool'
      : chat.isStreaming
        ? 'responding'
        : assistant?.isError
          ? 'error'
          : assistant
            ? 'done'
            : 'idle';

  // Report status up so the briefing can show an aggregate progress header.
  useEffect(() => {
    onStatus?.(agent.id, status);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, agent.id]);

  const active = status === 'thinking' || status === 'tool' || status === 'responding';
  const label =
    status === 'thinking'
      ? 'thinking…'
      : status === 'tool'
        ? `running ${chat.currentTool}…`
        : status === 'responding'
          ? 'responding…'
          : status === 'error'
            ? 'error'
            : status === 'done'
              ? 'done'
              : 'standing by';

  return (
    <div
      className={`flex h-72 flex-col overflow-hidden rounded-xl border bg-slate-900/60 transition-colors ${
        active ? 'border-unicorn-500/60 shadow-lg shadow-unicorn-500/10' : 'border-slate-700/60'
      }`}
    >
      <div className="flex items-center gap-2 border-b border-slate-800 px-3 py-2">
        <AgentAvatar agent={agent} size={28} rounded="rounded-lg" status={status} />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-white">{agent.displayName || agent.name}</div>
          <div className={`truncate text-[11px] ${active ? 'text-unicorn-200' : 'text-slate-400'}`}>{label}</div>
        </div>
        {!active && fired.current > 0 && (
          <button
            onClick={() => prompt && chat.send(prompt)}
            title="Re-run this agent"
            aria-label="Re-run this agent"
            className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <RotateCw className="h-3.5 w-3.5" />
          </button>
        )}
        <button
          onClick={() => onPromote?.(agent, { seed: chat.messages })}
          title="Open in a comms window (carries this answer)"
          aria-label="Open in a comms window"
          className="rounded-md p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 text-sm text-slate-100">
        {(assistant?.toolCalls || []).map((tc, i) => (
          <div key={i} className="mb-1 flex items-center gap-1 text-[11px] text-cyan-300/80">
            <Wrench className="h-3 w-3" />
            {tc.name}
            {tc.result === undefined && tc.error === undefined ? '…' : ''}
          </div>
        ))}
        {assistant?.content ? (
          <div className={assistant.isError ? 'text-red-200' : ''}>
            <Markdown>{assistant.content}</Markdown>
          </div>
        ) : chat.isThinking ? (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin" /> thinking…
          </div>
        ) : (
          <p className="text-xs text-slate-400">{agent.bio || agent.title || 'Awaiting the briefing.'}</p>
        )}
      </div>
    </div>
  );
}
