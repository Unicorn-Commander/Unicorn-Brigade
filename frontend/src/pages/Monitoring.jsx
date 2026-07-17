import { useState, useEffect } from 'react';
import {
  Activity,
  Server,
  Database,
  Zap,
  AlertCircle,
  CheckCircle,
  Clock,
  Cpu,
  HardDrive,
  Network,
  BarChart3,
  RefreshCw
} from 'lucide-react';
import { apiJson } from '../services/http';
import Breadcrumbs from '../components/Breadcrumbs';
import TimeSeriesChart from '../components/ui/TimeSeriesChart';

// Rolling window of live resource samples (~10 min at the 15s poll interval).
const MAX_HISTORY = 40;
const sampleTime = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

// Icons + display names for the backend's /monitoring/services entries.
const SERVICE_ICONS = {
  database: Database,
  falkordb: Network,
  qdrant: Database,
  'ops-center-llm': Zap,
  'local-llm-router': Cpu,
  langfuse: Activity,
  scheduler: Clock,
};

const SERVICE_LABELS = {
  database: 'PostgreSQL',
  falkordb: 'FalkorDB Graph',
  qdrant: 'Qdrant Vectors',
  'ops-center-llm': 'Ops-Center LLM',
  'local-llm-router': 'Local LLM Router',
  langfuse: 'Langfuse Tracing',
  scheduler: 'Scheduler (APScheduler)',
};

const statusColors = (status) => {
  if (status === 'healthy') return { text: 'text-emerald-400', dot: 'bg-emerald-400' };
  if (status === 'unhealthy') return { text: 'text-red-400', dot: 'bg-red-400' };
  return { text: 'text-orange-400', dot: 'bg-orange-400' };
};

