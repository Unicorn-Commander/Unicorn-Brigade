/**
 * Orchestration Demo - Hollywood-Style Agent Visualization
 *
 * Showcases 1000+ agents executing workflows in an auto-playing simulation.
 * Features camera choreography, scripted scenarios, and performance optimization.
 */

import { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Users,
  Network,
  Zap,
  Play,
  Pause,
  RotateCcw,
  Maximize2
} from 'lucide-react';
import WorkflowVisualization3D from '../components/WorkflowVisualization3D';

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
    data: '📉',
    ai: '🤖',
  };
  return emojis[domain] || '🦄';
};

// Generate synthetic agents with realistic properties
const generateAgents = (count) => {
  const domains = [
    'financial', 'legal', 'medical', 'technology', 'intelligence',
    'investigation', 'cybersecurity', 'operations', 'research', 'sales',
    'marketing', 'content', 'devops', 'support', 'data', 'ai'
  ];
  const ranks = ['General', 'Colonel', 'Major', 'Captain', 'Lieutenant', 'Sergeant', 'Specialist', 'Corporal'];
  const specialties = [
    'Analyst', 'Coordinator', 'Specialist', 'Expert', 'Officer',
    'Director', 'Manager', 'Lead', 'Engineer', 'Scientist'
  ];

  const agents = [];

  // Create The General as the main orchestrator
  agents.push({
    id: 'the-general',
    name: 'The General',
    displayName: 'The General',
    domain: 'operations',
    avatar: '⭐',
    agentType: 'local',
    title: 'Supreme Commander',
    bio: 'Orchestrates all mission operations',
    x: 0,
    y: 0,
    z: 0,
  });

  // Generate domain leaders (one per domain)
  domains.forEach((domain, idx) => {
    const rank = ranks[idx % ranks.length];
    agents.push({
      id: `${domain}-lead`,
      name: `${rank} ${domain.charAt(0).toUpperCase() + domain.slice(1)}`,
      displayName: `${rank} ${domain.charAt(0).toUpperCase() + domain.slice(1)}`,
      domain,
      avatar: getDomainEmoji(domain),
      agentType: idx % 3 === 0 ? 'federated' : 'local',
      title: `${domain.charAt(0).toUpperCase() + domain.slice(1)} Team Lead`,
      bio: `Coordinates ${domain} operations`,
      // Position domain leaders in a circle around The General
      x: Math.cos((idx / domains.length) * 2 * Math.PI) * 150,
      y: Math.sin((idx / domains.length) * 2 * Math.PI) * 150,
      z: (Math.random() - 0.5) * 50,
    });
  });

  // Generate remaining agents distributed across domains
  for (let i = agents.length; i < count; i++) {
    const domain = domains[i % domains.length];
    const domainIndex = domains.indexOf(domain);
    const rank = ranks[Math.floor(Math.random() * ranks.length)];
    const specialty = specialties[Math.floor(Math.random() * specialties.length)];

    // Determine agent type distribution
    let agentType = 'local';
    const typeRoll = Math.random();
    if (typeRoll < 0.05) agentType = 'external-paid';
    else if (typeRoll < 0.15) agentType = 'external-free';
    else if (typeRoll < 0.30) agentType = 'federated';

    // Position agents in clusters by domain
    const clusterAngle = (domainIndex / domains.length) * 2 * Math.PI;
    const clusterRadius = 150 + Math.random() * 200;
    const clusterSpread = 80;

    agents.push({
      id: `agent-${i}`,
      name: `${rank} ${specialty}`,
      displayName: `${rank} ${specialty} #${i}`,
      domain,
      avatar: getDomainEmoji(domain),
      agentType,
      title: `${domain.charAt(0).toUpperCase() + domain.slice(1)} ${specialty}`,
      bio: `Specialized in ${domain} tasks`,
      x: Math.cos(clusterAngle) * clusterRadius + (Math.random() - 0.5) * clusterSpread,
      y: Math.sin(clusterAngle) * clusterRadius + (Math.random() - 0.5) * clusterSpread,
      z: (Math.random() - 0.5) * 100,
    });
  }

  return agents;
};

