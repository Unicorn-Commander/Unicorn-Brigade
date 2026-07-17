/**
 * WorkflowDiagram - Visual workflow step diagram using Xyflow
 *
 * Displays workflow steps as an interactive flow diagram with:
 * - Orchestrator, Team Lead, Worker, and Checkpoint nodes
 * - Step-by-step connections
 * - Real-time execution progress
 * - Minimap and controls
 */

import { useCallback, useMemo, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Crown,
  Users,
  Hammer,
  PauseCircle,
  CheckCircle,
  Clock,
  Play,
  XCircle
} from 'lucide-react';

// Custom node component for workflow steps
const StepNode = ({ data }) => {
  const getIcon = () => {
    switch (data.type) {
      case 'orchestrator':
        return <Crown className="w-5 h-5" />;
      case 'team-lead':
        return <Users className="w-5 h-5" />;
      case 'worker':
        return <Hammer className="w-5 h-5" />;
      case 'checkpoint':
        return <PauseCircle className="w-5 h-5" />;
      default:
        return <Play className="w-5 h-5" />;
    }
  };

  const getStateIcon = () => {
    switch (data.state) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'running':
        return <Clock className="w-4 h-4 text-blue-400 animate-spin" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-400" />;
      default:
        return null;
    }
  };

  const getNodeStyle = () => {
    const baseClasses = "px-4 py-3 rounded-lg border-2 w-[260px] transition-all shadow-lg";

    switch (data.type) {
      case 'orchestrator':
        return `${baseClasses} bg-gradient-to-br from-unicorn-500/20 to-unicorn-500/20 border-unicorn-500/50`;
      case 'team-lead':
        return `${baseClasses} bg-gradient-to-br from-blue-500/20 to-cyan-500/20 border-blue-500/50`;
      case 'worker':
        return `${baseClasses} bg-gradient-to-br from-emerald-500/20 to-green-500/20 border-emerald-500/50`;
      case 'checkpoint':
        return `${baseClasses} bg-gradient-to-br from-amber-500/20 to-orange-500/20 border-amber-500/50`;
      default:
        return `${baseClasses} bg-slate-800/50 border-slate-600`;
    }
  };

  const isActive = data.state === 'running' || data.state === 'completed';

  return (
    <div className={`${getNodeStyle()} ${isActive ? 'ring-2 ring-unicorn-400/50' : ''}`}>
      <div className="flex items-center gap-2 mb-1">
        <div className={`${data.type === 'checkpoint' ? 'text-amber-400' : 'text-unicorn-400'}`}>
          {getIcon()}
        </div>
        <div className="font-semibold text-white text-sm flex-1">{data.label}</div>
        {getStateIcon()}
      </div>
      {data.description && (
        <div className="text-xs text-slate-400 mb-2">{data.description}</div>
      )}
      {data.executor && (
        <div className="text-xs text-slate-500 font-mono">{data.executor}</div>
      )}
      {data.outputs && data.outputs.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {data.outputs.slice(0, 3).map((output, idx) => (
            <span
              key={idx}
              className="px-1.5 py-0.5 bg-slate-700/50 rounded text-[10px] text-slate-300"
            >
              {output}
            </span>
          ))}
          {data.outputs.length > 3 && (
            <span className="px-1.5 py-0.5 bg-slate-700/50 rounded text-[10px] text-slate-300">
              +{data.outputs.length - 3}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

// Custom node types
const nodeTypes = {
  stepNode: StepNode,
};

const WorkflowDiagram = ({ workflow, executionState = {} }) => {
  // Convert workflow steps to nodes
  const initialNodes = useMemo(() => {
    if (!workflow || !workflow.steps) return [];

    const nodes = workflow.steps.map((step, index) => {
      const stepState = executionState[step.id] || 'pending';

      // Determine node type based on executor
      let nodeType = 'default';
      if (step.executor === 'orchestrator') nodeType = 'orchestrator';
      else if (step.executor?.includes('lead')) nodeType = 'team-lead';
      else if (step.executor?.includes('worker')) nodeType = 'worker';

      // Check if this step has a checkpoint
      const hasCheckpoint = step.checkpoints && step.checkpoints.length > 0;

      // Layout: horizontal flow with spacing
      const nodeWidth = 280;
      const nodeSpacing = 100;
      const x = index * (nodeWidth + nodeSpacing);
      const y = 200; // Center vertically

      return {
        id: step.id,
        type: 'stepNode',
        position: { x, y },
        data: {
          label: step.name,
          description: step.description,
          executor: step.executor,
          outputs: step.outputs,
          type: hasCheckpoint ? 'checkpoint' : nodeType,
          state: stepState,
        },
      };
    });

    return nodes;
  }, [workflow, executionState]);

  // Convert workflow steps to edges
  const initialEdges = useMemo(() => {
    if (!workflow || !workflow.steps) return [];

    return workflow.steps.slice(0, -1).map((step, index) => ({
      id: `e${index}`,
      source: step.id,
      target: workflow.steps[index + 1].id,
      type: 'smoothstep',
      animated: executionState[step.id] === 'running',
      style: {
        stroke: executionState[step.id] === 'completed' ? '#10b981' : '#6366f1',
        strokeWidth: 2,
      },
      markerEnd: {
        type: 'arrowclosed',
        color: executionState[step.id] === 'completed' ? '#10b981' : '#6366f1',
      },
    }));
  }, [workflow, executionState]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  if (!workflow) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-slate-900/50 rounded-lg border border-slate-700">
        <div className="text-center">
          <Play className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">Select a workflow to view diagram</p>
        </div>
      </div>
    );
  }

  if (!workflow.steps || workflow.steps.length === 0) {
    return (
      <div className="h-[600px] flex items-center justify-center bg-slate-900/50 rounded-lg border border-slate-700">
        <div className="text-center">
          <Play className="w-16 h-16 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">Workflow has no steps</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[600px] bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
      <ReactFlow
        key={workflow?.id || 'default'}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-right"
        className="bg-slate-900"
        defaultEdgeOptions={{
          style: { strokeWidth: 2 },
          type: 'smoothstep',
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant="dots"
          gap={20}
          size={1.5}
          color="#475569"
          className="bg-slate-900"
        />
        <Controls
          className="bg-slate-800/90 border border-slate-700 rounded-lg shadow-xl"
          showInteractive={false}
        />
        <MiniMap
          nodeColor={(node) => {
            switch (node.data.type) {
              case 'orchestrator':
                return '#a855f7';
              case 'team-lead':
                return '#3b82f6';
              case 'worker':
                return '#10b981';
              case 'checkpoint':
                return '#f59e0b';
              default:
                return '#64748b';
            }
          }}
          className="bg-slate-800/90 border border-slate-700 rounded-lg shadow-xl"
          maskColor="rgba(15, 23, 42, 0.9)"
        />
      </ReactFlow>
    </div>
  );
};

export default WorkflowDiagram;
