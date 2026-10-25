/**
 * Self-correction — Ralph's runs.
 *
 * The nav says "Self-Correction"; so does the page now. Ralph re-runs a failed
 * workflow in iterations, carrying forward what it learned, until the tasks
 * pass or it runs out of tries; a paused run is waiting for a person's hint.
 *
 * Frame → honest stat cards → runs table → the selected run in a Card with its
 * retry timeline and the guidance box → the four states.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, RefreshCw, MessageSquare, XCircle, GitBranch, CheckCircle2, AlertTriangle, Play, PauseCircle } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import api from '../services/api';
import Breadcrumbs from '../components/Breadcrumbs';
import { Button, Card, CardHeader, Chip, DataTable, Field, Textarea, Modal, StatCard, StatusDot, Page, PageHeader, EmptyState, ErrorState, OfflineState, LoadingState } from '../components/ui';

const RALPH_STATUS = {
  running: { tone: 'live', label: 'Running', dot: 'tool', pulse: true },
  paused: { tone: 'warn', label: 'Needs guidance', dot: 'thinking', pulse: true },
  needs_guidance: { tone: 'warn', label: 'Needs guidance', dot: 'thinking', pulse: true },
  success: { tone: 'ok', label: 'Succeeded', dot: 'done' },
  completed: { tone: 'ok', label: 'Succeeded', dot: 'done' },
  failed: { tone: 'danger', label: 'Failed', dot: 'error' },
  max_iterations: { tone: 'danger', label: 'Ran out of tries', dot: 'error' },
  cancelled: { tone: 'neutral', label: 'Cancelled', dot: 'offline' },
  not_started: { tone: 'neutral', label: 'Not started', dot: 'idle' },
};
const statusOf = (ex) => {
  const key = ex?.is_paused ? 'paused' : ex?.status || (ex?.is_complete ? 'completed' : 'running');
  return RALPH_STATUS[key] || { tone: 'neutral', label: String(key).replace(/_/g, ' '), dot: 'idle' };
};

/** The list endpoint answers a bare array; the mock wraps it. */
const asList = (data) => (Array.isArray(data) ? data : data?.executions || data?.items || []);

function Progress({ value, tone = 'accent' }) {
  const pct = Math.max(0, Math.min(100, Math.round(Number(value) || 0)));
  const fill = { accent: 'bg-accent-fill', ok: 'bg-ok-fill', danger: 'bg-danger-fill', warn: 'bg-warn-fill' }[tone] || 'bg-accent-fill';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-elevated" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className={`h-full rounded-full ${fill} transition-[width] duration-slow ease-standard`} style={{ width: `${pct}%` }} />
      </div>
      <span className="tabular-nums text-caption text-muted">{pct}%</span>
    </div>
  );
}

/** The retry timeline: one chip per iteration, the current one live. */
function IterationTimeline({ iteration, max, complete, status }) {
  const n = Math.max(1, Number(max) || 1);
  const cur = Math.max(1, Math.min(n, Number(iteration) || 1));
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Iterations">
      {Array.from({ length: n }, (_, i) => {
        const k = i + 1;
        let tone = 'neutral';
        let label = `Try ${k}`;
        let dot = false;
        let pulse = false;
        if (k < cur || (complete && k === cur && status.tone === 'ok')) {
          tone = k === cur ? 'ok' : 'neutral';
          label = k === cur ? `Try ${k} · passed` : `Try ${k} · retried`;
          dot = true;
        } else if (k === cur) {
          tone = complete ? status.tone : 'live';
          label = complete ? `Try ${k} · ${status.label.toLowerCase()}` : `Try ${k} · now`;
          dot = true;
          pulse = !complete;
        }
        return (
          <li key={k} className="flex items-center gap-1.5">
            <Chip tone={tone} dot={dot} pulse={pulse} size="sm" solid={k === cur && !complete}>
              {label}
            </Chip>
            {k < n && <span aria-hidden="true" className="h-px w-3 bg-border-strong" />}
          </li>
        );
      })}
    </ol>
  );
}

