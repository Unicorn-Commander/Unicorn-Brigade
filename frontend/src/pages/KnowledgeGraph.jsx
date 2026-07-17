/**
 * Knowledge Graph Browser Page
 *
 * 3D visualization of the FalkorDB knowledge graph.
 * Shows entities as nodes, relationships as edges, with filtering and search.
 */

import { useState, useEffect, useMemo, useCallback, useRef, lazy, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Network,
  Search,
  Filter,
  RefreshCw,
  Database,
  Share2,
  Circle,
  ChevronRight,
  X,
  Maximize2,
  Minimize2,
  Box,
  Grid3X3,
  Play,
  Pause,
  Layers,
  Zap,
  AlertCircle,
  CheckCircle2,
  Info
} from 'lucide-react';
import Breadcrumbs from '../components/Breadcrumbs';
import { apiJson } from '../services/http';

// Lazy load ForceGraph3D to gracefully handle WebGL failures
const ForceGraph3D = lazy(() =>
  import('react-force-graph-3d').then(mod => ({ default: mod.default })).catch(() => ({
    default: () => (
      <div className="h-full flex items-center justify-center">
        <div className="text-center p-8">
          <AlertCircle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <p className="text-slate-300 font-medium">3D graph unavailable</p>
          <p className="text-sm text-slate-400 mt-1">WebGL required for knowledge graph visualization</p>
        </div>
      </div>
    ),
  }))
);

// Entity type colors
const entityTypeColors = {
  Person: '#10b981',      // emerald
  Company: '#3b82f6',     // blue
  Concept: '#8b5cf6',     // purple
  Location: '#f59e0b',    // amber
  Product: '#ec4899',     // pink
  Event: '#06b6d4',       // cyan
  Organization: '#ef4444', // red
  default: '#6b7280'      // gray
};

// Get color for entity type
const getEntityColor = (type) => entityTypeColors[type] || entityTypeColors.default;

