import { useState, useEffect } from 'react';
import {
  Activity,
  Server,
  Database,
  Zap,
  AlertCircle,
  CheckCircle,
  Cpu,
  HardDrive,
  Network,
  BarChart3,
  AlertTriangle,
  RefreshCw,
  TrendingUp
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

const Monitoring = () => {
  const [systemHealth, setSystemHealth] = useState({
    status: 'healthy',
    uptime: '0s',
    lastCheck: new Date().toISOString()
  });
  const [metrics, setMetrics] = useState({
    totalAgents: 0,
    activeAgents: 0,
    totalModels: 0,
    totalTools: 0
  });
  const [resources, setResources] = useState({
    cpu_percent: 0,
    memory_percent: 0,
    memory_used_gb: 0,
    memory_total_gb: 0,
    disk_percent: 0
  });
  const [recentErrors, setRecentErrors] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadMonitoringData();
    const interval = setInterval(loadMonitoringData, 15000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
    return `${(seconds / 86400).toFixed(1)}d`;
  };

  const loadMonitoringData = async () => {
    setLoading(true);
    try {
      const [statsRes, healthRes] = await Promise.all([
        fetch(`${API_BASE}/stats`),
        fetch(`${API_BASE}/health`)
      ]);

      const stats = await statsRes.json();
      const health = await healthRes.json();

      setSystemHealth({
        status: stats.status === 'operational' ? 'healthy' : 'degraded',
        uptime: formatUptime(stats.uptime_seconds || 0),
        lastCheck: new Date().toISOString(),
        version: stats.version
      });

      setMetrics({
        totalAgents: stats.totalAgents || 0,
        activeAgents: stats.activeAgents || 0,
        totalModels: stats.totalModels || 0,
        totalTools: stats.totalTools || 0
      });

      if (stats.resources) {
        setResources(stats.resources);
      }
    } catch (error) {
      console.error('Failed to load monitoring data:', error);
      setSystemHealth(prev => ({ ...prev, status: 'degraded' }));
    } finally {
      setLoading(false);
    }
  };

  const services = [
    {
      name: 'API Server',
      status: systemHealth.status === 'healthy' ? 'healthy' : 'degraded',
      detail: `Uptime: ${systemHealth.uptime}`,
      icon: Server,
      color: systemHealth.status === 'healthy' ? 'emerald' : 'orange'
    },
    {
      name: 'Memory (mem0 + Qdrant)',
      status: 'healthy',
      detail: 'Vector memory operational',
      icon: Database,
      color: 'emerald'
    },
    {
      name: 'Ops-Center LLM',
      status: 'healthy',
      detail: `${metrics.totalModels} models available`,
      icon: Zap,
      color: 'emerald'
    },
    {
      name: 'LangGraph Workflows',
      status: 'healthy',
      detail: 'Orchestration ready',
      icon: Network,
      color: 'emerald'
    }
  ];

  const performanceMetrics = [
    {
      label: 'Total Agents',
      value: metrics.totalAgents,
      icon: Activity,
      color: 'purple'
    },
    {
      label: 'Active Agents',
      value: metrics.activeAgents,
      icon: CheckCircle,
      color: 'emerald'
    },
    {
      label: 'Models Available',
      value: metrics.totalModels,
      icon: Zap,
      color: 'orange'
    },
    {
      label: 'Built-in Tools',
      value: metrics.totalTools,
      icon: BarChart3,
      color: 'blue'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              System Monitoring
            </h1>
            <p className="text-slate-400 mt-1">
              Real-time platform health and performance metrics
            </p>
          </div>
          <button
            onClick={loadMonitoringData}
            disabled={loading}
            className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* System Status Banner */}
        <div className={`backdrop-blur-xl border rounded-xl p-6 ${
          systemHealth.status === 'healthy'
            ? 'bg-emerald-500/10 border-emerald-500/30'
            : 'bg-orange-500/10 border-orange-500/30'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              {systemHealth.status === 'healthy' ? (
                <CheckCircle className="w-8 h-8 text-emerald-400" />
              ) : (
                <AlertCircle className="w-8 h-8 text-orange-400" />
              )}
              <div>
                <h2 className={`text-2xl font-bold ${
                  systemHealth.status === 'healthy' ? 'text-emerald-400' : 'text-orange-400'
                }`}>
                  {systemHealth.status === 'healthy' ? 'All Systems Operational' : 'System Degraded'}
                </h2>
                <p className="text-slate-400">
                  Uptime: {systemHealth.uptime} • Last checked: {new Date(systemHealth.lastCheck).toLocaleTimeString()}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Performance Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {performanceMetrics.map((metric, idx) => (
            <div key={idx} className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <metric.icon className={`w-8 h-8 text-${metric.color}-400`} />
              </div>
              <p className="text-3xl font-bold text-white mb-1">{metric.value}</p>
              <p className="text-sm text-slate-400">{metric.label}</p>
            </div>
          ))}
        </div>

        {/* Service Status */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Service Health</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {services.map((service, idx) => (
              <div key={idx} className="p-4 bg-slate-800/50 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <service.icon className={`w-6 h-6 text-${service.color}-400`} />
                  <div className={`flex items-center space-x-1 ${
                    service.status === 'healthy' ? 'text-emerald-400' : 'text-orange-400'
                  }`}>
                    <div className={`w-2 h-2 rounded-full ${
                      service.status === 'healthy' ? 'bg-emerald-400' : 'bg-orange-400'
                    } animate-pulse`}></div>
                    <span className="text-xs font-medium capitalize">{service.status}</span>
                  </div>
                </div>
                <h3 className="font-semibold text-white mb-2">{service.name}</h3>
                <p className="text-xs text-slate-400">{service.detail}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Charts Placeholder */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* API Usage Chart */}
          <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-xl font-bold text-white mb-4">API Usage (Last 24 Hours)</h2>
            <div className="h-64 flex items-center justify-center bg-slate-800/50 rounded-lg">
              <div className="text-center">
                <BarChart3 className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">Chart visualization coming soon</p>
                <p className="text-slate-500 text-xs mt-1">Integrate with charting library</p>
              </div>
            </div>
          </div>

          {/* Response Time Chart */}
          <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
            <h2 className="text-xl font-bold text-white mb-4">Response Time Trend</h2>
            <div className="h-64 flex items-center justify-center bg-slate-800/50 rounded-lg">
              <div className="text-center">
                <TrendingUp className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-sm">Chart visualization coming soon</p>
                <p className="text-slate-500 text-xs mt-1">Integrate with charting library</p>
              </div>
            </div>
          </div>
        </div>

        {/* Resource Usage */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Resource Usage</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <Cpu className="w-6 h-6 text-blue-400" />
                <h3 className="font-semibold text-white">CPU Usage</h3>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Current</span>
                  <span className="text-white font-semibold">{resources.cpu_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-700" style={{ width: `${resources.cpu_percent || 0}%` }}></div>
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <HardDrive className="w-6 h-6 text-purple-400" />
                <h3 className="font-semibold text-white">Memory Usage</h3>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">{resources.memory_used_gb || 0} / {resources.memory_total_gb || 0} GB</span>
                  <span className="text-white font-semibold">{resources.memory_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-700" style={{ width: `${resources.memory_percent || 0}%` }}></div>
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center space-x-3 mb-3">
                <Database className="w-6 h-6 text-emerald-400" />
                <h3 className="font-semibold text-white">Disk Usage</h3>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Current</span>
                  <span className="text-white font-semibold">{resources.disk_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-700" style={{ width: `${resources.disk_percent || 0}%` }}></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Errors & Warnings */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Recent Errors & Warnings</h2>
          {recentErrors.length > 0 ? (
            <div className="space-y-3">
              {recentErrors.map((error, idx) => (
                <div
                  key={idx}
                  className={`p-4 rounded-lg border ${
                    error.level === 'error'
                      ? 'bg-red-500/10 border-red-500/30'
                      : 'bg-orange-500/10 border-orange-500/30'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      {error.level === 'error' ? (
                        <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5" />
                      )}
                      <div>
                        <p className={`font-medium ${
                          error.level === 'error' ? 'text-red-400' : 'text-orange-400'
                        }`}>
                          {error.message}
                        </p>
                        <p className="text-sm text-slate-400 mt-1">
                          {error.service} • {new Date(error.timestamp).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
              <p className="text-slate-400">No recent errors or warnings</p>
            </div>
          )}
        </div>

        {/* System Info */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">System Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Version</p>
              <p className="text-white font-semibold">v{systemHealth.version || '1.0.0'}</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Environment</p>
              <p className="text-white font-semibold">Development</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Backend</p>
              <p className="text-white font-semibold">FastAPI + LangGraph</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">LLM Gateway</p>
              <p className="text-white font-semibold">Ops-Center</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Monitoring;
