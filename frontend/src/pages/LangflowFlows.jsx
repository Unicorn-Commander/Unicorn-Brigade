/**
 * Langflow flows — visual flows built in Langflow, run from Brigade.
 * Only reachable when the deployment enables Langflow (the nav hides it
 * otherwise). Frame → toolbar → the four states → cards → run/delete dialogs.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, Plus, Play, Download, Upload, Trash2, ExternalLink, RefreshCw, Workflow, Copy, MoreHorizontal, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import Breadcrumbs from '../components/Breadcrumbs';
import { relativeTime, absoluteTime } from '../components/ActivityFeed';
import { Button, IconButton, Card, Chip, Input, Field, Textarea, Modal, Menu, Tooltip, Page, PageHeader, EmptyState, ErrorState, OfflineState, LoadingState } from '../components/ui';

const LANGFLOW_URL = (import.meta.env.VITE_LANGFLOW_URL || 'http://localhost:7860').replace(/\/$/, '');

export default function LangflowFlows() {
  const [flows, setFlows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [health, setHealth] = useState(null); // { ok, detail }
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [runInput, setRunInput] = useState('');
  const [runOutput, setRunOutput] = useState(null);
  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const fileRef = useRef(null);

  const checkHealth = useCallback(async () => {
    try {
      const data = await apiJson('/langflow/health');
      setHealth({ ok: data?.status === 'healthy', detail: data?.detail || data?.message || (data?.enabled === false ? 'Langflow is turned off for this deployment.' : null) });
    } catch (err) {
      setHealth({ ok: false, detail: humanize(err, { what: 'reaching Langflow' }) });
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson('/langflow/flows');
      setFlows(Array.isArray(data?.flows) ? data.flows : []);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    load();
  }, [checkHealth, load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      checkHealth();
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [checkHealth, load]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? flows.filter((f) => (f?.name || '').toLowerCase().includes(q) || (f?.description || '').toLowerCase().includes(q)) : flows;
  }, [flows, query]);

  const openFlow = async (flow) => {
    try {
      const data = await apiJson(`/langflow/flows/${flow.id}`);
      setSelected(data || flow);
      setRunInput('');
      setRunOutput(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'opening the flow' }));
    }
  };

  const runFlow = async (e) => {
    e.preventDefault();
    if (!selected) return;
    setRunning(true);
    setRunOutput(null);
    try {
      const data = await apiJson(`/langflow/flows/${selected.id}/run`, { method: 'POST', body: JSON.stringify({ inputs: { input_value: runInput } }) });
      setRunOutput({ data });
      notify.success('Flow ran');
    } catch (err) {
      setRunOutput({ error: humanize(err, { what: 'running the flow' }) });
    } finally {
      setRunning(false);
    }
  };

  const exportFlow = async (flow) => {
    setExporting(flow.id);
    try {
      const data = await apiJson(`/langflow/flows/${flow.id}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${flow.name || 'flow'}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      notify.success(`Exported ${flow.name || 'flow'}.json`);
    } catch (err) {
      notify.error(humanize(err, { what: 'exporting the flow' }));
    } finally {
      setExporting(null);
    }
  };

  const importFlow = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const flowData = JSON.parse(await file.text());
      await apiJson('/langflow/flows/import', { method: 'POST', body: JSON.stringify(flowData) });
      notify.success(`Imported ${file.name}`);
      load();
    } catch (err) {
      notify.error(err instanceof SyntaxError ? `${file.name} isn’t valid JSON.` : humanize(err, { what: 'importing the flow' }));
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await apiJson(`/langflow/flows/${deleting.id}`, { method: 'DELETE' });
      notify.success(`Deleted ${deleting.name || 'the flow'}`);
      setFlows((l) => l.filter((f) => f.id !== deleting.id));
      if (selected?.id === deleting.id) setSelected(null);
      setDeleting(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'deleting the flow' }));
    } finally {
      setDeleteBusy(false);
    }
  };

  const copyId = async (id) => {
    try {
      await navigator.clipboard.writeText(id);
      notify.success('Flow id copied');
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };

  const healthChip = !health ? (
    <Chip dot>Checking Langflow…</Chip>
  ) : health.ok ? (
    <Chip tone="ok" dot>
      Langflow connected
    </Chip>
  ) : (
    <Tooltip content={health.detail || 'Langflow did not answer its health check'}>
      <Chip tone="danger" dot>
        Langflow unreachable
      </Chip>
    </Tooltip>
  );

  let body;
  if (offline && !flows.length) body = <OfflineState onRetry={load} />;
  else if (loading) body = <LoadingState variant="cards" count={6} label="Loading flows" />;
  else if (error)
    body = <ErrorState title="Couldn’t load the flows" detail={health && !health.ok && health.detail ? health.detail : humanize(error, { what: 'loading the flows' })} onRetry={() => { checkHealth(); load(); }} />;
  else if (health && !health.ok && !flows.length)
    body = (
      <ErrorState
        title="Langflow isn’t reachable"
        detail={health.detail || 'Brigade could not reach the Langflow service, so there are no flows to show. Start Langflow, or check its URL in the deployment settings.'}
        onRetry={() => {
          checkHealth();
          load();
        }}
      />
    );
  else if (!flows.length)
    body = (
      <EmptyState
        icon={Workflow}
        title="No flows yet"
        description="Build a flow in Langflow and it appears here to run, or import one from a JSON export."
        action={
          <Button as="a" href={LANGFLOW_URL} target="_blank" rel="noopener noreferrer" icon={Plus} iconRight={ExternalLink}>
            Create in Langflow
          </Button>
        }
        secondary={
          <Button variant="secondary" icon={Upload} onClick={() => fileRef.current?.click()}>
            Import a flow
          </Button>
        }
      />
    );
  else if (!filtered.length)
    body = <EmptyState compact icon={Search} title="No flows match" description="Try another word." action={<Button variant="secondary" size="sm" icon={X} onClick={() => setQuery('')}>Clear search</Button>} />;
  else
    body = (
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Flows">
        {filtered.map((flow) => {
          const name = flow.name || 'Untitled flow';
          const when = flow.updated_at || flow.created_at;
          return (
            <li key={flow.id}>
              <Card className="flex h-full flex-col">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
                      <Workflow className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <button type="button" onClick={() => openFlow(flow)} className="block max-w-full truncate rounded-chip text-left text-body font-semibold text-fg-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                        {name}
                      </button>
                      {when && (
                        <Tooltip content={absoluteTime(when)}>
                          <p className="truncate text-caption text-muted">Updated {relativeTime(when)}</p>
                        </Tooltip>
                      )}
                    </div>
                  </div>
                  <Menu
                    align="end"
                    trigger={({ props }) => <IconButton icon={MoreHorizontal} label={`Actions for ${name}`} size="sm" {...props} />}
                    items={[
                      { id: 'run', label: 'Run', icon: Play, onSelect: () => openFlow(flow) },
                      { id: 'export', label: 'Export JSON', icon: Download, onSelect: () => exportFlow(flow) },
                      { id: 'edit', label: 'Edit in Langflow', icon: ExternalLink, onSelect: () => window.open(`${LANGFLOW_URL}/flow/${flow.id}`, '_blank', 'noopener') },
                      { type: 'separator' },
                      { id: 'delete', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: () => setDeleting(flow) },
                    ]}
                  />
                </div>
                <p className="mb-4 line-clamp-2 flex-1 text-body-sm text-muted">{flow.description || 'No description yet.'}</p>
                <div className="flex items-center gap-2">
                  <Button size="sm" icon={Play} onClick={() => openFlow(flow)} className="flex-1">
                    Run
                  </Button>
                  <Button variant="secondary" size="sm" icon={Download} loading={exporting === flow.id} onClick={() => exportFlow(flow)}>
                    Export
                  </Button>
                </div>
              </Card>
            </li>
          );
        })}
      </ul>
    );

  return (
    <Page>
      <input ref={fileRef} type="file" accept=".json,application/json" onChange={importFlow} className="sr-only" aria-label="Import a flow JSON file" tabIndex={-1} />
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Builders"
        title="Langflow flows"
        description={loading ? 'Visual flows built in Langflow, run from here' : `${filtered.length === flows.length ? flows.length : `${filtered.length} of ${flows.length}`} flow${flows.length === 1 ? '' : 's'}`}
        actions={
          <>
            {healthChip}
            <Button variant="secondary" icon={RefreshCw} onClick={() => { checkHealth(); load(); }}>
              Refresh
            </Button>
            <Button variant="secondary" icon={Upload} onClick={() => fileRef.current?.click()}>
              Import
            </Button>
            <Button as="a" href={LANGFLOW_URL} target="_blank" rel="noopener noreferrer" icon={ExternalLink}>
              Open Langflow
            </Button>
          </>
        }
      />

      <Card padding="sm" className="mb-5">
        <div className="relative">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input type="search" aria-label="Search flows" placeholder="Search flows…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9" />
        </div>
      </Card>

      {body}

      {/* ── run ── */}
      <Modal
        isOpen={Boolean(selected)}
        onClose={() => !running && setSelected(null)}
        size="xl"
        title={selected?.name || 'Untitled flow'}
        description={selected?.description || 'Run this flow with an input of your choice.'}
        footer={
          selected && (
            <>
              <Button variant="ghost" icon={Download} loading={exporting === selected.id} onClick={() => exportFlow(selected)}>
                Export
              </Button>
              <Button as="a" variant="secondary" href={`${LANGFLOW_URL}/flow/${selected.id}`} target="_blank" rel="noopener noreferrer" icon={ExternalLink}>
                Edit in Langflow
              </Button>
              <Button type="submit" form="langflow-run" icon={Play} loading={running}>
                Run flow
              </Button>
            </>
          )
        }
      >
        {selected && (
          <form id="langflow-run" onSubmit={runFlow} className="space-y-4">
            <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <dt className="text-caption text-muted">Flow id</dt>
                <dd className="mt-1 flex items-center gap-1">
                  <code className="min-w-0 flex-1 truncate rounded-chip bg-elevated px-2 py-1 font-mono text-caption text-fg">{selected.id}</code>
                  <IconButton icon={Copy} label="Copy flow id" size="sm" onClick={() => copyId(selected.id)} />
                </dd>
              </div>
              <div>
                <dt className="text-caption text-muted">Last updated</dt>
                <dd className="mt-1 text-body-sm text-fg">{absoluteTime(selected.updated_at || selected.created_at) || 'Unknown'}</dd>
              </div>
            </dl>
            <Field label="Input" help="Sent to the flow as input_value.">
              <Textarea rows={4} value={runInput} onChange={(e) => setRunInput(e.target.value)} placeholder="Your message or input for the flow…" />
            </Field>
            {runOutput && (
              <div>
                <p className="mb-1.5 text-caption text-muted">Output</p>
                {runOutput.error ? (
                  <ErrorState compact title="The flow didn’t finish" detail={runOutput.error} />
                ) : (
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-control border border-border bg-surface p-3 font-mono text-caption text-fg">
                    {typeof runOutput.data === 'string' ? runOutput.data : JSON.stringify(runOutput.data, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </form>
        )}
      </Modal>

      {/* ── delete ── */}
      <Modal
        isOpen={Boolean(deleting)}
        onClose={() => !deleteBusy && setDeleting(null)}
        tone="danger"
        size="sm"
        title="Delete this flow?"
        description={deleting ? `“${deleting.name || 'This flow'}” is removed from Langflow. This can’t be undone.` : ''}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)} disabled={deleteBusy}>
              Keep it
            </Button>
            <Button variant="danger" icon={Trash2} loading={deleteBusy} onClick={confirmDelete}>
              Delete
            </Button>
          </>
        }
      />
    </Page>
  );
}
