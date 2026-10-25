import { useEffect, useRef, useState } from 'react';
import { connectOrchestrationStream } from '../services/orchestrationStream';
import { humanize } from '../utils/errors';

// Orchestration event type -> the shared AGENT_STATUS vocabulary
// (components/ui/StatusDot.jsx): idle · thinking · tool · responding · done · error.
const STATUS_BY_EVENT = {
  agent_started: 'thinking',
  agent_thinking: 'thinking',
  agent_responding: 'responding',
  tool_call: 'tool',
  tool_result: 'thinking',
  agent_completed: 'done',
  agent_error: 'error',
};

// How long a delegation edge stays lit on the org chart after the invocation
// fires, and how long "Done" shows before the agent settles back to idle.
const INVOCATION_TTL = 6000;
const DONE_TTL = 8000;

/** The reason an agent_error event carries, in human words. */
function errorReason(ev) {
  const d = ev.data || {};
  const raw = d.error ?? d.detail ?? d.message ?? ev.message ?? ev.error;
  if (!raw) return 'The agent stopped without saying why.';
  if (typeof raw === 'string') return raw.length > 240 ? `${raw.slice(0, 237)}…` : raw;
  return humanize(raw, { what: 'the agent’s last step' });
}

/**
 * Subscribe to the live orchestration SSE stream and keep, per agent, what it
 * is doing right now (`statuses`), a recent event feed (`events`, newest
 * first) and the delegation edges currently lit (`invocations`). Powers the
 * Command Center's chart, activity wall and feed. Connection, auth tickets and
 * reconnects are handled by connectOrchestrationStream.
 *
 *   statuses[id] = { status, detail, reason, ts }
 *     status  one of AGENT_STATUS; `error` carries `reason` (human words)
 *     detail  the tool name / task / purpose behind the status
 *
 *   events[] = { key, id, agentId, agentName, type, data, detail, reason,
 *                tool, toAgent, toAgentName, purpose, protocol, message, ts }
 *
 * Ordinary single-agent chats emit agent_started / tool_call / completed on
 * this bus too, so opening a dock chat lights up the board.
 */
export function useOrchestrationStream() {
  const [statuses, setStatuses] = useState({});
  const [events, setEvents] = useState([]);
  const [invocations, setInvocations] = useState([]);
  const [connected, setConnected] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const conn = connectOrchestrationStream({
      onConnected: () => setConnected(true),
      onDisconnected: () => setConnected(false),
      onEvent: (ev) => {
        if (!ev || ev.type === 'connected') {
          setConnected(true);
          return;
        }
        const data = ev.data || {};
        const id = ev.agentId || data.agentId || data.fromAgent;
        const tool = ev.name || data.name || data.tool;
        const toAgent = data.toAgent;

        // Delegation: one agent invoking another. Record a transient edge so the
        // org chart can light source -> target while the delegated agent works.
        if (ev.type === 'agent_invocation' && id && toAgent && id !== toAgent) {
          seq.current += 1;
          const inv = {
            id: `inv-${seq.current}`,
            source: id,
            target: toAgent,
            protocol: data.protocol || 'internal',
            purpose: data.purpose || '',
            ts: Date.now(),
          };
          setInvocations((prev) => [...prev, inv].slice(-40));
        }

        const status = STATUS_BY_EVENT[ev.type];
        const reason = ev.type === 'agent_error' ? errorReason(ev) : undefined;
        const detail =
          ev.type === 'tool_call' || ev.type === 'tool_result'
            ? tool
            : data.purpose || data.task || data.thought || data.result || undefined;

        if (id && status) {
          setStatuses((prev) => ({
            ...prev,
            [id]: { status, detail, reason, ts: Date.now(), at: ev.timestamp || null },
          }));
        }
        if (id) {
          // Allocate the key NOW, not inside the updater: React batches
          // updaters, so two events in one tick would otherwise share a key.
          const key = `ev-${(seq.current += 1)}`;
          setEvents((prev) =>
            [
              {
                key,
                id: key,
                agentId: id,
                agentName: ev.agentName || data.agentName,
                type: ev.type,
                data, // raw payload, kept for consumers that draw their own edges
                detail,
                reason,
                tool,
                toAgent,
                toAgentName: data.toAgentName,
                purpose: data.purpose,
                protocol: data.protocol,
                message: ev.message,
                ts: ev.timestamp || new Date().toISOString(),
              },
              ...prev,
            ].slice(0, 80)
          );
        }
      },
    });
    return () => conn.close();
  }, []);

  // Age out lit delegation edges. Only ticks while something is lit.
  useEffect(() => {
    if (invocations.length === 0) return undefined;
    const t = setInterval(() => {
      const cutoff = Date.now() - INVOCATION_TTL;
      setInvocations((prev) => {
        const live = prev.filter((i) => i.ts >= cutoff);
        return live.length === prev.length ? prev : live;
      });
    }, 750);
    return () => clearInterval(t);
  }, [invocations.length]);

  // "Done" is a moment, not a state: settle finished agents back to idle.
  const doneCount = Object.values(statuses).filter((s) => s.status === 'done').length;
  useEffect(() => {
    if (doneCount === 0) return undefined;
    const t = setInterval(() => {
      const cutoff = Date.now() - DONE_TTL;
      setStatuses((prev) => {
        let changed = false;
        const next = { ...prev };
        for (const [id, s] of Object.entries(prev)) {
          if (s.status === 'done' && s.ts < cutoff) {
            next[id] = { ...s, status: 'idle', detail: undefined };
            changed = true;
          }
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => clearInterval(t);
  }, [doneCount]);

  return { statuses, events, connected, invocations };
}

export default useOrchestrationStream;
