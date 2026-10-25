import { useCallback, useEffect, useState } from 'react';
import { Code2, Play, RefreshCw, Square, Terminal, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import McpServerIcon from '../utils/mcpIcons';
import { RoleGate } from './auth';
import { Button, Chip, EmptyState, ErrorState, Field, LoadingState, Sheet, Textarea } from './ui';

/**
 * MCPServerControlPanel — a side Sheet to run one server: start / stop /
 * restart, the registry facts the list endpoint does not carry (command,
 * args, env vars) fetched from the detail endpoint on open, and a tool tester.
 *
 *   <MCPServerControlPanel server={s} onClose={…} onServerUpdated={(detail) => …} />
 */
export default function MCPServerControlPanel({ server, onClose, onServerUpdated }) {
  const name = server?.name;
  const [detail, setDetail] = useState({ state: 'loading', data: server, error: null });
  const [action, setAction] = useState(null); // start | stop | restart
  const [actionError, setActionError] = useState(null);
  const [testing, setTesting] = useState(null);
  const [args, setArgs] = useState('{}');
  const [argsError, setArgsError] = useState(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const load = useCallback(async () => {
    setDetail((d) => ({ ...d, state: 'loading', error: null }));
    try {
      const data = await apiJson(`/mcp/registry/servers/${encodeURIComponent(name)}`);
      setDetail({ state: 'ready', data: { ...server, ...data }, error: null });
      onServerUpdated?.(data);
    } catch (err) {
      setDetail({ state: 'error', data: server, error: err });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  useEffect(() => {
    load();
  }, [load]);

  const d = detail.data || server || {};
  const title = d.display_name || d.name || 'Server';
  const isRunning = Boolean(d.running);
  const caps = Array.isArray(d.capabilities) ? d.capabilities : [];
  const env = Array.isArray(d.env_vars) ? d.env_vars : [];

  const run = async (what) => {
    setAction(what);
    setActionError(null);
    try {
      await apiJson(`/mcp/registry/servers/${encodeURIComponent(name)}/${what}`, { method: 'POST' });
      notify.success(`${title} ${what === 'start' ? 'started' : what === 'stop' ? 'stopped' : 'restarted'}`);
      await load();
    } catch (err) {
      const msg = humanize(err, { what: `${what}ing ${title}` });
      setActionError(msg);
      notify.error(msg);
    } finally {
      setAction(null);
    }
  };

  const execute = async () => {
    let parsed;
    try {
      parsed = args.trim() ? JSON.parse(args) : {};
      setArgsError(null);
    } catch {
      setArgsError('Arguments must be valid JSON, e.g. {"query": "status"}.');
      return;
    }
    setRunning(true);
    setResult(null);
    try {
      const data = await apiJson('/mcp/registry/tools/call', {
        method: 'POST',
        body: JSON.stringify({ server_name: name, tool_name: testing, arguments: parsed }),
      });
      setResult({ ok: true, data });
      notify.success(`${testing} ran`);
    } catch (err) {
      setResult({ ok: false, message: humanize(err, { what: `running ${testing}` }) });
    } finally {
      setRunning(false);
    }
  };

  return (
    <Sheet isOpen onClose={onClose} side="right" title={title}>
      <div className="space-y-6 pb-4">
        <div className="flex items-start gap-3">
          <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-elevated text-accent">
            <McpServerIcon name={d.name} className="h-5 w-5" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <Chip tone={isRunning ? 'ok' : 'neutral'} size="xs" dot pulse={isRunning}>
                {isRunning ? 'Running' : 'Stopped'}
              </Chip>
              {d.transport && (
                <Chip size="xs" tone="info" uppercase>
                  {d.transport}
                </Chip>
              )}
              {d.enabled === false && (
                <Chip size="xs" tone="warn">
                  Disabled in registry
                </Chip>
              )}
            </div>
            {d.description && <p className="mt-1.5 text-body-sm text-muted">{d.description}</p>}
          </div>
        </div>

        <RoleGate role="admin" showUpgradePrompt={false}>
          <section>
            <h3 className="mb-2 text-body-sm font-semibold uppercase tracking-wider text-muted">Controls</h3>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" icon={Play} loading={action === 'start'} disabled={isRunning || Boolean(action)} onClick={() => run('start')}>
                Start
              </Button>
              <Button size="sm" variant="secondary" icon={Square} loading={action === 'stop'} disabled={!isRunning || Boolean(action)} onClick={() => run('stop')}>
                Stop
              </Button>
              <Button size="sm" variant="secondary" icon={RefreshCw} loading={action === 'restart'} disabled={Boolean(action)} onClick={() => run('restart')}>
                Restart
              </Button>
            </div>
            {actionError && (
              <p role="alert" className="mt-2 text-caption text-danger">
                {actionError}
              </p>
            )}
          </section>
        </RoleGate>

        <section>
          <h3 className="mb-2 text-body-sm font-semibold uppercase tracking-wider text-muted">Registry entry</h3>
          {detail.state === 'loading' ? (
            <LoadingState variant="text" count={4} label="Loading server details" />
          ) : detail.state === 'error' ? (
            <ErrorState compact title="Couldn’t load the details" detail={humanize(detail.error, { what: 'loading the server' })} onRetry={load} />
          ) : (
            <dl className="space-y-2 text-body-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-muted">Id</dt>
                <dd className="font-mono text-fg">{d.name}</dd>
              </div>
              {d.command && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Command</dt>
                  <dd className="min-w-0 truncate text-right font-mono text-fg">
                    {d.command} {Array.isArray(d.args) ? d.args.join(' ') : ''}
                  </dd>
                </div>
              )}
              {d.config_file && (
                <div className="flex justify-between gap-4">
                  <dt className="text-muted">Config</dt>
                  <dd className="min-w-0 truncate text-right font-mono text-fg">{d.config_file}</dd>
                </div>
              )}
              <div>
                <dt className="text-muted">Environment</dt>
                <dd className="mt-1">
                  {env.length ? (
                    <>
                      <ul className="flex flex-wrap gap-1" aria-label="Required environment variables">
                        {env.map((v) => (
                          <li key={v}>
                            <Chip size="xs" tone="warn" className="font-mono">
                              {v}
                            </Chip>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-1 text-caption text-muted">Set these on the API host before starting the server.</p>
                    </>
                  ) : (
                    <span className="text-fg">Nothing required</span>
                  )}
                </dd>
              </div>
            </dl>
          )}
        </section>

        <section>
          <h3 className="mb-2 text-body-sm font-semibold uppercase tracking-wider text-muted">
            Declared tools <span className="font-normal normal-case tracking-normal text-subtle">· {caps.length}</span>
          </h3>
          {caps.length ? (
            <ul className="space-y-1.5" aria-label="Declared tools">
              {caps.map((tool) => (
                <li key={tool} className="flex items-center gap-2 rounded-control border border-border bg-surface/60 px-3 py-2">
                  <Code2 aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
                  <span className="min-w-0 flex-1 truncate font-mono text-body-sm text-fg">{tool}</span>
                  {/* Calling a tool hits the admin-only tools/call route. */}
                  <RoleGate role="admin" showUpgradePrompt={false}>
                    <Button
                      size="xs"
                      variant="ghost"
                      icon={Terminal}
                      disabled={!isRunning}
                      aria-label={`Test ${tool}`}
                      onClick={() => {
                        setTesting(tool);
                        setArgs('{}');
                        setResult(null);
                        setArgsError(null);
                      }}
                    >
                      Test
                    </Button>
                  </RoleGate>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState compact icon={Code2} title="No tools declared" description="Start the server to discover its tools at runtime." />
          )}
          {!isRunning && caps.length > 0 && <p className="mt-1.5 text-caption text-muted">Start the server to test a tool.</p>}
        </section>

        {testing && (
          <section className="rounded-card border border-border bg-surface/60 p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="min-w-0 truncate text-body font-semibold text-fg-strong">
                Test <span className="font-mono">{testing}</span>
              </h3>
              <Button size="xs" variant="ghost" icon={X} onClick={() => setTesting(null)} aria-label="Close tool test">
                Close
              </Button>
            </div>
            <Field label="Arguments (JSON)" error={argsError}>
              <Textarea rows={4} value={args} onChange={(e) => setArgs(e.target.value)} className="font-mono text-body-sm" placeholder='{"param": "value"}' />
            </Field>
            <Button size="sm" icon={Terminal} loading={running} onClick={execute} className="mt-3">
              Run tool
            </Button>
            {result && (
              <div className={`mt-3 rounded-control border p-3 ${result.ok ? 'border-ok/30 bg-ok/10' : 'border-danger/30 bg-danger/10'}`} role="status">
                <p className={`mb-1 text-caption font-semibold ${result.ok ? 'text-ok' : 'text-danger'}`}>{result.ok ? 'Result' : 'Failed'}</p>
                <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-caption text-fg">{result.ok ? JSON.stringify(result.data, null, 2) : result.message}</pre>
              </div>
            )}
          </section>
        )}
      </div>
    </Sheet>
  );
}
