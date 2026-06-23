import { useEffect, useMemo, useState } from 'react';
import AgentAvatar from '../AgentAvatar';

// Per event-type accent (dot + action text colour).
const KIND = {
  agent_invocation: { dot: 'bg-purple-400', text: 'text-purple-200' },
  tool_call: { dot: 'bg-cyan-400', text: 'text-cyan-200' },
  tool_result: { dot: 'bg-cyan-400/70', text: 'text-cyan-200/80' },
  agent_responding: { dot: 'bg-emerald-400', text: 'text-emerald-200' },
  agent_completed: { dot: 'bg-emerald-500', text: 'text-emerald-200' },
  agent_error: { dot: 'bg-red-400', text: 'text-red-200' },
  agent_started: { dot: 'bg-amber-400', text: 'text-amber-200' },
  agent_thinking: { dot: 'bg-amber-400', text: 'text-amber-200' },
};

const Tool = ({ name }) => (
  <code className="rounded bg-slate-800 px-1 py-0.5 text-[11px] text-cyan-300">{name}</code>
);

// Human-readable action for an event. Returns a React node.
function actionText(ev) {
  const tool = ev.detail || ev.data?.name || ev.data?.tool;
  switch (ev.type) {
    case 'agent_invocation':
      return <>delegated to <span className="text-purple-100">{ev.data?.toAgentName || ev.data?.toAgent || 'an agent'}</span></>;
    case 'tool_call':
      return tool ? <>called <Tool name={tool} /></> : 'called a tool';
    case 'tool_result':
      return tool ? <>finished <Tool name={tool} /></> : 'finished a tool';
    case 'agent_responding':
      return 'is responding';
    case 'agent_completed':
      return 'completed';
    case 'agent_error':
      return 'hit an error';
    case 'agent_started':
      return 'started working';
    case 'agent_thinking':
      return 'is thinking…';
    default:
      return (ev.type || '').replace(/_/g, ' ');
  }
}

function relTime(ts) {
  if (ts == null) return '';
  const t = typeof ts === 'number' ? ts : Date.parse(ts);
  if (!t || Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 5) return 'now';
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  return `${Math.round(m / 60)}h`;
}

/**
 * A live, chronological ticker of orchestration events (delegations, tool
 * calls, completions) from the SSE stream — newest first. Complements the
 * status grid, which shows only each agent's *current* state.
 */
export default function ActivityFeed({ events = [], agents = [], onOpen }) {
  const byId = useMemo(() => {
    const m = new Map();
    for (const a of agents) m.set(a.id, a);
    return m;
  }, [agents]);

  // Refresh relative timestamps while events are present (cheap; small list).
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!events.length) return undefined;
    const t = setInterval(() => setTick((n) => n + 1), 10000);
    return () => clearInterval(t);
  }, [events.length]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-3 pb-2 pt-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
        Live feed
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-1.5 pb-3" aria-live="polite">
        {events.length === 0 ? (
          <p className="px-2 pt-6 text-center text-[12px] text-slate-500">
            No activity yet — open a chat or run a mission and it streams here.
          </p>
        ) : (
          events.map((ev) => {
            const agent = byId.get(ev.agentId);
            const kind = KIND[ev.type] || { dot: 'bg-slate-500', text: 'text-slate-300' };
            const name = agent?.displayName || agent?.name || ev.agentName || ev.agentId;
            return (
              <button
                key={ev.key}
                onClick={() => agent && onOpen?.(agent)}
                disabled={!agent}
                className="flex w-full items-start gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-slate-800/60 disabled:cursor-default disabled:hover:bg-transparent"
              >
                {agent ? (
                  <AgentAvatar agent={agent} size={22} rounded="rounded-md" status={null} />
                ) : (
                  <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${kind.dot}`} aria-hidden="true" />
                )}
                <span className="min-w-0 flex-1 text-[12px] leading-snug text-slate-200">
                  <span className="font-semibold text-white">{name}</span>{' '}
                  <span className={kind.text}>{actionText(ev)}</span>
                </span>
                <span className="shrink-0 pt-0.5 text-[10px] tabular-nums text-slate-500">{relTime(ev.ts)}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
