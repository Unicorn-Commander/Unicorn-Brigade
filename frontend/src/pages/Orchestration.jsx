/**
 * Orchestration Dashboard - The General's Command View
 *
 * 3D visualization of agent workflows and orchestration.
 * Shows real-time agent activity, connections, and mission status.
 */

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Globe,
  Cpu,
  Zap,
  Users,
  Activity,
  Play,
  Pause,
  RefreshCw,
  Expand,
  Filter,
  Search,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Sparkles,
  Network,
  Target,
  Shield
} from 'lucide-react';
import WorkflowVisualization3D from '../components/WorkflowVisualization3D';
import api from '../services/api';

// Generate mock connections between agents based on domain relationships
const generateConnections = (agents) => {
  const connections = [];
  const domainLeaders = {};

  // Find domain leaders (The General is the main orchestrator)
  const general = agents.find(a => a.id === 'the-general' || a.name?.toLowerCase().includes('general'));

  agents.forEach((agent) => {
    const domain = agent.domain || 'general';
    if (!domainLeaders[domain]) {
      domainLeaders[domain] = agent;
    }
  });

  // Connect The General to all domain leaders
  if (general) {
    Object.values(domainLeaders).forEach((leader) => {
      if (leader.id !== general.id) {
        connections.push({
          id: `${general.id}-${leader.id}`,
          source: general.id,
          target: leader.id,
          label: 'commands',
          type: 'command',
        });
      }
    });
  }

  // Connect agents within the same domain to their leader
  agents.forEach((agent) => {
    const domain = agent.domain || 'general';
    const leader = domainLeaders[domain];
    if (leader && agent.id !== leader.id) {
      connections.push({
        id: `${leader.id}-${agent.id}`,
        source: leader.id,
        target: agent.id,
        label: 'delegates',
        type: 'delegation',
      });
    }
  });

  return connections;
};

// Simulated active missions
const mockMissions = [
  {
    id: 'm1',
    name: 'Market Analysis Q1',
    status: 'active',
    progress: 67,
    agents: ['col-finance', 'lt-market-analyst', 'sgt-data'],
    started: '2 hours ago',
  },
  {
    id: 'm2',
    name: 'Legal Compliance Review',
    status: 'active',
    progress: 34,
    agents: ['capt-legal', 'lt-contract-analyst'],
    started: '45 minutes ago',
  },
  {
    id: 'm3',
    name: 'Security Audit',
    status: 'pending',
    progress: 0,
    agents: ['maj-cybersec', 'sgt-pentest'],
    started: 'Queued',
  },
];

