/**
 * MiniWorkflowDiagram - Compact workflow preview for cards
 *
 * Displays a simplified, non-interactive diagram of workflow steps
 * Perfect for gallery cards and previews
 */

import { useMemo } from 'react';
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Crown,
  Users,
  Hammer,
  PauseCircle,
} from 'lucide-react';

// Compact node component for mini view
const MiniStepNode = ({ data }) => {
  const getIcon = () => {
    switch (data.type) {
      case 'orchestrator':
        return <Crown className="w-3 h-3" />;
      case 'team-lead':
        return <Users className="w-3 h-3" />;
      case 'worker':
        return <Hammer className="w-3 h-3" />;
      case 'checkpoint':
        return <PauseCircle className="w-3 h-3" />;
      default:
        return null;
    }
  };

  const getNodeColor = () => {
    switch (data.type) {
      case 'orchestrator':
        return 'from-unicorn-500/30 to-unicorn-500/30 border-unicorn-500/50';
      case 'team-lead':
        return 'from-blue-500/30 to-cyan-500/30 border-blue-500/50';
      case 'worker':
        return 'from-emerald-500/30 to-green-500/30 border-emerald-500/50';
      case 'checkpoint':
        return 'from-amber-500/30 to-orange-500/30 border-amber-500/50';
      default:
        return 'from-slate-700/30 to-slate-600/30 border-slate-600/50';
    }
  };

  return (
    <div className={`px-2 py-1.5 rounded border bg-gradient-to-br ${getNodeColor()} w-[80px]`}>
      <div className="flex items-center gap-1 justify-center">
        <div className="text-unicorn-400">
          {getIcon()}
        </div>
        <div className="text-[9px] text-white font-medium truncate">{data.label}</div>
      </div>
    </div>
  );
};

const nodeTypes = {
  miniStepNode: MiniStepNode,
};

const MiniWorkflowDiagram = ({ workflow, height = '120px' }) => {
  // Convert workflow steps to compact nodes
  const initialNodes = useMemo(() => {
    if (!workflow || !workflow.steps) return [];

    const steps = workflow.steps.slice(0, 6); // Show max 6 steps for preview

    return steps.map((step, index) => {
      let nodeType = 'default';
      if (step.executor === 'orchestrator') nodeType = 'orchestrator';
      else if (step.executor?.includes('lead')) nodeType = 'team-lead';
      else if (step.executor?.includes('worker')) nodeType = 'worker';

      const hasCheckpoint = step.checkpoints && step.checkpoints.length > 0;

      // Compact horizontal layout
      const nodeWidth = 90;
      const x = index * nodeWidth;
      const y = 0;

      return {
        id: step.id || `step-${index}`,
        type: 'miniStepNode',
        position: { x, y },
        data: {
          label: step.name.length > 8 ? step.name.slice(0, 8) + '...' : step.name,
          type: hasCheckpoint ? 'checkpoint' : nodeType,
        },
      };
    });
  }, [workflow]);

  // Convert workflow steps to edges
  const initialEdges = useMemo(() => {
    if (!workflow || !workflow.steps) return [];

    const steps = workflow.steps.slice(0, 6);

    return steps.slice(0, -1).map((step, index) => ({
      id: `e${index}`,
      source: step.id || `step-${index}`,
      target: steps[index + 1].id || `step-${index + 1}`,
      type: 'smoothstep',
      style: {
        stroke: '#6366f1',
        strokeWidth: 1.5,
      },
      markerEnd: {
        type: 'arrowclosed',
        color: '#6366f1',
        width: 12,
        height: 12,
      },
    }));
  }, [workflow]);

  const [nodes] = useNodesState(initialNodes);
  const [edges] = useEdgesState(initialEdges);

  if (!workflow || !workflow.steps || workflow.steps.length === 0) {
    return (
      <div
        className="flex items-center justify-center bg-slate-900/50 rounded-lg border border-slate-700/50"
        style={{ height }}
      >
        <div className="text-xs text-slate-400">No workflow steps</div>
      </div>
    );
  }

  return (
    <div
      className="bg-slate-900/50 rounded-lg border border-slate-700/50 overflow-hidden"
      style={{ height }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.1, minZoom: 0.8, maxZoom: 0.8 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        zoomOnDoubleClick={false}
        preventScrolling={true}
        attributionPosition="bottom-right"
        className="bg-slate-900/50"
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant="dots"
          gap={12}
          size={0.8}
          color="#475569"
          className="bg-slate-900/50"
        />
      </ReactFlow>
      {workflow.steps.length > 6 && (
        <div className="absolute bottom-1 right-2 text-[10px] text-slate-400 bg-slate-900/80 px-1.5 py-0.5 rounded">
          +{workflow.steps.length - 6} more
        </div>
      )}
    </div>
  );
};

export default MiniWorkflowDiagram;
