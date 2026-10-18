/**
 * 3D Workflow Visualization Component
 *
 * Uses react-force-graph-3d for immersive 3D visualization of agent orchestration.
 * Shows agents as nodes, connections as edges, with depth representing complexity.
 * Falls back to a 2D agent grid when WebGL is not available.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Maximize2,
  Minimize2,
  RotateCcw,
  Eye,
  Layers,
  Zap,
  Box,
  Grid3X3,
  Play,
  Pause,
  RefreshCw,
  Network
} from 'lucide-react';

import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { normalizeProtocol } from '../utils/protocol';

// Domain colors — one per seed domain, matched to the org chart's ring hues so
// the 3D graph and the org chart speak the same color language.
const domainColors = {
  orchestration: '#fde047', // yellow-300
  meta: '#e879f9', // fuchsia-400
  financial: '#fbbf24', // amber-400
  legal: '#60a5fa', // blue-400
  medical: '#fb7185', // rose-400
  technology: '#22d3ee', // cyan-400
  engineering: '#22d3ee', // cyan-400
  investigation: '#fb923c', // orange-400
  intelligence: '#818cf8', // indigo-400
  support: '#f472b6', // pink-400
  data: '#38bdf8', // sky-400
  knowledge: '#a78bfa', // violet-400
  productivity: '#2dd4bf', // teal-400
  sales: '#34d399', // emerald-400
  cybersecurity: '#06b6d4', // cyan (subdomain)
  general: '#6b7280', // slate fallback
};

// Hex to RGB helper
const hexToRgb = (hex) => {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16)
  } : { r: 139, g: 92, b: 246 };
};

// Recursively dispose a cached node object's GPU resources (geometries,
// materials, and any textures they reference) so reusing/clearing the cache
// doesn't leak VRAM.
const disposeNodeObject = (object) => {
  if (!object) return;
  object.traverse((child) => {
    if (child.geometry && typeof child.geometry.dispose === 'function') {
      child.geometry.dispose();
    }
    const materials = Array.isArray(child.material)
      ? child.material
      : (child.material ? [child.material] : []);
    materials.forEach((material) => {
      if (material.map && typeof material.map.dispose === 'function') {
        material.map.dispose();
      }
      if (typeof material.dispose === 'function') {
        material.dispose();
      }
    });
  });
};

const WorkflowVisualization3D = ({
  agents = [],
  connections = [],
  activeAgents = [],
  onAgentClick,
  onConnectionClick,
  isFullscreen = false,
  onToggleFullscreen,
  showLabels = true,
  animate = true,
  realtimeEvents = [], // NEW: SSE events for dynamic connections
}) => {
  const fgRef = useRef();
  const containerRef = useRef();
  const fadeTimers = useRef(new Set());
  // Cache of per-node Three.js objects so react-force-graph reuses the same
  // Group/sprite/material/texture across refreshes instead of allocating (and
  // leaking) a fresh set on every graphData update. Keyed by node id; each entry
  // remembers the inputs it was built from so we only rebuild when they change.
  const nodeObjectCache = useRef(new Map());
  const [viewMode, setViewMode] = useState('3d');
  const [selectedNode, setSelectedNode] = useState(null);
  const [isAnimating, setIsAnimating] = useState(animate);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [activeConnections, setActiveConnections] = useState([]); // NEW: Track active connections

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width || 800,
          height: isFullscreen ? window.innerHeight : (rect.height || 600)
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [isFullscreen]);

  // NEW: Handle realtime events to create dynamic connections
  useEffect(() => {
    if (!realtimeEvents || realtimeEvents.length === 0) return;

    const latestEvent = realtimeEvents[0]; // Most recent event

    // Check for peer-to-peer agent_invocation events
    if (latestEvent.type === 'agent_invocation') {
      // Extract target agent info from data object (backend structure)
      const targetAgentId = latestEvent.data?.toAgent || latestEvent.targetAgentId;
      const purpose = latestEvent.data?.purpose || latestEvent.purpose || 'Peer request';
      const protocol = latestEvent.data?.protocol || latestEvent.protocol || 'peer';

      if (!targetAgentId) return; // Skip if no target

      const newConnection = {
        id: `peer-${latestEvent.agentId}-${targetAgentId}-${Date.now()}`,
        source: latestEvent.agentId,
        target: targetAgentId,
        label: purpose,
        protocol: protocol,
        isPeer: true,
        temporary: true,
        timestamp: Date.now(),
      };

      // Add connection
      setActiveConnections(prev => {
        // Avoid duplicates
        const exists = prev.some(c =>
          c.source === newConnection.source &&
          c.target === newConnection.target &&
          Date.now() - c.timestamp < 4000 // Within last 4 seconds
        );

        if (exists) return prev;
        return [...prev, newConnection];
      });

      // Auto-fade after 5 seconds (tracked so unmount can clear it).
      const t = setTimeout(() => {
        fadeTimers.current.delete(t);
        setActiveConnections(prev => prev.filter(c => c.id !== newConnection.id));
      }, 5000);
      fadeTimers.current.add(t);
    }

    // Check for delegation or message events with a target agent
    if (
      ['agent_delegation', 'agent_message'].includes(latestEvent.type) &&
      latestEvent.data?.toAgent
    ) {
      const newConnection = {
        id: `temp-${latestEvent.id}`,
        source: latestEvent.agentId,
        target: latestEvent.data.toAgent,
        label: latestEvent.type === 'agent_delegation' ? 'delegates' : 'message',
        protocol: latestEvent.data.protocol || 'internal',
        temporary: true,
        timestamp: Date.now(),
      };

      // Add connection
      setActiveConnections(prev => [...prev, newConnection]);

      // Auto-fade after 5 seconds (tracked so unmount can clear it).
      const t = setTimeout(() => {
        fadeTimers.current.delete(t);
        setActiveConnections(prev => prev.filter(c => c.id !== newConnection.id));
      }, 5000);
      fadeTimers.current.add(t);
    }
  }, [realtimeEvents]);

  // Clear any pending fade timers on unmount (the 3D view is lazy/Suspense-
  // mounted, so switching away mid-delegation otherwise leaks timers and warns
  // on setState-after-unmount).
  useEffect(() => {
    const timers = fadeTimers.current;
    return () => {
      timers.forEach(clearTimeout);
      timers.clear();
    };
  }, []);

  // Transform data for force-graph
  const graphData = useMemo(() => {
    const nodes = agents.map((agent) => {
      const isActive = activeAgents.includes(agent.id);
      const domain = agent.domain || 'general';
      const color = isActive ? '#22c55e' : (domainColors[domain] || domainColors.general);

      // Determine agent type for protocol indicators
      // Default to 'local' if not specified
      const agentType = agent.agentType || 'local';

      return {
        id: agent.id,
        name: agent.displayName || agent.name,
        domain: domain,
        color: color,
        val: isActive ? 15 : 10,
        isActive: isActive,
        avatar: agent.avatar,
        bio: agent.bio,
        title: agent.title,
        tools: agent.tools,
        capabilities: agent.capabilities,
        agentType: agentType, // NEW: For border/glow styling
        ...agent,
      };
    });

    // Merge static connections with active/temporary connections
    const allConnections = [...connections, ...activeConnections];

    const links = allConnections.map((conn, index) => {
      const protocol = normalizeProtocol(conn.protocol || 'internal');
      // Protocol-based coloring with peer-to-peer support
      let linkColor = 'rgba(139, 92, 246, 0.4)'; // Default purple for internal/hierarchical
      let particleColor = '#c084fc';

      if (protocol === 'peer') {
        linkColor = 'rgba(251, 191, 36, 0.8)'; // Yellow/amber for peer-to-peer
        particleColor = '#fbbf24';
      } else if (protocol === 'a2a') {
        linkColor = 'rgba(59, 130, 246, 0.8)'; // Blue for A2A
        particleColor = '#60a5fa';
      } else if (protocol === 'paid') {
        linkColor = 'rgba(6, 182, 212, 0.8)'; // Cyan for paid external API
        particleColor = '#22d3ee';
      } else if (conn.temporary) {
        // Temporary hierarchical connections are more vibrant
        linkColor = 'rgba(139, 92, 246, 0.8)';
      }

      return {
        id: conn.id || `edge-${index}`,
        source: conn.source,
        target: conn.target,
        label: conn.label,
        color: linkColor,
        particleColor: particleColor,
        temporary: conn.temporary || false,
        isPeer: conn.isPeer || false,
        ...conn,
        protocol,
      };
    });

    return { nodes, links };
  }, [agents, connections, activeAgents, activeConnections]);

  // Prune cached Three.js objects for nodes that are no longer present so the
  // cache can't grow without bound as agents come and go. Disposes each removed
  // entry's GPU resources.
  useEffect(() => {
    const cache = nodeObjectCache.current;
    const liveIds = new Set(graphData.nodes.map((n) => n.id));
    for (const [id, entry] of cache) {
      if (!liveIds.has(id)) {
        disposeNodeObject(entry.object);
        cache.delete(id);
      }
    }
  }, [graphData]);

  // Dispose every cached node object on unmount so switching away from the 3D
  // view (it is lazy/Suspense-mounted) releases all GPU memory it held.
  useEffect(() => {
    const cache = nodeObjectCache.current;
    return () => {
      for (const entry of cache.values()) {
        disposeNodeObject(entry.object);
      }
      cache.clear();
    };
  }, []);

  // Handle node click
  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    if (onAgentClick) {
      onAgentClick(node);
    }
    // Do NOT move camera - user has full manual control
  }, [onAgentClick]);

  // Handle link click
  const handleLinkClick = useCallback((link) => {
    if (onConnectionClick) {
      onConnectionClick(link);
    }
  }, [onConnectionClick]);

  // Toggle 2D/3D
  const toggleViewMode = () => {
    setViewMode(viewMode === '3d' ? '2d' : '3d');
  };

  // Reset camera (disabled in demo mode for full manual control)
  const resetCamera = () => {
    // Camera reset disabled - user has full manual control
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

  // Build the actual Three.js avatar group for a node. This allocates GPU
  // resources, so it must only run when a node's visual inputs change — the
  // cached wrapper below decides when to call it.
  const buildNodeObject = useCallback((node) => {
    // Create sprite group
    const group = new THREE.Group();

    // Determine avatar source
    let avatarSrc = null;
    let useCanvas = true; // Default to canvas emoji

    // Check for known agents with image logos
    if (node.id === 'the-general') {
      avatarSrc = '/The_General_Logo.png';
      useCanvas = false;
    } else if (node.id === 'gunny' || node.name?.toLowerCase().includes('gunny')) {
      avatarSrc = '/Gunny_Logo.png';
      useCanvas = false;
    } else if (node.avatar && (node.avatar.startsWith('/') || node.avatar.startsWith('http'))) {
      // Avatar is a URL
      avatarSrc = node.avatar;
      useCanvas = false;
    }
    // Otherwise, use emoji/canvas approach

    if (useCanvas) {
      // Create canvas with emoji
      const canvas = document.createElement('canvas');
      canvas.width = 128;
      canvas.height = 128;
      const ctx = canvas.getContext('2d');

      // Background circle
      ctx.beginPath();
      ctx.arc(64, 64, 60, 0, 2 * Math.PI);
      ctx.fillStyle = node.color || '#8b5cf6';
      ctx.fill();

      // Emoji
      ctx.font = 'bold 64px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(node.avatar || '🦄', 64, 64);

      const texture = new THREE.CanvasTexture(canvas);
      const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
      });
      const sprite = new THREE.Sprite(material);
      sprite.scale.set(12, 12, 1);
      group.add(sprite);
    } else {
      // Load image texture
      const loader = new THREE.TextureLoader();

      // Create a placeholder sprite first
      const canvas = document.createElement('canvas');
      canvas.width = 128;
      canvas.height = 128;
      const ctx = canvas.getContext('2d');
      ctx.beginPath();
      ctx.arc(64, 64, 60, 0, 2 * Math.PI);
      ctx.fillStyle = node.color || '#8b5cf6';
      ctx.fill();
      ctx.font = 'bold 64px Arial';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#ffffff';
      ctx.fillText(node.avatar || '🦄', 64, 64);

      const placeholderTexture = new THREE.CanvasTexture(canvas);
      const material = new THREE.SpriteMaterial({
        map: placeholderTexture,
        transparent: true,
      });
      const sprite = new THREE.Sprite(material);
      sprite.scale.set(12, 12, 1);
      group.add(sprite);

      // Load actual image and replace when ready
      loader.load(
        avatarSrc,
        // onLoad callback
        (texture) => {
          material.map = texture;
          material.needsUpdate = true;
        },
        // onProgress callback
        undefined,
        // onError callback - keep placeholder
        (error) => {
          console.warn(`Failed to load avatar image: ${avatarSrc}`, error);
        }
      );
    }

    // Add border/glow based on agent type
    const agentType = node.agentType || 'local';

    // Border ring
    const ringGeometry = new THREE.RingGeometry(6.5, 7.5, 32);
    let ringColor = '#ffffff';
    let ringOpacity = 0.5;

    switch (agentType) {
      case 'federated':
        ringColor = '#3b82f6'; // Blue
        ringOpacity = 0.8;
        break;
      case 'external-free':
        ringColor = '#10b981'; // Green
        ringOpacity = 0.8;
        break;
      case 'external-paid':
        ringColor = '#f59e0b'; // Gold
        ringOpacity = 0.9;
        break;
      default:
        // 'local' - subtle white border
        ringColor = '#ffffff';
        ringOpacity = 0.4;
    }

    const ringMaterial = new THREE.MeshBasicMaterial({
      color: ringColor,
      transparent: true,
      opacity: ringOpacity,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeometry, ringMaterial);
    group.add(ring);

    // Add glow for non-local agents
    if (agentType !== 'local') {
      const glowGeometry = new THREE.CircleGeometry(8, 32);
      const glowMaterial = new THREE.MeshBasicMaterial({
        color: ringColor,
        transparent: true,
        opacity: 0.2,
        side: THREE.DoubleSide,
      });
      const glow = new THREE.Mesh(glowGeometry, glowMaterial);
      group.add(glow);

      // Animate glow
      group.userData.animate = (time) => {
        const scale = 1 + Math.sin(time * 0.002) * 0.1;
        glow.scale.set(scale, scale, 1);
        glowMaterial.opacity = 0.15 + Math.sin(time * 0.002) * 0.05;
      };
    }

    return group;
  }, []);

  // Cache key for a node: the set of inputs buildNodeObject reads. If none of
  // these change, the previously built object is byte-for-byte equivalent and
  // can be reused as-is. node.color already folds in active-vs-domain state, and
  // node.name is included because it can select a different logo (e.g. Gunny).
  const nodeObjectKey = useCallback((node) => (
    [
      node.id,
      node.color || '',
      node.avatar || '',
      node.agentType || 'local',
      node.name || '',
    ].join('|')
  ), []);

  // Custom node rendering — returns a cached Three.js object per node, rebuilding
  // only when the node's visual inputs change. react-force-graph calls this on
  // every graphData refresh, so without the cache each refresh would allocate
  // (and never dispose) a new Group + sprite + textures + geometries per node.
  const nodeThreeObject = useCallback((node) => {
    const cache = nodeObjectCache.current;
    const key = nodeObjectKey(node);
    const cached = cache.get(node.id);

    if (cached && cached.key === key) {
      return cached.object;
    }

    // Inputs changed (or first build) — dispose the stale object before
    // replacing it so we don't leak its GPU resources.
    if (cached) {
      disposeNodeObject(cached.object);
    }

    const object = buildNodeObject(node);
    cache.set(node.id, { key, object });
    return object;
  }, [buildNodeObject, nodeObjectKey]);

  // Node label
  const nodeLabel = useCallback((node) => {
    return `<div style="background: rgba(15, 23, 42, 0.95); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(139, 92, 246, 0.3); font-family: system-ui, sans-serif;">
      <div style="font-size: 14px; font-weight: 600; color: #f8fafc;">${node.avatar || '🦄'} ${node.name}</div>
      <div style="font-size: 11px; color: #c084fc; text-transform: capitalize;">${node.domain}</div>
      ${node.isActive ? '<div style="font-size: 10px; color: #22c55e; margin-top: 4px;">● Active</div>' : ''}
    </div>`;
  }, []);

  return (
    <div
      ref={containerRef}
      className={`relative ${isFullscreen ? 'fixed inset-0 z-50' : 'w-full h-full'} bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 overflow-hidden border border-slate-700/50`}
    >
      {/* Background grid effect */}
      <div className="absolute inset-0 opacity-10 pointer-events-none">
        <div className="absolute inset-0" style={{
          backgroundImage: `
            linear-gradient(rgba(139, 92, 246, 0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(139, 92, 246, 0.1) 1px, transparent 1px)
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
                ? 'bg-unicorn-500/80 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
            title={viewMode === '3d' ? 'Switch to 2D' : 'Switch to 3D'}
            aria-label={viewMode === '3d' ? 'Switch to 2D view' : 'Switch to 3D view'}
          >
            {viewMode === '3d' ? <Box className="w-4 h-4" /> : <Grid3X3 className="w-4 h-4" />}
          </button>
          <button
            onClick={toggleAnimation}
            className={`p-2 rounded-lg transition-all ${
              isAnimating
                ? 'bg-unicorn-500/80 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
            title={isAnimating ? 'Pause animation' : 'Resume animation'}
            aria-label={isAnimating ? 'Pause animation' : 'Resume animation'}
          >
            {isAnimating ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={resetCamera}
            className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
            title="Reset camera"
            aria-label="Reset camera"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          {onToggleFullscreen && (
            <button
              onClick={onToggleFullscreen}
              className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
              aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
              aria-pressed={isFullscreen}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Stats panel */}
      <div className="absolute top-4 right-4 z-10 p-3 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
        <div className="flex items-center space-x-4 text-xs">
          <div className="flex items-center space-x-1.5">
            <div className="w-2 h-2 rounded-full bg-unicorn-500" />
            <span className="text-slate-400">Agents:</span>
            <span className="text-white font-semibold">{graphData.nodes.length}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span className="text-slate-400">Active:</span>
            <span className="text-white font-semibold">{activeAgents.length}</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <Zap className="w-3 h-3 text-yellow-400" />
            <span className="text-slate-400">Links:</span>
            <span className="text-white font-semibold">{graphData.links.length}</span>
          </div>
        </div>
      </div>

      {/* Domain legend + Protocol legend */}
      <div className="absolute bottom-4 left-4 z-10 p-3 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50 space-y-3">
        {/* Domains */}
        <div>
          <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Domains</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {[...new Set(agents.map((a) => a.domain).filter(Boolean))].sort().map((domain) => (
              <div key={domain} className="flex items-center space-x-1.5">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: domainColors[domain] || domainColors.general }}
                />
                <span className="text-[10px] text-slate-400 capitalize">{domain}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Connection Types */}
        <div>
          <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Connection Types</p>
          <div className="space-y-1">
            <div className="flex items-center space-x-1.5">
              <div className="w-2 h-2 rounded-full bg-unicorn-500" />
              <span className="text-[10px] text-slate-400">Hierarchical</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-2 h-2 rounded-full bg-yellow-400" />
              <span className="text-[10px] text-slate-400">Peer-to-Peer</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-[10px] text-slate-400">A2A Protocol</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-2 h-2 rounded-full bg-cyan-400" />
              <span className="text-[10px] text-slate-400">paid (external API)</span>
            </div>
          </div>
        </div>

        {/* Agent Types */}
        <div>
          <p className="text-[10px] text-slate-400 uppercase tracking-wider mb-2">Agent Types</p>
          <div className="space-y-1">
            <div className="flex items-center space-x-1.5">
              <div className="w-3 h-3 rounded-full border-2 border-white/40" />
              <span className="text-[10px] text-slate-400">Local</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-3 h-3 rounded-full border-2 border-blue-500" style={{ boxShadow: '0 0 8px rgba(59, 130, 246, 0.5)' }} />
              <span className="text-[10px] text-slate-400">Federated</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-3 h-3 rounded-full border-2 border-green-500" style={{ boxShadow: '0 0 8px rgba(16, 185, 129, 0.5)' }} />
              <span className="text-[10px] text-slate-400">External (Free)</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <div className="w-3 h-3 rounded-full border-2 border-yellow-500" style={{ boxShadow: '0 0 8px rgba(245, 158, 11, 0.5)' }} />
              <span className="text-[10px] text-slate-400">External (Paid)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Selected node panel */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="absolute bottom-4 right-4 z-10 w-64 p-4 rounded-lg bg-slate-800/90 backdrop-blur-sm border border-slate-700/50"
          >
            <div className="flex items-start space-x-3">
              <div className="text-3xl">{selectedNode.avatar || '🦄'}</div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-semibold text-white truncate">
                  {selectedNode.displayName || selectedNode.name}
                </h3>
                <p className="text-xs text-unicorn-400 capitalize">{selectedNode.domain}</p>
                <p className="text-[10px] text-slate-400 mt-1 line-clamp-2">
                  {selectedNode.bio || selectedNode.title}
                </p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1">
              {(selectedNode.tools || []).slice(0, 4).map((tool) => (
                <span
                  key={tool}
                  className="px-1.5 py-0.5 text-[9px] rounded bg-slate-700 text-slate-300"
                >
                  {tool}
                </span>
              ))}
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="absolute top-2 right-2 text-slate-400 hover:text-white"
            >
              &times;
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 3D Graph Canvas */}
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
            nodeOpacity={0.9}
            linkColor={link => link.color || 'rgba(139, 92, 246, 0.4)'}
            linkWidth={link => link.temporary ? 2.5 : 1.5}
            linkOpacity={0.8}
            linkDirectionalParticles={link => link.temporary ? 4 : 2}
            linkDirectionalParticleSpeed={link => link.temporary ? 0.008 : 0.005}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={link => link.particleColor || '#c084fc'}
            onNodeClick={handleNodeClick}
            onLinkClick={handleLinkClick}
            enableNodeDrag={false}
            enableNavigationControls={true}
            showNavInfo={false}
            warmupTicks={1}
            cooldownTicks={1}
            d3AlphaDecay={1}
            d3VelocityDecay={1}
            numDimensions={viewMode === '3d' ? 3 : 2}
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <Layers className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400">No agents to visualize</p>
              <p className="text-sm text-slate-400">Add agents to see the workflow graph</p>
            </div>
          </div>
        )}
      </div>

      {/* Title overlay */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10">
        <div className="px-4 py-2 rounded-full bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
          <p className="text-xs text-slate-400 flex items-center space-x-2">
            <Eye className="w-3 h-3" />
            <span>The General's Command View</span>
            <span className="text-unicorn-400">|</span>
            <span className="text-unicorn-400">{viewMode.toUpperCase()}</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default WorkflowVisualization3D;
