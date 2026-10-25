import { useEffect, useMemo, useRef } from 'react';
import { Maximize2, Wrench, RotateCw } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import Markdown from '../chat/Markdown';
import { useAgentChat } from '../../hooks/useAgentChat';
import { roleLine } from '../../utils/agentClass';
import { Card, IconButton, Spinner, StatusDot, statusMeta } from '../ui';

const WORKING = new Set(['thinking', 'tool', 'responding']);

/**
 * One recipient's live answer to a briefing. Owns its own headless chat, so all
 * cards stream independently and in parallel. Fires once per `round` (the
 * parent bumps `round` when the operator sends a briefing). The card's own chat
 * state drives the face and the status dot, so each agent visibly reacts.
 */
export default function BriefingCard({ agent, prompt, round, onPromote, onStatus }) {
  const chat = useAgentChat(agent);
  const fired = useRef(0);
  const name = agent.displayName || agent.name;

  // One send per round, scheduled a tick out so a mount/unmount/mount cycle
  // (StrictMode, a key change) never aborts its own request; the cleanup
  // stops the previous answer when the round changes or the card unmounts
  // (scope change, leaving the briefing) so no SSE request leaks.
  useEffect(() => {
    if (!(round > 0 && prompt)) return undefined;
    const t = setTimeout(() => {
      fired.current = round;
      chat.send(prompt);
    }, 0);
    return () => {
      clearTimeout(t);
      chat.abort();
    };
    // chat.send/prompt intentionally excluded: fire once per round.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round]);

  const assistant = useMemo(() => [...chat.messages].reverse().find((m) => m.role === 'assistant'), [chat.messages]);

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

  const working = WORKING.has(status);
  const label =
    status === 'tool' ? `Running ${chat.currentTool}…` : status === 'idle' ? 'Standing by' : statusMeta(status).label;

  return (
    <Card padding="none" className={`flex h-72 flex-col overflow-hidden ${status === 'error' ? 'border-danger/50' : working ? 'border-accent/50 shadow-e2' : ''}`}>
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <span className="relative shrink-0">
          <AgentAvatar agent={agent} size={28} rounded="rounded-control" status={status} />
          <StatusDot status={status} size="sm" ring className="absolute -bottom-0.5 -right-0.5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-body-sm font-semibold text-fg-strong">{name}</div>
          <div className={`truncate text-micro ${status === 'error' ? 'text-danger' : working ? 'text-fg' : 'text-muted'}`}>{label}</div>
        </div>
        {!working && fired.current > 0 && (
          <IconButton icon={RotateCw} label={`Run ${name} again`} size="xs" onClick={() => prompt && chat.send(prompt)} />
        )}
        <IconButton icon={Maximize2} label={`Open ${name} in a comms window with this answer`} size="xs" onClick={() => onPromote?.(agent, { seed: chat.messages })} />
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 text-body-sm text-fg">
        {(assistant?.toolCalls || []).map((tc, i) => (
          <div key={i} className="mb-1 flex items-center gap-1 text-micro text-live">
            <Wrench aria-hidden="true" className="h-3 w-3" />
            {tc.name}
            {tc.result === undefined && tc.error === undefined ? '…' : ''}
          </div>
        ))}
        {assistant?.content ? (
          <div className={assistant.isError ? 'text-danger' : ''}>
            <Markdown>{assistant.content}</Markdown>
          </div>
        ) : chat.isThinking ? (
          <div className="flex items-center gap-2 text-caption text-muted">
            <Spinner className="h-3 w-3" label="Thinking" /> thinking…
          </div>
        ) : (
          <p className="text-caption text-muted">{agent.bio || roleLine(agent)}</p>
        )}
      </div>
    </Card>
  );
}
