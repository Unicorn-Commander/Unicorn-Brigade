import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  Sparkles,
  BookOpen,
  Wrench,
  Activity,
  TrendingUp,
  Shield,
  Zap,
  MessageSquare,
  Database,
  Server,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  Clock,
  Play,
  RefreshCw,
  Loader2,
  GitBranch,
  Users,
  Cpu,
  MemoryStick,
  HardDrive,
  Wifi,
  WifiOff,
  ChevronRight,
  Plus
} from 'lucide-react';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import { GeneralAvatar, GunnyAvatar } from '../components/UnicornBrigadeLogo';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

const Dashboard = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    totalAgents: 0,
    activeAgents: 0,
    domains: [],
    recentActivity: []
  });
  const [loading, setLoading] = useState(true);
  const [systemStatus, setSystemStatus] = useState('online');
  const [recentConversations, setRecentConversations] = useState([]);
  const [systemHealth, setSystemHealth] = useState({
    api: 'checking',
    database: 'checking',
    llm: 'checking',
    memory: 'checking'
  });
  const [usageStats, setUsageStats] = useState({
    messagesTotal: 0,
    toolCallsTotal: 0,
    conversationsToday: 0
  });
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDashboardData();
    checkSystemHealth();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // Load agents
      const agentsResponse = await axios.get(`${API_BASE}/agents`);
      const agents = agentsResponse.data.agents || [];

      // Load domains
      const domainsResponse = await axios.get(`${API_BASE}/agents/domains`);
      const domains = domainsResponse.data.domains || [];

      // Load recent conversations
      try {
        const conversationsResponse = await axios.get(`${API_BASE}/conversations?limit=5`);
        setRecentConversations(conversationsResponse.data.conversations || []);
      } catch (err) {
        console.log('Conversations endpoint not available');
        setRecentConversations([]);
      }

      // Calculate stats
      const activeAgents = agents.filter(a => a.status === 'active').length;

      // Calculate usage stats from agents
      let totalMessages = 0;
      agents.forEach(agent => {
        totalMessages += agent._count?.messages || 0;
      });

      setStats({
        totalAgents: agents.length,
        activeAgents: activeAgents,
        domains: domains,
        recentActivity: agents.slice(0, 5) // Last 5 agents as activity
      });

      setUsageStats({
        messagesTotal: totalMessages,
        toolCallsTotal: Math.floor(totalMessages * 0.3), // Estimate
        conversationsToday: recentConversations.length
      });

      setSystemStatus('online');
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      toast.error('Failed to load dashboard data');
      setSystemStatus('degraded');
    } finally {
      setLoading(false);
    }
  };

  const checkSystemHealth = async () => {
    // Check API health
    try {
      await axios.get(`${API_BASE}/health`);
      setSystemHealth(prev => ({ ...prev, api: 'healthy' }));
    } catch {
      setSystemHealth(prev => ({ ...prev, api: 'error' }));
    }

    // Check database via stats endpoint
    try {
      await axios.get(`${API_BASE}/stats`);
      setSystemHealth(prev => ({ ...prev, database: 'healthy' }));
    } catch {
      setSystemHealth(prev => ({ ...prev, database: 'error' }));
    }

    // Check LLM providers via models endpoint
    try {
      const res = await axios.get(`${API_BASE}/models`);
      if (res.data.models?.length > 0) {
        setSystemHealth(prev => ({ ...prev, llm: 'healthy' }));
      } else {
        setSystemHealth(prev => ({ ...prev, llm: 'warning' }));
      }
    } catch {
      setSystemHealth(prev => ({ ...prev, llm: 'error' }));
    }

    // Assume memory is healthy if API is up
    setSystemHealth(prev => ({ ...prev, memory: prev.api === 'healthy' ? 'healthy' : 'error' }));
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadDashboardData();
    await checkSystemHealth();
    setRefreshing(false);
    toast.success('Dashboard refreshed');
  };

  const quickActions = [
    {
      icon: MessageSquare,
      label: 'New Chat',
      description: 'Start a conversation with an agent',
      path: '/chat',
      color: 'from-purple-500 to-pink-500',
      primary: true
    },
    {
      icon: GitBranch,
      label: 'Workflows',
      description: 'Run hierarchical agent workflows',
      path: '/workflows',
      color: 'from-blue-500 to-cyan-500'
    },
    {
      icon: BookOpen,
      label: 'Browse Agents',
      description: `Explore ${stats.totalAgents} available agents`,
      path: '/library',
      color: 'from-emerald-500 to-teal-500'
    },
    {
      icon: Sparkles,
      label: 'Build Agent',
      description: 'Chat with Gunny to create new agents',
      path: '/builder-chat',
      color: 'from-orange-500 to-red-500'
    }
  ];

  const systemMetrics = [
    {
      icon: Bot,
      label: 'Total Agents',
      value: stats.totalAgents,
      change: `${stats.activeAgents} active`,
      trend: 'up'
    },
    {
      icon: MessageSquare,
      label: 'Total Messages',
      value: usageStats.messagesTotal.toLocaleString(),
      change: 'All time',
      trend: 'up'
    },
    {
      icon: Wrench,
      label: 'Tool Calls',
      value: usageStats.toolCallsTotal.toLocaleString(),
      change: 'Estimated',
      trend: 'up'
    },
    {
      icon: Activity,
      label: 'System Status',
      value: systemStatus === 'online' ? 'Online' : 'Degraded',
      change: Object.values(systemHealth).filter(s => s === 'healthy').length + '/4 healthy',
      trend: systemStatus === 'online' ? 'up' : 'down'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              Unicorn Brigade
            </h1>
            <p className="text-slate-400 mt-2 text-lg">Agent Infrastructure Platform</p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-2 rounded-lg bg-slate-800/50 border border-slate-700/50 text-slate-400 hover:text-white hover:bg-slate-700/50 transition-colors disabled:opacity-50"
              title="Refresh dashboard"
            >
              <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            </button>
            <div className={`flex items-center space-x-2 px-4 py-2 rounded-lg ${
              systemStatus === 'online'
                ? 'bg-emerald-500/20 border border-emerald-500/30'
                : 'bg-orange-500/20 border border-orange-500/30'
            }`}>
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                systemStatus === 'online' ? 'bg-emerald-500' : 'bg-orange-500'
              }`}></div>
              <span className={`text-sm font-medium ${
                systemStatus === 'online' ? 'text-emerald-400' : 'text-orange-400'
              }`}>
                {systemStatus === 'online' ? 'All Systems Operational' : 'System Degraded'}
              </span>
            </div>
          </div>
        </div>

        {/* System Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {systemMetrics.map((metric, idx) => (
            <div key={idx} className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <metric.icon className="w-8 h-8 text-purple-400" />
                {metric.trend === 'up' && <TrendingUp className="w-5 h-5 text-emerald-400" />}
                {metric.trend === 'down' && <TrendingUp className="w-5 h-5 text-red-400 rotate-180" />}
              </div>
              <p className="text-3xl font-bold text-white mb-1">{metric.value}</p>
              <p className="text-sm text-slate-400">{metric.label}</p>
              <p className={`text-xs mt-2 ${
                metric.trend === 'up' ? 'text-emerald-400' :
                metric.trend === 'down' ? 'text-red-400' :
                'text-slate-400'
              }`}>
                {metric.change}
              </p>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div>
          <h2 className="text-2xl font-bold text-white mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {quickActions.map((action, idx) => (
              <button
                key={idx}
                onClick={() => navigate(action.path)}
                className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 hover:border-purple-500/50 transition-all group text-left"
              >
                <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${action.color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  <action.icon className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-lg font-semibold text-white mb-2 group-hover:text-purple-400 transition-colors">
                  {action.label}
                </h3>
                <p className="text-sm text-slate-400">{action.description}</p>
                <ArrowRight className="w-5 h-5 text-purple-400 mt-3 opacity-0 group-hover:opacity-100 transition-opacity" />
              </button>
            ))}
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Agent Domains */}
          <div className="lg:col-span-2">
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <h2 className="text-xl font-bold text-white mb-4">Agent Domains</h2>
              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
                </div>
              ) : (
                <div className="space-y-3">
                  {stats.domains.map((domain, idx) => {
                    const domainIcons = {
                      financial: '💰',
                      legal: '⚖️',
                      medical: '🏥',
                      technology: '💻',
                      investigation: '🔍',
                      orchestration: '🎯',
                      meta: '🎖️',
                      intelligence: '🕵️'
                    };
                    const icon = domainIcons[domain.name] || '🤖';
                    const percentage = ((domain.count / stats.totalAgents) * 100).toFixed(0);

                    return (
                      <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors">
                        <div className="flex items-center space-x-3">
                          <span className="text-2xl">{icon}</span>
                          <div>
                            <p className="font-medium text-white capitalize">{domain.name}</p>
                            <p className="text-sm text-slate-400">{domain.count} agents</p>
                          </div>
                        </div>
                        <div className="flex items-center space-x-3">
                          <div className="w-32 h-2 bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-purple-500 to-pink-500"
                              style={{ width: `${percentage}%` }}
                            ></div>
                          </div>
                          <span className="text-sm font-medium text-slate-300">{percentage}%</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Character Cards */}
          <div className="space-y-6">
            {/* The General Card */}
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-4">
                <GeneralAvatar size={64} />
                <div>
                  <h3 className="font-bold text-white">The General</h3>
                  <p className="text-sm text-purple-400">Commanding</p>
                </div>
              </div>
              <p className="text-sm text-slate-400 mb-4">
                Orchestrator of orchestrators. Managing agent workflows and coordinating the entire Unicorn Brigade.
              </p>
              <button
                onClick={() => toast.info('Orchestration features coming soon!')}
                className="w-full px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-colors flex items-center justify-center space-x-2"
              >
                <Shield className="w-4 h-4" />
                <span>View Orchestration</span>
              </button>
            </div>

            {/* Gunny Card */}
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <div className="flex items-center space-x-3 mb-4">
                <GunnyAvatar size={64} />
                <div>
                  <h3 className="font-bold text-white">Gunny</h3>
                  <p className="text-sm text-emerald-400">Ready</p>
                </div>
              </div>
              <p className="text-sm text-slate-400 mb-4">
                Your Agent Builder. Ready to help you create and deploy new AI agents through conversation.
              </p>
              <button
                onClick={() => navigate('/builder-chat')}
                className="w-full px-4 py-2 bg-gradient-to-r from-amber-500 to-orange-600 text-white rounded-lg hover:from-amber-600 hover:to-orange-700 transition-colors flex items-center justify-center space-x-2"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Chat with Gunny</span>
              </button>
            </div>

            {/* System Health */}
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-bold text-white">System Health</h3>
                <button
                  onClick={checkSystemHealth}
                  className="p-1 rounded hover:bg-slate-700/50 text-slate-400 hover:text-white transition-colors"
                  title="Refresh health status"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Server className={`w-4 h-4 ${
                      systemHealth.api === 'healthy' ? 'text-emerald-400' :
                      systemHealth.api === 'checking' ? 'text-slate-400 animate-pulse' :
                      'text-red-400'
                    }`} />
                    <span className="text-sm text-slate-300">API Server</span>
                  </div>
                  <span className={`text-xs ${
                    systemHealth.api === 'healthy' ? 'text-emerald-400' :
                    systemHealth.api === 'checking' ? 'text-slate-400' :
                    'text-red-400'
                  }`}>
                    {systemHealth.api === 'healthy' ? 'Healthy' :
                     systemHealth.api === 'checking' ? 'Checking...' : 'Error'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Database className={`w-4 h-4 ${
                      systemHealth.database === 'healthy' ? 'text-emerald-400' :
                      systemHealth.database === 'checking' ? 'text-slate-400 animate-pulse' :
                      'text-red-400'
                    }`} />
                    <span className="text-sm text-slate-300">Database</span>
                  </div>
                  <span className={`text-xs ${
                    systemHealth.database === 'healthy' ? 'text-emerald-400' :
                    systemHealth.database === 'checking' ? 'text-slate-400' :
                    'text-red-400'
                  }`}>
                    {systemHealth.database === 'healthy' ? 'Connected' :
                     systemHealth.database === 'checking' ? 'Checking...' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Cpu className={`w-4 h-4 ${
                      systemHealth.llm === 'healthy' ? 'text-emerald-400' :
                      systemHealth.llm === 'warning' ? 'text-amber-400' :
                      systemHealth.llm === 'checking' ? 'text-slate-400 animate-pulse' :
                      'text-red-400'
                    }`} />
                    <span className="text-sm text-slate-300">LLM Providers</span>
                  </div>
                  <span className={`text-xs ${
                    systemHealth.llm === 'healthy' ? 'text-emerald-400' :
                    systemHealth.llm === 'warning' ? 'text-amber-400' :
                    systemHealth.llm === 'checking' ? 'text-slate-400' :
                    'text-red-400'
                  }`}>
                    {systemHealth.llm === 'healthy' ? 'Active' :
                     systemHealth.llm === 'warning' ? 'Limited' :
                     systemHealth.llm === 'checking' ? 'Checking...' : 'Unavailable'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <MemoryStick className={`w-4 h-4 ${
                      systemHealth.memory === 'healthy' ? 'text-emerald-400' :
                      systemHealth.memory === 'checking' ? 'text-slate-400 animate-pulse' :
                      'text-red-400'
                    }`} />
                    <span className="text-sm text-slate-300">Memory Store</span>
                  </div>
                  <span className={`text-xs ${
                    systemHealth.memory === 'healthy' ? 'text-emerald-400' :
                    systemHealth.memory === 'checking' ? 'text-slate-400' :
                    'text-red-400'
                  }`}>
                    {systemHealth.memory === 'healthy' ? 'Ready' :
                     systemHealth.memory === 'checking' ? 'Checking...' : 'Offline'}
                  </span>
                </div>
                <button
                  onClick={() => navigate('/monitoring')}
                  className="w-full mt-3 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors text-sm flex items-center justify-center space-x-2"
                >
                  <Activity className="w-4 h-4" />
                  <span>View Detailed Metrics</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Two-column bottom section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Conversations */}
          <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">Recent Conversations</h2>
              <button
                onClick={() => navigate('/chat')}
                className="flex items-center space-x-1 text-sm text-purple-400 hover:text-purple-300 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>New Chat</span>
              </button>
            </div>
            {loading ? (
              <div className="text-center py-8">
                <Loader2 className="w-6 h-6 text-purple-400 animate-spin mx-auto" />
              </div>
            ) : recentConversations.length > 0 ? (
              <div className="space-y-3">
                {recentConversations.map((conv, idx) => (
                  <div
                    key={conv.id || idx}
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer group"
                    onClick={() => navigate(`/chat?conversation=${conv.id}`)}
                  >
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xl flex-shrink-0">
                        {conv.agent?.avatar || '🦄'}
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-white truncate">
                          {conv.title || 'Untitled conversation'}
                        </p>
                        <p className="text-sm text-slate-400 truncate">
                          {conv.agent?.displayName || conv.agent?.name || 'Agent'} • {conv.message_count || 0} messages
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-slate-500">
                        {conv.updated_at ? new Date(conv.updated_at).toLocaleDateString() : ''}
                      </span>
                      <ChevronRight className="w-4 h-4 text-slate-500 group-hover:text-purple-400 transition-colors" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <MessageSquare className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 mb-4">No conversations yet</p>
                <button
                  onClick={() => navigate('/chat')}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors text-sm"
                >
                  Start a Chat
                </button>
              </div>
            )}
          </div>

          {/* Recent Agents */}
          <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">Recent Agents</h2>
              <button
                onClick={() => navigate('/library')}
                className="flex items-center space-x-1 text-sm text-purple-400 hover:text-purple-300 transition-colors"
              >
                <span>View All</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            {loading ? (
              <div className="text-center py-8">
                <Loader2 className="w-6 h-6 text-purple-400 animate-spin mx-auto" />
              </div>
            ) : stats.recentActivity.length > 0 ? (
              <div className="space-y-3">
                {stats.recentActivity.map((agent, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer group"
                    onClick={() => navigate(`/agent/${agent.id}`)}
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xl">
                        {agent.avatar || '🦄'}
                      </div>
                      <div>
                        <p className="font-medium text-white">{agent.displayName || agent.name}</p>
                        <p className="text-sm text-slate-400">
                          {agent.domain} • {(agent.tools?.length || agent.agentTools?.length || 0)} tools
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs ${
                        agent.status === 'active' ? 'bg-emerald-500/20 text-emerald-400' :
                        'bg-slate-500/20 text-slate-400'
                      }`}>
                        {agent.status}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/chat?agent=${agent.id}`);
                        }}
                        className="p-1.5 rounded bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 opacity-0 group-hover:opacity-100 transition-all"
                        title="Chat with agent"
                      >
                        <MessageSquare className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-slate-400 py-8">No agents available</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
