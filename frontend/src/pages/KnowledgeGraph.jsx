/**
 * Knowledge graph — what the agents have learned, in FalkorDB.
 *
 * Frame → honest stat cards → a labelled search + type filter → the graph
 * pane framed in a Card (fullscreen through the real Fullscreen API) → entity
 * detail in a Card (a Sheet on phones) → relationship types as chips → the
 * four states, including "FalkorDB unreachable" with the reason.
 */
import { useState, useEffect, useMemo, useCallback, useRef, lazy, Suspense } from 'react';
import { Network, Search, RefreshCw, Database, Share2, Layers, Zap, Box, Grid3X3, Play, Pause, Maximize2, Minimize2, RotateCcw, Circle, X } from 'lucide-react';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import { tokenHsl } from '../utils/tokens';
import Breadcrumbs from '../components/Breadcrumbs';
import { absoluteTime } from '../components/ActivityFeed';
import { Button, IconButton, Card, CardHeader, Chip, Input, Select, Sheet, StatCard, Page, PageHeader, EmptyState, ErrorState, OfflineState, LoadingState } from '../components/ui';

const ForceGraph3D = lazy(() =>
  import('react-force-graph-3d')
    .then((mod) => ({ default: mod.default }))
    .catch(() => ({
      default: () => <EmptyState compact icon={Box} title="3D graph unavailable" description="This browser has no WebGL, which the graph needs." className="h-full" />,
    }))
);

// Entity types get a tone each, in order, cycling — the same tone drives the
// legend chip and the node colour, so the legend is always true.
const TONES = ['accent', 'info', 'ok', 'warn', 'live', 'danger', 'neutral'];
const TONE_TOKEN = { accent: '--accent', info: '--info', ok: '--ok', warn: '--warn', live: '--live', danger: '--danger', neutral: '--subtle' };
const LIMIT = 200;

function useMediaQuery(q) {
  const [match, setMatch] = useState(() => typeof window !== 'undefined' && window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setMatch(m.matches);
    m.addEventListener('change', on);
    return () => m.removeEventListener('change', on);
  }, [q]);
  return match;
}

