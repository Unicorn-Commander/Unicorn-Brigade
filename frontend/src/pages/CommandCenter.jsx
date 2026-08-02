import { useMemo, useCallback, useState, useEffect, useRef, lazy, Suspense } from 'react';
import { useCommsStore } from '../stores/useCommsStore';
import CommsLayer from '../components/command/CommsLayer';
import { useOrchestrationStream } from '../hooks/useOrchestrationStream';
import ActivityGrid from '../components/command/ActivityGrid';
import ActivityFeed from '../components/command/ActivityFeed';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useReactFlow,
  getNodesBounds,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, Boxes, LayoutGrid, Radio, Zap, Orbit, Loader2, Megaphone, Maximize2 } from 'lucide-react';
import BriefingView from '../components/command/BriefingView';

// Heavy (three.js) — only loaded when the operator flips to the 3D view.
const WorkflowVisualization3D = lazy(() => import('../components/WorkflowVisualization3D'));
import { useAgents } from '../hooks/useAgents';
import { buildOrgTree } from '../utils/orgTree';
import { useOrgLayout, ORG_NODE_W, ORG_NODE_H } from '../hooks/useOrgLayout';
import OrgAgentNode from '../components/command/OrgAgentNode';

const nodeTypes = { orgAgent: OrgAgentNode };

// A fit must be allowed to zoom out far enough to actually show the widest
// tier. The old floor of 0.2 was *also* the zoom the fit landed on — the apex
// has 19 direct reports, ~5100px of row inside a ~1400px pane — so every node
// rendered as a sliver. Keep this at or below what a real fit needs, and let
// the legibility floor below decide whether to use it at all.
const FIT_MIN_ZOOM = 0.12;
const FIT_OPTIONS = { padding: 0.14, minZoom: FIT_MIN_ZOOM, maxZoom: 0.9 };

// Below this, node labels stop being readable — names turn to grey mush. A
// board this wide only "fits" at about 0.25, so fitting everything is worse
// than not fitting: you get a ribbon that is legible at no zoom level floating
// in an empty pane. Past this point we anchor on the apex at a readable size
// and let the operator pan, use the minimap, or hit Fit all.
const LEGIBLE_ZOOM = 0.55;

/**
 * Owns the viewport. Decides — BEFORE moving it — whether a fit would land at a
 * readable zoom; fits if it would, anchors on the apex at LEGIBLE_ZOOM if it
 * would not.
 *
 * Polls for real geometry rather than gating on a single readiness signal:
 * dagre positions are synchronous but xyflow's node measurement is not, and a
 * bounds read before measurement is zero-sized. Polling is indifferent to
 * whether pane measurement, node measurement or layout settles last.
 * setInterval is deliberate over requestAnimationFrame, which never fires in a
 * hidden tab — which is every background or automated one.
 *
 * Rendered inside <ReactFlow> so it has the flow context.
 */
function FitOnChange({ token, rootId, paneRef, onModeChange }) {
  const rf = useReactFlow();
  useEffect(() => {
    const apply = () => {
      const pane = paneRef.current;
      const ns = rf.getNodes();
      if (!pane || !ns.length) return false;
      const w = pane.clientWidth;
      const h = pane.clientHeight;
      // Trust the bounds only once EVERY node has been measured. A partly
      // measured set reports a smaller board, which reads as "this would fit
      // legibly" and takes the fit branch — and because apply() then returns
      // true, that wrong viewport is the one that sticks.
      if (ns.some((n) => !(n.measured?.width && n.measured?.height))) return false;
      const bounds = getNodesBounds(ns);
      if (!w || !h || !bounds.width || !bounds.height) return false;

      // What zoom would fitView land on? Mirror its padding so the choice is
      // made before the viewport moves — fitting and then correcting would let
      // the unreadable fit be what the operator sees first.
      const pad = 1 + FIT_OPTIONS.padding * 2;
      const wouldFit = Math.min(w / (bounds.width * pad), h / (bounds.height * pad));

      if (wouldFit >= LEGIBLE_ZOOM) {
        rf.fitView({ ...FIT_OPTIONS, duration: 300 });
        onModeChange?.('fit');
        return true;
      }
      // Too WIDE to show legibly. Anchor horizontally on the apex, which sits
      // centred over its own tier, so the top of the chain of command and the
      // middle of the tier under it are what you land on.
      const root = rootId ? rf.getNode(rootId) : undefined;
      const cx = root ? root.position.x + ORG_NODE_W / 2 : bounds.x + bounds.width / 2;
      // Vertically it is only the width that forces our hand — an org chart is
      // far wider than it is deep, and this board is 3 tiers in a pane with
      // room for 10. Pinning the apex to the top of the pane the way a
      // depth-constrained chart needs left 70% of the canvas empty under the
      // chart, which is most of what "unreadable sliver in an empty pane"
      // meant. So centre the whole depth when it fits, and only pin the apex
      // to the top when the depth overflows too.
      const cy =
        bounds.height * LEGIBLE_ZOOM <= h || !root
          ? bounds.y + bounds.height / 2
          : root.position.y + h / (2 * LEGIBLE_ZOOM) - ORG_NODE_H;
      rf.setCenter(cx, cy, { zoom: LEGIBLE_ZOOM, duration: 300 });
      onModeChange?.('anchored');
      return true;
    };

    if (apply()) return undefined;
    let tries = 0;
    const iv = setInterval(() => {
      if (apply() || ++tries > 40) clearInterval(iv);
    }, 50);
    return () => clearInterval(iv);
  }, [token, rf, rootId, paneRef, onModeChange]);
  return null;
}

