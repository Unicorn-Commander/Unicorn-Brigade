/**
 * Orchestration Demo - Hollywood-Style Agent Visualization
 *
 * Showcases 1000+ agents executing workflows in an auto-playing simulation.
 * Features camera choreography, scripted scenarios, and performance optimization.
 */

import { useState, useEffect, useMemo, useRef, useCallback, lazy, Suspense } from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Users,
  Network,
  Zap,
  Play,
  Pause,
  RotateCcw,
  Maximize2,
  AlertCircle
} from 'lucide-react';

const WorkflowVisualization3D = lazy(() =>
  import('../components/WorkflowVisualization3D').catch(() => ({
    default: () => (
      <div className="h-full flex items-center justify-center bg-slate-900/50 rounded-xl border border-slate-700/50">
        <div className="text-center p-8">
          <AlertCircle className="w-12 h-12 text-amber-400 mx-auto mb-3" />
          <p className="text-slate-300 font-medium">3D visualization unavailable</p>
          <p className="text-sm text-slate-500 mt-1">WebGL is required for the demo view</p>
        </div>
      </div>
    ),
  }))
);

// Domain emojis for different agent types
const getDomainEmoji = (domain) => {
  const emojis = {
    financial: '💰',
    legal: '⚖️',
    medical: '⚕️',
    technology: '💻',
    intelligence: '🔍',
    investigation: '🕵️',
    cybersecurity: '🔒',
    operations: '⚙️',
    research: '📊',
    sales: '📈',
    marketing: '📢',
    content: '📝',
    devops: '🚀',
    support: '🎧',
    data: '💾',
    'data-science': '📉',
    security: '🛡️',
    compliance: '✅',
  };
  return emojis[domain] || '🦄';
};

// Generate synthetic agents with realistic properties - The General at center
const generateAgents = (count) => {
  const domains = ['financial', 'legal', 'medical', 'technology', 'intelligence', 'investigation', 'cybersecurity', 'operations'];

  const agents = [];

  // 1. The General at center (0, 0, 0) - Command Center
  agents.push({
    id: 'the-general',
    name: 'The General',
    displayName: 'The General',
    domain: 'command',
    avatar: '/The_General_Logo.png',
    agentType: 'local',
    title: 'Supreme Commander',
    bio: 'Orchestrates all mission operations from Command Center',
    x: 0,
    y: 0,
    z: 0,
    isOrchestrator: true,
  });

  // 2. Gunny (meta-agent advisor) - positioned near The General
  agents.push({
    id: 'gunny',
    name: 'Gunny',
    displayName: 'Gunny',
    domain: 'meta',
    avatar: '/Gunny_Logo.png',
    agentType: 'local',
    title: 'Agent Builder & Advisor',
    bio: 'Builds new agents and advises on operations',
    x: 50,
    y: 30,
    z: 50,
    isAdvisor: true,
  });

  // 3. Team Leads in a ring around The General (8 domains, radius ~200)
  domains.forEach((domain, i) => {
    const angle = (i / domains.length) * Math.PI * 2;
    const radius = 200;

    agents.push({
      id: `${domain}-lead`,
      name: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Team Lead`,
      displayName: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Lead`,
      domain: domain,
      avatar: getDomainEmoji(domain),
      agentType: 'local',
      title: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Team Lead`,
      bio: `Coordinates ${domain} operations`,
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius * 0.3, // Flatten vertically
      z: Math.sin(angle) * radius,
      isTeamLead: true,
    });
  });

  // 4. Workers clustered around their Team Leads (20 workers per domain)
  domains.forEach((domain, domainIdx) => {
    const angle = (domainIdx / domains.length) * Math.PI * 2;
    const leadX = Math.cos(angle) * 200;
    const leadY = Math.sin(angle) * 200 * 0.3;
    const leadZ = Math.sin(angle) * 200;

    for (let w = 0; w < 20; w++) {
      const workerAngle = (w / 20) * Math.PI * 2;
      const workerRadius = 80 + Math.random() * 40;

      agents.push({
        id: `${domain}-worker-${w}`,
        name: `${domain} Worker ${w}`,
        displayName: `Worker ${w}`,
        domain: domain,
        avatar: '🔧',
        agentType: Math.random() > 0.8 ? 'federated' : 'local',
        title: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Worker`,
        bio: `Executes ${domain} tasks`,
        x: leadX + Math.cos(workerAngle) * workerRadius,
        y: leadY + (Math.random() - 0.5) * 60,
        z: leadZ + Math.sin(workerAngle) * workerRadius,
        isWorker: true,
      });
    }
  });

  // 5. Data Source agents (shared resources, clustered in center)
  for (let d = 0; d < 50; d++) {
    const angle = Math.random() * Math.PI * 2;
    const radius = 50 + Math.random() * 80;

    agents.push({
      id: `data-source-${d}`,
      name: `Data Source ${d}`,
      displayName: `Data ${d}`,
      domain: 'data',
      avatar: '💾',
      agentType: 'local',
      title: 'Data Source',
      bio: 'Provides data to workers',
      x: Math.cos(angle) * radius,
      y: (Math.random() - 0.5) * 40,
      z: Math.sin(angle) * radius,
      isDataSource: true,
    });
  }

  // Total: 1 General + 1 Gunny + 8 Team Leads + 160 Workers + 50 Data Sources = 220 agents
  return agents;
};

