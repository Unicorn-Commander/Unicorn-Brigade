import { useEffect, useRef, useState, memo } from 'react';
import { Send, Wrench, Square } from 'lucide-react';
import Markdown from './Markdown';
import { IconButton, Spinner, Textarea } from '../ui';

/**
 * One message bubble. Memoized on the message object so that streaming (which
 * replaces only the active message) never re-renders or re-parses the markdown
 * of every prior message in the conversation.
 */
const MessageBubble = memo(function MessageBubble({ m }) {
  const isUser = m.role === 'user';
  return (
    <div className={isUser ? 'text-right' : 'text-left'}>
      <div
        className={`inline-block max-w-[88%] break-words rounded-card px-3 py-2 text-left text-body-sm ${
          isUser
            ? 'whitespace-pre-wrap bg-accent/15 text-fg'
            : m.isError
              ? 'border border-danger/30 bg-danger/10 text-danger'
              : 'bg-elevated/70 text-fg'
        }`}
      >
        {(m.toolCalls || []).map((tc, i) => (
          <div key={i} className="mb-1 flex items-center gap-1 text-micro text-live">
            <Wrench aria-hidden="true" className="h-3 w-3" />
            {tc.name}
            {tc.result === undefined && tc.error === undefined ? '…' : ''}
          </div>
        ))}
        {isUser ? m.content : m.content ? <Markdown>{m.content}</Markdown> : m.isStreaming ? '…' : ''}
      </div>
    </div>
  );
});

/**
 * Presentational chat surface — fills its container (no h-screen), so it works
 * inside a floating comms window, a phone sheet or a full page. Driven entirely
 * by props from useAgentChat; holds only the draft input locally.
 *
 * Keys: Enter sends, Shift+Enter is a newline, Escape stops a running answer
 * (and only then — otherwise it bubbles so the window can close).
 */
export default function ChatPanel({ agent, messages, isThinking, currentTool, isStreaming, onSend, onAbort, autoFocus = false }) {
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);
  const name = agent?.displayName || agent?.name || 'this agent';

  // Stick to the bottom only when the user is already near it, and scroll the
  // panel itself (not the nearest page/canvas) so streaming never hijacks the
  // org-chart scroll position.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) el.scrollTop = el.scrollHeight;
  }, [messages, isThinking]);

  const submit = () => {
    const t = input.trim();
    if (!t || isStreaming) return;
    onSend(t);
    setInput('');
  };

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-3" role="log" aria-live="polite" aria-atomic="false">
        {messages.length === 0 && (
          <p className="mt-4 px-2 text-center text-caption text-muted">{agent?.bio || `Start chatting with ${name}.`}</p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} m={m} />
        ))}
        {isThinking && (
          <div className="flex items-center gap-2 text-caption text-muted">
            <Spinner className="h-3 w-3" label={currentTool ? `Running ${currentTool}` : 'Thinking'} />
            {currentTool ? `running ${currentTool}…` : 'thinking…'}
          </div>
        )}
      </div>

      <div className="border-t border-border p-2">
        <div className="flex items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              } else if (e.key === 'Escape' && isStreaming) {
                e.preventDefault();
                e.stopPropagation();
                onAbort?.();
              }
            }}
            rows={1}
            autoFocus={autoFocus}
            aria-label={`Message ${name}`}
            placeholder={`Message ${name}…`}
            className="max-h-24 resize-none"
          />
          {isStreaming ? (
            <IconButton icon={Square} label="Stop generating (Esc)" variant="secondary" onClick={() => onAbort?.()} />
          ) : (
            <IconButton icon={Send} label="Send message" variant="primary" disabled={!input.trim()} onClick={submit} />
          )}
        </div>
      </div>
    </div>
  );
}
