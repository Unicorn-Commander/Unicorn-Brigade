/**
 * ActivityFeed — the orchestration feed as readable sentences.
 *
 * Every row is one event told as a sentence: who did what, with the tool in
 * <code>, the failure reason in human words, a portrait, and a relative time.
 * The status dot uses the shared AGENT_STATUS vocabulary, so "thinking" is the
 * same amber here as on the org chart.
 *
 *   <ActivityFeed events={events} agents={agents} />        // orchestration SSE
 *   <ActivityFeed activities={[{ id, status, message, time }]} />  // legacy rows
 *
 * The time helpers live here (not in utils/) because this lane's file set does
 * not include a shared time module; the integrator may lift them out.
 */
import { useMemo } from 'react';
import { Activity } from 'lucide-react';
import AgentAvatar from './AgentAvatar';
import { Chip, StatusDot, Tooltip, EmptyState } from './ui';

// ── time helpers ────────────────────────────────────────────────────────────
const RTF =
  typeof Intl !== 'undefined' && typeof Intl.RelativeTimeFormat === 'function'
    ? new Intl.RelativeTimeFormat('en', { numeric: 'auto' })
    : null;
const UNITS = [
  ['year', 31536000],
  ['month', 2592000],
  ['week', 604800],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
];

/** "8 hours ago", "yesterday", "in 3 days", "just now". */
export function relativeTime(value, now = Date.now()) {
  if (value == null || value === '') return '—';
  const t = typeof value === 'number' ? value : Date.parse(value);
  if (Number.isNaN(t)) return '—';
  const diff = (t - now) / 1000;
  const abs = Math.abs(diff);
  // Under a minute no unit below applies: say which side of now it is (a time 50 s ahead is not "just now").
  if (abs < 60) return diff <= 0 ? 'just now' : 'in a moment';
  for (const [unit, secs] of UNITS) {
    if (abs >= secs) {
      const n = Math.round(diff / secs);
      if (RTF) return RTF.format(n, unit);
      const k = Math.abs(n);
      return `${k} ${unit}${k === 1 ? '' : 's'} ${diff < 0 ? 'ago' : 'from now'}`;
    }
  }
  return 'just now';
}

/** "Oct 24, 2026, 4:15 AM EDT" — in the given zone when one is known. */
export function absoluteTime(value, timeZone) {
  if (value == null || value === '') return '';
  const d = new Date(value);
  if (Number.isNaN(d.valueOf())) return String(value);
  try {
    return d.toLocaleString('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
      ...(timeZone ? { timeZone } : {}),
    }) + (timeZone ? ` ${zoneShortName(timeZone, d)}` : '');
  } catch {
    return d.toLocaleString();
  }
}

/** "EDT" / "PST" / "UTC" for a zone at a given instant. */
export function zoneShortName(timeZone, at = new Date()) {
  try {
    const part = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'short' })
      .formatToParts(at)
      .find((p) => p.type === 'timeZoneName');
    return part ? part.value : timeZone;
  } catch {
    return timeZone;
  }
}

// ── sentences ───────────────────────────────────────────────────────────────
const DOT_BY_TYPE = {
  agent_started: 'thinking',
  agent_thinking: 'thinking',
  tool_call: 'tool',
  tool_result: 'thinking',
  agent_responding: 'responding',
  agent_completed: 'done',
  agent_error: 'error',
  agent_invocation: 'tool',
  mission_created: 'thinking',
  mission_updated: 'thinking',
  mission_completed: 'done',
  mission_failed: 'error',
};

const LEGACY_DOT = { success: 'done', warning: 'thinking', error: 'error', info: 'idle' };

const Code = ({ children }) => (
  <code className="rounded-chip bg-elevated px-1 py-0.5 font-mono text-caption text-fg">{children}</code>
);

function humanWords(s) {
  return typeof s === 'string' ? s.replace(/_/g, ' ') : '';
}