// Workflow definitions for simultaneous execution (staggered start times)
const WORKFLOWS = [
  { id: 'financial', domain: 'financial', interval: 12000, offset: 0 },
  { id: 'intelligence', domain: 'intelligence', interval: 15000, offset: 3000 },
  { id: 'cybersecurity', domain: 'cybersecurity', interval: 10000, offset: 5000 },
  { id: 'legal', domain: 'legal', interval: 18000, offset: 7000 },
  { id: 'medical', domain: 'medical', interval: 14000, offset: 9000 },
  { id: 'technology', domain: 'technology', interval: 16000, offset: 11000 },
];

const StatCard = ({ label, value, icon: Icon, color = 'purple' }) => (
  <div className="card glass hover:border-slate-600 transition-all">
    <div className="flex items-center space-x-3">
      <div className={`p-2 rounded-lg bg-${color}-500/20`}>
        <Icon className={`w-5 h-5 text-${color}-400`} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white">{value.toLocaleString()}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  </div>
);

const OrchestrationDemo = () => {
  const [agents, setAgents] = useState([]);
  const [connections, setConnections] = useState([]);
  const [activeAgents, setActiveAgents] = useState(['the-general']); // The General always active
  const [isPlaying, setIsPlaying] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const fgRef = useRef();
  const workflowIntervalsRef = useRef([]);

  // Generate agents on mount
  useEffect(() => {
    const syntheticAgents = generateAgents(220);
    setAgents(syntheticAgents);
  }, []);

  // Execute a single workflow with proper delegation flow
  const executeWorkflow = useCallback((domain) => {
    const teamLeadId = `${domain}-lead`;
    const teamLead = agents.find(a => a.id === teamLeadId);
    if (!teamLead) return;

    // Phase 1: The General → Team Lead (1s)
    setTimeout(() => {
      setActiveAgents(prev => [...new Set([...prev, 'the-general', teamLeadId])]);
      setConnections(prev => [...prev, {
        id: `general-${teamLeadId}-${Date.now()}`,
        source: 'the-general',
        target: teamLeadId,
        color: 'rgba(139, 92, 246, 0.8)',
        protocol: 'internal',
        createdAt: Date.now(),
      }]);
    }, 0);

    // Phase 2: Team Lead → Workers (2s)
    setTimeout(() => {
      const workers = agents
        .filter(a => a.domain === domain && a.isWorker)
        .slice(0, 5); // Pick 5 workers

      const workerIds = workers.map(w => w.id);
      setActiveAgents(prev => [...new Set([...prev, ...workerIds])]);

      const newConns = workers.map(w => ({
        id: `${teamLeadId}-${w.id}-${Date.now()}`,
        source: teamLeadId,
        target: w.id,
        color: 'rgba(139, 92, 246, 0.8)',
        protocol: 'internal',
        createdAt: Date.now(),
      }));
      setConnections(prev => [...prev, ...newConns]);
    }, 1000);

    // Phase 3: Workers ↔ Data Sources (3s) - PEER-TO-PEER YELLOW
    setTimeout(() => {
      const workers = agents
        .filter(a => a.domain === domain && a.isWorker)
        .slice(0, 5);

      const dataSources = agents
        .filter(a => a.isDataSource)
        .sort(() => Math.random() - 0.5)
        .slice(0, 3);

      const peerConns = workers.flatMap(w =>
        dataSources.map(ds => ({
          id: `peer-${w.id}-${ds.id}-${Date.now()}`,
          source: w.id,
          target: ds.id,
          color: 'rgba(251, 191, 36, 0.8)', // YELLOW
          protocol: 'peer',
          createdAt: Date.now(),
        }))
      );

      setConnections(prev => [...prev, ...peerConns]);
      setActiveAgents(prev => [...new Set([...prev, ...dataSources.map(ds => ds.id)])]);
    }, 2000);

    // Phase 4: Results flow back - Workers → Team Lead (5s)
    setTimeout(() => {
      const workers = agents
        .filter(a => a.domain === domain && a.isWorker)
        .slice(0, 5);

      const backConns = workers.map(w => ({
        id: `back-${w.id}-${teamLeadId}-${Date.now()}`,
        source: w.id,
        target: teamLeadId,
        color: 'rgba(34, 197, 94, 0.6)', // GREEN (results)
        protocol: 'internal',
        createdAt: Date.now(),
      }));

      setConnections(prev => [...prev, ...backConns]);
    }, 4000);

    // Phase 5: Team Lead → The General (6s)
    setTimeout(() => {
      setConnections(prev => [...prev, {
        id: `result-${teamLeadId}-general-${Date.now()}`,
        source: teamLeadId,
        target: 'the-general',
        color: 'rgba(34, 197, 94, 0.6)', // GREEN
        protocol: 'internal',
        createdAt: Date.now(),
      }]);
    }, 5000);

    // Phase 6: Cleanup (8s)
    setTimeout(() => {
      setConnections(prev =>
        prev.filter(c => Date.now() - c.createdAt < 5000)
      );
      setActiveAgents(prev =>
        prev.filter(id => id === 'the-general' || agents.find(a => a.id === id && a.isTeamLead))
      );
    }, 7000);
  }, [agents]);

  // Camera position is fully manual - no automatic positioning

  // Run multiple simultaneous workflows with staggered starts
  useEffect(() => {
    if (!isPlaying || agents.length === 0) return;

    const intervals = [];

    WORKFLOWS.forEach(wf => {
      // Initial delay for staggered start
      const initialTimeout = setTimeout(() => {
        executeWorkflow(wf.domain);

        // Repeat workflow
        const interval = setInterval(() => {
          executeWorkflow(wf.domain);
        }, wf.interval);

        intervals.push(interval);
      }, wf.offset);

      intervals.push(initialTimeout);
    });

    workflowIntervalsRef.current = intervals;

    return () => {
      intervals.forEach(interval => clearInterval(interval));
      intervals.forEach(timeout => clearTimeout(timeout));
    };
  }, [isPlaying, agents, executeWorkflow]);

  // Reset demo
  const handleReset = () => {
    setActiveAgents(['the-general']);
    setConnections([]);
    setIsPlaying(false);
    workflowIntervalsRef.current.forEach(interval => clearInterval(interval));
    workflowIntervalsRef.current.forEach(timeout => clearTimeout(timeout));
    workflowIntervalsRef.current = [];
  };

  // Stats
  const stats = useMemo(() => ({
    totalAgents: agents.length,
    activeAgents: activeAgents.length,
    connections: connections.length,
    activeWorkflows: WORKFLOWS.length,
  }), [agents, activeAgents, connections]);

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-full mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30">
                <Sparkles className="w-8 h-8 text-purple-400" />
              </div>
              <div>
                <h1 className="text-4xl font-bold text-white mb-2">
                  The General's Command Center
                </h1>
                <p className="text-slate-400">
                  Orchestrating {agents.length} agents across {WORKFLOWS.length} concurrent workflows
                </p>
              </div>
            </div>

            {/* Controls */}
            <div className="flex items-center space-x-3">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
                  isPlaying
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}
              >
                {isPlaying ? (
                  <>
                    <Pause className="w-4 h-4" />
                    <span>Pause</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Play</span>
                  </>
                )}
              </button>

              <button
                onClick={handleReset}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600 transition-all"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Reset</span>
              </button>

              <button
                onClick={() => setIsFullscreen(!isFullscreen)}
                className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600 transition-all"
              >
                <Maximize2 className="w-4 h-4" />
                <span>Fullscreen</span>
              </button>
            </div>
          </div>
        </div>

        {/* Workflow status */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <span className="text-sm text-slate-400">
              Mission Control: {WORKFLOWS.length} Concurrent Operations
            </span>
            <div className="flex space-x-2">
              {WORKFLOWS.map((wf, i) => (
                <div
                  key={wf.id}
                  className="px-3 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs border border-purple-500/30"
                >
                  {wf.domain}
                </div>
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-500">
            Continuous Operation • All workflows running simultaneously
          </div>
        </div>

        {/* Stats overlay */}
        <div className="mb-6 grid grid-cols-4 gap-4">
          <StatCard
            label="Total Agents"
            value={stats.totalAgents}
            icon={Users}
            color="purple"
          />
          <StatCard
            label="Active Workflows"
            value={isPlaying ? stats.activeWorkflows : 0}
            icon={Zap}
            color="green"
          />
          <StatCard
            label="Active Agents"
            value={stats.activeAgents}
            icon={Network}
            color="blue"
          />
          <StatCard
            label="Connections"
            value={stats.connections}
            icon={Network}
            color="pink"
          />
        </div>

        {/* 3D Visualization */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className={isFullscreen ? 'fixed inset-0 z-50 p-6' : ''}
        >
          <Suspense fallback={<div className="h-[600px] flex items-center justify-center"><Network className="w-8 h-8 text-purple-400 animate-pulse" /></div>}>
            <WorkflowVisualization3D
              ref={fgRef}
              agents={agents}
              connections={connections}
              activeAgents={activeAgents}
              isFullscreen={isFullscreen}
              onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
              showLabels={true}
              animate={isPlaying}
              onAgentClick={null}
            />
          </Suspense>
        </motion.div>

        {/* Workflow legend */}
        {!isFullscreen && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-6"
          >
            <div className="card glass">
              <h3 className="text-lg font-semibold text-white mb-4">Mission Control Legend</h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-purple-500"></div>
                    <span className="text-sm text-slate-300">Delegation (Outward)</span>
                  </div>
                  <p className="text-xs text-slate-500 ml-5">
                    The General → Team Lead → Workers
                  </p>
                </div>
                <div>
                  <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                    <span className="text-sm text-slate-300">Peer Communication</span>
                  </div>
                  <p className="text-xs text-slate-500 ml-5">
                    Workers ↔ Data Sources
                  </p>
                </div>
                <div>
                  <div className="flex items-center space-x-2 mb-2">
                    <div className="w-3 h-3 rounded-full bg-green-500"></div>
                    <span className="text-sm text-slate-300">Results (Return)</span>
                  </div>
                  <p className="text-xs text-slate-500 ml-5">
                    Workers → Team Lead → The General
                  </p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-slate-700">
                <p className="text-xs text-slate-400">
                  <strong className="text-slate-300">Camera:</strong> Drag to rotate • Scroll to zoom • Right-click to pan
                  <span className="mx-2">•</span>
                  <strong className="text-slate-300">View:</strong> {WORKFLOWS.length} workflows executing simultaneously with staggered timing
                  <span className="mx-2">•</span>
                  <strong className="text-slate-300">Pattern:</strong> Continuous delegation, execution, and result collection
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OrchestrationDemo;