function EntityDetail({ node, details, error, onClear, toneOf }) {
  if (!node) return <EmptyState compact icon={Circle} title="Pick an entity" description="Click a node in the graph to see where it came from and what it is linked to." />;
  const rels = details?.relationships || [];
  const entity = details?.entity || {};
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-lead font-semibold text-fg-strong">{node.name}</p>
          <Chip tone={toneOf(node.type)} size="xs" dot className="mt-1">
            {node.type}
          </Chip>
        </div>
        <IconButton icon={X} label="Clear selection" size="sm" onClick={onClear} />
      </div>
      {error ? (
        <p className="text-caption text-warn">Couldn’t load the details: {humanize(error, { what: 'loading the entity' })}</p>
      ) : !details ? (
        <LoadingState variant="text" count={3} label="Loading entity" />
      ) : (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            {entity.created_at && (
              <div>
                <dt className="text-caption text-muted">Learned</dt>
                <dd className="text-body-sm text-fg">{absoluteTime(entity.created_at)}</dd>
              </div>
            )}
            {entity.created_by && (
              <div>
                <dt className="text-caption text-muted">By</dt>
                <dd className="truncate text-body-sm text-fg">{entity.created_by}</dd>
              </div>
            )}
            {entity.properties?.source && (
              <div className="col-span-2">
                <dt className="text-caption text-muted">Source</dt>
                <dd className="truncate font-mono text-caption text-fg">{entity.properties.source}</dd>
              </div>
            )}
          </dl>
          <div>
            <p className="mb-1.5 text-caption text-muted">
              Relationships{rels.length ? ` (${rels.length})` : ''}
            </p>
            {rels.length === 0 ? (
              <p className="text-body-sm text-muted">No relationships recorded yet.</p>
            ) : (
              <ul className="max-h-56 space-y-1 overflow-y-auto">
                {rels.slice(0, 20).map((r, i) => (
                  <li key={i} className="rounded-control border border-border bg-surface/60 px-2 py-1.5 text-caption text-fg">
                    <span className="font-medium">{r.from?.name}</span> <Chip size="xs" tone="accent" className="mx-1 align-middle">{r.relationship}</Chip> <span className="font-medium">{r.to?.name}</span>
                    {r.confidence != null && <span className="ml-1 text-subtle">· {Math.round(r.confidence * 100)}%</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function KnowledgeGraph() {
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const [selected, setSelected] = useState(null);
  const [details, setDetails] = useState(null);
  const [detailsError, setDetailsError] = useState(null);
  const [viewMode, setViewMode] = useState('3d');
  const [animating, setAnimating] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [size, setSize] = useState({ width: 800, height: 600 });
  const fgRef = useRef();
  const paneRef = useRef();
  const narrow = useMediaQuery('(max-width: 1279px)');

  const colors = useMemo(() => {
    const m = {};
    TONES.forEach((t) => {
      m[t] = tokenHsl(TONE_TOKEN[t]);
    });
    return { ...m, link: tokenHsl('--accent', 0.35), particle: tokenHsl('--info') };
  }, []);

  // ── data ──
  const loadGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson('/knowledge/graph', { params: { entity_type: type || undefined, name_pattern: query || undefined, limit: LIMIT } });
      if (data?.success === false) throw new Error(data.error || 'The knowledge graph could not be read.');
      setGraph({ nodes: (data?.nodes || []).map((n) => ({ ...n, val: n.val ?? 10 })), links: data?.links || [] });
    } catch (err) {
      setError(err);
      setGraph({ nodes: [], links: [] });
    } finally {
      setLoading(false);
    }
  }, [type, query]);

  const loadStats = useCallback(async () => {
    try {
      const data = await apiJson('/knowledge/stats');
      setStats(data || null);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);
  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      loadGraph();
      loadStats();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [loadGraph, loadStats]);

  // ── pane size + fullscreen ──
  useEffect(() => {
    const el = paneRef.current;
    if (!el) return undefined;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setSize({ width: Math.max(200, Math.round(r.width)), height: Math.max(200, Math.round(r.height)) });
    };
    measure();
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null;
    ro?.observe(el);
    window.addEventListener('resize', measure);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', measure);
    };
  }, [loading, error]);

  useEffect(() => {
    const on = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', on);
    return () => document.removeEventListener('fullscreenchange', on);
  }, []);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else paneRef.current?.requestFullscreen?.().catch(() => {});
  };

  // ── derived ──
  const entityTypes = useMemo(() => {
    const fromStats = stats?.entity_types || [];
    const fromData = [...new Set(graph.nodes.map((n) => n.type).filter(Boolean))];
    return [...new Set([...fromStats, ...fromData])];
  }, [stats, graph.nodes]);
  const toneOf = useCallback((t) => TONES[Math.max(0, entityTypes.indexOf(t)) % TONES.length], [entityTypes]);
  const disconnected = stats && stats.status && stats.status !== 'connected';
  const hasFilters = Boolean(query || type);

  // ── interactions ──
  const selectNode = useCallback(async (node) => {
    setSelected(node);
    setDetails(null);
    setDetailsError(null);
    if (fgRef.current && node && Number.isFinite(node.x)) {
      const dist = 200;
      const ratio = 1 + dist / Math.max(1, Math.hypot(node.x, node.y, node.z || 0));
      fgRef.current.cameraPosition({ x: node.x * ratio, y: node.y * ratio, z: (node.z || 0) * ratio }, node, 1000);
    }
    try {
      const data = await apiJson(`/knowledge/entity/${encodeURIComponent(node.name)}`);
      setDetails(data);
    } catch (err) {
      setDetailsError(err);
    }
  }, []);
  const clearSelection = () => {
    setSelected(null);
    setDetails(null);
  };
  const resetCamera = () => fgRef.current?.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
  const toggleAnimation = () => {
    if (animating) fgRef.current?.pauseAnimation();
    else fgRef.current?.resumeAnimation();
    setAnimating((a) => !a);
  };
  const nodeLabel = useCallback(
    (n) =>
      `<div style="background:hsl(var(--overlay));border:1px solid hsl(var(--border));border-radius:8px;padding:6px 10px;font-family:system-ui,sans-serif"><div style="font-size:13px;font-weight:600;color:hsl(var(--fg-strong))">${n.name}</div><div style="font-size:11px;color:hsl(var(--muted))">${n.type || ''}</div></div>`,
    []
  );

  // ── the pane body (four states) ──
  let pane;
  if (offline && !graph.nodes.length) pane = <OfflineState onRetry={loadGraph} className="h-full" />;
  else if (loading) pane = <LoadingState variant="chart" label="Loading the knowledge graph" className="h-full p-4" />;
  else if (disconnected)
    pane = (
      <ErrorState
        title="FalkorDB isn’t reachable"
        detail={stats?.error || stats?.detail || (stats?.enabled === false ? 'The knowledge graph is turned off for this deployment (FALKORDB_ENABLED).' : `Brigade could not connect to ${stats?.host || 'the graph database'}${stats?.port ? `:${stats.port}` : ''}.`)}
        onRetry={() => {
          loadStats();
          loadGraph();
        }}
        className="h-full"
      />
    );
  else if (error) pane = <ErrorState title="Couldn’t read the knowledge graph" detail={humanize(error, { what: 'loading the graph' })} onRetry={loadGraph} className="h-full" />;
  else if (!graph.nodes.length)
    pane = hasFilters ? (
      <EmptyState compact icon={Search} title="No entities match" description="Try another name or type." action={<Button variant="secondary" size="sm" onClick={() => { setDraft(''); setQuery(''); setType(''); }}>Clear filters</Button>} className="h-full" />
    ) : (
      <EmptyState icon={Layers} title="Nothing learned yet" description="Agents with knowledge tools add entities and relationships as they work. The graph fills in on its own." className="h-full" />
    );
  else
    pane = (
      <Suspense fallback={<LoadingState variant="chart" label="Loading the graph" className="h-full p-4" />}>
        <ForceGraph3D
          ref={fgRef}
          graphData={graph}
          width={size.width}
          height={size.height}
          backgroundColor="rgba(0,0,0,0)"
          nodeLabel={nodeLabel}
          nodeColor={(n) => colors[toneOf(n.type)]}
          nodeVal={(n) => n.val}
          nodeOpacity={0.9}
          linkColor={() => colors.link}
          linkWidth={1.5}
          linkOpacity={0.6}
          linkLabel={(l) => l.label}
          linkDirectionalParticles={animating ? 2 : 0}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleWidth={2}
          linkDirectionalParticleColor={() => colors.particle}
          onNodeClick={selectNode}
          enableNodeDrag
          enableNavigationControls
          showNavInfo={false}
          warmupTicks={100}
          cooldownTicks={50}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
          numDimensions={viewMode === '3d' ? 3 : 2}
        />
      </Suspense>
    );

  const statusChip = !stats ? (
    <Chip dot>Checking FalkorDB…</Chip>
  ) : disconnected ? (
    <Chip tone="danger" dot>
      FalkorDB unreachable
    </Chip>
  ) : (
    <Chip tone="ok" dot>
      FalkorDB connected
    </Chip>
  );
  const n = (v) => (v == null ? '—' : Number(v).toLocaleString());

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Knowledge"
        title="Knowledge graph"
        description="Entities and relationships your agents have learned, stored in FalkorDB."
        actions={
          <>
            {statusChip}
            <Button variant="secondary" icon={RefreshCw} onClick={() => { loadStats(); loadGraph(); }}>
              Refresh
            </Button>
          </>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Circle} label="Entities" value={n(stats?.total_entities)} />
        <StatCard icon={Share2} label="Relationships" value={n(stats?.total_relationships)} />
        <StatCard icon={Layers} label="Entity types" value={n(stats?.entity_types?.length)} />
        <StatCard icon={Zap} label="Relationship types" value={n(stats?.relationship_types?.length)} />
      </div>

      <Card padding="sm" className="mb-5">
        <form
          className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(draft.trim());
          }}
        >
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input type="search" aria-label="Search entities by name" placeholder="Search entities by name, then press Enter" value={draft} onChange={(e) => setDraft(e.target.value)} className="pl-9" />
          </div>
          <Select aria-label="Filter by entity type" value={type} onChange={(e) => setType(e.target.value)} className="md:w-48">
            <option value="">All types</option>
            {entityTypes.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Button type="submit" variant="secondary" icon={Search}>
            Search
          </Button>
        </form>
        {hasFilters && !loading && (
          <div className="mt-2 flex items-center gap-2 text-caption text-muted">
            <span>
              {graph.nodes.length} entit{graph.nodes.length === 1 ? 'y' : 'ies'}{query ? ` matching “${query}”` : ''}{type ? ` of type ${type}` : ''}
            </span>
            <Button variant="link" size="xs" onClick={() => { setDraft(''); setQuery(''); setType(''); }}>
              Clear
            </Button>
          </div>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Card padding="none" className="flex flex-col overflow-hidden">
          <div ref={paneRef} className={`relative h-[480px] lg:h-[560px] xl:h-[640px] ${isFullscreen ? 'bg-surface' : ''}`}>
            {pane}
            {!loading && !error && !disconnected && graph.nodes.length > 0 && (
              <>
                <div className="absolute left-3 top-3 z-raised flex items-center gap-0.5 rounded-control border border-border bg-overlay/90 p-0.5 shadow-e2 backdrop-blur">
                  <IconButton icon={viewMode === '3d' ? Grid3X3 : Box} label={viewMode === '3d' ? 'Switch to 2D' : 'Switch to 3D'} size="sm" onClick={() => setViewMode((v) => (v === '3d' ? '2d' : '3d'))} />
                  <IconButton icon={animating ? Pause : Play} label={animating ? 'Pause motion' : 'Resume motion'} size="sm" onClick={toggleAnimation} />
                  <IconButton icon={RotateCcw} label="Reset camera" size="sm" onClick={resetCamera} />
                  <IconButton icon={isFullscreen ? Minimize2 : Maximize2} label={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'} size="sm" onClick={toggleFullscreen} />
                </div>
                <div className="absolute right-3 top-3 z-raised">
                  <Chip size="xs">
                    {graph.nodes.length} nodes · {graph.links.length} links{graph.nodes.length >= LIMIT ? ` · first ${LIMIT}` : ''}
                  </Chip>
                </div>
                {isFullscreen && selected && (
                  <div className="absolute bottom-4 right-4 z-raised w-80 max-w-[calc(100%-2rem)]">
                    <Card variant="glass" padding="sm">
                      <EntityDetail node={selected} details={details} error={detailsError} onClear={clearSelection} toneOf={toneOf} />
                    </Card>
                  </div>
                )}
              </>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-1.5 border-t border-border px-3 py-2">
            {entityTypes.length === 0 ? (
              <span className="text-caption text-muted">Entity types appear here as the graph fills.</span>
            ) : (
              entityTypes.map((t) => (
                <Chip key={t} size="xs" tone={toneOf(t)} dot selected={type === t} onClick={() => setType(type === t ? '' : t)} aria-label={`${type === t ? 'Show all types' : `Show only ${t}`}`}>
                  {t}
                </Chip>
              ))
            )}
            <span className="ml-auto hidden text-caption text-muted sm:inline">Click a node for details · drag to rearrange · scroll to zoom</span>
          </div>
        </Card>

        <div className="space-y-5">
          <Card className="hidden xl:block">
            <CardHeader title="Entity" description={selected ? 'Selected in the graph' : 'Nothing selected'} />
            <EntityDetail node={selected} details={details} error={detailsError} onClear={clearSelection} toneOf={toneOf} />
          </Card>

          <Card>
            <CardHeader title="Relationship types" description={stats?.relationship_types?.length ? `${stats.relationship_types.length} kinds of link` : 'How entities connect'} />
            {stats?.relationship_types?.length ? (
              <div className="flex flex-wrap gap-1.5">
                {stats.relationship_types.map((t) => (
                  <Chip key={t} size="xs" tone="accent" className="font-mono">
                    {t}
                  </Chip>
                ))}
              </div>
            ) : (
              <p className="text-body-sm text-muted">{disconnected ? 'Unavailable while FalkorDB is unreachable.' : 'None recorded yet.'}</p>
            )}
          </Card>

          <Card>
            <CardHeader icon={Database} title="FalkorDB" description={stats?.host ? `${stats.host}${stats.port ? `:${stats.port}` : ''}` : 'Graph database'} />
            <dl className="space-y-2 text-body-sm">
              <div className="flex items-center justify-between gap-2">
                <dt className="text-muted">Status</dt>
                <dd>{statusChip}</dd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <dt className="text-muted">Enabled</dt>
                <dd className="text-fg">{stats ? (stats.enabled ? 'Yes' : 'No') : '—'}</dd>
              </div>
              {stats?.graphs &&
                Object.entries(stats.graphs).map(([name, g]) => (
                  <div key={name} className="flex items-center justify-between gap-2">
                    <dt className="truncate font-mono text-caption text-muted">{name}</dt>
                    <dd className="whitespace-nowrap tabular-nums text-fg">
                      {n(g.nodes)} nodes · {n(g.relationships)} links
                    </dd>
                  </div>
                ))}
            </dl>
          </Card>
        </div>
      </div>

      <Sheet isOpen={Boolean(selected) && narrow && !isFullscreen} onClose={clearSelection} title={selected?.name}>
        <div className="pt-1">
          <EntityDetail node={selected} details={details} error={detailsError} onClear={clearSelection} toneOf={toneOf} />
        </div>
      </Sheet>
    </Page>
  );
}
