import { useMemo, useCallback, useState, useEffect, useRef, lazy, Suspense } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ReactFlow, ReactFlowProvider, Background, BackgroundVariant, Controls, MiniMap, Panel, MarkerType, useReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Network, LayoutGrid, Orbit, Megaphone, Target, Maximize2, Search, Bot, Sparkles, Library, ChevronsDownUp, ChevronsUpDown, ChevronRight, Zap, Repeat } from 'lucide-react';
import { Button, IconButton, Card, Chip, Input, Select, Tabs, Tooltip, PageHeader, EmptyState, ErrorState, OfflineState, LoadingState } from '../components/ui';
import { humanize } from '../utils/errors';
import { tokenHsl, statusColors } from '../utils/tokens';
import { normalizeProtocol } from '../utils/protocol';
import { buildOrgTree } from '../utils/orgTree';
import { useCommsStore } from '../stores/useCommsStore';
import { useAgents } from '../hooks/useAgents';
import { useOrchestrationStream } from '../hooks/useOrchestrationStream';
import { useOrgLayout } from '../hooks/useOrgLayout';
import { useAutonomy } from '../hooks/useAutonomy';
import { countsByAgent, needsAttention } from '../utils/autonomy';
import CommsLayer from '../components/command/CommsLayer';
import ActivityGrid from '../components/command/ActivityGrid';
import ActivityFeed from '../components/command/ActivityFeed';
import BriefingView from '../components/command/BriefingView';
import MissionsView from '../components/command/MissionsView';
import AutonomousView from '../components/command/AutonomousView';
import OrgAgentNode from '../components/command/OrgAgentNode';
import OrgStackEdge from '../components/command/OrgStackEdge';
import { usePhone, useReducedMotion, useThemeKey } from '../components/command/media';

// Heavy (three.js) — only loaded when the operator opts into the 3D view.
const WorkflowVisualization3D = lazy(() => import('../components/WorkflowVisualization3D'));

const nodeTypes = { orgAgent: OrgAgentNode };
const edgeTypes = { orgStack: OrgStackEdge };

// Delegation edges light up in the protocol's colour, read from the tokens so
// a theme flip reaches the graph too.
const PROTOCOL_TOKEN = { internal: '--accent', a2a: '--info', paid: '--warn', peer: '--live' };
const WORKING = new Set(['thinking', 'tool', 'responding', 'streaming']);

const VIEWS = [
  { id: 'chart', icon: Network, label: 'Org Chart' },
  { id: 'activity', icon: LayoutGrid, label: 'Activity' },
  { id: 'missions', icon: Target, label: 'Missions' },
  { id: 'autonomous', icon: Repeat, label: 'Autonomous' },
  { id: 'graph3d', icon: Orbit, label: '3D' },
  { id: 'briefing', icon: Megaphone, label: 'Briefing' },
];
const VIEW_IDS = VIEWS.map((v) => v.id);

// The chart remembers how you left it: which teams are folded, which team is
// in focus, and which view you were on.
const STORAGE_KEY = 'brigade.command-center.v1';
const readPrefs = () => {
  try {
    const p = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
    return p && typeof p === 'object' ? p : {};
  } catch {
    return {};
  }
};
const writePrefs = (patch) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readPrefs(), ...patch }));
  } catch {
    /* storage unavailable (private mode) — the choice just doesn't persist */
  }
};

// When the apex has more direct reports than this, the chart opens with every
// team folded: the apex and its leads stack on one screen, and each team is
// one click away. (Nine leads side by side is already 2,600px wide.)
const FOLD_ABOVE_REPORTS = 6;

// A fit must be allowed to zoom out far enough to show the widest tier...
const FIT_MIN_ZOOM = 0.12;
const FIT_OPTIONS = { padding: 0.12, minZoom: FIT_MIN_ZOOM, maxZoom: 1 };
// ...but below this, 14px names are under 11px on screen and nobody can read
// them, so a board that would only fit smaller is anchored on the apex at a
// readable size instead, and the operator pans, folds teams, or focuses one.
const LEGIBLE_ZOOM = 0.8;

/**
 * Owns the viewport. Decides — BEFORE moving it — whether a fit would land at
 * a readable zoom; fits if it would, anchors on the apex at LEGIBLE_ZOOM if it
 * would not. Polls for real geometry (xyflow measures nodes asynchronously)
 * with setInterval, which keeps firing in a hidden tab where rAF does not.
 * A search fits the matching nodes instead. Rendered inside <ReactFlow>.
 */
