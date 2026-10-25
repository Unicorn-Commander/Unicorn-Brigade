import { useMemo } from 'react';
import { ReactFlow, Controls, Background, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Database, FileText, MessageSquare, Sparkles, User, Wrench } from 'lucide-react';
import { tokenHsl } from '../utils/tokens';
import { SectionHeader } from './ui';

// One tone per stage, drawn from the status tokens so the graph follows the
// theme like every other surface.
const TONE = {
  info: 'bg-info/10 text-info border-info/30',
  accent: 'bg-accent/10 text-accent border-accent/30',
  live: 'bg-live/10 text-live border-live/30',
  ok: 'bg-ok/10 text-ok border-ok/30',
};

function StageNode({ data }) {
  const Icon = data.icon;
  return (
    <div className={`w-56 rounded-card border bg-card p-3 shadow-e2 ${data.large ? 'w-64' : ''}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-control border ${TONE[data.tone] || TONE.info}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <p className="truncate text-body font-semibold text-fg-strong">{data.label}</p>
          {data.details?.map((d, i) => (
            <p key={i} className="truncate text-caption text-muted">
              {d}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

const nodeTypes = { stage: StageNode };

/**
 * AgentArchitectureDiagram — how a request moves through this agent:
 * input → system prompt → model → tools / memory → response. Read-only;
 * pan and zoom with the controls.
 */
export default function AgentArchitectureDiagram({ agent }) {
  const tools = Array.isArray(agent?.toolDetails) && agent.toolDetails.length ? agent.toolDetails.map((t) => t.displayName || t.name) : Array.isArray(agent?.tools) ? agent.tools : [];

  const nodes = useMemo(
    () => [
      { id: 'input', type: 'stage', position: { x: 260, y: 0 }, data: { label: 'Request', icon: User, tone: 'info', details: ['From chat, comms or the API'] } },
      {
        id: 'prompt',
        type: 'stage',
        position: { x: 260, y: 120 },
        data: { label: 'System prompt', icon: FileText, tone: 'accent', details: [agent?.systemPrompt ? `${agent.systemPrompt.slice(0, 48)}…` : 'No prompt set'] },
      },
      {
        id: 'model',
        type: 'stage',
        position: { x: 244, y: 240 },
        data: {
          label: agent?.model || 'Model',
          icon: Sparkles,
          tone: 'accent',
          large: true,
          details: [`Temperature ${agent?.temperature ?? 0.7}`, `Max tokens ${(agent?.maxTokens ?? 4096).toLocaleString()}`],
        },
      },
      {
        id: 'tools',
        type: 'stage',
        position: { x: 40, y: 380 },
        data: { label: `Tools (${tools.length})`, icon: Wrench, tone: 'live', details: [tools.length ? tools.slice(0, 3).join(', ') + (tools.length > 3 ? ` +${tools.length - 3}` : '') : 'None attached'] },
      },
      { id: 'memory', type: 'stage', position: { x: 480, y: 380 }, data: { label: 'Memory', icon: Database, tone: 'ok', details: ['Conversation context'] } },
      { id: 'out', type: 'stage', position: { x: 260, y: 500 }, data: { label: 'Response', icon: MessageSquare, tone: 'ok', details: ['Streamed back to the caller'] } },
    ],
    [agent, tools]
  );

  const edges = useMemo(() => {
    const stroke = tokenHsl('--border-strong');
    const mk = (source, target) => ({
      id: `${source}-${target}`,
      source,
      target,
      animated: true,
      style: { stroke, strokeWidth: 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
    });
    return [mk('input', 'prompt'), mk('prompt', 'model'), mk('model', 'tools'), mk('model', 'memory'), mk('tools', 'out'), mk('memory', 'out')];
  }, []);

  return (
    <div className="space-y-4">
      <SectionHeader title="Architecture" description={`How ${agent?.displayName || agent?.name || 'this agent'} handles a request`} />
      <div className="h-[520px] overflow-hidden rounded-card border border-border bg-surface">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color={tokenHsl('--border', 0.7)} gap={18} size={1} variant="dots" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}
