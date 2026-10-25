/**
 * 3D view — a force-directed map of the brigade (react-force-graph-3d).
 *
 * Agents are nodes (their real portraits), chain-of-command and live
 * delegations are links, colour comes from the design tokens (status and
 * protocol hues; domains cycle through the token palette), and the camera is
 * fitted once the simulation settles so the graph fills the pane. Under
 * prefers-reduced-motion it renders a settled, static scene: no particles, no
 * glow. Every Three.js object is cached per node and disposed on unmount.
 *
 * Props are the same contract the Orchestration page uses; `statuses` is new
 * and optional ({ [agentId]: { status } } in the AGENT_STATUS vocabulary).
 */
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { Maximize2, Minimize2, Layers, Box, Grid3X3, Play, Pause, RefreshCw, X } from 'lucide-react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { normalizeProtocol } from '../utils/protocol';
import { tokenRaw, tokenHsl } from '../utils/tokens';
import { prettyDomain, roleLine } from '../utils/agentClass';
import AgentAvatar from './AgentAvatar';
import { Card, Chip, EmptyState, IconButton, StatusDot, statusMeta } from './ui';
import { useReducedMotion, useThemeKey } from './command/media';

// Domains cycle through the token hues (sorted, so a domain keeps its colour
// between renders); 'general' is muted.
const DOMAIN_TOKENS = ['--accent', '--info', '--ok', '--warn', '--live', '--danger'];
const STATUS_TOKEN = { thinking: '--warn', tool: '--live', responding: '--ok', streaming: '--ok', done: '--ok', error: '--danger' };
const PROTOCOL_TOKEN = { internal: '--accent', a2a: '--info', paid: '--warn', peer: '--live' };
const AGENT_TYPE_TOKEN = { federated: '--info', 'external-free': '--ok', 'external-paid': '--warn' };
const LINK_TTL = 5000;

/** A token's HSL triple as a 24-bit number for Three.js materials. */
function tokenHex(name) {
  const m = /^\s*([\d.]+)\s+([\d.]+)%\s+([\d.]+)%/.exec(tokenRaw(name));
  if (!m) return 0x888888;
  const h = Number(m[1]) / 360;
  const s = Number(m[2]) / 100;
  const l = Number(m[3]) / 100;
  return new THREE.Color().setHSL(h, s, l).getHex();
}

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// Dispose a node object's GPU resources (geometries, materials, textures).
function disposeNodeObject(object) {
  if (!object) return;
  object.traverse((child) => {
    child.geometry?.dispose?.();
    const materials = Array.isArray(child.material) ? child.material : child.material ? [child.material] : [];
    materials.forEach((m) => {
      m.map?.dispose?.();
      m.dispose?.();
    });
  });
}

/**
 * One camera-facing sprite per agent: a round portrait (the real avatar once
 * it loads, the emoji until then) with its status/affiliation ring and, when
 * the agent is working, a soft glow — all drawn into one texture so nothing
 * turns edge-on when the camera moves.
 */
const hex6 = (n) => `#${n.toString(16).padStart(6, '0')}`;
function makePortrait(node, { fillHex, ringHex, ringOpacity, glow }) {
  const canvas = document.createElement('canvas');
  canvas.width = 160;
  canvas.height = 160;
  const ctx = canvas.getContext('2d');
  const emoji = node.avatar && !String(node.avatar).startsWith('/') ? node.avatar : '🦄';
  const paint = (image) => {
    ctx.clearRect(0, 0, 160, 160);
    if (glow) {
      ctx.globalAlpha = 0.22;
      ctx.beginPath();
      ctx.arc(80, 80, 78, 0, 2 * Math.PI);
      ctx.fillStyle = hex6(ringHex);
      ctx.fill();
      ctx.globalAlpha = 1;
    }
    ctx.save();
    ctx.beginPath();
    ctx.arc(80, 80, 58, 0, 2 * Math.PI);
    ctx.closePath();
    ctx.clip();
    ctx.fillStyle = hex6(fillHex);
    ctx.fillRect(0, 0, 160, 160);
    if (image) ctx.drawImage(image, 22, 22, 116, 116);
    else {
      ctx.font = 'bold 56px system-ui, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'white';
      ctx.fillText(emoji, 80, 84);
    }
    ctx.restore();
    ctx.globalAlpha = ringOpacity;
    ctx.beginPath();
    ctx.arc(80, 80, 62, 0, 2 * Math.PI);
    ctx.lineWidth = 6;
    ctx.strokeStyle = hex6(ringHex);
    ctx.stroke();
    ctx.globalAlpha = 1;
  };
  paint(null);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(glow ? 22 : 18, glow ? 22 : 18, 1);

  const src = node.avatarUrl || (node.id ? `/avatars/${node.id}.webp` : null);
  if (src) {
    new THREE.TextureLoader().load(
      src,
      (loaded) => {
        paint(loaded.image);
        loaded.dispose();
        texture.needsUpdate = true;
      },
      undefined,
      () => {} // keep the emoji
    );
  }
  return sprite;
}

