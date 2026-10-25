import { useEffect, useMemo, useState } from 'react';
import { Radio } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import { normalizeProtocol } from '../../utils/protocol';
import { Chip, EmptyState, StatusDot } from '../ui';

// Event type -> the status it means (for the dot on rows without a known agent).
const STATUS_OF = {
  agent_invocation: 'thinking',
  tool_call: 'tool',
  tool_result: 'tool',
  agent_responding: 'responding',
  agent_completed: 'done',
  agent_error: 'error',
  agent_started: 'thinking',
  agent_thinking: 'thinking',
};
const PROTOCOL_TONE = { internal: 'accent', a2a: 'info', paid: 'warn', peer: 'live' };

const Tool = ({ name }) => <code className="rounded-chip bg-surface px-1 py-0.5 font-mono text-micro text-live">{name}</code>;
const Em = ({ children }) => <span className="font-medium text-fg-strong">{children}</span>;
const Muted = ({ children }) => <span className="text-muted">{children}</span>;

/** The event as a sentence fragment after the agent's name. */
function sentence(ev) {
  const tool = ev.tool || ev.detail;
  switch (ev.type) {
    case 'agent_invocation': {
      const protocol = normalizeProtocol(ev.protocol || 'internal');
      return (
        <>
          delegated to <Em>{ev.toAgentName || ev.toAgent || 'an agent'}</Em>{' '}
          <Chip size="xs" tone={PROTOCOL_TONE[protocol] || 'neutral'}>
            {protocol}
          </Chip>
          {ev.purpose && <Muted> · {ev.purpose}</Muted>}
        </>
      );
    }
    case 'tool_call':
      return tool ? <>called <Tool name={tool} /></> : 'called a tool';
    case 'tool_result':
      return tool ? <>finished <Tool name={tool} /></> : 'finished a tool';
    case 'agent_responding':
      return 'is responding';
    case 'agent_completed':
      return ev.detail ? <>finished<Muted> · {ev.detail}</Muted></> : 'finished';
    case 'agent_error':
      return 'hit an error';
    case 'agent_started':
      return ev.detail ? <>started on <Muted>{ev.detail}</Muted></> : 'started working';
    case 'agent_thinking':
      return ev.detail ? <>is thinking<Muted> · {ev.detail}</Muted></> : 'is thinking…';
    default:
      return (ev.type || '').replace(/_/g, ' ');
  }
}

function relTime(ts) {
  if (ts == null) return '';
  const t = typeof ts === 'number' ? ts : Date.parse(ts);
  if (!t || Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.round(m / 60)}h ago`;
}

/**
 * A live, chronological ticker of orchestration events (delegations, tool
 * calls, completions, failures with their reason) — newest first. Complements
 * the activity wall, which shows only each agent's *current* state.
 */
export default function ActivityFeed({ events = [], agents = [], connected, onOpen }) {
  const byId = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);

  // Refresh relative timestamps while events are present (cheap; small list).
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!events.length) return undefined;
    const t = setInterval(() => setTick((n) => n + 1), 10000);
    return () => clearInterval(t);
  }, [events.length]);

  return (
    <section className="flex h-full flex-col" aria-label="Live feed">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3">
        <h2 className="text-micro font-semibold uppercase tracking-wider text-muted">Live feed</h2>
        {connected != null && (
          <Chip size="xs" tone={connected ? 'ok' : 'warn'} dot pulse={!connected} className="ml-auto">
            {connected ? 'Live' : 'Reconnecting…'}
          </Chip>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-3" aria-live="polite">
        {events.length === 0 ? (
          <EmptyState
            compact
            icon={Radio}
            title="Nothing happening yet"
            description="Open a chat with any agent or run a mission — every delegation, tool call and answer streams here as it happens."
          />
        ) : (
          <ul>
            {events.map((ev) => {
              const agent = byId.get(ev.agentId);
              const name = agent?.displayName || agent?.name || ev.agentName || ev.agentId;
              const when = relTime(ev.ts);
              return (
                <li key={ev.key}>
                  <button
                    type="button"
                    onClick={() => agent && onOpen?.(agent)}
                    disabled={!agent}
                    className="flex w-full items-start gap-2 rounded-control px-2 py-1.5 text-left transition-colors duration-fast hover:bg-elevated/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:hover:bg-transparent"
                  >
                    {agent ? (
                      <AgentAvatar agent={agent} size={24} rounded="rounded-control" status={STATUS_OF[ev.type] || 'idle'} className="mt-0.5" />
                    ) : (
                      <StatusDot status={STATUS_OF[ev.type] || 'idle'} className="mt-2" />
                    )}
                    <span className="min-w-0 flex-1 text-caption leading-snug text-fg">
                      <span className="font-semibold text-fg-strong">{name}</span> {sentence(ev)}
                      {ev.type === 'agent_error' && <span className="mt-0.5 block text-danger">{ev.reason}</span>}
                    </span>
                    {when && (
                      <time dateTime={typeof ev.ts === 'string' ? ev.ts : undefined} className="shrink-0 pt-0.5 text-micro tabular-nums text-subtle">
                        {when}
                      </time>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