/** Turn one orchestration event into a sentence (React nodes) + a status key. */
export function describeEvent(ev, nameOf) {
  const who = nameOf(ev.agentId) || ev.agentName || ev.agentId || 'An agent';
  const data = ev.data || {};
  const tool = ev.name || data.name || data.tool || ev.tool;
  const type = ev.type || '';
  switch (type) {
    case 'agent_started':
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> started working
            {data.task ? <> on “{data.task}”</> : null}
          </>
        ),
      };
    case 'agent_thinking':
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> is thinking
            {data.thought ? <>: {data.thought}</> : null}
          </>
        ),
      };
    case 'tool_call':
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> called {tool ? <Code>{tool}</Code> : 'a tool'}
          </>
        ),
      };
    case 'tool_result': {
      const failed = data.success === false || data.error;
      return {
        text: (
          <>
            {tool ? <Code>{tool}</Code> : 'The tool'} {failed ? 'failed for' : 'returned to'}{' '}
            <strong className="font-medium text-fg-strong">{who}</strong>
            {failed && data.error ? <>: {String(data.error)}</> : null}
          </>
        ),
        tone: failed ? 'danger' : undefined,
        dot: failed ? 'error' : undefined,
      };
    }
    case 'agent_responding':
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> is responding
          </>
        ),
      };
    case 'agent_completed':
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> finished
            {data.result ? <>: {String(data.result)}</> : null}
          </>
        ),
      };
    case 'agent_error': {
      const reason = ev.message || data.error || data.message || 'no reason was given';
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> hit a problem
            {tool ? <> in <Code>{tool}</Code></> : null}: <span className="text-danger">{String(reason)}</span>
          </>
        ),
        tone: 'danger',
      };
    }
    case 'agent_invocation': {
      const target = nameOf(data.toAgent || ev.targetAgentId) || data.toAgentName || ev.targetAgentName || data.toAgent || 'another agent';
      const purpose = data.purpose || ev.purpose;
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong> asked{' '}
            <strong className="font-medium text-fg-strong">{target}</strong>
            {purpose ? <> to {String(purpose).replace(/^to\s+/i, '')}</> : ' for help'}
          </>
        ),
        protocol: data.protocol || ev.protocol,
      };
    }
    default: {
      if (type.startsWith('mission_')) {
        const name = data.name || ev.missionId || 'a mission';
        return { text: <>Mission “{name}” {humanWords(type.replace('mission_', ''))}</> };
      }
      return {
        text: (
          <>
            <strong className="font-medium text-fg-strong">{who}</strong>: {ev.message || humanWords(type) || 'did something'}
          </>
        ),
      };
    }
  }
}

export default function ActivityFeed({
  events,
  activities,
  agents = [],
  max = 20,
  compact = false,
  emptyTitle = 'Nothing has happened yet',
  emptyDescription = 'Talk to an agent or start a mission and every step shows up here as it happens.',
  className = '',
}) {
  const byId = useMemo(() => {
    const m = new Map();
    const list = Array.isArray(agents) ? agents : Object.values(agents || {});
    list.forEach((a) => a && a.id && m.set(a.id, a));
    return m;
  }, [agents]);
  const nameOf = (id) => (id && byId.get(id) ? byId.get(id).displayName || byId.get(id).name : null);

  const rows = useMemo(() => {
    if (Array.isArray(events)) {
      // Keys must be unique even when the stream hands us a repeated id (two
      // updaters racing for one counter) — suffix any repeat we see.
      const seen = new Set();
      const uniq = (base) => {
        let k = base;
        for (let n = 2; seen.has(k); n += 1) k = `${base}~${n}`;
        seen.add(k);
        return k;
      };
      return events.slice(0, max).map((ev, i) => {
        const d = describeEvent(ev, nameOf);
        return {
          key: uniq(String(ev.key || ev.id || `${ev.type}-${ev.timestamp || ev.ts || i}`)),
          agent: byId.get(ev.agentId) || (ev.agentId ? { id: ev.agentId, name: ev.agentName } : null),
          dot: d.dot || DOT_BY_TYPE[ev.type] || 'idle',
          tone: d.tone,
          text: d.text,
          protocol: d.protocol,
          ts: ev.timestamp || ev.ts || null,
        };
      });
    }
    return (activities || []).slice(0, max).map((a, i) => ({
      key: a.id ?? i,
      agent: null,
      dot: LEGACY_DOT[a.status] || 'idle',
      tone: a.status === 'error' ? 'danger' : undefined,
      text: a.message,
      ts: a.time ?? null,
      tsIsText: typeof a.time === 'string' && Number.isNaN(Date.parse(a.time)),
    }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, activities, max, byId]);

  if (rows.length === 0) {
    return <EmptyState compact icon={Activity} title={emptyTitle} description={emptyDescription} className={className} />;
  }

  return (
    <ol className={`space-y-1 ${className}`} aria-label="Activity">
      {rows.map((r) => (
        <li
          key={r.key}
          className={`flex items-start gap-2.5 rounded-control px-2 ${compact ? 'py-1.5' : 'py-2'} ${
            r.tone === 'danger' ? 'bg-danger/5' : ''
          }`}
        >
          <span className="relative mt-0.5 shrink-0">
            {r.agent ? (
              <AgentAvatar agent={r.agent} size={compact ? 24 : 28} rounded="rounded-full" status={r.dot === 'done' ? 'idle' : r.dot} />
            ) : (
              <span aria-hidden="true" className={`flex items-center justify-center rounded-full bg-elevated ${compact ? 'h-6 w-6' : 'h-7 w-7'}`}>
                <Activity className="h-3.5 w-3.5 text-muted" />
              </span>
            )}
            <StatusDot status={r.dot} size="sm" ring className="absolute -bottom-0.5 -right-0.5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className={`${compact ? 'text-caption' : 'text-body-sm'} leading-snug text-fg`}>{r.text}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-micro text-subtle">
              {r.tsIsText ? (
                <span>{r.ts}</span>
              ) : r.ts ? (
                <Tooltip content={absoluteTime(r.ts)}>
                  <time dateTime={new Date(r.ts).toISOString()}>{relativeTime(r.ts)}</time>
                </Tooltip>
              ) : (
                <span>just now</span>
              )}
              {r.protocol && (
                <Chip size="xs" uppercase>
                  {r.protocol}
                </Chip>
              )}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
