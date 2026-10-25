/**
 * Code attribution — which agent wrote which code, for audit trails.
 *
 * Data: GET /trace/recent?days=N (one window, shared by every tab) and
 * GET /trace/stats. The trace API answers an EMPTY window with 404 + "No
 * attributions found …"; traceService turns that into [] so this page shows an
 * honest empty state, and only a missing route becomes an error.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BarChart3, Clock, Download, FileCode, RefreshCw, Search, User, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import traceService from '../services/traceService';
import CodeAttributionCard from '../components/CodeAttributionCard';
import AttributionTimeline from '../components/AttributionTimeline';
import FileAttributionViewer from '../components/FileAttributionViewer';
import AttributionStats from '../components/AttributionStats';
import Breadcrumbs from '../components/Breadcrumbs';
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  OfflineState,
  Page,
  PageHeader,
  Select,
  Tabs,
  Toggle,
} from '../components/ui';

// The UI date-range picker → the trace API's `days` lookback (1-90).
const RANGES = [
  { id: '24h', label: 'Last 24 hours', days: 1 },
  { id: '7d', label: 'Last 7 days', days: 7 },
  { id: '30d', label: 'Last 30 days', days: 30 },
  { id: '90d', label: 'Last 90 days', days: 90 },
];
const daysFor = (id) => RANGES.find((r) => r.id === id)?.days || 7;

const TABS = [
  { id: 'by-file', label: 'By file', icon: FileCode },
  { id: 'by-agent', label: 'By agent', icon: User },
  { id: 'recent', label: 'Recent', icon: Clock },
  { id: 'statistics', label: 'Statistics', icon: BarChart3 },
];

const fileName = (p = '') => p.split('/').pop() || p;

export default function CodeAttribution() {
  const [tab, setTab] = useState('by-file');
  const [query, setQuery] = useState('');
  const [range, setRange] = useState('7d');
  const [agent, setAgent] = useState('');

  const [attributions, setAttributions] = useState([]);
  const [statistics, setStatistics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [exporting, setExporting] = useState(false);

  const [viewer, setViewer] = useState(null); // { filePath, attributions, code }
  const [viewerLoading, setViewerLoading] = useState(null); // filePath being opened

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (silent) setRefreshing(true);
      else setLoading(true);
      setError(null);
      const [a, s] = await Promise.allSettled([traceService.getAttributions({ days: daysFor(range) }), traceService.getStatistics()]);
      if (a.status === 'fulfilled') setAttributions(a.value || []);
      else setError(a.reason);
      if (s.status === 'fulfilled') setStatistics(s.value || null);
      setLoading(false);
      setRefreshing(false);
    },
    [range]
  );

  useEffect(() => {
    load();
  }, [load]);

  // The Recent tab keeps itself fresh.
  useEffect(() => {
    if (tab !== 'recent' || !autoRefresh) return undefined;
    const t = setInterval(() => load({ silent: true }), 10000);
    return () => clearInterval(t);
  }, [tab, autoRefresh, load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  const agents = useMemo(
    () => [...new Map(attributions.filter((a) => a.agent_id).map((a) => [a.agent_id, { id: a.agent_id, name: a.agent_name || a.agent_id }])).values()],
    [attributions]
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return attributions.filter((a) => {
      if (agent && a.agent_id !== agent) return false;
      if (!q) return true;
      return [a.file_path, a.agent_name, a.agent_id, a.model, a.prompt].some((f) => (f || '').toLowerCase().includes(q));
    });
  }, [attributions, query, agent]);

  const byFile = useMemo(() => {
    const m = new Map();
    for (const a of filtered) {
      if (!m.has(a.file_path)) m.set(a.file_path, []);
      m.get(a.file_path).push(a);
    }
    return [...m.entries()];
  }, [filtered]);

  const byAgent = useMemo(() => {
    const m = new Map();
    for (const a of filtered) {
      const k = a.agent_id || a.agent_name || 'unknown';
      if (!m.has(k)) m.set(k, { id: k, name: a.agent_name || k, items: [] });
      m.get(k).items.push(a);
    }
    return [...m.values()];
  }, [filtered]);

  const hasFilters = Boolean(query || agent);
  const clearFilters = () => {
    setQuery('');
    setAgent('');
  };

  const openFile = async (filePath) => {
    setViewerLoading(filePath);
    try {
      const data = await traceService.getFileAttributions(filePath);
      setViewer({ filePath, attributions: data?.attributions || [], code: data?.code || '' });
    } catch (err) {
      notify.error(humanize(err, { what: 'opening the file' }));
    } finally {
      setViewerLoading(null);
    }
  };

  const exportReport = async () => {
    setExporting(true);
    try {
      const filters = {};
      const days = daysFor(range);
      const end = new Date();
      const start = new Date(end.getTime() - days * 86400000);
      filters.startDate = start.toISOString();
      filters.endDate = end.toISOString();
      if (agent) filters.agentId = agent;
      const blob = await traceService.exportReport(filters, 'json');
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `attribution-report-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      notify.success('Report downloaded');
    } catch (err) {
      notify.error(humanize(err, { what: 'exporting the report' }));
    } finally {
      setExporting(false);
    }
  };

  // ── the four states ────────────────────────────────────────────────────────
  let body;
  if (offline && !attributions.length && loading) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = tab === 'statistics' ? <LoadingState variant="stats" count={4} label="Loading statistics" /> : tab === 'recent' ? <LoadingState variant="list" count={5} label="Loading activity" /> : <LoadingState variant="cards" count={6} label="Loading attributions" />;
  } else if (error) {
    body = (
      <ErrorState
        title={error.routeMissing ? 'Attribution isn’t available on this server' : 'Couldn’t load attributions'}
        detail={
          error.routeMissing
            ? 'The trace service (GET /api/v1/trace/recent) didn’t answer on this deployment. Attribution appears here once the service is enabled and an agent has written code through it.'
            : humanize(error, { what: 'loading attributions' })
        }
        onRetry={load}
      />
    );
  } else if (tab === 'statistics') {
    body = <AttributionStats statistics={statistics} />;
  } else if (!attributions.length) {
    body = (
      <EmptyState
        icon={FileCode}
        title="No attributed files in this window"
        description="Attribution is recorded when an agent writes code through the trace service (POST /api/v1/trace/report). Widen the window, or check back after an agent has worked on a file."
        action={
          range !== '90d' && (
            <Button variant="secondary" icon={Clock} onClick={() => setRange('90d')}>
              Look back 90 days
            </Button>
          )
        }
      />
    );
  } else if (!filtered.length) {
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No attributions match"
        description="Try another word, or clear the agent filter."
        action={
          <Button variant="secondary" size="sm" icon={X} onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else if (tab === 'by-file') {
    body = (
      <ul className="space-y-4" aria-label="Attributed files">
        {byFile.map(([filePath, items]) => (
          <li key={filePath}>
            <Card>
              <div className="mb-3 flex items-start justify-between gap-3">
                <button
                  type="button"
                  onClick={() => openFile(filePath)}
                  className="flex min-w-0 flex-1 items-start gap-2 rounded-chip text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-label={`Open attributions for ${filePath}`}
                >
                  <FileCode aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                  <span className="min-w-0">
                    <span className="block truncate text-body font-semibold text-fg-strong">{fileName(filePath)}</span>
                    <span className="block truncate font-mono text-caption text-muted">{filePath}</span>
                  </span>
                </button>
                <Chip tone="accent" size="sm" className="shrink-0 tabular-nums">
                  {items.length} attribution{items.length === 1 ? '' : 's'}
                </Chip>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {items.slice(0, 3).map((a, i) => (
                  <CodeAttributionCard key={a.id || i} attribution={a} compact onClick={() => openFile(filePath)} />
                ))}
              </div>
              <div className="mt-3 flex justify-end">
                <Button variant="link" size="sm" loading={viewerLoading === filePath} onClick={() => openFile(filePath)}>
                  {items.length > 3 ? `View all ${items.length} attributions` : 'View attributed code'}
                </Button>
              </div>
            </Card>
          </li>
        ))}
      </ul>
    );
  } else if (tab === 'by-agent') {
    body = (
      <ul className="space-y-4" aria-label="Agents">
        {byAgent.map((g) => {
          const lines = g.items.reduce((n, a) => n + (a.lines_count || 0), 0);
          const files = new Set(g.items.map((a) => a.file_path)).size;
          return (
            <li key={g.id}>
              <Card>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
                      <User className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <h3 className="truncate text-lead font-semibold text-fg-strong">{g.name}</h3>
                      <p className="truncate font-mono text-caption text-muted">{g.id}</p>
                    </div>
                  </div>
                  <dl className="flex items-center gap-5 text-body-sm">
                    <div className="text-right">
                      <dt className="text-caption text-muted">Lines</dt>
                      <dd className="font-semibold tabular-nums text-fg-strong">{lines.toLocaleString()}</dd>
                    </div>
                    <div className="text-right">
                      <dt className="text-caption text-muted">Files</dt>
                      <dd className="font-semibold tabular-nums text-fg-strong">{files}</dd>
                    </div>
                  </dl>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  {g.items.slice(0, 4).map((a, i) => (
                    <CodeAttributionCard key={a.id || i} attribution={a} compact onClick={() => openFile(a.file_path)} />
                  ))}
                </div>
                {g.items.length > 4 && <p className="mt-3 text-center text-caption text-muted">+ {g.items.length - 4} more attributions</p>}
              </Card>
            </li>
          );
        })}
      </ul>
    );
  } else {
    body = (
      <div>
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-body-sm text-muted">{refreshing ? 'Refreshing…' : `${filtered.length} change${filtered.length === 1 ? '' : 's'} in this window`}</p>
          <label htmlFor="attr-auto-refresh" className="inline-flex items-center gap-2 text-body-sm text-muted">
            Auto-refresh every 10s
            <Toggle id="attr-auto-refresh" label="Auto-refresh every 10 seconds" checked={autoRefresh} onChange={setAutoRefresh} />
          </label>
        </div>
        <AttributionTimeline attributions={filtered} onItemClick={(a) => openFile(a.file_path)} />
      </div>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Audit"
        title="Code attribution"
        description={loading ? 'Which agent wrote which code, for audit trails and compliance.' : `${attributions.length} attribution${attributions.length === 1 ? '' : 's'} in the ${RANGES.find((r) => r.id === range)?.label.toLowerCase()}.`}
        actions={
          <>
            <Button variant="secondary" icon={Download} loading={exporting} onClick={exportReport} disabled={!attributions.length}>
              Export report
            </Button>
            <Button variant="secondary" icon={RefreshCw} loading={refreshing} onClick={() => load({ silent: true })}>
              Refresh
            </Button>
          </>
        }
        tabs={<Tabs tabs={TABS} value={tab} onChange={setTab} label="Attribution views" idBase="attr-tab" />}
      />

      <Card padding="sm" className="mb-5">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input type="search" aria-label="Search files, agents, models or prompts" placeholder="Search files, agents, models, prompts…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9" />
          </div>
          <Select aria-label="Date range" value={range} onChange={(e) => setRange(e.target.value)} className="md:w-44">
            {RANGES.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by agent" value={agent} onChange={(e) => setAgent(e.target.value)} className="md:w-48" disabled={!agents.length}>
            <option value="">All agents</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </Select>
        </div>
        {hasFilters && !loading && (
          <div className="mt-2 flex items-center gap-2 text-caption text-muted">
            <span>
              {filtered.length} match{filtered.length === 1 ? '' : 'es'}
            </span>
            <Button variant="link" size="xs" onClick={clearFilters}>
              Clear
            </Button>
          </div>
        )}
      </Card>

      <div role="tabpanel" aria-labelledby={`attr-tab-${tab}`}>
        {body}
      </div>

      {viewer && <FileAttributionViewer filePath={viewer.filePath} attributions={viewer.attributions} code={viewer.code} onClose={() => setViewer(null)} />}
    </Page>
  );
}
