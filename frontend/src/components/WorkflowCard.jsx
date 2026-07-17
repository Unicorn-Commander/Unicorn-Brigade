/**
 * WorkflowCard - Visual workflow card with preview diagram
 *
 * Displays workflow information with:
 * - Miniature workflow diagram
 * - Key stats (steps, inputs, checkpoints, cost)
 * - Domain tags and badges
 * - Quick actions (view details, execute)
 */

import {
  Play,
  Eye,
  FileText,
  PauseCircle,
  DollarSign,
  Clock,
  Users,
  GitBranch,
  Zap,
  TrendingUp,
} from 'lucide-react';
import MiniWorkflowDiagram from './MiniWorkflowDiagram';

// Tag colors (same as Workflows.jsx)
const tagColors = {
  finance: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  research: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  sales: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  devops: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  content: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  legal: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  medical: 'bg-red-500/20 text-red-400 border-red-500/30',
  investment: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  marketing: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  seo: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
  incident: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  monitoring: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  analysis: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  documents: 'bg-lime-500/20 text-lime-400 border-lime-500/30',
  compliance: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  outreach: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  documentation: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

// Domain icons
const domainIcons = {
  research: '🔍',
  finance: '💰',
  content: '📝',
  sales: '💼',
  devops: '⚙️',
  legal: '⚖️',
  medical: '🏥',
  investigation: '🕵️',
};

// Estimated cost per preset
const presetCostEstimates = {
  cost_optimized: { estimate: '$0.02-0.05', description: 'Uses local models for team leads/workers' },
  balanced: { estimate: '$0.10-0.20', description: 'Mix of API and local models' },
  quality_focused: { estimate: '$0.30-0.50', description: 'Uses premium API models' },
  speed_focused: { estimate: '$0.15-0.25', description: 'Fast API models' },
  local_only: { estimate: 'Free', description: 'All local models (slower)' },
};

const WorkflowCard = ({
  workflow,
  onViewDetails,
  onExecute,
  showDiagram = true,
  compact = false,
}) => {
  if (!workflow) return null;

  // Extract primary domain from tags
  const primaryDomain = (workflow.tags || []).find(tag =>
    ['research', 'finance', 'content', 'sales', 'devops', 'legal', 'medical', 'investigation'].includes(tag)
  );
  const domainIcon = primaryDomain ? domainIcons[primaryDomain] : '🔄';

  // Get cost estimate (default to cost_optimized)
  const costInfo = presetCostEstimates['cost_optimized'];

  // Calculate complexity based on steps and checkpoints
  const stepCount = workflow.step_count || workflow.stepCount || (workflow.steps?.length || 0);
  const checkpointCount = workflow.checkpoint_count || workflow.checkpointCount || 0;
  const inputCount = (workflow.required_inputs || workflow.requiredInputs || []).length;

  const getComplexityLabel = () => {
    if (stepCount <= 3 && checkpointCount === 0) return { label: 'Simple', color: 'text-emerald-400' };
    if (stepCount <= 5 && checkpointCount <= 1) return { label: 'Moderate', color: 'text-blue-400' };
    return { label: 'Complex', color: 'text-amber-400' };
  };

  const complexity = getComplexityLabel();

  // Count unique team leads
  const teamLeadCount = workflow.team_leads?.length || workflow.teamLeads?.length || 0;

  return (
    <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden hover:border-unicorn-500/50 transition-all group">
      {/* Diagram Preview */}
      {showDiagram && !compact && (
        <div className="relative">
          <MiniWorkflowDiagram workflow={workflow} height="140px" />
          {/* Overlay gradient for depth */}
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent pointer-events-none"></div>
        </div>
      )}

      {/* Card Content */}
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start gap-3 mb-3">
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-unicorn-500/20 to-unicorn-500/20 border border-unicorn-500/30 flex items-center justify-center text-2xl flex-shrink-0">
            {domainIcon}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white group-hover:text-unicorn-400 transition-colors line-clamp-1">
              {workflow.name}
            </h3>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-slate-400 flex items-center gap-1">
                <GitBranch className="w-3 h-3" />
                {stepCount} steps
              </span>
              <span className={`text-xs ${complexity.color} flex items-center gap-1`}>
                <TrendingUp className="w-3 h-3" />
                {complexity.label}
              </span>
              {primaryDomain && (
                <span className={`px-1.5 py-0.5 rounded text-[10px] border ${tagColors[primaryDomain] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'}`}>
                  {primaryDomain}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Description */}
        <p className="text-sm text-slate-400 mb-4 line-clamp-2 leading-relaxed">
          {workflow.description}
        </p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {(workflow.tags || [])
            .filter(t => t !== primaryDomain)
            .slice(0, 3)
            .map(tag => (
              <span
                key={tag}
                className={`px-2 py-0.5 rounded text-xs border ${tagColors[tag] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'}`}
              >
                {tag}
              </span>
            ))}
          {(workflow.tags || []).filter(t => t !== primaryDomain).length > 3 && (
            <span className="px-2 py-0.5 rounded bg-slate-800 text-xs text-slate-400">
              +{(workflow.tags || []).filter(t => t !== primaryDomain).length - 3}
            </span>
          )}
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2 mb-4">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40">
            <FileText className="w-3.5 h-3.5 text-slate-400" />
            <div>
              <div className="text-xs text-slate-400">Inputs</div>
              <div className="text-sm font-medium text-white">{inputCount}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40">
            <PauseCircle className="w-3.5 h-3.5 text-slate-400" />
            <div>
              <div className="text-xs text-slate-400">Checkpoints</div>
              <div className="text-sm font-medium text-white">{checkpointCount}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40">
            <Users className="w-3.5 h-3.5 text-slate-400" />
            <div>
              <div className="text-xs text-slate-400">Team Leads</div>
              <div className="text-sm font-medium text-white">{teamLeadCount}</div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-slate-800/40">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
            <div>
              <div className="text-xs text-slate-400">Est. Cost</div>
              <div className="text-sm font-medium text-emerald-400">{costInfo.estimate}</div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onViewDetails(workflow)}
            className="flex-1 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm font-medium"
          >
            <Eye className="w-4 h-4" />
            <span>Details</span>
          </button>
          <button
            onClick={() => onExecute(workflow)}
            className="flex-1 px-3 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center justify-center gap-2 text-sm font-medium"
          >
            <Play className="w-4 h-4" />
            <span>Run</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default WorkflowCard;
