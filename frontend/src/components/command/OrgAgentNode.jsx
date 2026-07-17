import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { DollarSign } from 'lucide-react';
import AgentAvatar from '../AgentAvatar';
import { rankStars } from '../../utils/rank';
import {
  affiliationBorder,
  modelTier,
  modelTierChip,
  paidToolInfo,
} from '../../utils/agentClass';

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
  meta: 'ring-unicorn-400/70',
  sales: 'ring-emerald-400/70',
  data: 'ring-sky-400/70',
  knowledge: 'ring-violet-400/70',
  productivity: 'ring-teal-400/70',
  support: 'ring-unicorn-400/70',
  default: 'ring-slate-500/60',
};

const statusDot = {
  thinking: 'bg-amber-400',
  tool: 'bg-cyan-400',
  responding: 'bg-emerald-400',
  streaming: 'bg-emerald-400',
  error: 'bg-red-400',
  idle: 'bg-slate-500',
};

function OrgAgentNodeBase({ data }) {
  const { agent, isRoot, status = 'idle', subordinates = 0 } = data;
  const ring = domainRing[agent.domain?.toLowerCase()] || domainRing.default;
  const stars = rankStars(agent.rank);
  const avatarSize = isRoot ? 56 : 44;
  const active = status !== 'idle';
  const capabilities = (agent.capabilities || []).slice(0, 6);

  // Classification signals (kept in sync with Stable).
  const affBorder = affiliationBorder(agent.affiliation);
  const tier = modelTier(agent.model);
  const tierChip = modelTierChip(tier);
  const paid = paidToolInfo(agent);

  const restingBorder = isRoot
    ? 'border-yellow-300/50 bg-yellow-300/[0.06] shadow-lg shadow-yellow-300/10'
    : 'border-slate-700/60 bg-slate-900/70';

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Open comms with ${agent.displayName || agent.name}, ${agent.rank}${active ? `, currently ${status}` : ''}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          data.onOpen?.(agent);
        }
      }}
      className={`group relative flex cursor-pointer items-center gap-3 rounded-xl border border-l-4 ${affBorder} px-3 py-2 backdrop-blur-md transition-colors
        ${active ? 'border-unicorn-500/70 bg-slate-900/90 shadow-lg shadow-unicorn-500/20' : restingBorder}
        hover:border-unicorn-500/70 hover:bg-slate-900/90`}
      style={{ width: 208 }}
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-slate-600" />

      <div className={`relative shrink-0 rounded-full ring-2 ${active ? 'ring-unicorn-500/70' : isRoot ? 'ring-yellow-300/80' : ring}`}>
        <AgentAvatar agent={agent} size={avatarSize} rounded="rounded-full" status={status} />
        <span
          className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-slate-900 ${
            statusDot[status] || statusDot.idle
          } ${active ? 'animate-pulse' : ''}`}
        />
      </div>

      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-semibold text-white">
          {agent.displayName || agent.name}
        </div>
        <div className="truncate text-[11px] text-slate-300">{agent.title || agent.rank}</div>
        <div className="mt-0.5 flex items-center gap-1">
          <span className={`rounded px-1.5 py-0.5 text-[10px] leading-none ${tierChip}`}>{tier}</span>
          {paid.count > 0 && (
            <span
              title={paid.names.length ? `Paid tools: ${paid.names.join(', ')}` : `${paid.count} paid tool${paid.count > 1 ? 's' : ''}`}
              className="flex items-center gap-0.5 rounded bg-amber-500/15 px-1 py-0.5 text-[10px] leading-none text-amber-200"
            >
              <DollarSign className="h-2.5 w-2.5" />
              {paid.count}
            </span>
          )}
        </div>
        {stars > 0 && (
          <div aria-hidden="true" className="mt-0.5 flex gap-px text-[9px] leading-none text-yellow-400">
            {Array.from({ length: stars }).map((_, i) => (
              <span key={i}>★</span>
            ))}
          </div>
        )}
      </div>

      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-slate-600" />

      {/* Hover detail — appears on hover, never blocks the click-to-open. */}
      <div className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 hidden w-60 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-900/95 p-3 text-left shadow-2xl shadow-black/60 backdrop-blur-md group-hover:block">
        <div className="text-sm font-semibold text-white">{agent.displayName || agent.name}</div>
        <div className="text-[11px] text-slate-400">{agent.title || agent.rank}</div>
        <div className="mt-2 flex flex-wrap gap-1">
          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">{agent.rank}</span>
          {agent.domain && (
            <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] capitalize text-slate-300">
              {agent.domain}
            </span>
          )}
          {subordinates > 0 && (
            <span className="rounded bg-unicorn-500/20 px-1.5 py-0.5 text-[10px] text-unicorn-200">
              {subordinates} report{subordinates > 1 ? 's' : ''}
            </span>
          )}
        </div>
        {agent.model && (
          <div className="mt-2 text-[11px]">
            <span className="text-slate-500">Model: </span>
            <span className="text-cyan-300">{agent.model}</span>
            <span className={`ml-1.5 rounded px-1 py-0.5 text-[9px] leading-none ${tierChip}`}>{tier}</span>
          </div>
        )}
        {paid.count > 0 && (
          <div className="mt-2 flex items-center gap-1 text-[11px] text-amber-200">
            <DollarSign className="h-3 w-3" />
            <span className="truncate">
              {paid.names.length ? paid.names.join(', ') : `${paid.count} paid tool${paid.count > 1 ? 's' : ''}`}
            </span>
          </div>
        )}
        {capabilities.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {capabilities.map((c) => (
              <span key={c} className="rounded bg-slate-800/80 px-1.5 py-0.5 text-[10px] text-slate-300">
                {c}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(OrgAgentNodeBase);
