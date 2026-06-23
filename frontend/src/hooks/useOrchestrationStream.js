import { useEffect, useRef, useState } from 'react';
import { connectOrchestrationStream } from '../services/orchestrationStream';

// Map orchestration event types -> a coarse per-agent status.
const STATUS_BY_EVENT = {
  agent_started: 'thinking',
  agent_thinking: 'thinking',
  agent_responding: 'responding',
  tool_call: 'tool',
  tool_result: 'thinking',
  agent_completed: 'idle',
  agent_error: 'error',
};

/**
 * Subscribe to the live orchestration SSE stream and maintain a per-agent
 * status map + a recent activity feed. Powers the Activity view (and live
 * status dots). Connection/auth/reconnect is handled by connectOrchestrationStream.
 *
 * Note: ordinary single-agent chats DO emit agent_started/tool_call/completed
 * to this bus, so opening dock chats lights up the board.
 */
// How long a delegation edge stays "live" (pulsing) on the org chart after the
// invocation fires, in ms.
const INVOCATION_TTL = 6000;

export function useOrchestrationStream() {
  const [statuses, setStatuses] = useState({}); // agentId -> { status, detail, ts }
  const [events, setEvents] = useState([]); // recent activity, newest first
  const [invocations, setInvocations] = useState([]); // live delegation edges
  const [connected, setConnected] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const conn = connectOrchestrationStream({
      onConnected: () => setConnected(true),
      onDisconnected: () => setConnected(false),
      onEvent: (ev) => {
        if (ev.type === 'connected') {
          setConnected(true);
          return;
        }
        // Delegation: one agent invoking another. Record a transient edge so the
        // org chart can pulse source -> target while the delegated agent works.
        if (ev.type === 'agent_invocation') {
          const source = ev.agentId || ev.data?.fromAgent;
          const target = ev.data?.toAgent;
          if (source && target && source !== target) {
            seq.current += 1;
            const inv = {
              id: `inv-${seq.current}`,
              source,
              target,
              protocol: ev.data?.protocol || 'internal',
              purpose: ev.data?.purpose || '',
              ts: Date.now(),
            };
            setInvocations((prev) => [...prev, inv].slice(-40));
          }
        }
        const id = ev.agentId || ev.data?.agentId || ev.data?.fromAgent;
        const status = STATUS_BY_EVENT[ev.type];
        const detail =
          ev.type === 'tool_call'
            ? ev.name || ev.data?.name || ev.data?.tool
            : ev.data?.purpose || ev.type.replace('agent_', '');

        if (id && status) {
          setStatuses((prev) => ({ ...prev, [id]: { status, detail, ts: ev.timestamp || null } }));
        }
        if (id) {
          seq.current += 1;
          setEvents((prev) =>
            [
              {
                key: `ev-${seq.current}`,
                id: `ev-${seq.current}`,
                agentId: id,
                agentName: ev.agentName || ev.data?.agentName,
                type: ev.type,
                // Preserve the raw event data (e.g. data.toAgent/protocol/purpose)
                // so consumers like the 3D graph can draw live peer edges.
                data: ev.data,
                detail,
                ts: ev.timestamp,
              },
              ...prev,
            ].slice(0, 60)
          );
        }
      },
    });
    return () => conn.close();
  }, []);

  // Age out expired delegation edges. Only ticks while something is live.
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

  return { statuses, events, connected, invocations };
}

export default useOrchestrationStream;
