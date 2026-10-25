import { memo, useMemo } from 'react';
import AgentAvatar from '../AgentAvatar';
import { byRankDesc } from '../../utils/rank';
import { roleLine } from '../../utils/agentClass';
import { Card, StatusDot, statusMeta, Tooltip } from '../ui';

const WORKING = new Set(['thinking', 'tool', 'responding', 'streaming']);
const TONE_TEXT = { ok: 'text-ok', warn: 'text-warn', danger: 'text-danger', live: 'text-live', neutral: 'text-muted' };

// Memoized so an SSE tick only re-renders the tile whose status changed.
const Tile = memo(function Tile({ agent, status, detail, reason, onOpen }) {
  const meta = statusMeta(status);
  const working = WORKING.has(status);
  const error = status === 'error';
  const name = agent.displayName || agent.name;
  const line = error ? reason || 'Something went wrong' : detail;
  return (
    <Tooltip content={agent.bio || undefined}>
      <Card
        as="button"
        type="button"
        interactive
        padding="sm"
        onClick={() => onOpen?.(agent)}
        aria-label={`${name} — ${meta.label}${line ? `: ${line}` : ''}. Open comms.`}
        className={`flex w-full items-start gap-3 ${error ? 'border-danger/50' : working ? 'border-accent/50' : ''}`}
      >
        <span className="relative shrink-0">
          <AgentAvatar agent={agent} size={40} rounded="rounded-control" status={status} />
          <StatusDot status={status} size="md" ring className="absolute -bottom-1 -right-1" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-body-sm font-semibold text-fg-strong">{name}</span>
          <span className="block truncate text-caption text-muted">{roleLine(agent)}</span>
          <span className={`mt-0.5 block text-caption ${error ? 'line-clamp-2' : 'truncate'}`}>
            <span className={`font-medium ${TONE_TEXT[meta.tone] || 'text-muted'}`}>{meta.label}</span>
            {line && <span className={error ? 'text-danger' : 'text-muted'}> · {line}</span>}
          </span>
        </span>
      </Card>
    </Tooltip>
  );
});

/**
 * A live wall of every agent and what it is doing right now (driven by the
 * orchestration SSE stream). Agents that need attention come first, then the
 * ones working (most recent first), then the rest by rank. Click to open comms.
 */
export default function ActivityGrid({ agents, statuses, onOpen }) {
  const sorted = useMemo(() => {
    const bucket = (a) => {
      const s = statuses[a.id]?.status || 'idle';
      return s === 'error' ? 0 : WORKING.has(s) ? 1 : s === 'done' ? 2 : 3;
    };
    return [...agents].sort((a, b) => {
      const ba = bucket(a);
      const bb = bucket(b);
      if (ba !== bb) return ba - bb;
      if (ba < 3) return (statuses[b.id]?.ts || 0) - (statuses[a.id]?.ts || 0);
      return byRankDesc(a, b);
    });
  }, [agents, statuses]);

  const working = sorted.filter((a) => WORKING.has(statuses[a.id]?.status)).length;
  const attention = sorted.filter((a) => statuses[a.id]?.status === 'error').length;

  return (
    <div className="h-full overflow-y-auto p-4 sm:p-5">
      <p className="mb-3 text-body-sm text-muted" aria-live="polite">
        {working === 0 && attention === 0 ? (
          'All idle — open a chat or run a mission and the board lights up.'
        ) : (
          <>
            {working > 0 && <span className="font-medium text-fg">{working} working now</span>}
            {working > 0 && attention > 0 && ' · '}
            {attention > 0 && (
              <span className="font-medium text-danger">
                {attention} need{attention === 1 ? 's' : ''} attention
              </span>
            )}
          </>
        )}
      </p>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5" aria-label="Agents">
        {sorted.map((a) => (
          <li key={a.id}>
            <Tile
              agent={a}
              status={statuses[a.id]?.status || 'idle'}
              detail={statuses[a.id]?.detail}
              reason={statuses[a.id]?.reason}
              onOpen={onOpen}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}
