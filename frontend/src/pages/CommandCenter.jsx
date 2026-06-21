import { useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { ReactFlow, Background, BackgroundVariant, Controls, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, Boxes } from 'lucide-react';
import { useAgents } from '../hooks/useAgents';
import { buildOrgTree } from '../utils/orgTree';
import { useOrgLayout } from '../hooks/useOrgLayout';
import OrgAgentNode from '../components/command/OrgAgentNode';

const nodeTypes = { orgAgent: OrgAgentNode };

/**
 * Command Center — "The General's War Room".
 * The whole Brigade as a top-down org chart of real agent faces. Click any
 * agent to open comms (today: jump to /chat?agent=; soon: a floating dock).
 * Phase 1 = static chart (dagre layout, resting chain-of-command edges).
 */
export default function CommandCenter() {
  const navigate = useNavigate();
  const { agents, loading } = useAgents();

  const tree = useMemo(() => buildOrgTree(agents), [agents]);

  const rawNodes = useMemo(
    () =>
      tree.agents.map((a) => ({
        id: a.id,
        type: 'orgAgent',
        position: { x: 0, y: 0 },
        data: { agent: a, isRoot: a.id === tree.root?.id, status: 'idle' },
      })),
    [tree]
  );

  const edges = useMemo(
    () =>
      tree.edgesResting.map((e) => ({
        ...e,
        type: 'smoothstep',
        animated: false,
        style: { stroke: '#475569', strokeWidth: 1.5 },
      })),
    [tree]
  );

  const nodes = useOrgLayout(rawNodes, edges);

  const onNodeClick = useCallback((_, node) => navigate(`/chat?agent=${node.id}`), [navigate]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* HUD header */}
      <div className="flex items-center gap-3 border-b border-slate-800 px-6 py-3.5">
        <div className="rounded-xl border border-unicorn-500/30 bg-gradient-to-br from-unicorn-500/30 to-purple-600/20 p-2">
          <Network className="h-5 w-5 text-unicorn-300" />
        </div>
        <div>
          <h1 className="text-gradient text-xl font-bold leading-tight">Command Center</h1>
          <p className="text-xs text-slate-400">
            The General&apos;s War Room — click any agent to open comms
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-400">
          <Boxes className="h-4 w-4" />
          {loading ? 'loading…' : `${agents.length} agents`}
        </div>
      </div>

      {/* Org-chart canvas */}
      <div className="relative flex-1">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={onNodeClick}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          minZoom={0.2}
          maxZoom={1.6}
          nodesDraggable={false}
          proOptions={{ hideAttribution: true }}
          className="bg-transparent"
        >
          <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1e293b" />
          <Controls showInteractive={false} className="!border-slate-700 !bg-slate-800/80" />
          <MiniMap
            pannable
            zoomable
            nodeColor="#7c3aed"
            maskColor="rgba(2,6,23,0.7)"
            className="!border-slate-700 !bg-slate-900"
          />
        </ReactFlow>
      </div>
    </div>
  );
}