const KnowledgeGraph = () => {
  // State
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('all');
  const [selectedNode, setSelectedNode] = useState(null);
  const [nodeDetails, setNodeDetails] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [viewMode, setViewMode] = useState('3d');
  const [isAnimating, setIsAnimating] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

  // Refs
  const fgRef = useRef();
  const containerRef = useRef();

  // Fetch graph data
  const fetchGraphData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiJson('/knowledge/graph', {
        params: {
          entity_type: filterType !== 'all' ? filterType : undefined,
          name_pattern: searchQuery || undefined,
          limit: 200,
        },
      });

      if (data.success) {
        // Transform nodes with colors based on type
        const coloredNodes = data.nodes.map(node => ({
          ...node,
          color: getEntityColor(node.type),
          val: 10
        }));

        // Transform links with colors
        const coloredLinks = data.links.map(link => ({
          ...link,
          color: 'rgba(139, 92, 246, 0.4)'
        }));

        setGraphData({ nodes: coloredNodes, links: coloredLinks });
      } else {
        setError(data.error || 'Failed to load graph data');
        setGraphData({ nodes: [], links: [] });
      }
    } catch (err) {
      console.error('Failed to fetch graph data:', err);
      setError('Failed to connect to knowledge graph service');
      setGraphData({ nodes: [], links: [] });
    } finally {
      setIsLoading(false);
    }
  }, [filterType, searchQuery]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const data = await apiJson('/knowledge/stats');
      if (data.success) {
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  // Fetch entity details
  const fetchEntityDetails = useCallback(async (entityName) => {
    try {
      const data = await apiJson(`/knowledge/entity/${encodeURIComponent(entityName)}`);
      if (data.success) {
        setNodeDetails(data);
      }
    } catch (err) {
      console.error('Failed to fetch entity details:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchGraphData();
    fetchStats();
  }, [fetchGraphData, fetchStats]);

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width || 800,
          height: isFullscreen ? window.innerHeight : 600
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [isFullscreen]);

  // Handle node click
  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    fetchEntityDetails(node.name);

    // Focus on node in 3D
    if (fgRef.current && viewMode === '3d') {
      const distance = 200;
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
      fgRef.current.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1000
      );
    }
  }, [fetchEntityDetails, viewMode]);

  // Handle link click
  const handleLinkClick = useCallback((link) => {
    console.log('Relationship clicked:', link);
  }, []);

  // Toggle view mode
  const toggleViewMode = () => {
    setViewMode(viewMode === '3d' ? '2d' : '3d');
  };

  // Reset camera
  const resetCamera = () => {
    if (fgRef.current) {
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
    }
  };

  // Toggle animation
  const toggleAnimation = () => {
    setIsAnimating(!isAnimating);
    if (fgRef.current) {
      if (isAnimating) {
        fgRef.current.pauseAnimation();
      } else {
        fgRef.current.resumeAnimation();
      }
    }
  };

  // Node label HTML
  const nodeLabel = useCallback((node) => {
    return `<div style="background: rgba(15, 23, 42, 0.95); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(139, 92, 246, 0.3); font-family: system-ui, sans-serif;">
      <div style="font-size: 14px; font-weight: 600; color: #f8fafc;">${node.name}</div>
      <div style="font-size: 11px; color: ${node.color}; text-transform: capitalize;">${node.type}</div>
    </div>`;
  }, []);

  // Get unique entity types for filter
  const entityTypes = useMemo(() => {
    if (!stats?.entity_types?.length) {
      // Fallback to types from current data
      const types = new Set(graphData.nodes.map(n => n.type));
      return ['all', ...Array.from(types)];
    }
    return ['all', ...stats.entity_types];
  }, [stats, graphData.nodes]);

  // Handle search submit
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchGraphData();
  };

  // Loading state
  if (isLoading && !graphData.nodes.length) {
    return (
      <div className="min-h-screen p-8 flex items-center justify-center">
        <div className="text-center">
          <Network className="w-16 h-16 text-unicorn-500 animate-pulse mx-auto mb-4" />
          <p className="text-slate-400">Loading Knowledge Graph...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${isFullscreen ? 'p-0' : 'p-4 md:p-6 lg:p-8'}`}>
      {!isFullscreen && (
        <>
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <Breadcrumbs />
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 border border-cyan-500/30">
                  <Network className="w-8 h-8 text-cyan-400" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 via-blue-400 to-cyan-400 bg-clip-text text-transparent">
                    Knowledge Graph
                  </h1>
                  <p className="text-slate-400">
                    Explore entities and relationships in FalkorDB
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                {stats && (
                  <span className={`flex items-center space-x-1 text-xs ${
                    stats.status === 'connected' ? 'text-green-400' : 'text-yellow-400'
                  }`}>
                    <span className={`w-2 h-2 rounded-full ${
                      stats.status === 'connected' ? 'bg-green-400' : 'bg-yellow-400'
                    } animate-pulse`}></span>
                    <span>{stats.status === 'connected' ? 'Connected' : 'Disconnected'}</span>
                  </span>
                )}
                <button
                  onClick={() => { fetchGraphData(); fetchStats(); }}
                  className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 hover:border-cyan-500/50 transition-all"
                >
                  <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                  <span>Refresh</span>
                </button>
              </div>
            </div>
          </motion.div>

          {/* Stats Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-4 gap-4 mb-6"
          >
            {[
              { label: 'Entities', value: stats?.total_entities || graphData.nodes.length, icon: Circle, color: 'cyan' },
              { label: 'Relationships', value: stats?.total_relationships || graphData.links.length, icon: Share2, color: 'purple' },
              { label: 'Entity Types', value: stats?.entity_types?.length || entityTypes.length - 1, icon: Layers, color: 'blue' },
              { label: 'Rel. Types', value: stats?.relationship_types?.length || 0, icon: Zap, color: 'pink' },
            ].map((stat) => (
              <div
                key={stat.label}
                className="card glass hover:border-slate-600 transition-all"
              >
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg bg-${stat.color}-500/20`}>
                    <stat.icon className={`w-5 h-5 text-${stat.color}-400`} />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-white">{stat.value}</p>
                    <p className="text-xs text-slate-400">{stat.label}</p>
                  </div>
                </div>
              </div>
            ))}
          </motion.div>

          {/* Search and Filter */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex items-center space-x-4 mb-6"
          >
            <form onSubmit={handleSearchSubmit} className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="Search entities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </form>

            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500"
              >
                {entityTypes.map((type) => (
                  <option key={type} value={type}>
                    {type === 'all' ? 'All Types' : type}
                  </option>
                ))}
              </select>
            </div>
          </motion.div>

          {/* Error message */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-6 p-4 rounded-lg bg-red-500/10 border border-red-500/30 flex items-center space-x-3"
            >
              <AlertCircle className="w-5 h-5 text-red-400" />
              <p className="text-red-400">{error}</p>
            </motion.div>
          )}
        </>
      )}

      {/* Main Content Grid */}
      <div className={`grid ${isFullscreen ? '' : 'grid-cols-4 gap-6'}`}>
        {/* 3D Visualization */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className={isFullscreen ? 'fixed inset-0 z-50' : 'col-span-3'}
        >
          <div
            ref={containerRef}
            className={`relative ${isFullscreen ? 'fixed inset-0 z-50' : 'w-full h-[600px]'} bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl overflow-hidden border border-slate-700/50`}
          >
            {/* Background grid effect */}
            <div className="absolute inset-0 opacity-10 pointer-events-none">
              <div className="absolute inset-0" style={{
                backgroundImage: `
                  linear-gradient(rgba(6, 182, 212, 0.1) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(6, 182, 212, 0.1) 1px, transparent 1px)
                `,
                backgroundSize: '50px 50px',
              }} />
            </div>

            {/* Control panel */}
            <div className="absolute top-4 left-4 z-10 flex flex-col space-y-2">
              <div className="flex items-center space-x-2 p-2 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
                <button
                  onClick={toggleViewMode}
                  className={`p-2 rounded-lg transition-all ${
                    viewMode === '3d'
                      ? 'bg-cyan-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                  title={viewMode === '3d' ? 'Switch to 2D' : 'Switch to 3D'}
                >
                  {viewMode === '3d' ? <Box className="w-4 h-4" /> : <Grid3X3 className="w-4 h-4" />}
                </button>
                <button
                  onClick={toggleAnimation}
                  className={`p-2 rounded-lg transition-all ${
                    isAnimating
                      ? 'bg-green-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                  title={isAnimating ? 'Pause animation' : 'Resume animation'}
                >
                  {isAnimating ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>
                <button
                  onClick={resetCamera}
                  className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
                  title="Reset camera"
                >
                  <RefreshCw className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setIsFullscreen(!isFullscreen)}
                  className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
                  title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
                >
                  {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Stats panel */}
            <div className="absolute top-4 right-4 z-10 p-3 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
              <div className="flex items-center space-x-4 text-xs">
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 rounded-full bg-cyan-500" />
                  <span className="text-slate-400">Nodes:</span>
                  <span className="text-white font-semibold">{graphData.nodes.length}</span>
                </div>
                <div className="flex items-center space-x-1.5">
                  <div className="w-2 h-2 rounded-full bg-unicorn-500" />
                  <span className="text-slate-400">Links:</span>
                  <span className="text-white font-semibold">{graphData.links.length}</span>
                </div>
              </div>
            </div>

            {/* Entity type legend */}
            <div className="absolute bottom-4 left-4 z-10 p-3 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Entity Types</p>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                {Object.entries(entityTypeColors).slice(0, 6).map(([type, color]) => (
                  <div key={type} className="flex items-center space-x-1.5">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                    <span className="text-[10px] text-slate-400">{type}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Graph Canvas */}
            <div className="absolute inset-0">
              {graphData.nodes.length > 0 ? (
                <Suspense fallback={<div className="h-full flex items-center justify-center"><Network className="w-8 h-8 text-unicorn-400 animate-pulse" /></div>}>
                  <ForceGraph3D
                    ref={fgRef}
                    graphData={graphData}
                    width={dimensions.width}
                    height={dimensions.height}
                    backgroundColor="rgba(0,0,0,0)"
                    nodeLabel={nodeLabel}
                    nodeColor={node => node.color}
                    nodeVal={node => node.val}
                    nodeOpacity={0.9}
                    linkColor={link => link.color || 'rgba(139, 92, 246, 0.4)'}
                    linkWidth={1.5}
                    linkOpacity={0.6}
                    linkLabel={link => link.label}
                    linkDirectionalParticles={2}
                    linkDirectionalParticleSpeed={0.005}
                    linkDirectionalParticleWidth={2}
                    linkDirectionalParticleColor={() => '#06b6d4'}
                    onNodeClick={handleNodeClick}
                    onLinkClick={handleLinkClick}
                    enableNodeDrag={true}
                    enableNavigationControls={true}
                    showNavInfo={false}
                    warmupTicks={100}
                    cooldownTicks={50}
                    d3AlphaDecay={0.02}
                    d3VelocityDecay={0.3}
                    numDimensions={viewMode === '3d' ? 3 : 2}
                  />
                </Suspense>
              ) : (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    {stats?.status === 'disconnected' ? (
                      <>
                        <Database className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
                        <p className="text-slate-400">FalkorDB not connected</p>
                        <p className="text-sm text-slate-400 mt-2">
                          Enable FalkorDB in your environment to use the knowledge graph
                        </p>
                        <p className="text-xs text-slate-600 mt-1">
                          Set FALKORDB_ENABLED=true and configure connection
                        </p>
                      </>
                    ) : (
                      <>
                        <Layers className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                        <p className="text-slate-400">No entities in knowledge graph</p>
                        <p className="text-sm text-slate-400 mt-2">
                          Use agents with knowledge tools to populate the graph
                        </p>
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Title overlay */}
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10">
              <div className="px-4 py-2 rounded-full bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
                <p className="text-xs text-slate-400 flex items-center space-x-2">
                  <Database className="w-3 h-3" />
                  <span>Knowledge Graph Browser</span>
                  <span className="text-cyan-400">|</span>
                  <span className="text-cyan-400">{viewMode.toUpperCase()}</span>
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Sidebar */}
        {!isFullscreen && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
            className="space-y-6"
          >
            {/* Selected Entity Details */}
            <div className="card glass">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                <Info className="w-4 h-4 text-cyan-400" />
                <span>Entity Details</span>
              </h3>

              {selectedNode && nodeDetails ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-lg font-semibold text-white">{selectedNode.name}</p>
                    <p className="text-sm text-cyan-400">{selectedNode.type}</p>
                  </div>

                  {nodeDetails.entity?.created_at && (
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Created</p>
                      <p className="text-sm text-slate-300">
                        {new Date(nodeDetails.entity.created_at).toLocaleString()}
                      </p>
                    </div>
                  )}

                  {nodeDetails.entity?.created_by && (
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-1">Created By</p>
                      <p className="text-sm text-slate-300">{nodeDetails.entity.created_by}</p>
                    </div>
                  )}

                  {nodeDetails.relationships?.length > 0 && (
                    <div>
                      <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">
                        Relationships ({nodeDetails.relationships.length})
                      </p>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {nodeDetails.relationships.slice(0, 10).map((rel, idx) => (
                          <div
                            key={idx}
                            className="p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-xs"
                          >
                            <div className="flex items-center space-x-1 text-slate-300">
                              <span className="text-cyan-400">{rel.from?.name}</span>
                              <ChevronRight className="w-3 h-3 text-unicorn-400" />
                              <span className="text-unicorn-400">{rel.relationship}</span>
                              <ChevronRight className="w-3 h-3 text-unicorn-400" />
                              <span className="text-cyan-400">{rel.to?.name}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <button
                    onClick={() => { setSelectedNode(null); setNodeDetails(null); }}
                    className="w-full mt-2 px-3 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all text-sm"
                  >
                    Clear Selection
                  </button>
                </div>
              ) : (
                <p className="text-sm text-slate-400 text-center py-4">
                  Click on a node to view details
                </p>
              )}
            </div>

            {/* Relationship Types */}
            {stats?.relationship_types?.length > 0 && (
              <div className="card glass">
                <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                  <Share2 className="w-4 h-4 text-unicorn-400" />
                  <span>Relationship Types</span>
                </h3>
                <div className="flex flex-wrap gap-2">
                  {stats.relationship_types.map((type) => (
                    <span
                      key={type}
                      className="px-2 py-1 text-xs rounded-full bg-unicorn-500/20 text-unicorn-300"
                    >
                      {type}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Connection Status */}
            <div className="card glass">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                <Database className="w-4 h-4 text-emerald-400" />
                <span>FalkorDB Status</span>
              </h3>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">Status</span>
                  <span className={`flex items-center space-x-1 text-sm ${
                    stats?.status === 'connected' ? 'text-emerald-400' : 'text-yellow-400'
                  }`}>
                    {stats?.status === 'connected' ? (
                      <CheckCircle2 className="w-4 h-4" />
                    ) : (
                      <AlertCircle className="w-4 h-4" />
                    )}
                    <span>{stats?.status || 'Unknown'}</span>
                  </span>
                </div>

                {stats?.host && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-300">Host</span>
                    <span className="text-sm text-slate-400">{stats.host}:{stats.port}</span>
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <span className="text-sm text-slate-300">Enabled</span>
                  <span className={`text-sm ${stats?.enabled ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {stats?.enabled ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Tips */}
            <div className="card glass bg-slate-800/30">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-3">
                <Zap className="w-4 h-4 text-yellow-400" />
                <span>Tips</span>
              </h3>
              <ul className="space-y-2 text-xs text-slate-400">
                <li>Click on nodes to view entity details</li>
                <li>Drag nodes to rearrange the graph</li>
                <li>Use scroll to zoom in/out</li>
                <li>Toggle between 2D/3D views</li>
                <li>Use search to filter entities</li>
              </ul>
            </div>
          </motion.div>
        )}
      </div>

      {/* Selected Node Panel (Fullscreen mode) */}
      <AnimatePresence>
        {selectedNode && isFullscreen && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="fixed bottom-4 right-4 z-50 w-80 p-4 rounded-lg bg-slate-800/90 backdrop-blur-sm border border-slate-700/50"
          >
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">{selectedNode.name}</h3>
                <p className="text-xs text-cyan-400">{selectedNode.type}</p>
              </div>
              <button
                onClick={() => { setSelectedNode(null); setNodeDetails(null); }}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {nodeDetails?.relationships?.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">
                  Relationships ({nodeDetails.relationships.length})
                </p>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {nodeDetails.relationships.slice(0, 5).map((rel, idx) => (
                    <div key={idx} className="text-[10px] text-slate-400">
                      {rel.from?.name} <span className="text-unicorn-400">{rel.relationship}</span> {rel.to?.name}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default KnowledgeGraph;
