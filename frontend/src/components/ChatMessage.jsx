/**
 * ChatMessage — one turn in a conversation with an agent.
 *
 * A user turn is a tinted bubble on the right; an assistant turn is the
 * agent's portrait, name, model and the reply on the left. Tool calls render
 * above the reply as <ToolCallCard>s in the order the agent made them, so a
 * person can watch what the agent is doing while it works. Timestamps show on
 * hover / focus (always on phones), every message has a Copy control, a
 * streaming reply carries a cursor, and a failed reply is an inline
 * <ErrorState> with "Try again" — never a raw exception.
 *
 * Memoised: in a long conversation only the streaming turn re-renders.
 */
import { Fragment, memo, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Check, Copy, Cpu } from 'lucide-react';
import notify from '../utils/notify';
import AgentAvatar from './AgentAvatar';
import ToolCallCard from './ToolCallCard';
import { Chip, ErrorState, IconButton, Tooltip } from './ui';

// ── time helpers (shared with the Conversations page) ────────────────────────
export function formatRelative(value, now = Date.now()) {
  if (!value) return '';
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return '';
  const diff = Math.max(0, now - t);
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  const date = new Date(t);
  const sameYear = date.getFullYear() === new Date(now).getFullYear();
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: sameYear ? undefined : 'numeric' });
}

