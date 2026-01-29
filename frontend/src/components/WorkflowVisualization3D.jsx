/**
 * 3D Workflow Visualization Component
 *
 * Uses react-force-graph-3d for immersive 3D visualization of agent orchestration.
 * Shows agents as nodes, connections as edges, with depth representing complexity.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
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
  RefreshCw
} from 'lucide-react';

// Domain colors for agents
const domainColors = {
  financial: '#10b981',
  legal: '#3b82f6',
  medical: '#ef4444',
  technology: '#8b5cf6',
  intelligence: '#f59e0b',
  investigation: '#ec4899',
  cybersecurity: '#06b6d4',
  general: '#6b7280',
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
}) => {
  const fgRef = useRef();
  const containerRef = useRef();
  const [viewMode, setViewMode] = useState('3d');
  const [selectedNode, setSelectedNode] = useState(null);
  const [isAnimating, setIsAnimating] = useState(animate);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

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

  // Transform data for force-graph
  const graphData = useMemo(() => {
    const nodes = agents.map((agent) => {
      const isActive = activeAgents.includes(agent.id);
      const domain = agent.domain || 'general';
      const color = isActive ? '#22c55e' : (domainColors[domain] || domainColors.general);

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
        ...agent,
      };
    });

    const links = connections.map((conn, index) => ({
      id: conn.id || `edge-${index}`,
      source: conn.source,
      target: conn.target,
      label: conn.label,
      color: 'rgba(139, 92, 246, 0.4)',
      ...conn,
    }));

    return { nodes, links };
  }, [agents, connections, activeAgents]);

  // Handle node click
  const handleNodeClick = useCallback((node) => {
    setSelectedNode(node);
    if (onAgentClick) {
      onAgentClick(node);
    }
    // Focus on node
    if (fgRef.current && viewMode === '3d') {
      const distance = 200;
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
      fgRef.current.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1000
      );
    }
  }, [onAgentClick, viewMode]);

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

  // Custom node rendering
  const nodeThreeObject = useCallback((node) => {
    // We'll use the default spheres with custom colors
    // Return undefined to use default rendering
    return undefined;
  }, []);

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
      className={`relative ${isFullscreen ? 'fixed inset-0 z-50' : 'w-full h-[600px]'} bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-xl overflow-hidden border border-slate-700/50`}
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
                ? 'bg-purple-600 text-white'
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
          {onToggleFullscreen && (
            <button
              onClick={onToggleFullscreen}
              className="p-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
              title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
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
            <div className="w-2 h-2 rounded-full bg-purple-500" />
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

      {/* Domain legend */}
      <div className="absolute bottom-4 left-4 z-10 p-3 rounded-lg bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
        <p className="text-[10px] text-slate-500 uppercase tracking-wider mb-2">Domains</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {Object.entries(domainColors).slice(0, 6).map(([domain, color]) => (
            <div key={domain} className="flex items-center space-x-1.5">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-slate-400 capitalize">{domain}</span>
            </div>
          ))}
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
                <p className="text-xs text-purple-400 capitalize">{selectedNode.domain}</p>
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
              className="absolute top-2 right-2 text-slate-500 hover:text-white"
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
            nodeColor={node => node.color}
            nodeVal={node => node.val}
            nodeOpacity={0.9}
            linkColor={link => link.color || 'rgba(139, 92, 246, 0.4)'}
            linkWidth={1.5}
            linkOpacity={0.6}
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={0.005}
            linkDirectionalParticleWidth={2}
            linkDirectionalParticleColor={() => '#c084fc'}
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
        ) : (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <Layers className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400">No agents to visualize</p>
              <p className="text-sm text-slate-500">Add agents to see the workflow graph</p>
            </div>
          </div>
        )}
      </div>

      {/* Title overlay */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10">
        <div className="px-4 py-2 rounded-full bg-slate-800/80 backdrop-blur-sm border border-slate-700/50">
          <p className="text-xs text-slate-400 flex items-center space-x-2">
            <Eye className="w-3 h-3" />
            <span>The General's Command View</span>
            <span className="text-purple-400">|</span>
            <span className="text-purple-400">{viewMode.toUpperCase()}</span>
          </p>
        </div>
      </div>
    </div>
  );
};

export default WorkflowVisualization3D;
