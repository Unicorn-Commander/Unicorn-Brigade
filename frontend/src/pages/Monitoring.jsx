/**
 * Monitoring — service health, resources and scheduled runs, polled every 15s.
 * The banner is COMPUTED from the service checks (any unhealthy service → the
 * banner says so, by name); it can never read "operational" above a failing
 * service. Every failure carries its reason in human words.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  Server,
  Database,
  Zap,
  CheckCircle,
  AlertTriangle,
  Clock,
  Cpu,
  HardDrive,
  Network,
  Wrench,
  RefreshCw,
  Bot,
  CalendarClock,
  Timer,
  MemoryStick,
} from 'lucide-react';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import Breadcrumbs from '../components/Breadcrumbs';
import StatCard from '../components/ui/StatCard';
import TimeSeriesChart from '../components/ui/TimeSeriesChart';
import {
  Button,
  Card,
  CardHeader,
  Chip,
  DataTable,
  Page,
  PageHeader,
  SectionHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  Tooltip,
} from '../components/ui';

const POLL_MS = 15000;
const MAX_HISTORY = 40; // ~10 minutes at the 15s interval
const sampleTime = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

// The backend's /monitoring/services names → how people know them.
const SERVICE_META = {
  database: { label: 'PostgreSQL', icon: Database },
  falkordb: { label: 'FalkorDB graph', icon: Network },
  qdrant: { label: 'Qdrant vectors', icon: Database },
  'ops-center-llm': { label: 'Ops-Center LLM', icon: Zap },
  'local-llm-router': { label: 'Local LLM router', icon: Cpu },
  langfuse: { label: 'Langfuse tracing', icon: Activity },
  scheduler: { label: 'Scheduler', icon: Clock },
};

const STATUS_CHIP = {
  healthy: { tone: 'ok', label: 'Healthy' },
  unhealthy: { tone: 'danger', label: 'Unhealthy' },
  degraded: { tone: 'warn', label: 'Degraded' },
  unknown: { tone: 'neutral', label: 'Unknown' },
};

const RUN_CHIP = {
  success: { tone: 'ok', label: 'Succeeded' },
  error: { tone: 'danger', label: 'Failed' },
  timeout: { tone: 'danger', label: 'Timed out' },
  running: { tone: 'live', label: 'Running' },
};

function formatUptime(seconds) {
  if (!seconds || seconds < 60) return `${Math.round(seconds || 0)}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}d`;
}

/** The backend's check detail, in words a person can act on. */
function describeCheck(svc) {
  const d = String(svc.detail || '');
  if (svc.status === 'healthy') return d || 'Responding normally.';
  const http = d.match(/HTTP\s+(\d{3})/);
  if (/ECONNREFUSED|connection refused/i.test(d)) return 'Not accepting connections — the service may be down or still starting.';
  if (/ETIMEDOUT|timed? ?out/i.test(d)) return 'Timed out — the service is up but not answering in time.';
  if (/ENOTFOUND|getaddrinfo|name resolution/i.test(d)) return 'Hostname can’t be resolved — check the service name in the deployment.';
  if (/ECONNRESET/i.test(d)) return 'The connection was dropped mid-check.';
  if (http && http[1][0] === '5') return `Answered with a server error (HTTP ${http[1]}).`;
  if (http && http[1][0] === '4') return `Rejected the health check (HTTP ${http[1]}) — likely an auth or path problem.`;
  if (/unauthori[sz]ed|forbidden|auth/i.test(d)) return 'Rejected the health check — credentials or permissions.';
  return d ? 'Failing its health check.' : 'No details reported.';
}

/** The API's own failure, in words that help on THIS page ("check Monitoring" is no help here). */
function apiFailure(err) {
  if (err?.status >= 500) {
    return {
      title: 'The API is answering with errors',
      detail: `It responded ${err.status} to the health checks. Try again in a moment; if it keeps happening, look at the API container’s logs.`,
    };
  }
  if (err?.status) return { title: 'The API rejected the health checks', detail: humanize(err, { what: 'reaching the API' }) };
  return { title: 'Couldn’t reach the API', detail: 'Nothing is answering at the API address. Check that the API container is running, then try again.' };
}

