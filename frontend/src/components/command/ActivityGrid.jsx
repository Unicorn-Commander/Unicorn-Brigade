import { memo, useMemo } from 'react';
import AgentAvatar from '../AgentAvatar';
import { byRankDesc } from '../../utils/rank';

const STATUS = {
  thinking: { dot: 'bg-amber-400', ring: 'ring-amber-400/50', label: 'thinking' },
  tool: { dot: 'bg-cyan-400', ring: 'ring-cyan-400/50', label: 'running tool' },
  responding: { dot: 'bg-emerald-400', ring: 'ring-emerald-400/50', label: 'responding' },
  error: { dot: 'bg-red-400', ring: 'ring-red-400/50', label: 'error' },
  idle: { dot: 'bg-slate-500', ring: 'ring-slate-700/40', label: 'idle' },
};

// Memoized so an SSE tick only re-renders the one tile whose status changed,
// not all 17 (the roster + onOpen are stable).
const Tile = memo(function Tile({ agent, status, detail, onOpen }) {
  const s = STATUS[status] || STATUS.idle;
  const active = status !== 'idle';
  const name = agent.displayName || agent.name;
  return (
    <button
      onClick={() => onOpen?.(agent)}
      title={agent.bio || name}
      aria-label={`${name} — ${s.label}. Open comms.`}
      className={`flex items-center gap-3 rounded-xl border p-3 text-left transition-all ${
        active
          ? `border-transparent bg-slate-800/80 ring-2 ${s.ring}`
          : 'border-slate-700/60 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900/80'
      }`}
    >
      <div className="relative shrink-0">
        <AgentAvatar agent={agent} size={40} rounded="rounded-lg" status={status} />
        <span
          aria-hidden="true"
          className={`absolute -bottom-1 -right-1 h-3 w-3 rounded-full border-2 border-slate-900 ${s.dot} ${
            active ? 'animate-pulse' : ''
          }`}
        />
      </div>
      <div className="min-w-0">
        <div className="truncate text-sm font-semibold text-white">{name}</div>
        <div className="truncate text-[11px] text-slate-300">{agent.title || agent.rank}</div>
        <div className={`mt-0.5 truncate text-[11px] ${active ? 'text-slate-200' : 'text-slate-500'}`}>
          {s.label}
          {active && detail ? ` · ${detail}` : ''}
        </div>
      </div>
    </button>
  );
});

/**
 * A live wall of every agent and what it's doing right now (driven by the
 * orchestration SSE stream). Tiles pulse/ring when active; click to open comms.
 */
export default function ActivityGrid({ agents, statuses, onOpen }) {
  const sorted = useMemo(() => [...agents].sort(byRankDesc), [agents]);
  const activeCount = sorted.filter((a) => (statuses[a.id]?.status || 'idle') !== 'idle').length;

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-3 px-1 text-xs text-slate-400" aria-live="polite">
        {activeCount > 0 ? (
          <span className="text-emerald-300">
            {activeCount} agent{activeCount > 1 ? 's' : ''} active now
          </span>
        ) : (
          <span>All idle — open a chat or run a mission to see agents light up.</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
        {sorted.map((a) => (
          <Tile
            key={a.id}
            agent={a}
            status={statuses[a.id]?.status || 'idle'}
            detail={statuses[a.id]?.detail}
            onOpen={onOpen}
          />
        ))}
      </div>
    </div>
  );
}