const Orchestration = () => {
  const [agents, setAgents] = useState([]);
  const [connections, setConnections] = useState([]);
  const [activeAgents, setActiveAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [filterDomain, setFilterDomain] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [isSimulating, setIsSimulating] = useState(true);
  const [missions, setMissions] = useState(mockMissions);

  // Fetch agents from API
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setIsLoading(true);
        const response = await api.get('/agents');
        const agentList = response.data.agents || response.data || [];
        setAgents(agentList);

        // Generate connections based on agent relationships
        const conns = generateConnections(agentList);
        setConnections(conns);

        // Initially, some agents are "active"
        const initialActive = agentList
          .filter(a => a.status === 'active')
          .slice(0, 3)
          .map(a => a.id);
        setActiveAgents(initialActive);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchAgents();
  }, []);

  // Simulate agent activity
  useEffect(() => {
    if (!isSimulating || agents.length === 0) return;

    const interval = setInterval(() => {
      setActiveAgents((current) => {
        const activeCount = Math.floor(Math.random() * 4) + 2;
        const shuffled = [...agents].sort(() => Math.random() - 0.5);
        return shuffled.slice(0, activeCount).map(a => a.id);
      });

      // Update mission progress
      setMissions((current) =>
        current.map((m) => ({
          ...m,
          progress: m.status === 'active'
            ? Math.min(100, m.progress + Math.floor(Math.random() * 5))
            : m.progress,
        }))
      );
    }, 3000);

    return () => clearInterval(interval);
  }, [isSimulating, agents]);

  // Get unique domains
  const domains = useMemo(() => {
    const domainSet = new Set(agents.map(a => a.domain || 'general'));
    return ['all', ...Array.from(domainSet)];
  }, [agents]);

  // Filter agents
  const filteredAgents = useMemo(() => {
    return agents.filter((agent) => {
      const matchesDomain = filterDomain === 'all' || agent.domain === filterDomain;
      const matchesSearch = !searchQuery ||
        (agent.name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (agent.displayName || '').toLowerCase().includes(searchQuery.toLowerCase());
      return matchesDomain && matchesSearch;
    });
  }, [agents, filterDomain, searchQuery]);

  // Filter connections based on filtered agents
  const filteredConnections = useMemo(() => {
    const agentIds = new Set(filteredAgents.map(a => a.id));
    return connections.filter(
      (conn) => agentIds.has(conn.source) && agentIds.has(conn.target)
    );
  }, [connections, filteredAgents]);

  // Stats
  const stats = useMemo(() => ({
    totalAgents: agents.length,
    activeAgents: activeAgents.length,
    domains: domains.length - 1,
    connections: connections.length,
    activeMissions: missions.filter(m => m.status === 'active').length,
  }), [agents, activeAgents, domains, connections, missions]);

  const handleAgentClick = useCallback((agentData) => {
    setSelectedAgent(agentData);
  }, []);

  const handleConnectionClick = useCallback((connectionData) => {
    console.log('Connection clicked:', connectionData);
  }, []);

  if (isLoading) {
    return (
      <div className="min-h-screen p-8 flex items-center justify-center">
        <div className="text-center">
          <Network className="w-16 h-16 text-purple-500 animate-pulse mx-auto mb-4" />
          <p className="text-slate-400">Initializing Command View...</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${isFullscreen ? 'p-0' : 'p-8'}`}>
      {!isFullscreen && (
        <>
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="p-3 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20 border border-purple-500/30">
                  <Globe className="w-8 h-8 text-purple-400" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent">
                    Orchestration Command
                  </h1>
                  <p className="text-slate-400">
                    The General's real-time view of agent operations
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-3">
                <button
                  onClick={() => setIsSimulating(!isSimulating)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${
                    isSimulating
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-slate-800 text-slate-400 border border-slate-700'
                  }`}
                >
                  {isSimulating ? (
                    <>
                      <Activity className="w-4 h-4 animate-pulse" />
                      <span>Live</span>
                    </>
                  ) : (
                    <>
                      <Pause className="w-4 h-4" />
                      <span>Paused</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </motion.div>

          {/* Stats Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-5 gap-4 mb-6"
          >
            {[
              { label: 'Total Agents', value: stats.totalAgents, icon: Users, color: 'purple' },
              { label: 'Active Now', value: stats.activeAgents, icon: Zap, color: 'green' },
              { label: 'Domains', value: stats.domains, icon: Target, color: 'blue' },
              { label: 'Connections', value: stats.connections, icon: Network, color: 'pink' },
              { label: 'Active Missions', value: stats.activeMissions, icon: Activity, color: 'yellow' },
            ].map((stat, index) => (
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
                    <p className="text-xs text-slate-500">{stat.label}</p>
                  </div>
                </div>
              </div>
            ))}
          </motion.div>

          {/* Filters */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex items-center space-x-4 mb-6"
          >
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-slate-500" />
              <select
                value={filterDomain}
                onChange={(e) => setFilterDomain(e.target.value)}
                className="px-3 py-2 rounded-lg bg-slate-800/50 border border-slate-700 text-slate-200 focus:outline-none focus:border-purple-500"
              >
                {domains.map((domain) => (
                  <option key={domain} value={domain}>
                    {domain === 'all' ? 'All Domains' : domain.charAt(0).toUpperCase() + domain.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </motion.div>
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
          <WorkflowVisualization3D
            agents={filteredAgents}
            connections={filteredConnections}
            activeAgents={activeAgents}
            onAgentClick={handleAgentClick}
            onConnectionClick={handleConnectionClick}
            isFullscreen={isFullscreen}
            onToggleFullscreen={() => setIsFullscreen(!isFullscreen)}
            showLabels={true}
            animate={isSimulating}
          />
        </motion.div>

        {/* Sidebar - Active Missions */}
        {!isFullscreen && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.4 }}
            className="space-y-6"
          >
            {/* Active Missions */}
            <div className="card glass">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                <Sparkles className="w-4 h-4 text-yellow-400" />
                <span>Active Missions</span>
              </h3>

              <div className="space-y-3">
                {missions.map((mission) => (
                  <div
                    key={mission.id}
                    className="p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-slate-600 transition-all cursor-pointer"
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-white truncate">
                          {mission.name}
                        </p>
                        <p className="text-xs text-slate-500">{mission.started}</p>
                      </div>
                      <span className={`px-2 py-0.5 text-[10px] rounded-full ${
                        mission.status === 'active'
                          ? 'bg-green-500/20 text-green-400'
                          : 'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {mission.status}
                      </span>
                    </div>

                    {mission.status === 'active' && (
                      <div className="mb-2">
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="text-slate-500">Progress</span>
                          <span className="text-purple-400">{mission.progress}%</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-slate-700 overflow-hidden">
                          <motion.div
                            className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                            initial={{ width: 0 }}
                            animate={{ width: `${mission.progress}%` }}
                            transition={{ duration: 0.5 }}
                          />
                        </div>
                      </div>
                    )}

                    <div className="flex items-center space-x-1">
                      <Users className="w-3 h-3 text-slate-500" />
                      <span className="text-[10px] text-slate-500">
                        {mission.agents.length} agents
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Quick Actions */}
            <div className="card glass">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                <Zap className="w-4 h-4 text-purple-400" />
                <span>Quick Actions</span>
              </h3>

              <div className="space-y-2">
                <button className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-purple-500/50 hover:bg-purple-500/10 transition-all text-left">
                  <div className="flex items-center space-x-2">
                    <Play className="w-4 h-4 text-green-400" />
                    <span className="text-sm text-slate-300">Start New Mission</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </button>

                <button className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-purple-500/50 hover:bg-purple-500/10 transition-all text-left">
                  <div className="flex items-center space-x-2">
                    <Target className="w-4 h-4 text-blue-400" />
                    <span className="text-sm text-slate-300">Assign Agents</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </button>

                <button className="w-full flex items-center justify-between p-3 rounded-lg bg-slate-800/50 border border-slate-700/50 hover:border-purple-500/50 hover:bg-purple-500/10 transition-all text-left">
                  <div className="flex items-center space-x-2">
                    <Shield className="w-4 h-4 text-yellow-400" />
                    <span className="text-sm text-slate-300">Security Sweep</span>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </button>
              </div>
            </div>

            {/* System Health */}
            <div className="card glass">
              <h3 className="flex items-center space-x-2 text-sm font-semibold text-white mb-4">
                <Cpu className="w-4 h-4 text-emerald-400" />
                <span>System Health</span>
              </h3>

              <div className="space-y-3">
                {[
                  { label: 'LLM Gateway', status: 'healthy', latency: '45ms' },
                  { label: 'Agent Pool', status: 'healthy', latency: '12ms' },
                  { label: 'Memory Store', status: 'healthy', latency: '8ms' },
                  { label: 'Tool Registry', status: 'healthy', latency: '3ms' },
                ].map((service) => (
                  <div key={service.label} className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="text-sm text-slate-300">{service.label}</span>
                    </div>
                    <span className="text-xs text-slate-500">{service.latency}</span>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Selected Agent Detail Modal */}
      <AnimatePresence>
        {selectedAgent && !isFullscreen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm"
            onClick={() => setSelectedAgent(null)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-lg p-6 rounded-2xl glass border border-slate-700"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start space-x-4">
                <div className="text-5xl">{selectedAgent.avatar || '🦄'}</div>
                <div className="flex-1">
                  <h2 className="text-xl font-bold text-white">
                    {selectedAgent.displayName || selectedAgent.name}
                  </h2>
                  <p className="text-sm text-purple-400 capitalize">{selectedAgent.domain}</p>
                  <p className="text-sm text-slate-400 mt-2">
                    {selectedAgent.bio || selectedAgent.title}
                  </p>
                </div>
              </div>

              {selectedAgent.capabilities && (
                <div className="mt-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Capabilities</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedAgent.capabilities.map((cap) => (
                      <span
                        key={cap}
                        className="px-2 py-1 text-xs rounded-full bg-purple-500/20 text-purple-300"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selectedAgent.tools && selectedAgent.tools.length > 0 && (
                <div className="mt-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Tools</p>
                  <div className="flex flex-wrap gap-2">
                    {selectedAgent.tools.map((tool) => (
                      <span
                        key={tool}
                        className="px-2 py-1 text-xs rounded-full bg-slate-700 text-slate-300"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="mt-6 flex justify-end space-x-3">
                <button
                  onClick={() => setSelectedAgent(null)}
                  className="px-4 py-2 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-all"
                >
                  Close
                </button>
                <button
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:opacity-90 transition-all"
                >
                  Chat with Agent
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Orchestration;