const pct = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const gaugeTone = (v) => (v >= 90 ? 'bg-danger' : v >= 70 ? 'bg-warn' : 'bg-ok');

function Gauge({ icon: Icon, label, value, detail }) {
  const v = pct(value);
  return (
    <Card variant="elevated" padding="sm">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-body-sm font-medium text-fg">
          <Icon aria-hidden="true" className="h-4 w-4 text-muted" />
          {label}
        </span>
        <span className="text-body font-semibold tabular-nums text-fg-strong">{v.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-surface" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v)} aria-label={label}>
        <div className={`h-full rounded-full transition-[width] duration-slow ${gaugeTone(v)}`} style={{ width: `${Math.min(100, v)}%` }} />
      </div>
      {detail && <p className="mt-1.5 text-caption text-muted">{detail}</p>}
    </Card>
  );
}

export default function Monitoring() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [statsError, setStatsError] = useState(null);
  const [checks, setChecks] = useState([]);
  const [checksError, setChecksError] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsError, setRunsError] = useState(null);
  const [history, setHistory] = useState([]);
  const [lastChecked, setLastChecked] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [nextIn, setNextIn] = useState(POLL_MS / 1000);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const inFlight = useRef(false);

  const load = useCallback(async ({ quiet = false } = {}) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (quiet) setRefreshing(true);
    try {
      const [statsRes, servicesRes, runsRes] = await Promise.allSettled([
        apiJson('/stats'),
        apiJson('/monitoring/services'),
        apiJson('/scheduled-runs', { redirectOn401: false }),
      ]);
      if (statsRes.status === 'fulfilled') {
        const s = statsRes.value;
        setStats(s);
        setStatsError(null);
        const r = s?.resources;
        if (r && (r.cpu_percent != null || r.memory_percent != null)) {
          setHistory((prev) => [...prev, { t: sampleTime(), cpu: pct(Number(r.cpu_percent)), mem: pct(Number(r.memory_percent)) }].slice(-MAX_HISTORY));
        }
      } else {
        setStatsError(statsRes.reason);
      }
      if (servicesRes.status === 'fulfilled') {
        setChecks(servicesRes.value?.services || []);
        setChecksError(null);
      } else {
        setChecksError(servicesRes.reason);
      }
      if (runsRes.status === 'fulfilled') {
        setRuns(runsRes.value?.items || []);
        setRunsError(null);
      } else {
        setRunsError(runsRes.reason);
      }
      setLastChecked(new Date());
      setNextIn(POLL_MS / 1000);
    } finally {
      inFlight.current = false;
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const poll = setInterval(() => load({ quiet: true }), POLL_MS);
    const tick = setInterval(() => setNextIn((n) => (n > 1 ? n - 1 : POLL_MS / 1000)), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load({ quiet: true });
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  // The API server itself is a service: reachable when /stats answers.
  const services = useMemo(() => {
    const apiUp = Boolean(stats) && !statsError;
    const api = {
      key: 'api',
      label: 'API server',
      icon: Server,
      status: apiUp ? 'healthy' : 'unhealthy',
      latency: null,
      detail: apiUp ? `Uptime ${formatUptime(stats?.uptime_seconds)}${stats?.version ? ` · v${stats.version}` : ''}` : apiFailure(statsError).detail,
      raw: apiUp ? null : String(statsError?.message || ''),
    };
    const rest = checks.map((svc) => {
      const meta = SERVICE_META[svc.name] || { label: svc.name, icon: Server };
      const status = STATUS_CHIP[svc.status] ? svc.status : 'unknown';
      return {
        key: svc.name,
        label: meta.label,
        icon: meta.icon,
        status,
        latency: typeof svc.latency_ms === 'number' ? svc.latency_ms : null,
        detail: describeCheck({ ...svc, status }),
        raw: svc.detail || null,
      };
    });
    return [api, ...rest];
  }, [stats, statsError, checks]);

  const attention = services.filter((s) => s.status !== 'healthy');
  const apiDown = Boolean(statsError) && Boolean(checksError);

  const banner = apiDown
    ? { tone: 'danger', icon: AlertTriangle, ...apiFailure(statsError) }
    : attention.length
      ? {
          tone: 'warn',
          icon: AlertTriangle,
          title: `${attention.length} service${attention.length === 1 ? '' : 's'} need${attention.length === 1 ? 's' : ''} attention`,
          detail: attention.map((s) => s.label).join(' · '),
        }
      : { tone: 'ok', icon: CheckCircle, title: 'All systems operational', detail: `${services.length} services healthy` };

  const BANNER_CLASS = {
    ok: 'border-ok/30 bg-ok/10 text-ok',
    warn: 'border-warn/30 bg-warn/10 text-warn',
    danger: 'border-danger/30 bg-danger/10 text-danger',
  };

  const res = stats?.resources || {};
  const statCards = [
    {
      icon: Bot,
      label: 'Agents',
      value: stats?.totalAgents ?? '—',
      change: (
        <Tooltip content="Active = agents whose status is “active” in the roster. Paused, draft and archived agents count in the total but not here.">
          <span tabIndex={0} className="cursor-help underline decoration-dotted underline-offset-2">
            {stats?.activeAgents ?? '—'} active
          </span>
        </Tooltip>
      ),
    },
    { icon: Zap, label: 'Models available', value: stats?.totalModels ?? '—', change: 'Across every provider' },
    { icon: Wrench, label: 'Tools registered', value: stats?.totalTools ?? '—', change: 'Built-in and MCP' },
    { icon: Timer, label: 'Uptime', value: stats ? formatUptime(stats.uptime_seconds) : '—', change: stats?.version ? `Version ${stats.version}` : 'Since the last restart' },
  ];

  const runColumns = [
    { key: 'name', label: 'Run', render: (r) => <span className="font-medium text-fg">{r.name}</span> },
    { key: 'cron', label: 'Schedule', mono: true },
    {
      key: 'enabled',
      label: 'State',
      render: (r) => (
        <Chip tone={r.enabled ? 'ok' : 'neutral'} size="xs" dot>
          {r.enabled ? 'Enabled' : 'Paused'}
        </Chip>
      ),
    },
    {
      key: 'lastStatus',
      label: 'Last result',
      render: (r) => {
        const m = RUN_CHIP[r.lastStatus];
        return m ? (
          <Chip tone={m.tone} size="xs" dot pulse={r.lastStatus === 'running'}>
            {m.label}
          </Chip>
        ) : (
          <Chip size="xs">Never run</Chip>
        );
      },
    },
    { key: 'lastRunAt', label: 'Last run', hideOnMobile: true, render: (r) => (r.lastRunAt ? new Date(r.lastRunAt).toLocaleString() : '—') },
  ];

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !stats && !checks.length) {
    body = <OfflineState onRetry={() => load()} />;
  } else if (loading) {
    body = (
      <div className="space-y-6">
        <div aria-hidden="true" className="h-16 animate-pulse rounded-card border border-border bg-card" />
        <LoadingState variant="stats" label="Loading monitoring" />
        <section>
          <SectionHeader title="Services" />
          <LoadingState variant="cards" count={4} label="Loading services" />
        </section>
      </div>
    );
  } else if (apiDown && !checks.length) {
    const f = apiFailure(statsError);
    body = <ErrorState title={f.title} detail={f.detail} onRetry={() => load()} />;
  } else {
    const B = banner.icon;
    body = (
      <div className="space-y-6">
        <div role="status" className={`flex flex-wrap items-center gap-3 rounded-card border px-4 py-3 ${BANNER_CLASS[banner.tone]}`}>
          <B aria-hidden="true" className="h-5 w-5 shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="text-body font-semibold">{banner.title}</p>
            <p className="text-body-sm text-muted">{banner.detail}</p>
          </div>
          <p className="text-caption text-muted">
            {lastChecked ? `Checked ${lastChecked.toLocaleTimeString()}` : 'Checking…'}
          </p>
        </div>

        <section aria-label="Key numbers" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {statCards.map((m) => (
            <StatCard key={m.label} icon={m.icon} label={m.label} value={m.value} change={m.change} />
          ))}
        </section>

        <section>
          <SectionHeader title="Services" description={checksError ? undefined : `${services.length} checks, latency as measured by the API`} />
          {checksError && (
            <ErrorState compact title="Service checks unavailable" detail={humanize(checksError, { what: 'loading service checks' })} onRetry={() => load({ quiet: true })} className="mb-4" />
          )}
          {services.length ? (
            <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Services">
              {services.map((s) => {
                const Icon = s.icon;
                const chip = STATUS_CHIP[s.status] || STATUS_CHIP.unknown;
                const chipEl = (
                  <Chip tone={chip.tone} size="xs" dot pulse={s.status === 'unhealthy'}>
                    {chip.label}
                  </Chip>
                );
                return (
                  <li key={s.key}>
                    <Card padding="sm" className={`h-full ${s.status === 'healthy' ? '' : 'border-warn/40'}`}>
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="flex min-w-0 items-center gap-2">
                          <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-elevated text-muted">
                            <Icon className="h-4 w-4" />
                          </span>
                          <span className="truncate text-body font-semibold text-fg-strong">{s.label}</span>
                        </span>
                        {s.raw ? <Tooltip content={s.raw}>{chipEl}</Tooltip> : chipEl}
                      </div>
                      <p className="text-body-sm text-muted">{s.detail}</p>
                      {s.latency != null && (
                        <p className="mt-1.5 font-mono text-caption tabular-nums text-subtle">{s.latency} ms</p>
                      )}
                    </Card>
                  </li>
                );
              })}
            </ul>
          ) : (
            !checksError && <EmptyState compact icon={Server} title="No service checks reported" description="The API hasn’t reported any service checks yet." />
          )}
        </section>

        <section>
          <SectionHeader title="Resources" description="Live samples from /stats, every 15 seconds" />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Gauge icon={Cpu} label="CPU" value={res.cpu_percent} />
            <Gauge icon={MemoryStick} label="Memory" value={res.memory_percent} detail={res.memory_total_gb ? `${res.memory_used_gb ?? 0} of ${res.memory_total_gb} GB` : undefined} />
            <Gauge icon={HardDrive} label="Disk" value={res.disk_percent} />
          </div>
          <Card className="mt-4">
            <CardHeader title="CPU and memory over time" description={history.length > 1 ? `${history.length} samples · the last ~${Math.round((history.length * POLL_MS) / 60000) || 1} min` : 'Collecting the first samples'} />
            <TimeSeriesChart
              series={[
                { key: 'cpu', label: 'CPU', color: 'var(--chart-1)', data: history.map((p) => p.cpu) },
                { key: 'mem', label: 'Memory', color: 'var(--chart-2)', data: history.map((p) => p.mem) },
              ]}
              labels={history.map((p) => p.t)}
              yMax={100}
              unit="%"
              height={220}
              emptyLabel="Collecting live samples — the first points appear within 30 seconds"
            />
          </Card>
        </section>

        <section>
          <SectionHeader
            title="Scheduled runs"
            description="The most recent cron-driven agent runs"
            actions={
              <Button variant="secondary" size="sm" icon={CalendarClock} onClick={() => navigate('/scheduled-runs')}>
                Manage runs
              </Button>
            }
          />
          <DataTable
            columns={runColumns}
            rows={runs.slice(0, 8)}
            rowKey="id"
            caption="Scheduled runs"
            dense
            onRowClick={() => navigate('/scheduled-runs')}
            error={runsError && { title: 'Couldn’t load scheduled runs', detail: humanize(runsError, { what: 'loading scheduled runs' }), onRetry: () => load({ quiet: true }) }}
            empty={{
              icon: CalendarClock,
              title: 'No scheduled runs yet',
              description: 'Schedule an agent to run on a cron and it appears here.',
              action: (
                <Button size="sm" icon={CalendarClock} onClick={() => navigate('/scheduled-runs')}>
                  Schedule a run
                </Button>
              ),
            }}
          />
        </section>
      </div>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="System"
        title="Monitoring"
        description="Service health, resource use and scheduled runs, refreshed every 15 seconds"
        actions={
          <>
            <span className="text-caption tabular-nums text-muted" aria-live="off">
              Next check in {nextIn}s
            </span>
            <Button variant="secondary" icon={RefreshCw} loading={refreshing} disabled={loading} onClick={() => load({ quiet: true })}>
              Refresh
            </Button>
          </>
        }
      />
      {body}
    </Page>
  );
}
