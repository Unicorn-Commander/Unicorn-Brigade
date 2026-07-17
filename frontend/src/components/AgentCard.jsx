import { Star, Sparkles, Cpu, TrendingUp, Wrench, DollarSign } from 'lucide-react';
import AgentAvatar from './AgentAvatar';
import { rankStars } from '../utils/rank';
import {
  affiliationBorder,
  modelTier,
  modelTierChip,
  paidToolInfo,
} from '../utils/agentClass';

// Domain gradient backgrounds
const domainGradients = {
  financial: 'from-amber-500 to-yellow-600',
  legal: 'from-blue-500 to-indigo-600',
  medical: 'from-red-500 to-unicorn-600',
  technology: 'from-cyan-500 to-blue-600',
  cybersecurity: 'from-unicorn-500 to-violet-600',
  orchestration: 'from-unicorn-500 to-rose-600',
  investigation: 'from-amber-500 to-orange-600',
  intelligence: 'from-indigo-500 to-unicorn-600',
  meta: 'from-orange-500 to-red-600',
  default: 'from-unicorn-600 to-unicorn-500'
};

// Model icons
const getModelIcon = (model) => {
  if (model?.includes('gpt-4') || model?.includes('claude')) {
    return Sparkles;
  }
  return Cpu;
};

// Render star rating
const StarRating = ({ rank }) => {
  const stars = rankStars(rank);

  return (
    <div className="flex items-center space-x-0.5">
      {[...Array(5)].map((_, i) => (
        <Star
          key={i}
          className={`w-3 h-3 ${i < stars ? 'fill-yellow-400 text-yellow-400' : 'text-slate-600'}`}
        />
      ))}
    </div>
  );
};

const AgentCard = ({ agent, onClick }) => {
  const gradient = domainGradients[agent.domain?.toLowerCase()] || domainGradients.default;
  const ModelIcon = getModelIcon(agent.model);
  const capabilities = Array.isArray(agent.capabilities) ? agent.capabilities : [];
  // The API emits toolDetails (rich) and tools (string array); agentTools was dead.
  const toolDetails = Array.isArray(agent.toolDetails) ? agent.toolDetails : [];
  const toolNames = toolDetails.length
    ? toolDetails.map((t) => t.displayName || t.name)
    : (Array.isArray(agent.tools) ? agent.tools : []);
  const invocationCount = agent._count?.messages || 0;

  // Classification signals (kept in sync with Stable).
  const affBorder = affiliationBorder(agent.affiliation);
  const tier = modelTier(agent.model);
  const tierChip = modelTierChip(tier);
  const paid = paidToolInfo(agent);

  return (
    <div
      onClick={onClick}
      className={`group relative overflow-hidden rounded-xl border border-slate-700/50 border-l-4 ${affBorder} bg-slate-900/50 backdrop-blur-xl cursor-pointer transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:shadow-unicorn-500/20`}
    >
      {/* Gradient Header */}
      <div className={`h-24 bg-gradient-to-br ${gradient} relative`}>
        <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-slate-900/50 to-transparent"></div>

        {/* Agent Avatar */}
        <div className="absolute -bottom-8 left-6">
          <AgentAvatar
            agent={agent}
            size="w-16 h-16"
            className="border-2 border-slate-700 shadow-xl group-hover:scale-110 transition-transform"
          />
        </div>
      </div>

      {/* Card Content */}
      <div className="pt-10 px-6 pb-6 space-y-4">
        {/* Title Section */}
        <div>
          <h3 className="text-xl font-bold text-white group-hover:text-unicorn-400 transition-colors mb-1">
            {agent.displayName || agent.name}
          </h3>
          {agent.title && (
            <p className="text-sm text-slate-400 font-medium">{agent.title}</p>
          )}
        </div>

        {/* Badges Row */}
        <div className="flex flex-wrap gap-2 items-center">
          {/* Model Badge */}
          <div className="flex items-center space-x-1 px-2 py-1 rounded-lg bg-slate-800/50 border border-slate-700/50">
            <ModelIcon className="w-3 h-3 text-cyan-400" />
            <span className="text-xs text-slate-300">{agent.model || 'Unknown model'}</span>
          </div>

          {/* Domain Badge */}
          <div className={`px-2 py-1 rounded-lg bg-gradient-to-r ${gradient} bg-opacity-20 border border-slate-700/50`}>
            <span className="text-xs text-white font-medium">{agent.domain || 'General'}</span>
          </div>

          {/* Model Tier Chip */}
          <span className={`px-2 py-1 rounded-lg text-xs font-medium ${tierChip}`}>{tier}</span>

          {/* Paid Tools Badge */}
          {paid.count > 0 && (
            <span
              title={paid.names.length ? `Paid tools: ${paid.names.join(', ')}` : `${paid.count} paid tool${paid.count > 1 ? 's' : ''}`}
              className="flex items-center gap-0.5 px-2 py-1 rounded-lg text-xs font-medium bg-amber-500/15 text-amber-200"
            >
              <DollarSign className="w-3 h-3" />
              {paid.count}
            </span>
          )}
        </div>

        {/* Rank Stars */}
        {agent.rank && (
          <div className="flex items-center space-x-2">
            <span className="text-xs text-slate-400 font-medium">{agent.rank}</span>
            <StarRating rank={agent.rank} />
          </div>
        )}

        {/* Capabilities Section */}
        {capabilities.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <div className="h-px flex-1 bg-slate-800"></div>
              <span className="text-xs text-slate-400 font-medium">Capabilities</span>
              <div className="h-px flex-1 bg-slate-800"></div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {capabilities.slice(0, 3).map((cap, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 rounded-md bg-unicorn-500/10 text-unicorn-300 text-xs border border-unicorn-500/20"
                >
                  {cap}
                </span>
              ))}
              {capabilities.length > 3 && (
                <span className="px-2 py-1 rounded-md bg-slate-800/50 text-slate-400 text-xs border border-slate-700/50">
                  +{capabilities.length - 3} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Tools Section */}
        {toolNames.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center space-x-2">
              <div className="h-px flex-1 bg-slate-800"></div>
              <span className="text-xs text-slate-400 font-medium">Tools</span>
              <div className="h-px flex-1 bg-slate-800"></div>
            </div>
            <div className="space-y-1">
              {toolNames.slice(0, 2).map((name, idx) => {
                const isPaid = paid.names.includes(name);
                return (
                  <div
                    key={`${name}-${idx}`}
                    className="flex items-center space-x-2 text-xs text-slate-400"
                  >
                    {isPaid ? (
                      <DollarSign className="w-3 h-3 text-amber-300" />
                    ) : (
                      <Wrench className="w-3 h-3 text-cyan-400" />
                    )}
                    <span>{name || 'Tool'}</span>
                  </div>
                );
              })}
              {toolNames.length > 2 && (
                <div className="text-xs text-slate-400 pl-5">
                  +{toolNames.length - 2} more tools
                </div>
              )}
            </div>
          </div>
        )}

        {/* Stats Section — real invocation count only (no fabricated success rate) */}
        <div className="pt-3 border-t border-slate-800">
          <div className="flex items-center space-x-1.5 text-xs">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
            <span className="text-slate-400">
              {invocationCount.toLocaleString()} invocations
            </span>
          </div>
        </div>
      </div>

      {/* Hover Glow Effect */}
      <div className={`absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-br ${gradient} mix-blend-overlay pointer-events-none`}></div>
    </div>
  );
};

export default AgentCard;
