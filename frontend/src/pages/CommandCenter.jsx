import { useMemo, useCallback, useState, useEffect, useRef, lazy, Suspense } from 'react';
import { useCommsStore } from '../stores/useCommsStore';
import CommsLayer from '../components/command/CommsLayer';
import { useOrchestrationStream } from '../hooks/useOrchestrationStream';
import ActivityGrid from '../components/command/ActivityGrid';
import { ReactFlow, Background, BackgroundVariant, Controls, MiniMap, MarkerType } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, Boxes, LayoutGrid, Radio, Zap, Orbit, Loader2, Megaphone } from 'lucide-react';
import BriefingView from '../components/command/BriefingView';

// Heavy (three.js) — only loaded when the operator flips to the 3D view.
const WorkflowVisualization3D = lazy(() => import('../components/WorkflowVisualization3D'));
import { useAgents } from '../hooks/useAgents';
import { buildOrgTree } from '../utils/orgTree';
import { useOrgLayout } from '../hooks/useOrgLayout';
import OrgAgentNode from '../components/command/OrgAgentNode';

const nodeTypes = { orgAgent: OrgAgentNode };

// Live delegation-edge color by protocol (matches the knowledge-graph legend).
const PROTOCOL_COLOR = {
  internal: '#ec4899', // unicorn pink — in-Brigade delegation
  a2a: '#22d3ee', // cyan — agent-to-agent
  ap2: '#f59e0b', // amber — agent payments
  peer: '#a855f7', // purple — peer comms
};
const RESTING_EDGE = { stroke: '#475569', strokeWidth: 1.5 };

const VIEWS = [
  { id: 'chart', icon: Network, label: 'Org Chart' },
  { id: 'activity', icon: LayoutGrid, label: 'Activity' },
  { id: 'graph3d', icon: Orbit, label: '3D' },
  { id: 'briefing', icon: Megaphone, label: 'Briefing' },
];

/**
 * Command Center — "The General's War Room".
 * The whole Brigade as a top-down org chart of real agent faces. Click any
 * agent to open comms (today: jump to /chat?agent=; soon: a floating dock).
 * Phase 1 = static chart (dagre layout, resting chain-of-command edges).
 */
