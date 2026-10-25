/**
 * WorkflowExecutionPanel — run a workflow, or watch one that is already running.
 *
 * A right-hand Sheet on desktop, full-screen on phones. Three live states:
 *   running  → StatusDot pulse, "step 2 of 5", a live step list
 *   done     → outputs, cost, tokens
 *   failed   → the reason in human words + "Retry with self-correction"
 *
 * Also exports the shared execution-status vocabulary (EXEC_STATUS,
 * ExecStatusChip) and the normalisers the Workflows page uses, so a "failed"
 * is the same red with the same reason on the card, in the table and here.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Play, StopCircle, ChevronDown, ChevronRight, Zap, RefreshCw, Terminal, PauseCircle } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import api from '../services/api';
import { Button, Chip, Field, Textarea, Sheet, StatusDot, Toggle, Tooltip, Spinner } from './ui';

// ── vocabulary ──────────────────────────────────────────────────────────────
export const EXEC_STATUS = {
  pending: { tone: 'neutral', label: 'Queued', dot: 'idle' },
  queued: { tone: 'neutral', label: 'Queued', dot: 'idle' },
  running: { tone: 'live', label: 'Running', dot: 'tool', pulse: true, active: true },
  delegating: { tone: 'live', label: 'Delegating', dot: 'tool', pulse: true, active: true },
  waiting_workers: { tone: 'live', label: 'Waiting on workers', dot: 'tool', pulse: true, active: true },
  aggregating: { tone: 'live', label: 'Aggregating', dot: 'tool', pulse: true, active: true },
  waiting: { tone: 'warn', label: 'Needs you', dot: 'thinking', pulse: true, active: true },
  waiting_checkpoint: { tone: 'warn', label: 'Needs you', dot: 'thinking', pulse: true, active: true },
  paused: { tone: 'warn', label: 'Paused', dot: 'thinking', active: true },
  completed: { tone: 'ok', label: 'Completed', dot: 'done' },
  success: { tone: 'ok', label: 'Completed', dot: 'done' },
  failed: { tone: 'danger', label: 'Failed', dot: 'error' },
  error: { tone: 'danger', label: 'Failed', dot: 'error' },
  cancelled: { tone: 'neutral', label: 'Cancelled', dot: 'offline' },
  skipped: { tone: 'neutral', label: 'Skipped', dot: 'offline' },
};
export const execStatus = (state) => EXEC_STATUS[state] || EXEC_STATUS.pending;
export const isActiveState = (state) => Boolean(execStatus(state).active);
const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

export function ExecStatusChip({ state, size = 'sm', className = '' }) {
  const s = execStatus(state);
  return (
    <Chip tone={s.tone} dot pulse={s.pulse} size={size} className={className}>
      {s.label}
    </Chip>
  );
}

// ── normalisers (the API answers in camelCase, older callers used snake) ────
export const normalizeExecution = (raw) => {
  const exec = raw?.execution || raw?.data?.execution || raw || {};
  const started = exec.startedAt || exec.started_at;
  const completed = exec.completedAt || exec.completed_at;
  const duration = exec.durationSeconds ?? exec.duration_seconds ?? toSeconds(started, completed);
  return {
    id: exec.id || exec.execution_id || exec.executionId,
    workflowId: exec.workflowId || exec.workflow_id,
    workflowName: exec.workflowName || exec.workflow_name,
    state: exec.state || exec.status,
    startedAt: started,
    completedAt: completed,
    durationSeconds: duration,
    outputs: exec.outputs || exec.result,
    totalCost: exec.totalCost ?? exec.total_cost,
    totalTokens: exec.totalTokens ?? exec.total_tokens,
    stepExecutions: exec.stepExecutions || exec.step_executions || exec.step_results || {},
    error: exec.error,
    modelConfigUsed: exec.modelConfigUsed || exec.model_config_used,
    pendingCheckpoint: exec.pendingCheckpoint || exec.pending_checkpoint,
    checkpointResponses: exec.checkpointResponses || exec.checkpoint_responses,
    currentStep: exec.currentStep || exec.current_step,
    raw: exec,
  };
};

const normalizeStep = (value, key) => ({
  stepId: value?.stepId || value?.step_id || key,
  state: value?.state || value?.status,
  startedAt: value?.startedAt || value?.started_at,
  completedAt: value?.completedAt || value?.completed_at,
  executorId: value?.executorId || value?.executor_id,
  modelUsed: value?.modelUsed || value?.model_used,
  outputs: value?.outputs,
  workerCalls: value?.workerCalls ?? value?.worker_calls,
  error: value?.error,
  retries: value?.retries,
  tokensUsed: value?.tokensUsed ?? value?.tokens_used,
  estimatedCost: value?.estimatedCost ?? value?.estimated_cost,
});

export const normalizeStepExecutions = (stepExecutions) =>
  Array.isArray(stepExecutions)
    ? stepExecutions.map((s, i) => normalizeStep(s, `step-${i + 1}`))
    : Object.entries(stepExecutions || {}).map(([key, value]) => normalizeStep(value, key));

export function toSeconds(start, end) {
  if (!start || !end) return null;
  const a = new Date(start);
  const b = new Date(end);
  if (Number.isNaN(a.valueOf()) || Number.isNaN(b.valueOf())) return null;
  return (b - a) / 1000;
}

export function fmtDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m < 60) return `${m}m ${s}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

export function fmtCost(cost) {
  if (cost == null) return '—';
  if (cost === 0) return 'Free';
  return `$${Number(cost).toFixed(4)}`;
}

export function fmtTokens(n) {
  return n == null ? '—' : Number(n).toLocaleString();
}

const requiredInputsOf = (workflow) => workflow?.required_inputs || workflow?.requiredInputs || [];
const stepDefsOf = (workflow) => workflow?.steps || workflow?.workflowSteps || [];
const humanKey = (k) => String(k).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const Pre = ({ children }) => (
  <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-control border border-border bg-surface p-3 font-mono text-caption text-fg">
    {typeof children === 'string' ? children : JSON.stringify(children, null, 2)}
  </pre>
);

// ── one step row ────────────────────────────────────────────────────────────
function StepRow({ index, step, expanded, onToggle }) {
  const s = execStatus(step.status);
  const meta = Object.entries(step.metadata || {}).filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== 0);
  return (
    <li className={`rounded-card border ${step.status === 'failed' ? 'border-danger/30' : 'border-border'} bg-card`}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 rounded-card px-3 py-2.5 text-left transition-colors duration-fast hover:bg-elevated/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <StatusDot status={s.dot} size="md" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-body font-medium text-fg-strong">
            {index + 1}. {step.name}
          </span>
          <span className="block truncate text-caption text-muted">
            {s.label}
            {step.assignedTo ? (
              <>
                {' · '}
                <code className="font-mono">{step.assignedTo}</code>
              </>
            ) : null}
            {step.duration != null ? ` · ${fmtDuration(step.duration)}` : ''}
          </span>
        </span>
        {expanded ? <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" /> : <ChevronRight aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />}
      </button>
      {step.error && !expanded && <p className="px-3 pb-2.5 text-caption text-danger">{step.error}</p>}
      {expanded && (
        <div className="space-y-3 border-t border-border px-3 py-3">
          {step.error && (
            <div className="rounded-control border border-danger/25 bg-danger/10 p-3">
              <p className="text-caption font-medium text-danger">What went wrong</p>
              <p className="mt-1 text-body-sm text-fg">{step.error}</p>
            </div>
          )}
          {step.result && Object.keys(step.result).length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1.5 text-caption text-muted">
                <Terminal aria-hidden="true" className="h-3.5 w-3.5" /> Result
              </p>
              <Pre>{step.result}</Pre>
            </div>
          )}
          {meta.length > 0 && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-caption">
              {meta.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-muted">{humanKey(k)}</dt>
                  <dd className="truncate font-mono text-fg">{String(v)}</dd>
                </div>
              ))}
            </dl>
          )}
          {!step.error && !(step.result && Object.keys(step.result).length) && meta.length === 0 && (
            <p className="text-caption text-muted">Nothing recorded for this step yet.</p>
          )}
        </div>
      )}
    </li>
  );
}

// ── the panel ───────────────────────────────────────────────────────────────
export default function WorkflowExecutionPanel({ workflow, execution: initialExecution = null, onClose, onExecutionComplete, onExecutionChange }) {
  const [inputs, setInputs] = useState({});
  const [inputErrors, setInputErrors] = useState({});
  const [execution, setExecution] = useState(() => (initialExecution ? normalizeExecution(initialExecution) : null));
  const [executionSource, setExecutionSource] = useState('hierarchical');
  const [loading, setLoading] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState(new Set());
  const [follow, setFollow] = useState(true);
  const [ralphProgress, setRalphProgress] = useState(null);
  const [ralphResult, setRalphResult] = useState(null);
  const [discoveryStartedAt, setDiscoveryStartedAt] = useState(null);
  const [pollError, setPollError] = useState(null);
  const listRef = useRef(null);
  const firstInputRef = useRef(null);

  // Reset when the workflow changes (a new run) or a different execution is opened.
  useEffect(() => {
    const initial = {};
    requiredInputsOf(workflow).forEach((k) => {
      initial[k] = '';
    });
    const ex = initialExecution ? normalizeExecution(initialExecution) : null;
    setInputs(ex?.raw?.inputs || initial);
    setInputErrors({});
    setExecution(ex);
    setExecutionSource('hierarchical');
    setRalphProgress(null);
    setRalphResult(null);
    setExpandedSteps(new Set());
    setDiscoveryStartedAt(null);
    setPollError(null);
  }, [workflow?.id, initialExecution?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (follow && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [execution, ralphProgress, follow]);

  // Poll a hierarchical execution until it settles.
  useEffect(() => {
    if (!execution?.id || executionSource !== 'hierarchical' || TERMINAL.has(execution.state)) return undefined;
    const interval = setInterval(async () => {
      try {
        const updated = normalizeExecution(await api.getWorkflowExecutionDetails(execution.id));
        setPollError(null);
        setExecution(updated);
        onExecutionChange?.(updated);
        if (TERMINAL.has(updated.state)) {
          clearInterval(interval);
          if (updated.state === 'completed') {
            notify.success(`${updated.workflowName || 'Workflow'} completed`);
            onExecutionComplete?.(updated);
          } else if (updated.state === 'failed') {
            notify.error(`${updated.workflowName || 'Workflow'} failed: ${updated.error || 'no reason was recorded'}`);
          }
        }
      } catch (err) {
        setPollError(err);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [execution?.id, execution?.state, executionSource, onExecutionComplete, onExecutionChange]);

  // When the API started the run asynchronously without returning its id, find it.
  useEffect(() => {
    if (!discoveryStartedAt || execution?.id || executionSource !== 'hierarchical') return undefined;
    const interval = setInterval(async () => {
      try {
        const list = await api.getWorkflowExecutions();
        const all = (list?.executions || list?.execution || (Array.isArray(list) ? list : []) || []).map(normalizeExecution);
        const newest = all
          .filter((ex) => ex.workflowId === workflow.id || ex.workflowName === workflow.name)
          .filter((ex) => !ex.startedAt || new Date(ex.startedAt).valueOf() >= discoveryStartedAt)
          .sort((a, b) => (b.startedAt ? Date.parse(b.startedAt) : 0) - (a.startedAt ? Date.parse(a.startedAt) : 0))[0];
        if (newest) {
          setExecution(newest);
          onExecutionChange?.(newest);
          setDiscoveryStartedAt(null);
        }
      } catch (err) {
        setPollError(err);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [discoveryStartedAt, execution?.id, executionSource, workflow?.id, workflow?.name, onExecutionChange]);

  // Poll a self-correction (Ralph) run.
  useEffect(() => {
    if (!execution?.id || executionSource !== 'ralph') return undefined;
    const interval = setInterval(async () => {
      try {
        const progress = await api.getRalphProgress(execution.id);
        setRalphProgress(progress);
        if (progress?.is_complete) {
          clearInterval(interval);
          const result = await api.getRalphResult(execution.id);
          setRalphResult(result);
          setExecution((prev) => ({ ...prev, state: result?.outcome === 'success' ? 'completed' : 'failed', error: result?.error || prev?.error }));
          if (result?.outcome === 'success') notify.success('Self-correction completed');
          else notify.error(`Self-correction ended: ${result?.outcome || 'failed'}`);
        }
      } catch (err) {
        setPollError(err);
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [execution?.id, executionSource]);

  const handleExecute = async (e) => {
    e.preventDefault();
    const required = requiredInputsOf(workflow);
    const errs = {};
    required.forEach((k) => {
      if (!inputs[k] || !String(inputs[k]).trim()) errs[k] = `${humanKey(k)} is needed before the run can start.`;
    });
    setInputErrors(errs);
    if (Object.keys(errs).length) return;

    setLoading(true);
    setExecution({ id: null, workflowId: workflow.id, workflowName: workflow.name, state: 'running', stepExecutions: {} });
    setDiscoveryStartedAt(Date.now());
    try {
      const result = normalizeExecution(await api.executeWorkflow(workflow.id, inputs, null, true));
      if (result.id && result.id !== 'pending') {
        setExecution(result);
        onExecutionChange?.(result);
      } else {
        setExecution((prev) => ({ ...prev, state: prev?.state || 'queued' }));
      }
      notify.success(`${workflow.name} started`);
    } catch (err) {
      notify.error(humanize(err, { what: 'starting the workflow' }));
      setExecution(null);
      setDiscoveryStartedAt(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!execution?.id) return;
    setCancelling(true);
    try {
      if (executionSource === 'ralph') await api.cancelRalphExecution(execution.id);
      else await api.cancelWorkflowExecution(execution.id);
      notify.success('Workflow cancelled');
      setExecution((prev) => {
        const next = { ...prev, state: 'cancelled' };
        onExecutionChange?.(next);
        return next;
      });
    } catch (err) {
      notify.error(humanize(err, { what: 'cancelling the workflow' }));
    } finally {
      setCancelling(false);
    }
  };

  const handleRetryWithRalph = async () => {
    setLoading(true);
    try {
      const result = await api.executeRalphWorkflow(workflow.id, inputs, {
        async_execution: true,
        max_iterations: 5,
        retry_failed_execution: execution?.id,
      });
      setExecution({ id: result.execution_id, workflowId: result.workflow_id, workflowName: workflow.name, state: result.status || 'running', stepExecutions: {} });
      setExecutionSource('ralph');
      setRalphProgress(null);
      setRalphResult(null);
      notify.success('Retrying with self-correction');
    } catch (err) {
      notify.error(humanize(err, { what: 'retrying the workflow' }));
    } finally {
      setLoading(false);
    }
  };

  const toggleStep = (stepId) =>
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) next.delete(stepId);
      else next.add(stepId);
      return next;
    });

  const stepDefinitions = stepDefsOf(workflow);
  const stepExecutionList = useMemo(() => normalizeStepExecutions(execution?.stepExecutions || {}), [execution?.stepExecutions]);

  const steps = useMemo(() => {
    const resolved = [];
    const used = new Set();
    const fromExec = (m) => ({
      status: m?.state || 'pending',
      duration: toSeconds(m?.startedAt, m?.completedAt),
      error: m?.error,
      result: m?.outputs,
      metadata: { model: m?.modelUsed, executor: m?.executorId, tokens: m?.tokensUsed, cost: m?.estimatedCost, retries: m?.retries, worker_calls: m?.workerCalls },
    });
    stepDefinitions.forEach((def, index) => {
      const id = def.id || def.step_id || def.name || `step-${index + 1}`;
      const m = stepExecutionList.find((x) => x.stepId === id) || (stepDefinitions.length === stepExecutionList.length ? stepExecutionList[index] : null);
      used.add(id);
      resolved.push({ id, name: def.name || def.title || def.executor || `Step ${index + 1}`, assignedTo: def.executor || def.assigned_to || def.assignedTo, ...fromExec(m) });
    });
    stepExecutionList.forEach((m, index) => {
      if (used.has(m.stepId)) return;
      resolved.push({ id: m.stepId || `exec-${index}`, name: humanKey(m.stepId || `Step ${index + 1}`), assignedTo: m.executorId, ...fromExec(m) });
    });
    return resolved;
  }, [stepDefinitions, stepExecutionList]);

  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const total = steps.length;
  const percent = execution?.raw?.progress_percent ?? (total ? Math.round((completedCount / total) * 100) : 0);
  const runningIndex = steps.findIndex((s) => isActiveState(s.status));
  const currentIndex = runningIndex >= 0 ? runningIndex + 1 : Math.min(completedCount + 1, total);
  const state = execution?.state;
  const status = execStatus(state);
  const active = isActiveState(state);
  const required = requiredInputsOf(workflow);
  const failReason = execution?.error || ralphResult?.error || steps.find((s) => s.error)?.error;
  const checkpoint = execution?.pendingCheckpoint;

  return (
    <Sheet isOpen={Boolean(workflow)} onClose={onClose} side="right" title={workflow?.name} initialFocusRef={execution ? undefined : firstInputRef} className="sm:max-w-xl">
      {workflow && (
        <div className="space-y-5 pt-1">
          <div className="flex flex-wrap items-center gap-2">
            {execution ? <ExecStatusChip state={state} /> : <Chip size="sm">Not started</Chip>}
            {(workflow.tags || []).map((t) => (
              <Chip key={t} size="xs">
                {t}
              </Chip>
            ))}
          </div>
          {workflow.description && <p className="text-body-sm text-muted">{workflow.description}</p>}

          {/* ── inputs / start ── */}
          {!execution ? (
            <form onSubmit={handleExecute} noValidate className="space-y-4">
              {required.length === 0 && <p className="text-body-sm text-muted">This workflow needs no inputs.</p>}
              {required.map((key, i) => (
                <Field key={key} label={humanKey(key)} required error={inputErrors[key]}>
                  <Textarea
                    ref={i === 0 ? firstInputRef : undefined}
                    rows={3}
                    value={inputs[key] || ''}
                    onChange={(e) => setInputs({ ...inputs, [key]: e.target.value })}
                    placeholder={`Enter the ${humanKey(key).toLowerCase()}…`}
                  />
                </Field>
              ))}
              <Button type="submit" icon={Play} loading={loading} className="w-full">
                Run workflow
              </Button>
            </form>
          ) : (
            Object.keys(inputs || {}).length > 0 && (
              <details className="rounded-control border border-border bg-surface/60 px-3 py-2">
                <summary className="cursor-pointer text-body-sm font-medium text-fg">Inputs</summary>
                <dl className="mt-2 space-y-1.5">
                  {Object.entries(inputs).map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-caption text-muted">{humanKey(k)}</dt>
                      <dd className="whitespace-pre-wrap text-body-sm text-fg">{String(v) || '—'}</dd>
                    </div>
                  ))}
                </dl>
              </details>
            )
          )}

          {/* ── progress / outcome ── */}
          {execution && (
            <section aria-live="polite" className="space-y-3">
              {active && (
                <div className="rounded-card border border-border bg-card p-3">
                  <div className="mb-2 flex items-center justify-between gap-2 text-body-sm">
                    <span className="flex items-center gap-2 text-fg">
                      <StatusDot status={status.dot} size="md" />
                      {execution.id ? (total ? `Step ${currentIndex} of ${total}` : 'Starting…') : 'Queued — waiting for the engine to pick it up'}
                    </span>
                    <span className="tabular-nums text-muted">{percent}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-elevated" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
                    <div className="h-full rounded-full bg-accent-fill transition-[width] duration-slow ease-standard" style={{ width: `${percent}%` }} />
                  </div>
                  {checkpoint && (
                    <div className="mt-3 flex items-start gap-2 rounded-control border border-warn/25 bg-warn/10 p-2.5">
                      <PauseCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-warn" />
                      <div className="text-body-sm">
                        <p className="font-medium text-fg-strong">{checkpoint.name || 'Checkpoint'}</p>
                        <p className="text-fg">{checkpoint.prompt || 'This run is waiting for a decision.'}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
              {state === 'failed' && (
                <div className="rounded-card border border-danger/30 bg-danger/10 p-3">
                  <p className="text-body-sm font-medium text-danger">The run failed</p>
                  <p className="mt-1 text-body-sm text-fg">{failReason || 'No reason was recorded for this failure.'}</p>
                  <Button variant="secondary" size="sm" icon={Zap} loading={loading} onClick={handleRetryWithRalph} className="mt-3">
                    Retry with self-correction
                  </Button>
                </div>
              )}
              {state === 'completed' && (
                <div className="rounded-card border border-ok/25 bg-ok/10 p-3">
                  <p className="text-body-sm font-medium text-ok">Completed</p>
                  <p className="mt-1 text-caption text-muted">
                    {fmtDuration(execution.durationSeconds)} · {fmtCost(execution.totalCost)}
                    {execution.totalTokens != null ? ` · ${fmtTokens(execution.totalTokens)} tokens` : ''}
                  </p>
                  {execution.outputs && Object.keys(execution.outputs).length > 0 && (
                    <div className="mt-3">
                      <Pre>{execution.outputs}</Pre>
                    </div>
                  )}
                </div>
              )}
              {state === 'cancelled' && <p className="text-body-sm text-muted">This run was cancelled.</p>}
              {executionSource === 'ralph' && (
                <div className="rounded-card border border-warn/25 bg-warn/10 p-3">
                  <p className="flex items-center gap-2 text-body-sm font-medium text-fg-strong">
                    <RefreshCw aria-hidden="true" className="h-4 w-4 text-warn" /> Self-correction
                    {ralphProgress?.progress_percent != null && <span className="ml-auto tabular-nums text-muted">{ralphProgress.progress_percent}%</span>}
                  </p>
                  {ralphProgress && (
                    <p className="mt-1 text-caption text-muted">
                      Iteration {ralphProgress.iteration} of {ralphProgress.max_iterations} · tasks {ralphProgress.tasks?.completed || 0} / {ralphProgress.tasks?.total || 0}
                    </p>
                  )}
                  {ralphResult && (
                    <div className="mt-3">
                      <Pre>{ralphResult}</Pre>
                    </div>
                  )}
                </div>
              )}
              {pollError && <p className="text-caption text-warn">Lost touch with the engine while refreshing: {humanize(pollError, { what: 'refreshing the run' })}</p>}
            </section>
          )}

          {/* ── steps ── */}
          {execution && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="text-caption font-semibold uppercase tracking-wider text-muted">Steps</p>
                {active && (
                  <label className="flex items-center gap-2 text-caption text-muted">
                    Follow
                    <Toggle checked={follow} onChange={setFollow} label="Follow the newest step" />
                  </label>
                )}
              </div>
              {steps.length === 0 ? (
                <p className="flex items-center gap-2 py-6 text-body-sm text-muted">
                  <Spinner /> Waiting for the first step…
                </p>
              ) : (
                <ol ref={listRef} className="max-h-[50vh] space-y-2 overflow-y-auto pr-1" aria-label="Workflow steps">
                  {steps.map((step, i) => (
                    <StepRow key={step.id} index={i} step={step} expanded={expandedSteps.has(step.id)} onToggle={() => toggleStep(step.id)} />
                  ))}
                </ol>
              )}
            </div>
          )}

          {execution && execution.modelConfigUsed && (
            <details className="rounded-control border border-border bg-surface/60 px-3 py-2">
              <summary className="cursor-pointer text-body-sm font-medium text-fg">Model configuration</summary>
              <div className="mt-2">
                <Pre>{execution.modelConfigUsed}</Pre>
              </div>
            </details>
          )}

          {execution && (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-border pt-4">
              {active && execution.id && (
                <Tooltip content="Stops the run; finished steps keep their results">
                  <Button variant="danger" icon={StopCircle} loading={cancelling} onClick={handleCancel}>
                    Cancel run
                  </Button>
                </Tooltip>
              )}
              <Button variant="secondary" onClick={onClose}>
                Close
              </Button>
            </div>
          )}
        </div>
      )}
    </Sheet>
  );
}