export function formatAbsolute(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

/** "anthropic/claude-sonnet-4" → "claude-sonnet-4" */
export const shortModel = (model) => (model ? String(model).split('/').pop() : '');

// ── markdown ─────────────────────────────────────────────────────────────────
function CodeBlock({ language, code }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };
  return (
    <div className="my-2 overflow-hidden rounded-control border border-border bg-surface">
      <div className="flex items-center justify-between gap-2 border-b border-border py-0.5 pl-3 pr-1">
        <span className="text-micro font-medium uppercase tracking-wider text-subtle">{language || 'code'}</span>
        <IconButton icon={copied ? Check : Copy} label={copied ? 'Copied' : 'Copy code'} size="xs" onClick={copy} />
      </div>
      <pre className="overflow-x-auto px-3 py-2.5 font-mono text-caption leading-5 text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}

// react-markdown v10 renders <pre><code class="language-x">…</code></pre>; the
// code element arrives here as the pre's child, so we read it and draw our own
// block instead of letting the inline `code` renderer style it.
function Pre({ children }) {
  const child = Array.isArray(children) ? children.find((c) => c && typeof c === 'object') : children;
  const props = child?.props || {};
  const language = /language-([\w+-]+)/.exec(props.className || '')?.[1];
  const raw = props.children;
  const code = (Array.isArray(raw) ? raw.join('') : String(raw ?? '')).replace(/\n$/, '');
  return <CodeBlock language={language} code={code} />;
}

const MD = {
  p: ({ children }) => <p className="my-2 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-fg-strong">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2 hover:text-fg-strong">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ),
  ul: ({ children }) => <ul className="my-2 ml-5 list-disc space-y-1">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 ml-5 list-decimal space-y-1">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h3 className="mb-1 mt-3 text-lead font-semibold text-fg-strong first:mt-0">{children}</h3>,
  h2: ({ children }) => <h4 className="mb-1 mt-3 text-body font-semibold text-fg-strong first:mt-0">{children}</h4>,
  h3: ({ children }) => <h5 className="mb-1 mt-2 text-body-sm font-semibold text-fg-strong first:mt-0">{children}</h5>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-border-strong pl-3 text-muted">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-border" />,
  code: ({ children }) => (
    <code className="rounded-chip bg-elevated px-1 py-0.5 font-mono text-caption text-fg-strong">{children}</code>
  ),
  pre: Pre,
};

// Cells inside a table are inline markdown: unwrap the paragraph.
const CELL = { ...MD, p: ({ children }) => <Fragment>{children}</Fragment> };

const isRow = (l) => /^\s*\|.*\|\s*$/.test(l);
const isSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
const cells = (l) =>
  l
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split('|')
    .map((s) => s.trim());

/**
 * GitHub-style pipe tables are not CommonMark and remark-gfm is not a
 * dependency, so split them out and draw them as real <table>s; everything
 * else goes through react-markdown.
 */
function splitTables(md) {
  const lines = String(md ?? '').split('\n');
  const out = [];
  let buf = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (isRow(line) && i + 1 < lines.length && isSep(lines[i + 1])) {
      if (buf.length) out.push({ type: 'md', text: buf.join('\n') });
      buf = [];
      const header = cells(line);
      const rows = [];
      i += 2;
      while (i < lines.length && isRow(lines[i])) {
        rows.push(cells(lines[i]));
        i += 1;
      }
      i -= 1;
      out.push({ type: 'table', header, rows });
    } else {
      buf.push(line);
    }
  }
  if (buf.length) out.push({ type: 'md', text: buf.join('\n') });
  return out;
}

export function Markdown({ children }) {
  const blocks = useMemo(() => splitTables(children), [children]);
  return (
    <>
      {blocks.map((b, i) =>
        b.type === 'md' ? (
          <ReactMarkdown key={i} components={MD}>
            {b.text}
          </ReactMarkdown>
        ) : (
          <div key={i} className="my-2 overflow-x-auto rounded-control border border-border">
            <table className="w-full border-collapse text-body-sm">
              <thead>
                <tr className="bg-elevated/70">
                  {b.header.map((h, j) => (
                    <th key={j} className="border-b border-border px-3 py-1.5 text-left font-semibold text-fg-strong">
                      <ReactMarkdown components={CELL}>{h}</ReactMarkdown>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((r, k) => (
                  <tr key={k} className="border-b border-border/60 last:border-b-0">
                    {b.header.map((_, j) => (
                      <td key={j} className="px-3 py-1.5 align-top text-fg">
                        <ReactMarkdown components={CELL}>{r[j] ?? ''}</ReactMarkdown>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </>
  );
}

// ── the message ──────────────────────────────────────────────────────────────
function Timestamp({ value }) {
  if (!value) return null;
  return (
    <Tooltip content={formatAbsolute(value)}>
      <time
        dateTime={value}
        tabIndex={0}
        className="rounded-chip text-micro text-subtle transition-opacity duration-fast sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100"
      >
        {formatRelative(value)}
      </time>
    </Tooltip>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };
  return (
    <span className="transition-opacity duration-fast sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
      <IconButton icon={copied ? Check : Copy} label={copied ? 'Copied' : 'Copy message'} size="xs" className="min-h-touch min-w-touch sm:min-h-0 sm:min-w-0" onClick={copy} />
    </span>
  );
}

function ChatMessage({ message, agent, onRetry, retryDisabled = false }) {
  const isUser = message.role === 'user';
  const toolCalls = message.toolCalls || [];
  const hasContent = Boolean(message.content);

  if (isUser) {
    return (
      <div className="group flex justify-end" data-role="user">
        <div className="flex max-w-[85%] flex-col items-end gap-1">
          <div className="whitespace-pre-wrap break-words rounded-pane rounded-br-chip border border-border bg-elevated px-4 py-2.5 text-body leading-relaxed text-fg">
            {message.content}
          </div>
          <div className="flex items-center gap-1">
            <Timestamp value={message.timestamp} />
            <CopyButton text={message.content} />
          </div>
        </div>
      </div>
    );
  }

  const name = agent?.displayName || agent?.name || message.agent?.name || 'Agent';
  return (
    <div className="group flex gap-3" data-role="assistant">
      <AgentAvatar agent={agent || message.agent} size={32} rounded="rounded-control" className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-body-sm font-semibold text-fg-strong">{name}</span>
          {message.model && (
            <Chip size="xs" icon={Cpu}>
              {shortModel(message.model)}
            </Chip>
          )}
          {message.stopped && (
            <Chip size="xs" tone="warn">
              Stopped
            </Chip>
          )}
          <Timestamp value={message.timestamp} />
        </div>

        {toolCalls.length > 0 && (
          <div className="mb-1">
            {toolCalls.map((tc, i) => (
              <ToolCallCard key={tc.id || `${message.id}-tool-${i}`} toolCall={tc} />
            ))}
          </div>
        )}

        {hasContent && (
          <div className="break-words text-body text-fg">
            <Markdown>{message.content}</Markdown>
            {message.isStreaming && (
              <span
                aria-hidden="true"
                className="ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 animate-pulse rounded-full bg-accent"
              />
            )}
          </div>
        )}

        {message.isError && (
          <div className="mt-2 rounded-card border border-danger/30 bg-danger/5">
            <ErrorState
              compact
              title="Couldn’t get a reply"
              detail={message.error}
              onRetry={onRetry && !retryDisabled ? () => onRetry(message) : undefined}
              retryLabel="Try again"
            />
          </div>
        )}

        {hasContent && !message.isStreaming && (
          <div className="mt-1 flex items-center gap-1">
            <CopyButton text={message.content} />
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(ChatMessage);
