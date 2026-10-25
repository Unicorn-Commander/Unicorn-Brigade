/**
 * WorkflowGallery — the templates grid or list, with all four states in the
 * place the content goes. A filtered-to-nothing empty is its own compact state.
 */
import { GitBranch, Search, X, RefreshCw } from 'lucide-react';
import WorkflowCard from './WorkflowCard';
import { Button, EmptyState, ErrorState, LoadingState } from './ui';

export default function WorkflowGallery({ workflows = [], viewMode = 'grid', loading = false, error = null, onRetry, onViewDetails, onExecute, busyId = null, hasFilters = false, onClearFilters }) {
  if (loading) return <LoadingState variant={viewMode === 'grid' ? 'cards' : 'list'} count={6} label="Loading workflows" />;
  if (error) return <ErrorState title="Couldn’t load the workflow templates" detail={error} onRetry={onRetry} />;
  if (workflows.length === 0) {
    if (hasFilters) {
      return (
        <EmptyState
          compact
          icon={Search}
          title="No workflows match"
          description="Try another word, or clear the tag and complexity filters."
          action={
            <Button variant="secondary" size="sm" icon={X} onClick={onClearFilters}>
              Clear filters
            </Button>
          }
        />
      );
    }
    return (
      <EmptyState
        icon={GitBranch}
        title="No workflow templates yet"
        description="Templates are registered by the workflow engine on the server. When it has one, it appears here ready to run."
        action={
          onRetry && (
            <Button variant="secondary" icon={RefreshCw} onClick={onRetry}>
              Check again
            </Button>
          )
        }
      />
    );
  }

  if (viewMode === 'list') {
    return (
      <ul className="space-y-3 animate-fade-in" aria-label="Workflow templates">
        {workflows.map((w) => (
          <li key={w.id}>
            <WorkflowCard workflow={w} layout="list" busy={busyId === w.id} onViewDetails={onViewDetails} onExecute={onExecute} />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul className="grid grid-cols-1 gap-4 animate-fade-in sm:grid-cols-2 xl:grid-cols-3" aria-label="Workflow templates">
      {workflows.map((w) => (
        <li key={w.id}>
          <WorkflowCard workflow={w} layout="grid" busy={busyId === w.id} onViewDetails={onViewDetails} onExecute={onExecute} />
        </li>
      ))}
    </ul>
  );
}