function ViewportOwner({ token, rootId, expectedCount, paneRef, matchKey, matchIds, onModeChange }) {
  const rf = useReactFlow();

  useEffect(() => {
    const apply = () => {
      const pane = paneRef.current;
      const ns = rf.getNodes();
      if (!pane || !ns.length) return false;
      // Wait for the WHOLE board: a partial node set reads as narrower than it
      // is, takes the fit branch, and that wrong viewport is what sticks.
      if (expectedCount && ns.length < expectedCount) return false;
      const w = pane.clientWidth;
      const h = pane.clientHeight;
      const bounds = rf.getNodesBounds(ns);
      if (!w || !h || !bounds.width || !bounds.height) return false;
      const pad = 1 + FIT_OPTIONS.padding * 2;
      const wouldFit = Math.min(w / (bounds.width * pad), h / (bounds.height * pad));
      if (wouldFit >= LEGIBLE_ZOOM) {
        rf.fitView({ ...FIT_OPTIONS, duration: 300 });
        onModeChange?.('fit');
        return true;
      }
      const root = rootId ? rf.getNode(rootId) : undefined;
      const rw = root?.width || root?.measured?.width || 0;
      const rh = root?.height || root?.measured?.height || 0;
      const cx = root ? root.position.x + rw / 2 : bounds.x + bounds.width / 2;
      // Centre the depth when it fits; pin the apex near the top when it doesn't.
      const cy = bounds.height * LEGIBLE_ZOOM <= h || !root ? bounds.y + bounds.height / 2 : root.position.y + h / (2 * LEGIBLE_ZOOM) - rh;
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
  }, [token, rf, rootId, paneRef, expectedCount, onModeChange]);

  useEffect(() => {
    if (!matchIds?.length) return undefined;
    const t = setTimeout(() => rf.fitView({ nodes: matchIds.map((id) => ({ id })), padding: 0.35, minZoom: FIT_MIN_ZOOM, maxZoom: 1, duration: 300 }), 80);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchKey, rf]);

  return null;
}

/** The loading state of the board: the shape of an org chart, no spinner. */
function ChartSkeleton() {
  const Bone = ({ className = '' }) => <div className={`rounded-card border border-border bg-card ${className}`} />;
  return (
    <div role="status" aria-busy="true" aria-label="Loading the brigade" className="flex h-full animate-pulse flex-col items-center justify-center gap-10 px-6">
      <Bone className="h-20 w-60" />
      <div className="flex flex-wrap justify-center gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <Bone key={i} className="h-20 w-56" />
        ))}
      </div>
      <div className="hidden flex-wrap justify-center gap-6 sm:flex">
        {Array.from({ length: 6 }).map((_, i) => (
          <Bone key={i} className="h-20 w-56" />
        ))}
      </div>
      <span className="sr-only">Loading the brigade…</span>
    </div>
  );
}

/**
 * Command Center — the home screen. The whole Brigade as a chain of command
 * of real agent faces, visibly alive from the orchestration stream; click any
 * agent to open comms in a floating dock. Views: Org Chart, Activity,
 * Missions, Autonomous (every job that runs on its own), 3D (opt-in) and
 * Briefing. The autonomy catalogue is read here once (every 60 s) and shared
 * by the Autonomous view and the org chart's clock badges.
 */