export default function RalphMonitor() {
  const navigate = useNavigate();
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState(null);
  const [guidance, setGuidance] = useState('');
  const [guidanceError, setGuidanceError] = useState('');
  const [sending, setSending] = useState(false);
  const [cancelling, setCancelling] = useState(null); // execution awaiting confirm
  const [cancelBusy, setCancelBusy] = useState(false);
  const selectedRef = useRef(null);
  selectedRef.current = selectedId;

  const loadDetail = useCallback(async (id) => {
    setDetailError(null);
    try {
      const data = await api.get(`/ralph/executions/${id}`);
      setDetail({ execution_id: id, ...(data || {}) });
    } catch (err) {
      setDetailError(err);
    }
  }, []);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) {
        setLoading(true);
        setError(null);
      }
      try {
        const list = asList(await api.get('/ralph/executions'));
        setExecutions(list);
        const sel = selectedRef.current;
        if (sel && list.some((e) => e.execution_id === sel && !e.is_complete)) loadDetail(sel);
      } catch (err) {
        if (!silent) setError(err);
      } finally {
        setLoading(false);
      }
    },
    [loadDetail]
  );

  useEffect(() => {
    load();
    const t = setInterval(() => load({ silent: true }), 3000);
    return () => clearInterval(t);
  }, [load]);

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

  const select = (ex) => {
    setSelectedId(ex.execution_id);
    setDetail(null);
    setGuidance('');
    setGuidanceError('');
    loadDetail(ex.execution_id);
  };

  const sendGuidance = async (e) => {
    e.preventDefault();
    if (!guidance.trim()) {
      setGuidanceError('Write the hint Ralph should carry into the next try.');
      return;
    }
    setGuidanceError('');
    setSending(true);
    try {
      await api.post(`/ralph/executions/${selectedId}/guidance`, { guidance: guidance.trim() });
      notify.success('Guidance sent — the run resumes');
      setGuidance('');
      await loadDetail(selectedId);
      load({ silent: true });
    } catch (err) {
      notify.error(humanize(err, { what: 'sending the guidance' }));
    } finally {
      setSending(false);
    }
  };

  const confirmCancel = async () => {
    if (!cancelling) return;
    setCancelBusy(true);
    try {
      await api.delete(`/ralph/executions/${cancelling.execution_id}`);
      notify.success('Run cancelled');
      setExecutions((l) => l.filter((x) => x.execution_id !== cancelling.execution_id));
      if (selectedId === cancelling.execution_id) {
        setSelectedId(null);
        setDetail(null);
      }
      setCancelling(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'cancelling the run' }));
    } finally {
      setCancelBusy(false);
    }
  };

  // ── derived ──
  const stats = useMemo(() => {
    const running = executions.filter((e) => !e.is_complete && !e.is_paused).length;
    const paused = executions.filter((e) => !e.is_complete && e.is_paused).length;
    const done = executions.filter((e) => e.is_complete && ['success', 'completed'].includes(e.status)).length;
    const failed = executions.filter((e) => e.is_complete && !['success', 'completed'].includes(e.status)).length;
    return { running, paused, done, failed };
  }, [executions]);

  const columns = [
    {
      key: 'workflow',
      label: 'Workflow',
      nowrap: false,
      render: (e) => (
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => select(e)}
            aria-current={selectedId === e.execution_id ? 'true' : undefined}
            className={`max-w-[16rem] truncate rounded-chip text-left font-semibold hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              selectedId === e.execution_id ? 'text-accent' : 'text-fg-strong'
            }`}
          >
            {e.workflow_id}
          </button>
          <p className="font-mono text-caption text-muted">{String(e.execution_id).slice(0, 12)}</p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      render: (e) => {
        const s = statusOf(e);
        return (
          <Chip tone={s.tone} dot pulse={s.pulse}>
            {s.label}
          </Chip>
        );
      },
    },
    { key: 'iteration', label: 'Try', render: (e) => <span className="tabular-nums">{e.iteration ?? '—'} of {e.max_iterations ?? '—'}</span> },
    { key: 'progress', label: 'Progress', render: (e) => <Progress value={e.progress_percent} tone={e.is_complete ? statusOf(e).tone : 'accent'} /> },
  ];

  const selected = executions.find((e) => e.execution_id === selectedId) || null;
  const current = detail || selected;
  const status = current ? statusOf(current) : null;
  const tasks = current?.tasks || {};
  const taskTotal = Number(tasks.total) || 0;
  const pct = (n) => (taskTotal ? Math.round((Number(n) / taskTotal) * 100) : 0);

  // ── states ──
  let list;
  if (offline && !executions.length) list = <OfflineState onRetry={load} />;
  else if (loading) list = <LoadingState variant="table" count={4} label="Loading self-correction runs" />;
  else if (error) list = <ErrorState title="Couldn’t load self-correction runs" detail={humanize(error, { what: 'loading the runs' })} onRetry={load} />;
  else if (!executions.length)
    list = (
      <EmptyState
        icon={Zap}
        title="No self-correction runs yet"
        description="One starts when a workflow fails and you choose “Retry with self-correction”. Ralph then reruns it in up to five tries, fixing what broke between each."
        action={
          <Button icon={GitBranch} onClick={() => navigate('/workflows')}>
            Open workflows
          </Button>
        }
      />
    );
  else list = <DataTable columns={columns} rows={executions} rowKey="execution_id" caption="Self-correction runs" dense />;

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Command"
        title="Self-correction"
        description="Ralph reruns a failed workflow in iterations, carrying forward what it learned, until the tasks pass or it runs out of tries."
        actions={
          <Button variant="secondary" icon={RefreshCw} onClick={() => load()}>
            Refresh
          </Button>
        }
      />

      {!loading && !error && executions.length > 0 && (
        <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard icon={Play} label="Running" value={stats.running} />
          <StatCard icon={PauseCircle} label="Needs guidance" value={stats.paused} />
          <StatCard icon={CheckCircle2} label="Succeeded" value={stats.done} />
          <StatCard icon={AlertTriangle} label="Failed" value={stats.failed} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <section aria-label="Runs">{list}</section>

        <section aria-label="Selected run">
          {!current ? (
            executions.length > 0 && (
              <Card>
                <EmptyState compact icon={Zap} title="Pick a run" description="Choose a run on the left to see its tries, its tasks, and to send guidance when it is paused." />
              </Card>
            )
          ) : (
            <Card>
              <CardHeader
                title={current.workflow_id}
                description={<span className="font-mono">{current.execution_id}</span>}
                actions={
                  !current.is_complete && (
                    <Button variant="danger" size="sm" icon={XCircle} onClick={() => setCancelling(current)}>
                      Cancel
                    </Button>
                  )
                }
              />
              {detailError && <p className="mb-3 text-caption text-warn">Showing the last known state: {humanize(detailError, { what: 'refreshing the run' })}</p>}
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <Chip tone={status.tone} dot pulse={status.pulse}>
                  {status.label}
                </Chip>
                <Progress value={current.progress_percent} tone={current.is_complete ? status.tone : 'accent'} />
              </div>

              <p className="mb-2 text-caption font-semibold uppercase tracking-wider text-muted">Tries</p>
              <IterationTimeline iteration={current.iteration} max={current.max_iterations} complete={current.is_complete} status={status} />

              <p className="mb-2 mt-5 text-caption font-semibold uppercase tracking-wider text-muted">Tasks</p>
              {taskTotal === 0 ? (
                <p className="text-body-sm text-muted">No task breakdown has been reported yet.</p>
              ) : (
                <>
                  <div className="mb-3 flex h-2 overflow-hidden rounded-full bg-elevated" aria-hidden="true">
                    <div className="bg-ok-fill" style={{ width: `${pct(tasks.completed)}%` }} />
                    <div className="bg-live" style={{ width: `${pct(tasks.in_progress)}%` }} />
                    <div className="bg-danger-fill" style={{ width: `${pct(tasks.failed)}%` }} />
                  </div>
                  <dl className="grid grid-cols-4 gap-2">
                    {[
                      ['Total', tasks.total, 'idle'],
                      ['Done', tasks.completed, 'done'],
                      ['In progress', tasks.in_progress, 'tool'],
                      ['Failed', tasks.failed, 'error'],
                    ].map(([label, value, dot]) => (
                      <div key={label}>
                        <dt className="flex items-center gap-1.5 text-micro uppercase tracking-wider text-subtle">
                          <StatusDot status={dot} size="xs" /> {label}
                        </dt>
                        <dd className="text-lead font-semibold tabular-nums text-fg-strong">{value ?? 0}</dd>
                      </div>
                    ))}
                  </dl>
                </>
              )}

              {current.is_paused && !current.is_complete && (
                <form onSubmit={sendGuidance} noValidate className="mt-5 rounded-card border border-warn/25 bg-warn/10 p-4">
                  <p className="flex items-center gap-2 text-body font-semibold text-fg-strong">
                    <PauseCircle aria-hidden="true" className="h-4 w-4 text-warn" /> Ralph is waiting for a hint
                  </p>
                  <p className="mb-3 mt-1 text-body-sm text-muted">It paused because it could not fix this on its own. Tell it what it is missing and it resumes with that context.</p>
                  <Field label="Guidance" error={guidanceError}>
                    <Textarea rows={3} value={guidance} onChange={(e) => setGuidance(e.target.value)} placeholder="e.g. The invoices table moved to the billing schema; query billing.invoices." />
                  </Field>
                  <Button type="submit" icon={MessageSquare} loading={sending} className="mt-3">
                    Send guidance and resume
                  </Button>
                </form>
              )}
            </Card>
          )}
        </section>
      </div>

      <Modal
        isOpen={Boolean(cancelling)}
        onClose={() => !cancelBusy && setCancelling(null)}
        tone="danger"
        size="sm"
        title="Cancel this run?"
        description={cancelling ? `Ralph stops retrying “${cancelling.workflow_id}”. Its state files stay on disk.` : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelling(null)} disabled={cancelBusy}>
              Keep running
            </Button>
            <Button variant="danger" icon={XCircle} loading={cancelBusy} onClick={confirmCancel}>
              Cancel run
            </Button>
          </>
        }
      />
    </Page>
  );
}