const WorkflowVisualization3D = ({
  agents = [],
  connections = [],
  activeAgents = [],
  statuses = {},
  onAgentClick,
  onConnectionClick,
  isFullscreen = false,
  onToggleFullscreen,
  animate = true,
  realtimeEvents = [],
}) => {
  const fgRef = useRef();
  const containerRef = useRef();
  const fadeTimers = useRef(new Set());
  const nodeObjects = useRef(new Map()); // id -> { key, object }
  const nodeIdentity = useRef(new Map()); // id -> the node object the engine positions
  const userMoved = useRef(false);
  const reducedMotion = useReducedMotion();
  const themeKey = useThemeKey();
  const [viewMode, setViewMode] = useState('3d');
  const [selected, setSelected] = useState(null);
  const [isAnimating, setIsAnimating] = useState(animate);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [liveLinks, setLiveLinks] = useState([]);

  // Colours from the tokens; re-read on a theme flip.
  const colors = useMemo(() => {
    const domains = [...new Set(agents.map((a) => a.domain).filter(Boolean))].sort();
    const domainHex = Object.fromEntries(domains.map((d, i) => [d, tokenHex(DOMAIN_TOKENS[i % DOMAIN_TOKENS.length])]));
    const domainCss = Object.fromEntries(domains.map((d, i) => [d, tokenHsl(DOMAIN_TOKENS[i % DOMAIN_TOKENS.length])]));
    return {
      domainHex,
      domainCss,
      generalHex: tokenHex('--muted'),
      statusHex: Object.fromEntries(Object.entries(STATUS_TOKEN).map(([k, v]) => [k, tokenHex(v)])),
      protoCss: Object.fromEntries(Object.entries(PROTOCOL_TOKEN).map(([k, v]) => [k, tokenHsl(v)])),
      agentTypeHex: Object.fromEntries(Object.entries(AGENT_TYPE_TOKEN).map(([k, v]) => [k, tokenHex(v)])),
      ring: tokenHex('--fg'),
      link: tokenHsl('--border-strong'),
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agents, themeKey]);

  // Size the canvas to whatever pane holds it (the Command Center tab, the
  // Orchestration page's column, fullscreen) and follow it as it resizes.
  useEffect(() => {
    const el = containerRef.current;
    const update = () => {
      const rect = el?.getBoundingClientRect();
      setDimensions({ width: Math.round(rect?.width || 800), height: isFullscreen ? window.innerHeight : Math.round(rect?.height || 600) });
    };
    update();
    const ro = typeof ResizeObserver !== 'undefined' && el ? new ResizeObserver(update) : null;
    ro?.observe(el);
    window.addEventListener('resize', update);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', update);
    };
  }, [isFullscreen]);

  // Live delegations become temporary links that fade after a few seconds.
  useEffect(() => {
    const ev = realtimeEvents?.[0];
    if (!ev) return;
    const target = ev.data?.toAgent || ev.targetAgentId;
    const isLive = ev.type === 'agent_invocation' || ((ev.type === 'agent_delegation' || ev.type === 'agent_message') && target);
    if (!isLive || !target || !ev.agentId) return;
    const link = {
      id: `live-${ev.agentId}-${target}-${Date.now()}`,
      source: ev.agentId,
      target,
      label: ev.data?.purpose || ev.purpose || (ev.type === 'agent_message' ? 'message' : 'delegates'),
      protocol: ev.data?.protocol || ev.protocol || 'internal',
      temporary: true,
      timestamp: Date.now(),
    };
    setLiveLinks((prev) => (prev.some((c) => c.source === link.source && c.target === link.target && Date.now() - c.timestamp < 4000) ? prev : [...prev, link]));
    const t = setTimeout(() => {
      fadeTimers.current.delete(t);
      setLiveLinks((prev) => prev.filter((c) => c.id !== link.id));
    }, LINK_TTL);
    fadeTimers.current.add(t);
  }, [realtimeEvents]);

  // Graph data. Node objects keep their identity across refreshes (the engine
  // stores x/y/z on them), so a new link reheats the layout without scattering it.
  const graphData = useMemo(() => {
    const nodes = agents.map((agent) => {
      const status = statuses[agent.id]?.status || (activeAgents.includes(agent.id) ? 'responding' : 'idle');
      const domain = agent.domain || 'general';
      const prev = nodeIdentity.current.get(agent.id) || {};
      const node = Object.assign(prev, {
        ...agent,
        id: agent.id,
        name: agent.displayName || agent.name,
        domain,
        status,
        isActive: status !== 'idle',
        agentType: agent.agentType || 'local',
        colorHex: colors.statusHex[status] ?? colors.domainHex[domain] ?? colors.generalHex,
        val: status !== 'idle' ? 15 : 10,
      });
      nodeIdentity.current.set(agent.id, node);
      return node;
    });
    const links = [...connections, ...liveLinks].map((conn, index) => {
      const protocol = normalizeProtocol(conn.protocol || 'internal');
      return {
        ...conn,
        id: conn.id || `edge-${index}`,
        protocol,
        color: conn.temporary || protocol !== 'internal' ? colors.protoCss[protocol] || colors.protoCss.internal : colors.link,
      };
    });
    return { nodes, links };
  }, [agents, connections, activeAgents, statuses, liveLinks, colors]);

  // Sensible forces: a tight tree rather than a cloud.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force('charge')?.strength(-120);
    fg.d3Force('link')?.distance((l) => (l.temporary ? 60 : 40));
  }, [viewMode, graphData.nodes.length]);

  // Fit the camera so the graph fills the pane. The library's zoomToFit uses a
  // very conservative distance (the "collapsed to a dot" look), so this
  // measures the bounding box and sets the distance from the camera's fov.
  const nodesRef = useRef([]);
  nodesRef.current = graphData.nodes;
  const fitCamera = useCallback(() => {
    const fg = fgRef.current;
    const camera = fg?.camera?.();
    const placed = nodesRef.current.filter((n) => Number.isFinite(n.x) && Number.isFinite(n.y));
    if (!fg || !camera || !placed.length) return;
    const min = (k) => Math.min(...placed.map((n) => n[k] || 0));
    const max = (k) => Math.max(...placed.map((n) => n[k] || 0));
    const center = { x: (min('x') + max('x')) / 2, y: (min('y') + max('y')) / 2, z: (min('z') + max('z')) / 2 };
    const half = Math.tan((camera.fov * Math.PI) / 180 / 2);
    const aspect = camera.aspect || 1;
    const margin = 16; // a node's radius, so edge nodes aren't clipped
    // Look along whichever horizontal axis the graph is thinnest on, so a
    // tree that grew along z is seen broadside rather than end-on.
    const depth = max('z') - min('z') <= max('x') - min('x') ? 'z' : 'x';
    const across = depth === 'z' ? 'x' : 'z';
    // Exact perspective fit: every node must project inside the frustum from
    // its own depth, nearer nodes needing more distance than farther ones.
    let distance = 60;
    for (const n of placed) {
      const d = (n[depth] || 0) - center[depth];
      distance = Math.max(distance, d + (Math.abs(n.y - center.y) + margin) / half, d + (Math.abs((n[across] || 0) - center[across]) + margin) / (half * aspect));
    }
    const eye = { ...center, [depth]: center[depth] + distance * 1.05 };
    fg.cameraPosition(eye, center, reducedMotion ? 0 : 500);
  }, [reducedMotion]);
  // Keep fitting while the layout settles (and once more when the engine
  // stops) — until the operator takes the camera, after which it is theirs.
  const onEngineStop = useCallback(() => {
    if (!userMoved.current) fitCamera();
  }, [fitCamera]);
  useEffect(() => {
    userMoved.current = false; // a fresh mount or a 2D/3D switch hands the camera back
    const timers = [350, 1200, 2600].map((ms) => setTimeout(() => !userMoved.current && fitCamera(), ms));
    return () => timers.forEach(clearTimeout);
  }, [fitCamera, viewMode]);

  // Dispose everything on unmount: timers, cached objects, the renderer.
  useEffect(() => {
    const timers = fadeTimers.current;
    const cache = nodeObjects.current;
    return () => {
      timers.forEach(clearTimeout);
      timers.clear();
      for (const entry of cache.values()) disposeNodeObject(entry.object);
      cache.clear();
      try {
        const fg = fgRef.current;
        fg?.pauseAnimation?.();
        const renderer = fg?.renderer?.();
        renderer?.dispose?.();
        renderer?.forceContextLoss?.();
      } catch {
        /* already gone */
      }
    };
  }, []);

  // Prune cached objects for nodes that left the roster.
  useEffect(() => {
    const live = new Set(graphData.nodes.map((n) => n.id));
    for (const [id, entry] of nodeObjects.current) {
      if (!live.has(id)) {
        disposeNodeObject(entry.object);
        nodeObjects.current.delete(id);
      }
    }
  }, [graphData]);

  const buildNodeObject = useCallback(
    (node) => {
      const working = node.status !== 'idle';
      const group = new THREE.Group();
      group.add(
        makePortrait(node, {
          fillHex: node.colorHex,
          ringHex: working ? node.colorHex : colors.agentTypeHex[node.agentType] ?? colors.ring,
          ringOpacity: working || node.agentType !== 'local' ? 0.95 : 0.45,
          glow: working,
        })
      );
      return group;
    },
    [colors]
  );

  // Cached per node; rebuilt only when its visual inputs change.
  const nodeThreeObject = useCallback(
    (node) => {
      const key = [node.id, node.colorHex, node.status, node.agentType, node.avatarUrl || ''].join('|');
      const cached = nodeObjects.current.get(node.id);
      if (cached && cached.key === key) return cached.object;
      if (cached) disposeNodeObject(cached.object);
      const object = buildNodeObject(node);
      nodeObjects.current.set(node.id, { key, object });
      return object;
    },
    [buildNodeObject]
  );

  const nodeLabel = useCallback((node) => {
    const meta = statusMeta(node.status);
    return `${escapeHtml(node.name)} · ${escapeHtml(prettyDomain(node.domain))}${node.status !== 'idle' ? ` · ${escapeHtml(meta.label)}` : ''}`;
  }, []);

  const handleNodeClick = useCallback(
    (node) => {
      setSelected(node);
      onAgentClick?.(node);
    },
    [onAgentClick]
  );

  const particles = !reducedMotion && isAnimating;
  const domains = Object.keys(colors.domainCss);

  return (
    <div
      ref={containerRef}
      onPointerDown={() => {
        userMoved.current = true;
      }}
      onWheel={() => {
        userMoved.current = true;
      }}
      className={`relative overflow-hidden bg-surface ${isFullscreen ? 'fixed inset-0 z-overlay' : 'h-full w-full'}`}
    >
      {/* Controls */}
      <div className="absolute left-3 top-3 z-raised">
        <Card padding="none" variant="glass" className="flex items-center gap-0.5 p-1">
          <IconButton icon={viewMode === '3d' ? Box : Grid3X3} label={viewMode === '3d' ? 'Switch to 2D' : 'Switch to 3D'} size="sm" onClick={() => setViewMode((m) => (m === '3d' ? '2d' : '3d'))} />
          <IconButton icon={isAnimating ? Pause : Play} label={isAnimating ? 'Pause motion' : 'Resume motion'} size="sm" disabled={reducedMotion} onClick={() => setIsAnimating((a) => !a)} />
          <IconButton icon={RefreshCw} label="Fit the graph" size="sm" onClick={fitCamera} />
          {onToggleFullscreen && (
            <IconButton icon={isFullscreen ? Minimize2 : Maximize2} label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'} size="sm" aria-pressed={isFullscreen} onClick={onToggleFullscreen} />
          )}
        </Card>
      </div>

      {/* Counts */}
      <div className="absolute right-3 top-3 z-raised flex flex-wrap items-center justify-end gap-1.5">
        <Chip size="xs">{graphData.nodes.length} agents</Chip>
        <Chip size="xs" tone={activeAgents.length ? 'ok' : 'neutral'} dot pulse={particles && activeAgents.length > 0}>
          {activeAgents.length} working
        </Chip>
        <Chip size="xs">{graphData.links.length} links</Chip>
      </div>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-raised hidden sm:block">
        <Card padding="sm" variant="glass" className="space-y-3 text-micro text-muted">
          {domains.length > 0 && (
            <div>
              <p className="mb-1.5 font-semibold uppercase tracking-wider">Domains</p>
              <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
                {domains.map((d) => (
                  <li key={d} className="flex items-center gap-1.5">
                    <svg aria-hidden="true" width="8" height="8" viewBox="0 0 8 8">
                      <circle cx="4" cy="4" r="4" fill={colors.domainCss[d]} />
                    </svg>
                    {prettyDomain(d)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div>
            <p className="mb-1.5 font-semibold uppercase tracking-wider">Links</p>
            <ul className="space-y-1">
              {Object.keys(PROTOCOL_TOKEN).map((p) => (
                <li key={p} className="flex items-center gap-1.5">
                  <svg aria-hidden="true" width="8" height="8" viewBox="0 0 8 8">
                    <circle cx="4" cy="4" r="4" fill={colors.protoCss[p]} />
                  </svg>
                  {p === 'internal' ? 'Chain of command' : p === 'a2a' ? 'A2A protocol' : p === 'paid' ? 'Paid external API' : 'Peer to peer'}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="mb-1.5 font-semibold uppercase tracking-wider">Status</p>
            <ul className="space-y-1">
              {['thinking', 'tool', 'responding', 'error'].map((s) => (
                <li key={s} className="flex items-center gap-1.5">
                  <StatusDot status={s} /> {statusMeta(s).label}
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>

      {/* Selected agent */}
      {selected && (
        <div className="absolute bottom-3 right-3 z-raised w-64 animate-slide-up">
          <Card padding="sm" variant="glass">
            <div className="flex items-start gap-3">
              <span className="relative shrink-0">
                <AgentAvatar agent={selected} size={40} rounded="rounded-control" status={selected.status} />
                <StatusDot status={selected.status} size="md" ring className="absolute -bottom-1 -right-1" />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-body-sm font-semibold text-fg-strong">{selected.name}</h3>
                <p className="truncate text-caption text-muted">{roleLine(selected)}</p>
                <p className="mt-1 line-clamp-2 text-micro text-muted">{selected.bio}</p>
              </div>
              <IconButton icon={X} label="Close" size="xs" onClick={() => setSelected(null)} />
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              <Chip size="xs" tone="accent">
                {prettyDomain(selected.domain)}
              </Chip>
              {(selected.tools || []).slice(0, 4).map((tool) => (
                <Chip key={tool} size="xs">
                  {tool}
                </Chip>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* Canvas */}
      <div className="absolute inset-0">
        {graphData.nodes.length > 0 ? (
          <ForceGraph3D
            ref={fgRef}
            graphData={graphData}
            width={dimensions.width}
            height={dimensions.height}
            backgroundColor="rgba(0,0,0,0)"
            nodeLabel={nodeLabel}
            nodeThreeObject={nodeThreeObject}
            nodeThreeObjectExtend={false}
            linkColor={(link) => link.color}
            linkWidth={(link) => (link.temporary ? 2.5 : 1.2)}
            linkOpacity={0.6}
            linkDirectionalParticles={(link) => (particles ? (link.temporary ? 4 : 1) : 0)}
            linkDirectionalParticleSpeed={(link) => (link.temporary ? 0.008 : 0.004)}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={(link) => link.color}
            onNodeClick={handleNodeClick}
            onLinkClick={onConnectionClick}
            onEngineStop={onEngineStop}
            enableNodeDrag={false}
            enableNavigationControls
            showNavInfo={false}
            // Static (reduced motion, or paused): the layout is computed up
            // front and never ticks; the render loop itself must keep running
            // or nothing paints at all.
            warmupTicks={reducedMotion ? 200 : 40}
            cooldownTicks={reducedMotion || !isAnimating ? 0 : 200}
            numDimensions={viewMode === '3d' ? 3 : 2}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <EmptyState compact icon={Layers} title="No agents to map" description="Add agents and the brigade appears here as a graph." />
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowVisualization3D;
