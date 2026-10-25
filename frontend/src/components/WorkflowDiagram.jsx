/**
 * WorkflowDiagram — the full, interactive step diagram (xyflow) for a
 * workflow's detail view, with live execution state on each node.
 */
import { useEffect, useMemo } from 'react';
import { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { GitBranch } from 'lucide-react';
import { tokenHsl } from '../utils/tokens';
import { STEP_KIND, stepKind } from './MiniWorkflowDiagram';
import { Chip, StatusDot, EmptyState } from './ui';

const STATE_DOT = { completed: 'done', running: 'tool', failed: 'error', skipped: 'offline' };

const StepNode = ({ data }) => {
  const kind = STEP_KIND[data.kind] || STEP_KIND.default;
  const Icon = kind.icon;
  const dot = STATE_DOT[data.state];
  const live = data.state === 'running';
  return (
    <div className={`w-[260px] rounded-card border bg-card p-3 shadow-e1 ${kind.cls} ${live ? 'ring-2 ring-ring/60' : ''}`}>
      <div className="mb-1 flex items-center gap-2">
        <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-body-sm font-semibold text-fg-strong">{data.label}</span>
        {dot && <StatusDot status={dot} size="md" />}
      </div>
      {data.description && <p className="mb-1.5 text-caption text-muted">{data.description}</p>}
      {data.executor && <code className="block truncate font-mono text-caption text-muted">{data.executor}</code>}
      {data.outputs && data.outputs.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {data.outputs.slice(0, 3).map((o) => (
            <Chip key={o} size="xs">
              {o}
            </Chip>
          ))}
          {data.outputs.length > 3 && <Chip size="xs">+{data.outputs.length - 3}</Chip>}
        </div>
      )}
    </div>
  );
};

const nodeTypes = { stepNode: StepNode };

export default function WorkflowDiagram({ workflow, executionState = {}, className = '' }) {
  const colors = useMemo(
    () => ({
      edge: tokenHsl('--border-strong'),
      done: tokenHsl('--ok'),
      dot: tokenHsl('--border'),
      mask: tokenHsl('--bg', 0.85),
      kind: {
        orchestrator: tokenHsl('--accent'),
        'team-lead': tokenHsl('--info'),
        worker: tokenHsl('--ok'),
        checkpoint: tokenHsl('--warn'),
        default: tokenHsl('--muted'),
      },
    }),
    []
  );
  const steps = workflow?.steps || [];

  const initialNodes = useMemo(
    () =>
      steps.map((step, index) => ({
        id: step.id,
        type: 'stepNode',
        position: { x: index * 380, y: 200 },
        data: {
          label: step.name,
          description: step.description,
          executor: step.executor,
          outputs: step.outputs,
          kind: stepKind(step),
          state: executionState[step.id] || 'pending',
        },
      })),
    [steps, executionState]
  );
  const initialEdges = useMemo(
    () =>
      steps.slice(0, -1).map((step, index) => {
        const done = executionState[step.id] === 'completed';
        return {
          id: `e${index}`,
          source: step.id,
          target: steps[index + 1].id,
          type: 'smoothstep',
          animated: executionState[step.id] === 'running',
          style: { stroke: done ? colors.done : colors.edge, strokeWidth: 2 },
          markerEnd: { type: 'arrowclosed', color: done ? colors.done : colors.edge },
        };
      }),
    [steps, executionState, colors]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes]);
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges]);

  if (!workflow || steps.length === 0) {
    return (
      <div className={`rounded-card border border-border bg-surface ${className}`}>
        <EmptyState compact icon={GitBranch} title="No steps to draw" description="This workflow has no steps defined yet." />
      </div>
    );
  }

  return (
    <div className={`h-[520px] overflow-hidden rounded-card border border-border bg-surface ${className}`}>
      <ReactFlow
        key={workflow.id || 'workflow'}
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        defaultEdgeOptions={{ style: { strokeWidth: 2 }, type: 'smoothstep' }}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant="dots" gap={20} size={1.5} color={colors.dot} />
        <Controls showInteractive={false} />
        <MiniMap nodeColor={(n) => colors.kind[n.data?.kind] || colors.kind.default} maskColor={colors.mask} pannable zoomable />
      </ReactFlow>
    </div>
  );
}
