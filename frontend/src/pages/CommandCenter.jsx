import { useMemo, useCallback, useState } from 'react';
import { useCommsStore } from '../stores/useCommsStore';
import CommsLayer from '../components/command/CommsLayer';
import { useOrchestrationStream } from '../hooks/useOrchestrationStream';
import ActivityGrid from '../components/command/ActivityGrid';
import { ReactFlow, Background, BackgroundVariant, Controls, MiniMap } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, Boxes, LayoutGrid, Radio } from 'lucide-react';
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
  const { agents, loading } = useAgents();
  const openWindow = useCommsStore((s) => s.openWindow);
  const [view, setView] = useState('chart');
  const { statuses, connected } = useOrchestrationStream();

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

  const onNodeClick = useCallback(
    (_, node) => {
      const agent = tree.byId.get(node.id);
      if (agent) openWindow(agent);
    },
    [tree, openWindow]
  );

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
        <div className="ml-auto flex items-center gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-0.5">
            <button
              onClick={() => setView('chart')}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                view === 'chart' ? 'bg-unicorn-500/20 text-unicorn-200' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Network className="h-3.5 w-3.5" /> Org Chart
            </button>
            <button
              onClick={() => setView('activity')}
              className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                view === 'activity' ? 'bg-unicorn-500/20 text-unicorn-200' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5" /> Activity
            </button>
          </div>
          <div
            className="flex items-center gap-1.5 text-xs text-slate-400"
            title={connected ? 'Live feed connected' : 'Live feed offline'}
          >
            <Radio className={`h-3.5 w-3.5 ${connected ? 'text-emerald-400' : 'text-slate-600'}`} />
            <Boxes className="h-4 w-4" />
            {loading ? '…' : agents.length}
          </div>
        </div>
      </div>

      {/* Canvas — org chart or live activity; comms windows float over both */}
      <div className="relative flex-1">
        {view === 'chart' ? (
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
        ) : (
          <ActivityGrid agents={agents} statuses={statuses} onOpen={openWindow} />
        )}
        <CommsLayer />
      </div>
    </div>
  );
}
