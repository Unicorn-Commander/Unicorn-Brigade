/**
 * WorkflowGallery - Responsive grid gallery for workflow cards
 *
 * Features:
 * - Responsive grid layout (1-3 columns based on screen size)
 * - List view alternative
 * - Loading states
 * - Empty states
 * - Smooth transitions
 */

import { GitBranch } from 'lucide-react';
import WorkflowCard from './WorkflowCard';
import CardSkeleton from './skeletons/CardSkeleton';
import ListSkeleton from './skeletons/ListSkeleton';

const WorkflowGallery = ({
  workflows,
  viewMode = 'grid',
  loading = false,
  onViewDetails,
  onExecute,
}) => {
  // Loading State
  if (loading) {
    return (
      <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6' : ''}>
        {viewMode === 'grid' ? <CardSkeleton count={6} /> : <ListSkeleton rows={6} />}
      </div>
    );
  }

  // Empty State
  if (!workflows || workflows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <div className="w-20 h-20 rounded-full bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30 flex items-center justify-center mb-4">
          <GitBranch className="w-10 h-10 text-purple-400" />
        </div>
        <h3 className="text-xl font-semibold text-slate-300 mb-2">
          No workflows found
        </h3>
        <p className="text-slate-400 text-center max-w-md">
          Try adjusting your filters or search query to find workflows
        </p>
      </div>
    );
  }

  // Grid View
  if (viewMode === 'grid') {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fadeIn">
        {workflows.map((workflow) => (
          <WorkflowCard
            key={workflow.id}
            workflow={workflow}
            onViewDetails={onViewDetails}
            onExecute={onExecute}
            showDiagram={true}
            compact={false}
          />
        ))}
      </div>
    );
  }

  // List View
  return (
    <div className="space-y-4 animate-fadeIn">
      {workflows.map((workflow) => (
        <div
          key={workflow.id}
          className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden hover:border-purple-500/50 transition-all"
        >
          <div className="flex items-stretch">
            {/* Diagram Preview (smaller in list view) */}
            <div className="w-64 flex-shrink-0 bg-slate-900/50 relative">
              <WorkflowCard
                workflow={workflow}
                onViewDetails={onViewDetails}
                onExecute={onExecute}
                showDiagram={false}
                compact={true}
              />
            </div>

            {/* Workflow Details */}
            <div className="flex-1 p-6 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-xl font-semibold text-white group-hover:text-purple-400 transition-colors">
                      {workflow.name}
                    </h3>
                    <p className="text-sm text-slate-400 mt-1">
                      {workflow.description}
                    </p>
                  </div>
                </div>

                {/* Tags */}
                <div className="flex flex-wrap gap-2 mt-3">
                  {(workflow.tags || []).slice(0, 6).map(tag => (
                    <span
                      key={tag}
                      className="px-2.5 py-1 rounded-lg text-xs border bg-slate-800/50 text-slate-300 border-slate-700"
                    >
                      {tag}
                    </span>
                  ))}
                  {(workflow.tags || []).length > 6 && (
                    <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-xs text-slate-400">
                      +{(workflow.tags || []).length - 6} more
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-3 mt-4">
                <button
                  onClick={() => onViewDetails(workflow)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors flex items-center gap-2 text-sm font-medium"
                >
                  <span>View Details</span>
                </button>
                <button
                  onClick={() => onExecute(workflow)}
                  className="px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-colors flex items-center gap-2 text-sm font-medium"
                >
                  <span>Execute Workflow</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default WorkflowGallery;
