/**
 * MiniWorkflowDiagram — a compact, non-interactive preview of a workflow's
 * steps for cards. Renders nothing when there are no steps; the card decides
 * what to show instead (a stage strip), so there is never an empty grey box.
 */
import { useEffect, useMemo } from 'react';
import { ReactFlow, Background, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Crown, Users, Hammer, PauseCircle } from 'lucide-react';
import { tokenHsl } from '../utils/tokens';
import { Chip } from './ui';

export const STEP_KIND = {
  orchestrator: { icon: Crown, cls: 'border-accent/50 text-accent', label: 'Orchestrator' },
  'team-lead': { icon: Users, cls: 'border-info/50 text-info', label: 'Team lead' },
  worker: { icon: Hammer, cls: 'border-ok/50 text-ok', label: 'Worker' },
  checkpoint: { icon: PauseCircle, cls: 'border-warn/50 text-warn', label: 'Checkpoint' },
  default: { icon: Hammer, cls: 'border-border-strong text-muted', label: 'Step' },
};

/** orchestrator | team-lead | worker | checkpoint | default — from a step definition. */
export function stepKind(step) {
  if (step?.checkpoints && step.checkpoints.length > 0) return 'checkpoint';
  const ex = step?.executor || '';
  if (ex === 'orchestrator') return 'orchestrator';
  if (ex.includes('lead')) return 'team-lead';
  if (ex.includes('worker')) return 'worker';
  return 'default';
}

const MiniStepNode = ({ data }) => {
  const kind = STEP_KIND[data.kind] || STEP_KIND.default;
  const Icon = kind.icon;
  return (
    <div className={`w-[96px] rounded-chip border bg-elevated/90 px-2 py-1 ${kind.cls}`}>
      <div className="flex items-center justify-center gap-1">
        <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />
        <span className="truncate text-micro font-medium text-fg">{data.label}</span>
      </div>
    </div>
  );
};

const nodeTypes = { miniStepNode: MiniStepNode };
const MAX = 6;

export default function MiniWorkflowDiagram({ workflow, height = 120, className = '' }) {
  const colors = useMemo(() => ({ edge: tokenHsl('--border-strong'), dot: tokenHsl('--border') }), []);
  const steps = useMemo(() => (workflow?.steps || []).slice(0, MAX), [workflow]);

  const initialNodes = useMemo(
    () =>
      steps.map((step, index) => ({
        id: step.id || `step-${index}`,
        type: 'miniStepNode',
        position: { x: index * 108, y: 0 },
        data: { label: step.name, kind: stepKind(step) },
      })),
    [steps]
  );
  const initialEdges = useMemo(
    () =>
      steps.slice(0, -1).map((step, index) => ({
        id: `e${index}`,
        source: step.id || `step-${index}`,
        target: steps[index + 1].id || `step-${index + 1}`,
        type: 'smoothstep',
        style: { stroke: colors.edge, strokeWidth: 1.5 },
        markerEnd: { type: 'arrowclosed', color: colors.edge, width: 12, height: 12 },
      })),
    [steps, colors]
  );

  const [nodes, setNodes] = useNodesState(initialNodes);
  const [edges, setEdges] = useEdgesState(initialEdges);
  useEffect(() => setNodes(initialNodes), [initialNodes, setNodes]);
  useEffect(() => setEdges(initialEdges), [initialEdges, setEdges]);

  if (steps.length === 0) return null;
  const total = workflow.steps.length;

  return (
    <div className={`relative overflow-hidden bg-surface/60 ${className}`} style={{ height }} aria-label={`${total} workflow steps`} role="img">
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
        panOnDrag={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant="dots" gap={12} size={0.8} color={colors.dot} />
      </ReactFlow>
      {total > MAX && (
        <span className="absolute bottom-1.5 right-2">
          <Chip size="xs">+{total - MAX} more</Chip>
        </span>
      )}
    </div>
  );
}
