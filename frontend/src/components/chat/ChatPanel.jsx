import { useEffect, useRef, useState, memo } from 'react';
import { Send, Loader2, Wrench, Square } from 'lucide-react';
import Markdown from './Markdown';

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
        className={`inline-block max-w-[88%] break-words rounded-xl px-3 py-2 text-left text-sm ${
          isUser
            ? 'whitespace-pre-wrap bg-unicorn-500/20 text-white'
            : m.isError
              ? 'bg-red-500/15 text-red-200'
              : 'bg-slate-800/70 text-slate-100'
        }`}
      >
        {(m.toolCalls || []).map((tc, i) => (
          <div key={i} className="mb-1 flex items-center gap-1 text-[11px] text-cyan-300/80">
            <Wrench className="h-3 w-3" />
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
 * inside a floating comms window or a full page. Driven entirely by props from
 * useAgentChat; holds only the draft input locally.
 */
export default function ChatPanel({ agent, messages, isThinking, currentTool, isStreaming, onSend, onAbort }) {
  const [input, setInput] = useState('');
  const scrollRef = useRef(null);

  // Stick to the bottom only when the user is already near it, and scroll the
  // panel itself (not the nearest page/canvas) so streaming never hijacks the
  // org-chart scroll position.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 80) {
      el.scrollTop = el.scrollHeight;
    }
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
          <p className="mt-4 px-2 text-center text-xs text-slate-500">
            {agent?.bio || `Start chatting with ${agent?.displayName || 'this agent'}.`}
          </p>
        )}
        {messages.map((m) => (
          <MessageBubble key={m.id} m={m} />
        ))}
        {isThinking && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Loader2 className="h-3 w-3 animate-spin" />
            {currentTool ? `running ${currentTool}…` : 'thinking…'}
          </div>
        )}
      </div>

      <div className="border-t border-slate-800 p-2">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              } else if (e.key === 'Escape' && isStreaming) {
                e.preventDefault();
                onAbort?.();
              }
            }}
            rows={1}
            placeholder={`Message ${agent?.displayName || 'agent'}…`}
            className="max-h-24 flex-1 resize-none rounded-lg bg-slate-800/70 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-unicorn-500/50"
          />
          {isStreaming ? (
            <button
              onClick={() => onAbort?.()}
              className="rounded-lg bg-slate-700 p-2 text-white hover:bg-slate-600"
              title="Stop generating (Esc)"
              aria-label="Stop generating"
            >
              <Square className="h-4 w-4" fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={submit}
              disabled={!input.trim()}
              className="rounded-lg bg-unicorn-500/80 p-2 text-white hover:bg-unicorn-500 disabled:opacity-40"
              title="Send"
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
