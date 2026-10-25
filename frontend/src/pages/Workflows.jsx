/**
 * Workflows — templates to run and the executions they produced.
 *
 * Templates: toolbar → grid/list of cards → all four states (+ filtered-empty).
 * Executions: a DataTable with status chips that carry the failure reason.
 * Running, viewing and retrying all happen in one side panel
 * (WorkflowExecutionPanel), so the page has no execution modal of its own.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GitBranch, Activity, RefreshCw, Play, Eye, XCircle, RotateCcw, Users, PauseCircle, Network, List, DollarSign, CheckCircle2 } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import Breadcrumbs from '../components/Breadcrumbs';
import WorkflowDiagram from '../components/WorkflowDiagram';
import WorkflowGallery from '../components/WorkflowGallery';
import WorkflowFilters from '../components/WorkflowFilters';
import WorkflowExecutionPanel, { ExecStatusChip, normalizeExecution, isActiveState, fmtDuration, fmtCost } from '../components/WorkflowExecutionPanel';
import { counts } from '../components/WorkflowCard';
import { relativeTime, absoluteTime } from '../components/ActivityFeed';
import { Button, IconButton, Chip, DataTable, Modal, Tabs, Tooltip, StatCard, Page, PageHeader, OfflineState, LoadingState } from '../components/ui';

const COMPLEXITY = {
  simple: (c) => c.steps <= 3 && c.checkpoints === 0,
  moderate: (c) => c.steps >= 4 && c.steps <= 5 && c.checkpoints <= 1,
  complex: (c) => c.steps >= 6 || c.checkpoints > 1,
};

function sortTemplates(list, sort) {
  const by = (fn) => [...list].sort(fn);
  switch (sort) {
    case 'name-asc':
      return by((a, b) => (a.name || '').localeCompare(b.name || ''));
    case 'name-desc':
      return by((a, b) => (b.name || '').localeCompare(a.name || ''));
    case 'steps-asc':
      return by((a, b) => counts(a).steps - counts(b).steps);
    case 'steps-desc':
      return by((a, b) => counts(b).steps - counts(a).steps);
    default:
      return list;
  }
}

const shortId = (id) => (id ? `${String(id).slice(0, 8)}…` : '');

export default function Workflows() {
  const [tab, setTab] = useState('templates');
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);
  const [templatesError, setTemplatesError] = useState(null);
  const [executions, setExecutions] = useState([]);
  const [executionsLoading, setExecutionsLoading] = useState(true);
  const [executionsError, setExecutionsError] = useState(null);
  const [health, setHealth] = useState(null); // 'connected' | 'error' | null
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [query, setQuery] = useState('');
  const [tag, setTag] = useState('');
  const [complexity, setComplexity] = useState('');
  const [sort, setSort] = useState('newest');
  const [view, setView] = useState('grid');
  const [detail, setDetail] = useState(null); // template detail in the modal
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailSteps, setDetailSteps] = useState('diagram');
  const [busyId, setBusyId] = useState(null);
  const [panel, setPanel] = useState(null); // { workflow, execution }
  const detailCache = useRef(new Map());

  // ── data ──
  const checkHealth = useCallback(async () => {
    try {
      const data = await apiJson('/hierarchical/health');
      setHealth(data?.status === 'healthy' ? 'connected' : 'error');
    } catch {
      setHealth('error');
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    try {
      const data = await apiJson('/hierarchical/templates');
      setTemplates(data?.workflows || []);
    } catch (err) {
      setTemplatesError(err);
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const loadExecutions = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setExecutionsLoading(true);
    setExecutionsError(null);
    try {
      const data = await apiJson('/hierarchical/executions');
      setExecutions((data?.executions || []).map(normalizeExecution));
    } catch (err) {
      if (!silent) setExecutionsError(err);
    } finally {
      setExecutionsLoading(false);
    }
  }, []);

  const reloadAll = useCallback(() => {
    loadTemplates();
    loadExecutions();
    checkHealth();
  }, [loadTemplates, loadExecutions, checkHealth]);

  useEffect(() => {
    reloadAll();
  }, [reloadAll]);

  // Keep the executions table live while anything is running.
  const anyActive = executions.some((e) => isActiveState(e.state));
  useEffect(() => {
    if (!anyActive) return undefined;
    const t = setInterval(() => loadExecutions({ silent: true }), 5000);
    return () => clearInterval(t);
  }, [anyActive, loadExecutions]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      reloadAll();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [reloadAll]);

  const loadDetail = useCallback(async (id) => {
    if (detailCache.current.has(id)) return detailCache.current.get(id);
    const data = await apiJson(`/hierarchical/templates/${id}`);
    const w = data?.workflow || data;
    if (w) detailCache.current.set(id, w);
    return w;
  }, []);

  // ── derived ──
  const tags = useMemo(() => [...new Set(templates.flatMap((t) => t.tags || []))].sort(), [templates]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = templates.filter((t) => {
      if (tag && !(t.tags || []).includes(tag)) return false;
      if (complexity && !COMPLEXITY[complexity]?.(counts(t))) return false;
      if (!q) return true;
      return (t.name || '').toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q) || (t.tags || []).some((x) => x.toLowerCase().includes(q));
    });
    return sortTemplates(list, sort);
  }, [templates, query, tag, complexity, sort]);
  const hasFilters = Boolean(query || tag || complexity);
  const clearFilters = () => {
    setQuery('');
    setTag('');
    setComplexity('');
  };
  const runningCount = executions.filter((e) => isActiveState(e.state)).length;

  // ── actions ──
  const openDetails = async (template) => {
    setDetailLoading(true);
    setDetail({ ...template });
    try {
      const w = await loadDetail(template.id);
      if (w) setDetail(w);
    } catch (err) {
      notify.error(humanize(err, { what: 'loading the workflow' }));
    } finally {
      setDetailLoading(false);
    }
  };

  const run = async (template) => {
    setBusyId(template.id);
    try {
      const w = (await loadDetail(template.id)) || template;
      setDetail(null);
      setPanel({ workflow: w, execution: null });
    } catch (err) {
      notify.error(humanize(err, { what: 'opening the workflow' }));
    } finally {
      setBusyId(null);
    }
  };

  const viewExecution = async (execution) => {
    try {
      const data = await apiJson(`/hierarchical/executions/${execution.id}`);
      const ex = normalizeExecution(data);
      let workflow = null;
      try {
        workflow = ex.workflowId ? await loadDetail(ex.workflowId) : null;
      } catch {
        workflow = null;
      }
      setPanel({ workflow: workflow || { id: ex.workflowId, name: ex.workflowName || ex.workflowId, tags: [] }, execution: ex });
    } catch (err) {
      notify.error(humanize(err, { what: 'opening the run' }));
    }
  };

  const cancelExecution = async (execution) => {
    try {
      await apiJson(`/hierarchical/executions/${execution.id}/cancel`, { method: 'POST' });
      notify.success('Run cancelled');
      loadExecutions({ silent: true });
    } catch (err) {
      notify.error(humanize(err, { what: 'cancelling the run' }));
    }
  };

  const runAgain = (execution) => {
    const template = templates.find((t) => t.id === execution.workflowId);
    if (template) run(template);
    else notify.error('That workflow template is no longer available.');
  };

  const onExecutionChange = useCallback((ex) => {
    setExecutions((list) => (list.some((e) => e.id === ex.id) ? list.map((e) => (e.id === ex.id ? { ...e, ...ex } : e)) : [ex, ...list]));
  }, []);

  // ── executions table ──
  const columns = [
    {
      key: 'workflow',
      label: 'Workflow',
      nowrap: false,
      render: (e) => (
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => viewExecution(e)}
            className="max-w-[18rem] truncate rounded-chip text-left font-semibold text-fg-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {e.workflowName || e.workflowId}
          </button>
          <p className="font-mono text-caption text-muted">{shortId(e.id)}</p>
        </div>
      ),
    },
    {
      key: 'status',
      label: 'Status',
      nowrap: false,
      render: (e) => (
        <div className="flex min-w-0 flex-col gap-1">
          <ExecStatusChip state={e.state} className="w-fit" />
          {e.state === 'failed' && (
            <Tooltip content={e.error || 'No reason was recorded'}>
              <p className="max-w-[60vw] truncate text-caption text-danger md:max-w-[22rem]">{e.error || 'No reason was recorded'}</p>
            </Tooltip>
          )}
          {e.pendingCheckpoint && <p className="max-w-[60vw] truncate text-caption text-warn md:max-w-[22rem]">{e.pendingCheckpoint.prompt || e.pendingCheckpoint.name}</p>}
        </div>
      ),
    },
    {
      key: 'started',
      label: 'Started',
      render: (e) =>
        e.startedAt ? (
          <Tooltip content={absoluteTime(e.startedAt)}>
            <time dateTime={e.startedAt}>{relativeTime(e.startedAt)}</time>
          </Tooltip>
        ) : (
          <span className="text-muted">—</span>
        ),
    },
    { key: 'duration', label: 'Duration', render: (e) => <span className="tabular-nums">{fmtDuration(e.durationSeconds)}</span> },
    { key: 'cost', label: 'Cost', render: (e) => <span className="tabular-nums">{fmtCost(e.totalCost)}</span> },
    {
      key: 'actions',
      label: 'Actions',
      align: 'right',
      render: (e) => (
        <span className="inline-flex items-center gap-1">
          <IconButton icon={Eye} label="Open run" size="sm" onClick={() => viewExecution(e)} />
          {isActiveState(e.state) && <IconButton icon={XCircle} label="Cancel run" size="sm" onClick={() => cancelExecution(e)} className="text-danger hover:text-danger" />}
          {e.state === 'completed' && <IconButton icon={RotateCcw} label="Run again" size="sm" onClick={() => runAgain(e)} />}
        </span>
      ),
    },
  ];

  const totalCost = executions.reduce((s, e) => s + (Number(e.totalCost) || 0), 0);

  // ── render ──
  const healthChip =
    health === 'connected' ? (
      <Chip tone="ok" dot>
        Engine connected
      </Chip>
    ) : health === 'error' ? (
      <Chip tone="danger" dot>
        Engine unreachable
      </Chip>
    ) : (
      <Chip dot>Checking engine…</Chip>
    );

  let templatesBody;
  if (offline && !templates.length) templatesBody = <OfflineState onRetry={reloadAll} />;
  else
    templatesBody = (
      <>
        <WorkflowFilters
          query={query}
          onQuery={setQuery}
          tag={tag}
          onTag={setTag}
          complexity={complexity}
          onComplexity={setComplexity}
          sort={sort}
          onSort={setSort}
          view={view}
          onView={setView}
          tags={tags}
          resultCount={filtered.length}
          totalCount={templates.length}
          onClear={clearFilters}
        />
        <WorkflowGallery
          workflows={filtered}
          viewMode={view}
          loading={templatesLoading}
          error={templatesError ? humanize(templatesError, { what: 'loading the templates' }) : null}
          onRetry={loadTemplates}
          onViewDetails={openDetails}
          onExecute={run}
          busyId={busyId}
          hasFilters={hasFilters}
          onClearFilters={clearFilters}
        />
      </>
    );

  let executionsBody;
  if (offline && !executions.length) executionsBody = <OfflineState onRetry={reloadAll} />;
  else
    executionsBody = (
      <>
        {!executionsLoading && !executionsError && executions.length > 0 && (
          <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard icon={Activity} label="Runs" value={executions.length} />
            <StatCard icon={CheckCircle2} label="Completed" value={executions.filter((e) => e.state === 'completed').length} />
            <StatCard icon={Play} label="Running now" value={runningCount} />
            <StatCard icon={DollarSign} label="Spent" value={fmtCost(totalCost)} />
          </div>
        )}
        <DataTable
          columns={columns}
          rows={executions}
          rowKey="id"
          caption="Workflow executions"
          loading={executionsLoading}
          error={executionsError && { title: 'Couldn’t load the executions', detail: humanize(executionsError, { what: 'loading the executions' }), onRetry: loadExecutions }}
          empty={{
            icon: Activity,
            title: 'No runs yet',
            description: 'Run a workflow from the Templates tab and it shows up here with its steps, cost and outcome.',
            action: (
              <Button size="sm" icon={GitBranch} onClick={() => setTab('templates')}>
                Browse templates
              </Button>
            ),
          }}
        />
      </>
    );

  const detailInputs = detail?.required_inputs || detail?.requiredInputs || [];
  const detailLeads = detail?.team_leads || detail?.teamLeads || [];

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Command"
        title="Workflows"
        description={
          templatesLoading
            ? 'Three-tier runs: The General plans, team leads delegate, workers execute'
            : `${templates.length} template${templates.length === 1 ? '' : 's'}${runningCount ? ` · ${runningCount} running now` : ''}`
        }
        actions={
          <>
            {healthChip}
            <Button variant="secondary" icon={RefreshCw} onClick={reloadAll}>
              Refresh
            </Button>
          </>
        }
        tabs={
          <Tabs
            value={tab}
            onChange={setTab}
            label="Workflow views"
            idBase="wf-tab"
            tabs={[
              { id: 'templates', label: 'Templates', icon: GitBranch, count: templatesLoading ? undefined : templates.length },
              { id: 'executions', label: 'Executions', icon: Activity, count: executionsLoading ? undefined : executions.length },
            ]}
          />
        }
      />

      <div role="tabpanel" aria-labelledby={`wf-tab-${tab}`}>
        {tab === 'templates' ? templatesBody : executionsBody}
      </div>

      {/* ── template detail ── */}
      <Modal
        isOpen={Boolean(detail)}
        onClose={() => setDetail(null)}
        size="3xl"
        title={detail?.name}
        description={detail?.description}
        footer={
          detail && (
            <>
              <Button variant="ghost" onClick={() => setDetail(null)}>
                Close
              </Button>
              <Button icon={Play} loading={busyId === detail.id} onClick={() => run(detail)}>
                Run workflow
              </Button>
            </>
          )
        }
      >
        {detail && (
          <div className="space-y-6">
            {(detail.tags || []).length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {detail.tags.map((t) => (
                  <Chip key={t}>{t}</Chip>
                ))}
              </div>
            )}
            {detailLoading ? (
              <LoadingState variant="text" count={4} label="Loading the workflow" />
            ) : (
              <>
                <section>
                  <h3 className="mb-2 text-body font-semibold text-fg-strong">Inputs it needs</h3>
                  {detailInputs.length === 0 ? (
                    <p className="text-body-sm text-muted">None.</p>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {detailInputs.map((i) => (
                        <Chip key={i} className="font-mono">
                          {i}
                        </Chip>
                      ))}
                    </div>
                  )}
                </section>
                {detailLeads.length > 0 && (
                  <section>
                    <h3 className="mb-2 text-body font-semibold text-fg-strong">Team leads</h3>
                    <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {detailLeads.map((lead) => (
                        <li key={lead.id} className="flex items-start gap-3 rounded-control border border-border bg-surface/60 p-3">
                          <Users aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-info" />
                          <div className="min-w-0">
                            <p className="truncate text-body font-medium text-fg-strong">{lead.name}</p>
                            <p className="text-caption text-muted">
                              {lead.domain}
                              {lead.workers?.length ? ` · ${lead.workers.length} worker${lead.workers.length === 1 ? '' : 's'}` : ''}
                              {lead.model ? ` · ${lead.model}` : ''}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                <section>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h3 className="text-body font-semibold text-fg-strong">Steps</h3>
                    <Tabs
                      variant="segmented"
                      size="sm"
                      label="Steps view"
                      idBase="wf-steps"
                      value={detailSteps}
                      onChange={setDetailSteps}
                      tabs={[
                        { id: 'diagram', label: 'Diagram', icon: Network },
                        { id: 'list', label: 'List', icon: List },
                      ]}
                    />
                  </div>
                  {detailSteps === 'diagram' ? (
                    <WorkflowDiagram workflow={detail} />
                  ) : (
                    <ol className="space-y-2">
                      {(detail.steps || []).map((step, i) => (
                        <li key={step.id || i} className="flex items-start gap-3 rounded-control border border-border bg-surface/60 p-3">
                          <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/10 text-caption font-semibold text-accent">
                            {i + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-body font-medium text-fg-strong">{step.name}</p>
                              {step.executor && <code className="font-mono text-caption text-muted">{step.executor}</code>}
                            </div>
                            {step.description && <p className="mt-0.5 text-body-sm text-muted">{step.description}</p>}
                            {step.outputs?.length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1">
                                {step.outputs.map((o) => (
                                  <Chip key={o} size="xs">
                                    {o}
                                  </Chip>
                                ))}
                              </div>
                            )}
                          </div>
                        </li>
                      ))}
                      {(detail.steps || []).length === 0 && <p className="text-body-sm text-muted">No steps defined.</p>}
                    </ol>
                  )}
                </section>
                {(detail.checkpoints || []).length > 0 && (
                  <section>
                    <h3 className="mb-2 text-body font-semibold text-fg-strong">Human checkpoints</h3>
                    <ul className="space-y-2">
                      {detail.checkpoints.map((cp) => (
                        <li key={cp.id} className="rounded-control border border-warn/25 bg-warn/10 p-3">
                          <div className="flex flex-wrap items-center gap-2">
                            <PauseCircle aria-hidden="true" className="h-4 w-4 text-warn" />
                            <span className="text-body font-medium text-fg-strong">{cp.name}</span>
                            {cp.type && (
                              <Chip size="xs" tone="warn">
                                {cp.type}
                              </Chip>
                            )}
                          </div>
                          {cp.prompt && <p className="mt-1 text-body-sm text-fg">{cp.prompt}</p>}
                          {cp.options?.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {cp.options.map((o) => (
                                <Chip key={o} size="xs">
                                  {o}
                                </Chip>
                              ))}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )}
          </div>
        )}
      </Modal>

      {/* ── run / watch ── */}
      {panel && (
        <WorkflowExecutionPanel
          workflow={panel.workflow}
          execution={panel.execution}
          onClose={() => setPanel(null)}
          onExecutionChange={onExecutionChange}
          onExecutionComplete={() => loadExecutions({ silent: true })}
        />
      )}
    </Page>
  );
}