const runStatusBadge = (status) => {
  if (status === 'success') return 'bg-emerald-500/20 text-emerald-400';
  if (status === 'error' || status === 'timeout') return 'bg-red-500/20 text-red-400';
  if (status === 'running') return 'bg-blue-500/20 text-blue-400';
  return 'bg-slate-500/20 text-slate-400';
};

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
  const [serviceChecks, setServiceChecks] = useState([]);
  // Live time-series accumulated from real /stats resource samples (no mock data).
  const [resourceHistory, setResourceHistory] = useState([]);
  const [scheduledRuns, setScheduledRuns] = useState([]);
  const [runsError, setRunsError] = useState(null);
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
      const [statsRes, servicesRes, runsRes] = await Promise.allSettled([
        apiJson('/stats'),
        apiJson('/monitoring/services'),
        apiJson('/scheduled-runs', { redirectOn401: false }),
      ]);

      if (statsRes.status === 'fulfilled') {
        const stats = statsRes.value;
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
          const r = stats.resources;
          if (r.cpu_percent != null || r.memory_percent != null) {
            setResourceHistory((prev) =>
              [
                ...prev,
                {
                  t: sampleTime(),
                  cpu: Number(r.cpu_percent) || 0,
                  mem: Number(r.memory_percent) || 0,
                },
              ].slice(-MAX_HISTORY)
            );
          }
        }
      } else {
        console.error('Failed to load monitoring data:', statsRes.reason);
        setSystemHealth(prev => ({ ...prev, status: 'degraded' }));
      }

      if (servicesRes.status === 'fulfilled') {
        setServiceChecks(servicesRes.value.services || []);
      } else {
        console.error('Failed to load service checks:', servicesRes.reason);
        setServiceChecks([]);
      }

      if (runsRes.status === 'fulfilled') {
        setScheduledRuns(runsRes.value.items || []);
        setRunsError(null);
      } else {
        setScheduledRuns([]);
        const status = runsRes.reason?.status;
        setRunsError(
          status === 401 || status === 403
            ? 'Sign in with an operator account to view scheduled runs'
            : 'Failed to load scheduled runs'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  // API Server card comes from /stats reachability; the rest are the
  // backend's real per-service checks.
  const services = [
    {
      name: 'API Server',
      status: systemHealth.status === 'healthy' ? 'healthy' : 'degraded',
      detail: `Uptime: ${systemHealth.uptime}`,
      icon: Server
    },
    ...serviceChecks.map((svc) => ({
      name: SERVICE_LABELS[svc.name] || svc.name,
      status: svc.status || 'unknown',
      detail: [
        typeof svc.latency_ms === 'number' ? `${svc.latency_ms}ms` : null,
        svc.detail || null,
      ].filter(Boolean).join(' · '),
      icon: SERVICE_ICONS[svc.name] || Server
    }))
  ];

  // Static color classes (no dynamic `text-${color}` — Tailwind can't see those).
  const performanceMetrics = [
    {
      label: 'Total Agents',
      value: metrics.totalAgents,
      icon: Activity,
      colorClass: 'text-unicorn-400'
    },
    {
      label: 'Active Agents',
      value: metrics.activeAgents,
      icon: CheckCircle,
      colorClass: 'text-emerald-400'
    },
    {
      label: 'Models Available',
      value: metrics.totalModels,
      icon: Zap,
      colorClass: 'text-orange-400'
    },
    {
      label: 'Tools Registered',
      value: metrics.totalTools,
      icon: BarChart3,
      colorClass: 'text-blue-400'
    }
  ];

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gradient">
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
                <metric.icon className={`w-8 h-8 ${metric.colorClass}`} />
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
            {services.map((service, idx) => {
              const colors = statusColors(service.status);
              return (
                <div key={idx} className="p-4 bg-slate-800/50 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <service.icon className={`w-6 h-6 ${colors.text}`} />
                    <div className={`flex items-center space-x-1 ${colors.text}`}>
                      <div className={`w-2 h-2 rounded-full ${colors.dot} animate-pulse`}></div>
                      <span className="text-xs font-medium capitalize">{service.status}</span>
                    </div>
                  </div>
                  <h3 className="font-semibold text-white mb-2">{service.name}</h3>
                  <p className="text-xs text-slate-400 break-words">{service.detail}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Scheduled Runs */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">Scheduled Runs (recent)</h2>
          {runsError ? (
            <p className="text-slate-400 text-center py-6">{runsError}</p>
          ) : scheduledRuns.length === 0 ? (
            <div className="text-center py-6">
              <Clock className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">No scheduled runs configured</p>
            </div>
          ) : (
            <div className="space-y-3">
              {scheduledRuns.slice(0, 8).map((run) => (
                <div key={run.id} className="flex items-center justify-between p-3 rounded-lg bg-slate-800/50">
                  <div className="min-w-0">
                    <p className="font-medium text-white truncate">{run.name}</p>
                    <p className="text-xs text-slate-400 truncate">
                      {run.cron} • {run.enabled ? 'enabled' : 'disabled'}
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0 ml-4">
                    <span className={`px-2 py-0.5 rounded-full text-xs ${runStatusBadge(run.lastStatus)}`}>
                      {run.lastStatus || 'never run'}
                    </span>
                    <p className="text-xs text-slate-500 mt-1">
                      {run.lastRunAt ? new Date(run.lastRunAt).toLocaleString() : '—'}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Resource Utilization over time — live samples from /stats */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-white">Resource Utilization</h2>
            <span className="text-xs text-slate-500">
              Live · sampled every 15s{resourceHistory.length > 1 ? ` · ${resourceHistory.length} points` : ''}
            </span>
          </div>
          <TimeSeriesChart
            series={[
              { key: 'cpu', label: 'CPU', color: 'var(--chart-1)', data: resourceHistory.map((p) => p.cpu) },
              { key: 'mem', label: 'Memory', color: 'var(--chart-2)', data: resourceHistory.map((p) => p.mem) },
            ]}
            labels={resourceHistory.map((p) => p.t)}
            yMax={100}
            unit="%"
            height={220}
            emptyLabel="Collecting live samples… (first points appear within ~30s)"
          />
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
                <HardDrive className="w-6 h-6 text-unicorn-400" />
                <h3 className="font-semibold text-white">Memory Usage</h3>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">{resources.memory_used_gb || 0} / {resources.memory_total_gb || 0} GB</span>
                  <span className="text-white font-semibold">{resources.memory_percent?.toFixed(1) || 0}%</span>
                </div>
                <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-unicorn-600 to-unicorn-500 transition-all duration-700" style={{ width: `${resources.memory_percent || 0}%` }}></div>
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

        {/* System Info */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4">System Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Version</p>
              <p className="text-white font-semibold">v{systemHealth.version || '—'}</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Workflow Engine</p>
              <p className="text-white font-semibold">APScheduler + Brigade</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-sm text-slate-400 mb-1">Backend</p>
              <p className="text-white font-semibold">FastAPI + SQLAlchemy</p>
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