// Workflow scenarios
const SCENARIOS = [
  {
    id: 'market-research',
    name: 'Market Research Campaign',
    orchestrator: 'the-general',
    domain: 'research',
    teamLeadCount: 5,
    workerCount: 20,
    protocol: 'internal',
    duration: 7000,
  },
  {
    id: 'financial-analysis',
    name: 'Financial Analysis',
    orchestrator: 'financial-lead',
    domain: 'financial',
    teamLeadCount: 8,
    workerCount: 25,
    protocol: 'internal',
    duration: 7000,
  },
  {
    id: 'cybersecurity-incident',
    name: 'Cybersecurity Incident Response',
    orchestrator: 'cybersecurity-lead',
    domain: 'cybersecurity',
    teamLeadCount: 10,
    workerCount: 30,
    protocol: 'internal',
    duration: 7000,
  },
  {
    id: 'legal-review',
    name: 'Legal Compliance Review',
    orchestrator: 'legal-lead',
    domain: 'legal',
    teamLeadCount: 6,
    workerCount: 15,
    protocol: 'internal',
    duration: 7000,
  },
  {
    id: 'medical-diagnosis',
    name: 'Medical Diagnosis Workflow',
    orchestrator: 'medical-lead',
    domain: 'medical',
    teamLeadCount: 7,
    workerCount: 22,
    protocol: 'internal',
    duration: 7000,
  },
  {
    id: 'multi-domain',
    name: 'Multi-Domain Coordination',
    orchestrator: 'the-general',
    domain: 'all',
    teamLeadCount: 16,
    workerCount: 50,
    protocol: 'peer',
    duration: 8000,
  },
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
  const [activeAgents, setActiveAgents] = useState([]);
  const [currentScene, setCurrentScene] = useState(0);
  const [isPlaying, setIsPlaying] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const fgRef = useRef();
  const scenarioTimeoutRef = useRef();
  const connectionTimeoutRefs = useRef([]);

  // Generate agents on mount
  useEffect(() => {
    const syntheticAgents = generateAgents(1500);
    setAgents(syntheticAgents);
  }, []);

  // Execute a workflow scenario
  const executeWorkflow = useCallback((scenario) => {
    const { orchestrator, domain, teamLeadCount, workerCount, protocol } = scenario;

    // Clear existing timeouts
    connectionTimeoutRefs.current.forEach(clearTimeout);
    connectionTimeoutRefs.current = [];

    // 1. Activate orchestrator
    setActiveAgents([orchestrator]);

    // 2. After 1s, delegate to team leads
    const timeout1 = setTimeout(() => {
      const leads = agents
        .filter(a => domain === 'all' ? a.id.endsWith('-lead') : a.domain === domain)
        .slice(0, teamLeadCount)
        .map(a => a.id);

      setActiveAgents([orchestrator, ...leads]);

      // Create connections to team leads
      const leadConnections = leads.map(lead => ({
        id: `${orchestrator}-${lead}-${Date.now()}`,
        source: orchestrator,
        target: lead,
        label: 'delegates',
        protocol: 'internal',
        color: 'rgba(139, 92, 246, 0.8)',
        particleColor: '#c084fc',
        temporary: true,
      }));

      setConnections(leadConnections);
    }, 1000);
    connectionTimeoutRefs.current.push(timeout1);

    // 3. After 2.5s, delegate to workers
    const timeout2 = setTimeout(() => {
      const leads = agents
        .filter(a => domain === 'all' ? a.id.endsWith('-lead') : a.domain === domain)
        .slice(0, teamLeadCount);

      const workers = [];
      const workerConnections = [];

      leads.forEach(lead => {
        const domainWorkers = agents
          .filter(a => a.domain === lead.domain && a.id !== lead.id && !a.id.endsWith('-lead'))
          .slice(0, Math.ceil(workerCount / teamLeadCount));

        workers.push(...domainWorkers.map(w => w.id));

        // Create peer-to-peer connections (yellow) or hierarchical (purple)
        domainWorkers.forEach(worker => {
          workerConnections.push({
            id: `${lead.id}-${worker.id}-${Date.now()}`,
            source: lead.id,
            target: worker.id,
            label: 'assigns',
            protocol: protocol === 'peer' ? 'peer' : 'internal',
            color: protocol === 'peer' ? 'rgba(251, 191, 36, 0.8)' : 'rgba(139, 92, 246, 0.6)',
            particleColor: protocol === 'peer' ? '#fbbf24' : '#c084fc',
            temporary: true,
          });
        });
      });

      setActiveAgents(prev => [...prev, ...workers]);
      setConnections(prev => [...prev, ...workerConnections]);
    }, 2500);
    connectionTimeoutRefs.current.push(timeout2);

    // 4. After 5.5s, fade connections and complete
    const timeout3 = setTimeout(() => {
      setConnections([]);
    }, 5500);
    connectionTimeoutRefs.current.push(timeout3);

    // 5. After 6.5s, clear active agents
    const timeout4 = setTimeout(() => {
      setActiveAgents([]);
    }, 6500);
    connectionTimeoutRefs.current.push(timeout4);
  }, [agents]);

  // Zoom camera to cluster
  const zoomToCluster = useCallback((domain) => {
    if (!fgRef.current || !agents.length) return;

    if (domain === 'all') {
      // Zoom out to see everything
      fgRef.current.cameraPosition(
        { x: 0, y: 500, z: 600 },
        { x: 0, y: 0, z: 0 },
        2000
      );
    } else {
      // Find center of domain cluster
      const domainAgents = agents.filter(a => a.domain === domain);
      if (domainAgents.length === 0) return;

      const centerX = domainAgents.reduce((sum, a) => sum + a.x, 0) / domainAgents.length;
      const centerY = domainAgents.reduce((sum, a) => sum + a.y, 0) / domainAgents.length;
      const centerZ = domainAgents.reduce((sum, a) => sum + a.z, 0) / domainAgents.length;

      // Zoom camera to cluster
      fgRef.current.cameraPosition(
        { x: centerX + 250, y: centerY + 150, z: centerZ + 200 },
        { x: centerX, y: centerY, z: centerZ },
        2000
      );
    }
  }, [agents]);

  // Auto-play scenarios
  useEffect(() => {
    if (!isPlaying || agents.length === 0) return;

    const playScene = () => {
      const scenario = SCENARIOS[currentScene];
      executeWorkflow(scenario);
      zoomToCluster(scenario.domain);
    };

    // Play current scene immediately
    playScene();

    // Schedule next scene
    scenarioTimeoutRef.current = setTimeout(() => {
      setCurrentScene((prev) => (prev + 1) % SCENARIOS.length);
    }, SCENARIOS[currentScene].duration);

    return () => {
      if (scenarioTimeoutRef.current) {
        clearTimeout(scenarioTimeoutRef.current);
      }
    };
  }, [currentScene, isPlaying, agents, executeWorkflow, zoomToCluster]);

  // Reset demo
  const handleReset = () => {
    setCurrentScene(0);
    setActiveAgents([]);
    setConnections([]);
    setIsPlaying(false);
    if (fgRef.current) {
      fgRef.current.cameraPosition({ x: 0, y: 0, z: 500 }, { x: 0, y: 0, z: 0 }, 1000);
    }
  };

  // Stats
  const stats = useMemo(() => ({
    totalAgents: agents.length,
    activeAgents: activeAgents.length,
    connections: connections.length,
    currentWorkflow: SCENARIOS[currentScene]?.name || 'Initializing...',
  }), [agents, activeAgents, connections, currentScene]);

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-full mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30">
                <Sparkles className="w-8 h-8 text-purple-400" />
              </div>
              <div>
                <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
                  Unicorn Brigade - Live Orchestration Demo
                </h1>
                <p className="text-slate-400">
                  Showcasing {agents.length.toLocaleString()} agents executing workflows in real-time
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

        {/* Scene indicator */}
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <span className="text-sm text-slate-400">
              Scene {currentScene + 1} of {SCENARIOS.length}: {SCENARIOS[currentScene]?.name}
            </span>
            <div className="flex space-x-2">
              {SCENARIOS.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentScene(i)}
                  className={`h-1.5 w-12 rounded-full transition-all ${
                    i === currentScene ? 'bg-purple-500' : 'bg-slate-700 hover:bg-slate-600'
                  }`}
                />
              ))}
            </div>
          </div>

          <div className="text-xs text-slate-500">
            Auto-playing • {SCENARIOS[currentScene]?.duration / 1000}s per scene
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
            value={isPlaying ? 1 : 0}
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
          <WorkflowVisualization3D
            ref={fgRef}
            agents={agents}
            connections={connections}
            activeAgents={activeAgents}
            isFullscreen={isFullscreen}
            onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
            showLabels={true}
            animate={isPlaying}
          />
        </motion.div>

        {/* Scenario descriptions */}
        {!isFullscreen && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mt-6 grid grid-cols-3 gap-4"
          >
            {SCENARIOS.map((scenario, idx) => (
              <div
                key={scenario.id}
                className={`card glass transition-all cursor-pointer ${
                  idx === currentScene
                    ? 'border-purple-500/50 bg-purple-500/5'
                    : 'hover:border-slate-600'
                }`}
                onClick={() => setCurrentScene(idx)}
              >
                <div className="flex items-start justify-between mb-2">
                  <h3 className="text-sm font-semibold text-white">{scenario.name}</h3>
                  {idx === currentScene && (
                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  )}
                </div>
                <p className="text-xs text-slate-500 mb-3">
                  {scenario.teamLeadCount} team leads → {scenario.workerCount} workers
                </p>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-0.5 text-[10px] rounded-full ${
                    scenario.protocol === 'peer'
                      ? 'bg-yellow-500/20 text-yellow-400'
                      : 'bg-purple-500/20 text-purple-400'
                  }`}>
                    {scenario.protocol === 'peer' ? 'Peer-to-Peer' : 'Hierarchical'}
                  </span>
                  <span className="px-2 py-0.5 text-[10px] rounded-full bg-slate-700 text-slate-400">
                    {scenario.domain === 'all' ? 'Multi-Domain' : scenario.domain}
                  </span>
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OrchestrationDemo;
