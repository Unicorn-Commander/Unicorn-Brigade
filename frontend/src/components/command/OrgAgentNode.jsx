import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import AgentAvatar from '../AgentAvatar';
import { rankStars } from '../../utils/rank';

// Domain → ring color, so a node's chain-of-command rank reads at a glance.
const domainRing = {
  financial: 'ring-amber-400/70',
  legal: 'ring-blue-400/70',
  medical: 'ring-rose-400/70',
  technology: 'ring-cyan-400/70',
  engineering: 'ring-cyan-400/70',
  orchestration: 'ring-yellow-300/80',
  investigation: 'ring-orange-400/70',
  intelligence: 'ring-indigo-400/70',
  meta: 'ring-fuchsia-400/70',
  sales: 'ring-emerald-400/70',
  data: 'ring-sky-400/70',
  knowledge: 'ring-violet-400/70',
  productivity: 'ring-teal-400/70',
  support: 'ring-pink-400/70',
  default: 'ring-slate-500/60',
};

const statusDot = {
  streaming: 'bg-emerald-400',
  thinking: 'bg-amber-400',
  error: 'bg-red-400',
  idle: 'bg-slate-500',
};

function OrgAgentNodeBase({ data }) {
  const { agent, isRoot, status = 'idle' } = data;
  const ring = domainRing[agent.domain?.toLowerCase()] || domainRing.default;
  const stars = rankStars(agent.rank);
  const avatarSize = isRoot ? 56 : 44;

  return (
    <div
      className={`relative flex items-center gap-3 rounded-xl border px-3 py-2 backdrop-blur-md transition-colors
        ${
          isRoot
            ? 'border-yellow-300/50 bg-yellow-300/[0.06] shadow-lg shadow-yellow-300/10'
            : 'border-slate-700/60 bg-slate-900/70'
        }
        hover:border-unicorn-500/70 hover:bg-slate-900/90`}
      style={{ width: 208 }}
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-slate-600" />

      <div className={`relative shrink-0 rounded-full ring-2 ${isRoot ? 'ring-yellow-300/80' : ring}`}>
        <AgentAvatar agent={agent} size={avatarSize} rounded="rounded-full" />
        <span
          className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-slate-900 ${
            statusDot[status] || statusDot.idle
          }`}
        />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-white">
          {agent.displayName || agent.name}
        </div>
        <div className="truncate text-[11px] text-slate-400">{agent.title || agent.rank}</div>
        {stars > 0 && (
          <div className="mt-0.5 flex gap-px text-[9px] leading-none text-yellow-400">
            {Array.from({ length: stars }).map((_, i) => (
              <span key={i}>★</span>
            ))}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-slate-600" />
    </div>
  );
}

export default memo(OrgAgentNodeBase);
