import { useState, useEffect } from 'react';
import {
  Activity,
  Server,
  Database,
  Zap,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  Clock,
  Cpu,
  HardDrive,
  Network,
  BarChart3,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';
import { toast } from 'react-hot-toast';

const Monitoring = () => {
  const [systemHealth, setSystemHealth] = useState({
    status: 'healthy',
    uptime: '99.9%',
    lastCheck: new Date().toISOString()
  });
  const [metrics, setMetrics] = useState({
    apiRequests: 1247,
    activeAgents: 42,
    llmCalls: 3891,
    avgResponseTime: 245
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadMonitoringData();
    // Refresh every 30 seconds
    const interval = setInterval(loadMonitoringData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadMonitoringData = async () => {
    setLoading(true);
    try {
      // In a real app, fetch from monitoring endpoints
      // For now, simulate with mock data
      await new Promise(resolve => setTimeout(resolve, 500));

      setSystemHealth({
        status: 'healthy',
        uptime: '99.9%',
        lastCheck: new Date().toISOString()
      });

      setMetrics({
        apiRequests: Math.floor(Math.random() * 500) + 1000,
        activeAgents: Math.floor(Math.random() * 10) + 40,
        llmCalls: Math.floor(Math.random() * 1000) + 3500,
        avgResponseTime: Math.floor(Math.random() * 100) + 200
      });
    } catch (error) {
      console.error('Failed to load monitoring data:', error);
      toast.error('Failed to load monitoring data');
    } finally {
      setLoading(false);
    }
  };

  const services = [
    {
      name: 'API Server',
      status: 'healthy',
      uptime: '99.99%',
      responseTime: '45ms',
      icon: Server,
      color: 'emerald'
    },
    {
      name: 'Database',
      status: 'healthy',
      uptime: '100%',
      responseTime: '12ms',
      icon: Database,
      color: 'emerald'
    },
    {
      name: 'LiteLLM',
      status: 'healthy',
      uptime: '99.8%',
      responseTime: '234ms',
      icon: Zap,
      color: 'emerald'
    },
    {
      name: 'OpenRouter',
      status: 'degraded',
      uptime: '97.5%',
      responseTime: '589ms',
      icon: Network,
      color: 'orange'
    }
  ];

  const recentErrors = [
    {
      timestamp: new Date(Date.now() - 300000).toISOString(),
      level: 'warning',
      message: 'High latency detected on OpenRouter',
      service: 'LLM Provider'
    },
    {
      timestamp: new Date(Date.now() - 1800000).toISOString(),
      level: 'error',
      message: 'Agent invocation timeout',
      service: 'Agent Runtime'
    },
    {
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      level: 'warning',
      message: 'Database connection pool near limit',
      service: 'Database'
    }
  ];

  const performanceMetrics = [
    {
      label: 'API Requests',
      value: metrics.apiRequests,
      change: '+12.5%',
      trend: 'up',
      icon: BarChart3,
      color: 'blue'
    },
    {
      label: 'Active Agents',
      value: metrics.activeAgents,
      change: '+5.2%',
      trend: 'up',
      icon: Activity,
      color: 'purple'
    },
    {
      label: 'LLM Calls',
      value: metrics.llmCalls,
      change: '+18.3%',
      trend: 'up',
      icon: Zap,
      color: 'orange'
    },
    {
      label: 'Avg Response Time',
      value: `${metrics.avgResponseTime}ms`,
      change: '-3.1%',
      trend: 'down',
      icon: Clock,
      color: 'emerald'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
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
                {metric.trend === 'up' && <TrendingUp className="w-5 h-5 text-emerald-400" />}
                {metric.trend === 'down' && <TrendingDown className="w-5 h-5 text-emerald-400" />}
              </div>
              <p className="text-3xl font-bold text-white mb-1">{metric.value}</p>
              <p className="text-sm text-slate-400 mb-2">{metric.label}</p>
              <p className={`text-xs ${
                metric.trend === 'down' && metric.label.includes('Response Time')
                  ? 'text-emerald-400'
                  : metric.trend === 'up'
                  ? 'text-emerald-400'
                  : 'text-red-400'
              }`}>
                {metric.change} from last hour
              </p>
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
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Uptime</span>
                    <span className="text-slate-300">{service.uptime}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Response Time</span>
                    <span className="text-slate-300">{service.responseTime}</span>
                  </div>
                </div>
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
                  <span className="text-white font-semibold">34%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-500" style={{ width: '34%' }}></div>
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
                  <span className="text-slate-400">Current</span>
                  <span className="text-white font-semibold">62%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-purple-500 to-pink-500" style={{ width: '62%' }}></div>
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
                  <span className="text-white font-semibold">45%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500" style={{ width: '45%' }}></div>
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
              <p className="text-white font-semibold">v1.0.0</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Environment</p>
              <p className="text-white font-semibold">Production</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Database</p>
              <p className="text-white font-semibold">PostgreSQL 15</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Node Version</p>
              <p className="text-white font-semibold">v20.11.0</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Monitoring;