export default function CommandCenter() {
  const navigate = useNavigate();
  const phone = usePhone();
  const reducedMotion = useReducedMotion();
  const themeKey = useThemeKey();
  const { agents, loading, error, reload } = useAgents();
  const openWindow = useCommsStore((s) => s.openWindow);
  const { statuses, connected, invocations, events } = useOrchestrationStream();
  const autonomy = useAutonomy();
  const autonomyByAgent = useMemo(() => countsByAgent(autonomy.items), [autonomy.items]);
  const autonomyAttention = useMemo(() => autonomy.items.filter(needsAttention).length, [autonomy.items]);

  const [view, setViewState] = useState(() => (VIEW_IDS.includes(readPrefs().view) ? readPrefs().view : 'chart'));
  const [searchParams, setSearchParams] = useSearchParams();
  const setView = useCallback((v) => {
    setViewState(v);
    writePrefs({ view: v });
  }, []);
  // Deep links (?view=missions from the palette, /orchestration's redirect,
  // ?view=autonomous&agent=<id> from an agent's page): switch once, remember
  // it like a tab click, then drop the params so a later reload honours
  // whatever the person picked last.
  const [focusAgent, setFocusAgent] = useState(null);
  useEffect(() => {
    const v = searchParams.get('view');
    const a = searchParams.get('agent');
    if (!v && !a) return;
    if (VIEW_IDS.includes(v)) setView(v);
    if (a && v === 'autonomous') setFocusAgent(a);
    const next = new URLSearchParams(searchParams);
    next.delete('view');
    next.delete('agent');
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams, setView]);
  // The org chart's clock badge: jump to that agent's jobs in the catalogue.
  const showAutonomy = useCallback(
    (agentId) => {
      setView('autonomous');
      setFocusAgent(agentId);
    },
    [setView]
  );
  const clearFocusAgent = useCallback(() => setFocusAgent(null), []);
  // null = "not decided yet": the roster size picks the default below.
  const [collapsed, setCollapsedState] = useState(() => (Array.isArray(readPrefs().collapsed) ? new Set(readPrefs().collapsed) : null));
  const setCollapsed = useCallback((next) => {
    setCollapsedState(next);
    writePrefs({ collapsed: [...next] });
  }, []);
  const [focus, setFocusState] = useState(() => readPrefs().focus || null);
  const setFocus = useCallback((id) => {
    setFocusState(id || null);
    writePrefs({ focus: id || null });
  }, []);
  const [query, setQuery] = useState('');
  const [fitMode, setFitMode] = useState(null); // 'fit' | 'anchored' | null
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const paneRef = useRef(null);

  // Offline is a state of the board, not a toast.
  useEffect(() => {
    const on = () => {
      setOffline(false);
      reload();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [reload]);

  // Defensive: `capabilities` can arrive as a non-array (bad seed data / JSON
  // column) and downstream renderers slice/map it. Normalize once here.
  const safeAgents = useMemo(
    () => (Array.isArray(agents) ? agents : []).map((a) => (Array.isArray(a?.capabilities) ? a : { ...a, capabilities: [] })),
    [agents]
  );
  const tree = useMemo(() => buildOrgTree(safeAgents), [safeAgents]);

  // How many agents sit under each one (what a folded pill says).
  const descendants = useMemo(() => {
    const m = new Map();
    const count = (id, trail) => {
      if (m.has(id)) return m.get(id);
      if (trail.has(id)) return 0;
      trail.add(id);
      let n = 0;
      for (const c of tree.childrenById.get(id) || []) n += 1 + count(c, trail);
      m.set(id, n);
      return n;
    };
    tree.agents.forEach((a) => count(a.id, new Set()));
    return m;
  }, [tree]);

  const leads = useMemo(() => tree.agents.filter((a) => (tree.childrenById.get(a.id) || []).length > 0 && a.id !== tree.root?.id), [tree]);

  // Default fold: a wide apex row opens with every lead's team folded.
  const collapsedSet = useMemo(() => {
    if (collapsed) return collapsed;
    const reports = tree.root ? tree.childrenById.get(tree.root.id) || [] : [];
    if (reports.length <= FOLD_ABOVE_REPORTS) return new Set();
    return new Set(reports.filter((id) => (tree.childrenById.get(id) || []).length > 0));
  }, [collapsed, tree]);
  const toggleCollapsed = useCallback(
    (id) => {
      const next = new Set(collapsedSet);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      setCollapsed(next);
    },
    [collapsedSet, setCollapsed]
  );
  const collapseAll = () => setCollapsed(new Set(leads.map((l) => l.id)));
  const expandAll = () => setCollapsed(new Set());

  // Search: match on anything a person would type; while searching every
  // team is open so a match is never hidden inside a folded one.
  const q = query.trim().toLowerCase();
  const matchIds = useMemo(() => {
    if (!q) return null;
    return new Set(
      tree.agents
        .filter((a) => [a.displayName, a.name, a.title, a.rank, a.domain, a.model, a.id].some((v) => String(v || '').toLowerCase().includes(q)))
        .map((a) => a.id)
    );
  }, [q, tree]);
  const searching = Boolean(q);
  const focusValid = focus && tree.byId.has(focus) && (tree.childrenById.get(focus) || []).length > 0;

  // Which agents are on the board right now, in chain-of-command order (apex,
  // then each parent's rank-sorted reports, depth first) — which is also the
  // Tab order, since xyflow renders nodes in array order.
  const visibleIds = useMemo(() => {
    const out = [];
    const seen = new Set();
    const walk = (id) => {
      if (seen.has(id) || !tree.byId.has(id)) return;
      seen.add(id);
      out.push(id);
      if (collapsedSet.has(id) && !searching) return;
      (tree.childrenById.get(id) || []).forEach(walk);
    };
    if (focusValid) walk(focus);
    else {
      if (tree.root) walk(tree.root.id);
      // Anyone the root cannot reach at all (a line the roster is mid-edit on)
      // still has to appear — dropping an agent off the board is worse than an
      // odd slot. Descendants of a folded team are reachable; they stay hidden.
      const reachable = new Set();
      const reach = (id) => {
        if (reachable.has(id)) return;
        reachable.add(id);
        (tree.childrenById.get(id) || []).forEach(reach);
      };
      if (tree.root) reach(tree.root.id);
      tree.agents.forEach((a) => {
        if (!reachable.has(a.id)) walk(a.id);
      });
    }
    return out;
  }, [tree, collapsedSet, searching, focus, focusValid]);
  const visibleSet = useMemo(() => new Set(visibleIds), [visibleIds]);

  const rawNodes = useMemo(() => {
    const siblingsOf = (id) => {
      const p = tree.parentOf.get(id);
      return (p ? tree.childrenById.get(p) || [] : visibleIds.filter((v) => !tree.parentOf.has(v))).filter((s) => visibleSet.has(s));
    };
    return visibleIds.map((id) => {
      const agent = tree.byId.get(id);
      const kids = tree.childrenById.get(id) || [];
      const folded = collapsedSet.has(id) && !searching;
      const sibs = siblingsOf(id);
      const i = sibs.indexOf(id);
      const parent = tree.parentOf.get(id);
      return {
        id,
        type: 'orgAgent',
        position: { x: 0, y: 0 },
        data: {
          agent,
          isRoot: id === tree.root?.id,
          subordinates: kids.length,
          hiddenCount: descendants.get(id) || 0,
          collapsed: folded,
          nav: {
            prev: sibs[i - 1],
            next: sibs[i + 1],
            up: parent && visibleSet.has(parent) ? parent : undefined,
            down: folded ? undefined : kids.find((k) => visibleSet.has(k)),
          },
          onOpen: openWindow,
          onToggle: toggleCollapsed,
          onAutonomy: showAutonomy,
        },
      };
    });
  }, [visibleIds, visibleSet, tree, collapsedSet, searching, descendants, openWindow, toggleCollapsed, showAutonomy]);

  // Stable topology drives the layout — it must NOT change with live activity,
  // or the nodes would jump every time a comm fires.
  const restingEdges = useMemo(() => tree.edgesResting.filter((e) => visibleSet.has(e.source) && visibleSet.has(e.target)), [tree, visibleSet]);
  const { nodes: positioned, edges: layoutEdges } = useOrgLayout(rawNodes, restingEdges);

  // Inject live status / search state / autonomy counts into the positioned
  // nodes, reusing the exact node object when nothing changed so an SSE tick
  // (or a catalogue refresh) re-renders only the node that changed — and
  // never re-lays-out — skipping the work when the chart isn't showing.
  const nodesCache = useRef(new Map());
  const nodes = useMemo(() => {
    if (view !== 'chart') return positioned;
    const cache = nodesCache.current;
    const next = positioned.map((n) => {
      const live = statuses[n.id];
      const status = live?.status || 'idle';
      const reason = status === 'error' ? live?.reason : undefined;
      const match = matchIds ? matchIds.has(n.id) : false;
      const dim = matchIds ? !match : false;
      const autonomy = autonomyByAgent.get(n.id) || null;
      const sig = `${status}|${reason || ''}|${match}|${dim}|${autonomy ? `${autonomy.total}/${autonomy.failing}/${autonomy.stale}` : ''}`;
      const cached = cache.get(n.id);
      if (cached && cached.__src === n && cached.__sig === sig) return cached;
      return { ...n, data: { ...n.data, status, reason, match, dim, autonomy }, __src: n, __sig: sig };
    });
    nodesCache.current = new Map(next.map((nn) => [nn.id, nn]));
    return next;
  }, [positioned, statuses, matchIds, view, autonomyByAgent]);

  // Colours for the parts of the chart that cannot take a class.
  const colors = useMemo(
    () => ({
      status: statusColors(),
      edge: tokenHsl('--border-strong'),
      node: tokenHsl('--muted'),
      dots: tokenHsl('--border', 0.55),
      mask: tokenHsl('--bg', 0.72),
      proto: Object.fromEntries(Object.entries(PROTOCOL_TOKEN).map(([k, v]) => [k, tokenHsl(v)])),
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [themeKey]
  );

  // Active delegation edges, keyed source->target (latest wins).
  const liveByPair = useMemo(() => {
    const m = new Map();
    for (const inv of invocations) m.set(`${inv.source}->${inv.target}`, inv);
    return m;
  }, [invocations]);

  // Resting chain-of-command edges, lit where a delegation is live, plus
  // transient edges for comms that jump across the hierarchy.
  const edges = useMemo(() => {
    if (view !== 'chart') return [];
    const staticPairs = new Set();
    const base = layoutEdges.map((e) => {
      staticPairs.add(`${e.source}->${e.target}`);
      staticPairs.add(`${e.target}->${e.source}`);
      const live = liveByPair.get(`${e.source}->${e.target}`) || liveByPair.get(`${e.target}->${e.source}`);
      if (!live) return { ...e, animated: false, style: { stroke: colors.edge, strokeWidth: 1.5 } };
      const color = colors.proto[normalizeProtocol(live.protocol)] || colors.proto.internal;
      return { ...e, animated: !reducedMotion, style: { stroke: color, strokeWidth: 2.5 }, markerEnd: { type: MarkerType.ArrowClosed, color }, zIndex: 10 };
    });
    const extra = [];
    for (const [key, inv] of liveByPair) {
      if (staticPairs.has(key) || !visibleSet.has(inv.source) || !visibleSet.has(inv.target)) continue;
      const color = colors.proto[normalizeProtocol(inv.protocol)] || colors.proto.internal;
      extra.push({
        id: `live-${key}`,
        source: inv.source,
        target: inv.target,
        sourceHandle: 'bottom',
        targetHandle: 'top',
        type: 'smoothstep',
        animated: !reducedMotion,
        style: { stroke: color, strokeWidth: 2, strokeDasharray: '6 4' },
        markerEnd: { type: MarkerType.ArrowClosed, color },
        zIndex: 10,
      });
    }
    return [...base, ...extra];
  }, [layoutEdges, liveByPair, visibleSet, view, colors, reducedMotion]);

  const minimapColor = useCallback(
    (n) => {
      const s = n.data?.status;
      return s && s !== 'idle' ? colors.status[s === 'done' ? 'responding' : s] || colors.status.accent : colors.node;
    },
    [colors]
  );

  // Agents working right now (for the 3D graph's highlighting and the header).
  const activeAgents = useMemo(() => Object.entries(statuses).filter(([, v]) => v && WORKING.has(v.status)).map(([id]) => id), [statuses]);
  const attention = useMemo(() => Object.values(statuses).filter((v) => v?.status === 'error').length, [statuses]);

  // Only call the feed stale after it stays down ~2.5s, so EventSource
  // reconnect blips don't flash the chip.
  const [staleFeed, setStaleFeed] = useState(false);
  useEffect(() => {
    if (connected) {
      setStaleFeed(false);
      return undefined;
    }
    const t = setTimeout(() => setStaleFeed(true), 2500);
    return () => clearTimeout(t);
  }, [connected]);

  const matchList = useMemo(() => (matchIds ? [...matchIds].filter((id) => visibleSet.has(id)) : []), [matchIds, visibleSet]);
  const roster = safeAgents.length;
  const description =
    loading && !roster
      ? 'Loading the roster…'
      : error && !roster
        ? 'The roster could not be loaded.'
        : !roster
          ? 'No agents in this organization yet.'
          : `${roster} agent${roster === 1 ? '' : 's'} · ${activeAgents.length ? `${activeAgents.length} working now` : 'all idle'}${
              attention ? ` · ${attention} need${attention === 1 ? 's' : ''} attention` : ''
            }`;

  // ── the four states of the board ─────────────────────────────────────────
  // The Autonomous catalogue stands on its own data (an outside job needs no
  // agent), so it skips the roster's states and draws its own.
  let body;
  if (view === 'autonomous') {
    body = <AutonomousView autonomy={autonomy} agents={safeAgents} focusAgentId={focusAgent} onFocusHandled={clearFocusAgent} />;
  } else if (offline && !roster) {
    body = <OfflineState onRetry={reload} />;
  } else if (loading && !roster) {
    body = <ChartSkeleton />;
  } else if (error && !roster) {
    body = <ErrorState title="Couldn’t load the roster" detail={humanize(error, { what: 'loading the roster' })} onRetry={reload} />;
  } else if (!roster) {
    body = (
      <EmptyState
        icon={Bot}
        title="No agents yet"
        description="Build your first agent with Gunny, or import one from the library, and the chain of command appears here."
        action={
          <Button icon={Sparkles} onClick={() => navigate('/builder-chat')}>
            Build an agent
          </Button>
        }
        secondary={
          <Button variant="ghost" icon={Library} onClick={() => navigate('/library')}>
            Open the library
          </Button>
        }
      />
    );
  } else if (view === 'chart') {
    const focusLead = focusValid ? tree.byId.get(focus) : null;
    // On a phone the toolbar sits above the canvas in normal flow, so nothing
    // floats over the nodes; from `sm` it floats in the top-left corner.
    const toolbar = (
      <Card padding="sm" variant="glass" className={`flex flex-col gap-2 ${phone ? 'w-full' : 'w-[min(calc(100vw_-_2.5rem),22rem)]'}`}>
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input type="search" size="sm" aria-label="Search agents" placeholder="Search agents…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-8" />
        </div>
        <div className="flex items-center gap-1.5">
          <div className="min-w-0 flex-1">
            <Select size="sm" aria-label="Focus on a team" value={focusValid ? focus : ''} onChange={(e) => setFocus(e.target.value)}>
              <option value="">Whole brigade</option>
              {leads.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.displayName || l.name} · {descendants.get(l.id)} under
                </option>
              ))}
            </Select>
          </div>
          <IconButton icon={ChevronsDownUp} label="Collapse all teams" variant="secondary" size="sm" onClick={collapseAll} disabled={!leads.length} />
          <IconButton icon={ChevronsUpDown} label="Expand all teams" variant="secondary" size="sm" onClick={expandAll} disabled={!collapsedSet.size} />
          <FitAllButton />
        </div>
        {focusLead && (
          <nav aria-label="Chart focus" className="flex items-center gap-1 text-caption text-muted">
            <Button variant="link" size="xs" onClick={() => setFocus(null)}>
              Whole brigade
            </Button>
            <ChevronRight aria-hidden="true" className="h-3 w-3" />
            <span className="truncate font-medium text-fg">{focusLead.displayName || focusLead.name}’s team</span>
          </nav>
        )}
        {searching && (
          <p className="text-caption text-muted" aria-live="polite">
            {matchList.length === 0 ? 'No agent matches.' : `${matchList.length} match${matchList.length === 1 ? '' : 'es'} — the rest are dimmed.`}
          </p>
        )}
        {!searching && fitMode === 'anchored' && (
          <p className="hidden text-micro text-subtle sm:block">Too wide to show at a readable size — anchored on the top of the chain. Pan, fold teams, or focus one.</p>
        )}
      </Card>
    );
    body = (
      <ReactFlowProvider>
        <div role="tabpanel" aria-labelledby="cc-view-chart" className="flex h-full w-full flex-col">
          {phone && <div className="shrink-0 border-b border-border p-3">{toolbar}</div>}
          <div ref={paneRef} className="min-h-0 flex-1">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              // No `fitView` prop: one owner for the viewport (ViewportOwner).
              minZoom={FIT_MIN_ZOOM}
              maxZoom={1.6}
              nodesDraggable={false}
              nodesConnectable={false}
              nodesFocusable={false}
              edgesFocusable={false}
              // Nodes stay selectable: xyflow gives a node that is neither
              // selectable nor draggable `pointer-events: none`, which would
              // swallow the clicks on the buttons inside it.
              proOptions={{ hideAttribution: true }}
              className="bg-transparent"
            >
              <ViewportOwner
                token={`${visibleIds.join(',')}|${phone ? 'p' : 'd'}`}
                rootId={focusValid ? focus : tree.root?.id}
                expectedCount={positioned.length}
                paneRef={paneRef}
                matchKey={matchList.join(',')}
                matchIds={matchList}
                onModeChange={setFitMode}
              />
              {!phone && <Panel position="top-left">{toolbar}</Panel>}
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color={colors.dots} />
              <Controls showInteractive={false} />
              {!phone && <MiniMap pannable zoomable nodeColor={minimapColor} nodeStrokeWidth={0} maskColor={colors.mask} />}
            </ReactFlow>
          </div>
        </div>
      </ReactFlowProvider>
    );
  } else if (view === 'activity') {
    body = (
      <div role="tabpanel" aria-labelledby="cc-view-activity" className="flex h-full min-h-0 flex-col lg:flex-row">
        <div className="min-h-0 flex-1 overflow-hidden">
          <ActivityGrid agents={safeAgents} statuses={statuses} onOpen={openWindow} />
        </div>
        <div className="max-h-[45%] min-h-0 shrink-0 border-t border-border bg-surface/50 lg:max-h-none lg:w-80 lg:border-l lg:border-t-0">
          <ActivityFeed events={events} agents={safeAgents} connected={connected} onOpen={openWindow} />
        </div>
      </div>
    );
  } else if (view === 'missions') {
    body = (
      <div role="tabpanel" aria-labelledby="cc-view-missions" className="h-full">
        <MissionsView agents={safeAgents} statuses={statuses} events={events} connected={connected} onOpen={openWindow} />
      </div>
    );
  } else if (view === 'graph3d') {
    body = (
      <div role="tabpanel" aria-labelledby="cc-view-graph3d" className="h-full">
        {/* Live: statuses and delegations repaint the graph from the SSE stream;
            the roster itself refreshes every 30s through useAgents. */}
        <Suspense fallback={<LoadingState variant="chart" label="Loading the 3D view" className="p-6" />}>
          <WorkflowVisualization3D
            agents={safeAgents}
            connections={tree.edgesResting}
            activeAgents={activeAgents}
            statuses={statuses}
            realtimeEvents={events}
            onAgentClick={(node) => {
              const a = node?.id ? tree.byId.get(node.id) : null;
              if (a) openWindow(a);
            }}
          />
        </Suspense>
      </div>
    );
  } else {
    body = (
      <div role="tabpanel" aria-labelledby="cc-view-briefing" className="h-full">
        <BriefingView tree={tree} onPromote={openWindow} />
      </div>
    );
  }

  const feedChip = connected ? (
    <Chip tone="ok" dot size="sm">
      Live
    </Chip>
  ) : staleFeed ? (
    <Tooltip content="The live feed dropped and is reconnecting — statuses may be stale.">
      <Chip tone="warn" dot pulse size="sm">
        Reconnecting…
      </Chip>
    </Tooltip>
  ) : (
    <Chip dot size="sm">
      Connecting…
    </Chip>
  );

  return (
    // Fill the viewport minus the mobile top bar (lg uses the sidebar, no top
    // bar) so the Controls, tray and Briefing composer never clip off-screen.
    <div className="flex h-[calc(100dvh-4rem)] flex-col overflow-hidden lg:h-[100dvh]">
      <div className="border-b border-border px-4 pt-4 sm:px-6 sm:pt-5">
        <PageHeader
          eyebrow="Command"
          title="Command Center"
          description={description}
          actions={
            <>
              {liveByPair.size > 0 && (
                <Tooltip content="Agents are delegating to each other right now">
                  <Chip tone="accent" dot pulse size="sm" icon={Zap}>
                    {liveByPair.size} live comm{liveByPair.size > 1 ? 's' : ''}
                  </Chip>
                </Tooltip>
              )}
              {feedChip}
              <div className="max-w-full overflow-x-auto">
                <Tabs
                  variant="segmented"
                  size="sm"
                  label="Command Center view"
                  idBase="cc-view"
                  value={view}
                  onChange={setView}
                  tabs={VIEWS.map((v) =>
                    v.id === 'activity' && activeAgents.length
                      ? { ...v, count: activeAgents.length }
                      : v.id === 'autonomous' && autonomyAttention
                        ? { ...v, count: autonomyAttention }
                        : v
                  )}
                />
              </div>
            </>
          }
        />
      </div>

      {/* Canvas — the board or a view; comms windows float over all of them */}
      <div className="relative min-h-0 flex-1">
        {body}
        <CommsLayer />
      </div>
    </div>
  );
}

/** Escape hatch: show the whole board however small, on demand. */
function FitAllButton() {
  const rf = useReactFlow();
  return (
    <IconButton
      icon={Maximize2}
      label="Fit the whole chart"
      variant="secondary"
      size="sm"
      onClick={() => rf.fitView({ ...FIT_OPTIONS, duration: 300 })}
    />
  );
}