export default function CommandCenter() {
  const { agents, loading, error, reload } = useAgents();
  const openWindow = useCommsStore((s) => s.openWindow);
  const [view, setView] = useState('chart');
  const { statuses, connected, invocations, events } = useOrchestrationStream();

  const tree = useMemo(() => buildOrgTree(agents), [agents]);

  const rawNodes = useMemo(
    () =>
      tree.agents.map((a) => ({
        id: a.id,
        type: 'orgAgent',
        position: { x: 0, y: 0 },
        data: {
          agent: a,
          isRoot: a.id === tree.root?.id,
          status: 'idle',
          subordinates: (tree.childrenById.get(a.id) || []).length,
          onOpen: openWindow, // keyboard activation path (mouse uses onNodeClick)
        },
      })),
    [tree, openWindow]
  );

  // Stable topology drives the dagre layout — it must NOT change with live
  // activity, or the nodes would jump every time a comm fires.
  const layoutEdges = useMemo(
    () => tree.edgesResting.map((e) => ({ ...e, type: 'smoothstep' })),
    [tree]
  );
  const positioned = useOrgLayout(rawNodes, layoutEdges);

  // Inject live per-agent status into the positioned nodes so the chart faces
  // light up. Reuse the exact node object when a node's source + status are
  // unchanged, so an SSE tick re-renders only the one node that changed (not all
  // 17), and skip the work entirely when the chart isn't the active view.
  const nodesCache = useRef(new Map());
  const nodes = useMemo(() => {
    if (view !== 'chart') return positioned;
    const cache = nodesCache.current;
    const next = positioned.map((n) => {
      const status = statuses[n.id]?.status || 'idle';
      const cached = cache.get(n.id);
      if (cached && cached.__src === n && cached.__status === status) return cached;
      return { ...n, data: { ...n.data, status }, __src: n, __status: status };
    });
    nodesCache.current = new Map(next.map((nn) => [nn.id, nn]));
    return next;
  }, [positioned, statuses, view]);

  // Active delegation edges, keyed source->target (latest wins).
  const liveByPair = useMemo(() => {
    const m = new Map();
    for (const inv of invocations) m.set(`${inv.source}->${inv.target}`, inv);
    return m;
  }, [invocations]);

  // Resting chain-of-command edges, lit + animated where a delegation is live,
  // plus transient edges for comms that jump across the hierarchy.
  const edges = useMemo(() => {
    if (view !== 'chart') return []; // ReactFlow isn't mounted in other views
    const staticPairs = new Set();
    const base = tree.edgesResting.map((e) => {
      staticPairs.add(`${e.source}->${e.target}`);
      staticPairs.add(`${e.target}->${e.source}`);
      const live =
        liveByPair.get(`${e.source}->${e.target}`) || liveByPair.get(`${e.target}->${e.source}`);
      if (live) {
        const color = PROTOCOL_COLOR[live.protocol] || PROTOCOL_COLOR.internal;
        return {
          ...e,
          type: 'smoothstep',
          animated: true,
          style: { stroke: color, strokeWidth: 2.75 },
          markerEnd: { type: MarkerType.ArrowClosed, color },
          zIndex: 10,
        };
      }
      return { ...e, type: 'smoothstep', animated: false, style: RESTING_EDGE };
    });
    const extra = [];
    for (const [key, inv] of liveByPair) {
      if (staticPairs.has(key)) continue;
      const color = PROTOCOL_COLOR[inv.protocol] || PROTOCOL_COLOR.internal;
      extra.push({
        id: `live-${key}`,
        source: inv.source,
        target: inv.target,
        type: 'smoothstep',
        animated: true,
        style: { stroke: color, strokeWidth: 2, strokeDasharray: '6 4' },
        markerEnd: { type: MarkerType.ArrowClosed, color },
        zIndex: 10,
      });
    }
    return [...base, ...extra];
  }, [tree, liveByPair, view]);

  const onNodeClick = useCallback(
    (_, node) => {
      const agent = tree.byId.get(node.id);
      if (agent) openWindow(agent);
    },
    [tree, openWindow]
  );

  // Active agent ids (for the 3D graph's node highlighting).
  const activeAgents = useMemo(
    () => Object.entries(statuses).filter(([, v]) => v && v.status !== 'idle').map(([id]) => id),
    [statuses]
  );

  // Only surface a disconnect after it persists ~2.5s, so brief EventSource
  // reconnect blips don't flash a banner.
  const [staleFeed, setStaleFeed] = useState(false);
  useEffect(() => {
    if (connected) {
      setStaleFeed(false);
      return undefined;
    }
    const t = setTimeout(() => setStaleFeed(true), 2500);
    return () => clearTimeout(t);
  }, [connected]);

  return (
    // Fill the viewport minus the mobile top bar (lg uses the sidebar, no top
    // bar) so the Controls, tray, and Briefing composer never clip off-screen.
    <div className="flex h-[calc(100dvh-4rem)] flex-col overflow-hidden lg:h-[100dvh]">
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
          <div
            role="tablist"
            aria-label="Command Center view"
            className="flex items-center gap-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-0.5"
          >
            {VIEWS.map(({ id, icon: Icon, label }) => (
              <button
                key={id}
                role="tab"
                aria-selected={view === id}
                onClick={() => setView(id)}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  view === id ? 'bg-unicorn-500/20 text-unicorn-200' : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="h-3.5 w-3.5" /> {label}
              </button>
            ))}
          </div>
          {liveByPair.size > 0 && (
            <div
              className="flex items-center gap-1.5 rounded-full border border-unicorn-500/40 bg-unicorn-500/10 px-2.5 py-1 text-xs font-medium text-unicorn-200"
              title="Agents are delegating to each other right now"
            >
              <Zap className="h-3.5 w-3.5 animate-pulse text-unicorn-300" />
              {liveByPair.size} live comm{liveByPair.size > 1 ? 's' : ''}
            </div>
          )}
          <div
            className="flex items-center gap-1.5 text-xs text-slate-400"
            title={connected ? 'Live feed connected' : 'Live feed offline'}
          >
            <Radio
              aria-hidden="true"
              className={`h-3.5 w-3.5 ${connected ? 'text-emerald-400' : 'text-slate-600'}`}
            />
            <span className="sr-only">{connected ? 'Live feed connected. ' : 'Live feed disconnected. '}</span>
            <Boxes aria-hidden="true" className="h-4 w-4" />
            {loading ? '…' : agents.length}
            <span className="sr-only"> agents</span>
          </div>
        </div>
      </div>

      {/* Canvas — org chart or live activity; comms windows float over both */}
      <div className="relative flex-1">
        {staleFeed && (
          <div className="absolute left-1/2 top-2 z-30 -translate-x-1/2 rounded-full border border-amber-500/40 bg-amber-500/15 px-3 py-1 text-xs text-amber-200 shadow-lg">
            Live feed disconnected — reconnecting…
          </div>
        )}
        {error ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-sm">
            <p className="text-slate-300">Couldn&apos;t load the agent roster.</p>
            <button
              onClick={reload}
              className="rounded-lg bg-unicorn-500/80 px-3 py-1.5 font-medium text-white hover:bg-unicorn-500"
            >
              Retry
            </button>
          </div>
        ) : loading && !agents.length ? (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading the Brigade…
          </div>
        ) : view === 'chart' ? (
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
        ) : view === 'activity' ? (
          <ActivityGrid agents={agents} statuses={statuses} onOpen={openWindow} />
        ) : view === 'graph3d' ? (
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-5 w-5 animate-spin" /> Loading 3D comms graph…
              </div>
            }
          >
            <WorkflowVisualization3D
              agents={agents}
              activeAgents={activeAgents}
              realtimeEvents={events}
              onAgentClick={(node) => {
                const a = node?.id ? tree.byId.get(node.id) : null;
                if (a) openWindow(a);
              }}
            />
          </Suspense>
        ) : (
          <BriefingView tree={tree} onPromote={openWindow} />
        )}
        <CommsLayer />
      </div>
    </div>
  );
}
