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
  Clock
} from 'lucide-react';
import axios from 'axios';
import { toast } from 'react-hot-toast';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8112/api';

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

  useEffect(() => {
    loadDashboardData();
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

      // Calculate stats
      const activeAgents = agents.filter(a => a.status === 'active').length;

      setStats({
        totalAgents: agents.length,
        activeAgents: activeAgents,
        domains: domains,
        recentActivity: agents.slice(0, 5) // Last 5 agents as activity
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

  const quickActions = [
    {
      icon: Sparkles,
      label: 'Build Agent',
      description: 'Chat with Gunny to build a new agent',
      path: '/builder-chat',
      color: 'from-purple-500 to-pink-500'
    },
    {
      icon: BookOpen,
      label: 'Browse Library',
      description: 'Explore 47+ pre-built agents',
      path: '/library',
      color: 'from-blue-500 to-cyan-500'
    },
    {
      icon: Wrench,
      label: 'Tool Library',
      description: 'Browse available tools and integrations',
      path: '/tools',
      color: 'from-emerald-500 to-teal-500'
    },
    {
      icon: BookOpen,
      label: 'API Docs',
      description: 'View API documentation and examples',
      path: '/docs',
      color: 'from-orange-500 to-red-500'
    }
  ];

  const systemMetrics = [
    {
      icon: Bot,
      label: 'Total Agents',
      value: stats.totalAgents,
      change: '+12%',
      trend: 'up'
    },
    {
      icon: CheckCircle,
      label: 'Active Agents',
      value: stats.activeAgents,
      change: '+8%',
      trend: 'up'
    },
    {
      icon: Database,
      label: 'Domains',
      value: stats.domains.length,
      change: 'Stable',
      trend: 'stable'
    },
    {
      icon: Activity,
      label: 'System Status',
      value: systemStatus === 'online' ? 'Online' : 'Degraded',
      change: '99.9% uptime',
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
                <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border-2 border-purple-500/30">
                  <img
                    src="/The_General_Logo.png"
                    alt="The General"
                    className="w-full h-full object-cover"
                  />
                </div>
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
                <div className="w-16 h-16 rounded-lg overflow-hidden flex-shrink-0 border-2 border-amber-500/30">
                  <img
                    src="/Gunny_Logo.png"
                    alt="Gunny"
                    className="w-full h-full object-cover"
                  />
                </div>
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
              <h3 className="font-bold text-white mb-4">System Health</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Server className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-slate-300">API Server</span>
                  </div>
                  <span className="text-xs text-emerald-400">Healthy</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Database className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-slate-300">Database</span>
                  </div>
                  <span className="text-xs text-emerald-400">Connected</span>
                </div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <span className="text-sm text-slate-300">LLM Providers</span>
                  </div>
                  <span className="text-xs text-emerald-400">Active</span>
                </div>
                <button
                  onClick={() => navigate('/monitoring')}
                  className="w-full mt-3 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors text-sm"
                >
                  View Detailed Metrics
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Recent Activity</h2>
          {loading ? (
            <div className="text-center py-4">
              <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-purple-500"></div>
            </div>
          ) : stats.recentActivity.length > 0 ? (
            <div className="space-y-3">
              {stats.recentActivity.map((agent, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer"
                  onClick={() => navigate(`/agent/${agent.id}`)}
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xl">
                      {agent.avatar || '🦄'}
                    </div>
                    <div>
                      <p className="font-medium text-white">{agent.displayName || agent.name}</p>
                      <p className="text-sm text-slate-400">{agent.domain} • {agent.status}</p>
                    </div>
                  </div>
                  <Clock className="w-4 h-4 text-slate-500" />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-slate-400 py-4">No recent activity</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