/** Escape hatch: show the whole board however small, on demand. */
function FitAllButton({ onFit }) {
  const rf = useReactFlow();
  return (
    <button
      onClick={() => {
        rf.fitView({ ...FIT_OPTIONS, maxZoom: LEGIBLE_ZOOM, duration: 300 });
        onFit?.();
      }}
      title="Zoom out until the whole chain of command is on screen"
      className="flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-slate-900/80 px-2.5 py-1 text-xs font-medium text-slate-300 backdrop-blur-md transition-colors hover:border-unicorn-500/60 hover:text-slate-100"
    >
      <Maximize2 className="h-3.5 w-3.5" /> Fit all
    </button>
  );
}

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

  // Defensive: `capabilities` can arrive as a non-array (bad seed data / JSON
  // column) and downstream renderers slice/map it (org nodes, activity, 3D).
  // Normalize once here so every consumer gets a real array.
  const safeAgents = useMemo(
    () =>
      (Array.isArray(agents) ? agents : []).map((a) =>
        Array.isArray(a?.capabilities) ? a : { ...a, capabilities: [] }
      ),
    [agents]
  );

  const tree = useMemo(() => buildOrgTree(safeAgents), [safeAgents]);

  // Emit nodes in CHAIN-OF-COMMAND order (apex, then each parent's rank-sorted
  // children, depth-first) rather than raw roster order. Dagre seeds its
  // within-rank ordering from insertion order, so roster order — which arrives
  // grouped by domain — scattered the tiers: agents landed beside strangers and
  // their reporting lines crossed the whole board to reach them. Walking the
  // tree puts each team together and the most senior of every tier first.
  const orderedAgents = useMemo(() => {
    const out = [];
    const seen = new Set();
    const walk = (id) => {
      const a = tree.byId.get(id);
      if (!a || seen.has(id)) return;
      seen.add(id);
      out.push(a);
      (tree.childrenById.get(id) || []).forEach(walk);
    };
    if (tree.root) walk(tree.root.id);
    // Anyone the walk can't reach (a line the roster is mid-edit on) still has
    // to appear — dropping an agent off the board is worse than an odd slot.
    tree.agents.forEach((a) => {
      if (!seen.has(a.id)) out.push(a);
    });
    return out;
  }, [tree]);

  const rawNodes = useMemo(
    () =>
      orderedAgents.map((a) => ({
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
    [orderedAgents, tree, openWindow]
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

  // Measured so the viewport owner can tell whether a fit would land at a
  // readable zoom BEFORE it moves anything.
  const paneRef = useRef(null);
  const [fitMode, setFitMode] = useState(null); // 'fit' | 'anchored' | null

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
        <div className="rounded-xl border border-unicorn-500/30 bg-gradient-to-br from-unicorn-500/30 to-unicorn-600/20 p-2">
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
          <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading the Brigade…
          </div>
        ) : view === 'chart' ? (
          <div ref={paneRef} className="h-full w-full">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              // No `fitView` prop: ReactFlow's built-in fit and <FitOnChange>
              // would both drive the viewport, and the built-in one wins — the
              // legibility anchoring below was computed, applied, and then
              // silently overwritten by a fit back down to ~0.25. One owner for
              // the viewport.
              minZoom={FIT_MIN_ZOOM}
              maxZoom={1.6}
              nodesDraggable={false}
              proOptions={{ hideAttribution: true }}
              className="bg-transparent"
            >
              <FitOnChange
                token={`${positioned.length}:${tree.root?.id || ''}`}
                rootId={tree.root?.id}
                paneRef={paneRef}
                onModeChange={setFitMode}
              />
              <Panel position="top-right" className="!m-2 flex flex-col items-end gap-1">
                <FitAllButton onFit={() => setFitMode('fit')} />
                {fitMode === 'anchored' && (
                  <p className="max-w-[13rem] text-right text-[10px] leading-tight text-slate-500">
                    Too wide to show legibly — anchored on{' '}
                    {tree.root?.displayName || tree.root?.name || 'the apex'}. Pan, use the
                    minimap, or Fit all.
                  </p>
                )}
              </Panel>
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
        ) : view === 'activity' ? (
          <div className="flex h-full min-h-0 flex-col lg:flex-row">
            <div className="min-h-0 flex-1 overflow-hidden">
              <ActivityGrid agents={safeAgents} statuses={statuses} onOpen={openWindow} />
            </div>
            <div className="min-h-0 shrink-0 border-t border-slate-800 bg-slate-950/40 lg:w-80 lg:border-l lg:border-t-0">
              <ActivityFeed events={events} agents={safeAgents} onOpen={openWindow} />
            </div>
          </div>
        ) : view === 'graph3d' ? (
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-400">
                <Loader2 className="h-5 w-5 animate-spin" /> Loading 3D comms graph…
              </div>
            }
          >
            <WorkflowVisualization3D
              agents={safeAgents}
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
