/**
 * Scheduled runs — agents on a cron.
 *
 * Frame → toolbar-less table → all four states → detail sheet → dialogs.
 * The failure REASON is always visible: in the Status cell on desktop, in the
 * card on phones, and in full in the detail sheet. Times are shown in the
 * run's own zone; an omitted zone means Eastern (the API default since the
 * 2026-10-16 "business time is explicit Eastern" change), and new runs default
 * to the browser's zone, as before.
 *
 * Each run can carry a RESPONSIBILITY (`description`): one or two plain
 * sentences saying what it is responsible for. It shows under the name here
 * and is the headline of the run in the Command Center's Autonomous catalogue.
 * Deep links: ?new=1 opens the new-run dialog, ?edit=<id> the edit dialog and
 * ?open=<id> the detail sheet (the catalogue and the palette link here).
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useSearchParams } from 'react-router-dom';
import { CalendarClock, Plus, RefreshCw, Play, Pencil, Trash2, MoreHorizontal, History, Bot } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import Breadcrumbs from '../components/Breadcrumbs';
import AgentAvatar from '../components/AgentAvatar';
import { relativeTime, absoluteTime } from '../components/ActivityFeed';
import { BUSINESS_TZ, describeCron, timezoneChoices, validateCron, viewerTimezone, zoneLabel as tzLabel } from '../utils/cron';
import {
  Button,
  IconButton,
  Card,
  Chip,
  DataTable,
  Field,
  Input,
  Textarea,
  Select,
  Modal,
  Sheet,
  Toggle,
  Tooltip,
  StatusDot,
  Page,
  PageHeader,
  SectionHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
} from '../components/ui';

// ── the status vocabulary for a run ─────────────────────────────────────────
const RUN_STATUS = {
  success: { tone: 'ok', label: 'Succeeded', dot: 'done' },
  error: { tone: 'danger', label: 'Failed', dot: 'error' },
  timeout: { tone: 'warn', label: 'Timed out', dot: 'error' },
  running: { tone: 'live', label: 'Running', dot: 'tool', pulse: true },
  skipped: { tone: 'neutral', label: 'Skipped', dot: 'idle' },
  none: { tone: 'neutral', label: 'Never run', dot: 'idle' },
};
/** A status outside the set ("degraded" on dogfood) is shown as itself in warn — never as "Never run". */
const runStatus = (s) => RUN_STATUS[s] || (s ? { tone: 'warn', label: String(s).charAt(0).toUpperCase() + String(s).slice(1), dot: 'idle' } : RUN_STATUS.none);
/** Failing = error, timeout, or any status outside the known set (the catalogue's health maps those to failing too). */
const isFailingStatus = (s) => Boolean(s) && !['success', 'running', 'skipped'].includes(s);

/** The reason a run ended the way it did, in human words, or null. */
function runReason(row) {
  const raw = row.lastResultSummary || row.error || row.outputSummary || '';
  if (!raw) return null;
  return String(raw).replace(/^(error|failed|skipped|degraded|warning)\s*:\s*/i, '').trim() || null;
}

function emptyForm() {
  return {
    name: '',
    description: '',
    agentId: '',
    prompt: '',
    cron: '0 13 * * *',
    timezone: viewerTimezone(),
    ownerUserId: '',
    enabled: true,
    maxRuntimeSeconds: 300,
  };
}

function validate(f) {
  const e = {};
  if (!f.name.trim()) e.name = 'Give the run a name so you can find it later.';
  if (!f.agentId) e.agentId = 'Pick the agent that will do the work.';
  if (String(f.description || '').length > 2000) e.description = 'Keep it to two thousand characters; one or two sentences is the goal.';
  if (!f.prompt.trim()) e.prompt = 'Tell the agent what to do each time it runs.';
  const cronProblem = validateCron(f.cron);
  if (cronProblem) e.cron = cronProblem;
  const n = Number(f.maxRuntimeSeconds);
  if (!Number.isFinite(n) || n < 5 || n > 3600) e.maxRuntimeSeconds = 'Between 5 seconds and one hour (3600).';
  return e;
}

// ── a row-actions menu that escapes the table's overflow ────────────────────
// ui/Menu positions its dropdown in-flow, so inside DataTable's overflow-x-auto
// wrapper the last rows' menus are clipped. This local variant portals the
// list to <body> at the trigger's position; same keyboard contract.
function ActionMenu({ label = 'Actions', items, size = 'sm' }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState(null);
  const [active, setActive] = useState(0);
  const triggerRef = useRef(null);
  const menuRef = useRef(null);
  const itemRefs = useRef([]);
  const id = useId();
  const enabled = items.map((it, i) => ({ it, i })).filter(({ it }) => it.type !== 'separator' && !it.disabled);

  const place = () => {
    const r = triggerRef.current?.getBoundingClientRect();
    if (!r) return;
    const est = Math.min(items.length * 40 + 8, 320);
    const below = window.innerHeight - r.bottom;
    const top = below < est + 8 ? Math.max(8, r.top - est - 4) : r.bottom + 4;
    setPos({ top, right: Math.max(8, window.innerWidth - r.right) });
  };
  const openMenu = () => {
    place();
    setOpen(true);
  };
  const close = (restore = true) => {
    setOpen(false);
    if (restore) triggerRef.current?.focus();
  };

  useEffect(() => {
    if (!open) return undefined;
    const first = enabled[0]?.i ?? 0;
    setActive(first);
    const raf = requestAnimationFrame(() => itemRefs.current[first]?.focus());
    const onDoc = (e) => {
      if (!menuRef.current?.contains(e.target) && !triggerRef.current?.contains(e.target)) setOpen(false);
    };
    const onMove = () => setOpen(false);
    document.addEventListener('mousedown', onDoc);
    window.addEventListener('scroll', onMove, true);
    window.addEventListener('resize', onMove);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('mousedown', onDoc);
      window.removeEventListener('scroll', onMove, true);
      window.removeEventListener('resize', onMove);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const focusAt = (i) => {
    setActive(i);
    itemRefs.current[i]?.focus();
  };
  const move = (dir) => {
    const idx = enabled.findIndex(({ i }) => i === active);
    const next = enabled[(idx + dir + enabled.length) % enabled.length];
    if (next) focusAt(next.i);
  };
  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Home') { e.preventDefault(); if (enabled[0]) focusAt(enabled[0].i); }
    else if (e.key === 'End') { e.preventDefault(); const l = enabled[enabled.length - 1]; if (l) focusAt(l.i); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'Tab') close(false);
  };

  return (
    <>
      <IconButton
        ref={triggerRef}
        icon={MoreHorizontal}
        label={label}
        size={size}
        className="min-h-touch min-w-touch md:min-h-0 md:min-w-0"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        onClick={() => (open ? close(false) : openMenu())}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            openMenu();
          }
        }}
      />
      {open &&
        pos &&
        createPortal(
          <div
            ref={menuRef}
            id={id}
            role="menu"
            aria-label={label}
            onKeyDown={onKeyDown}
            style={{ top: pos.top, right: pos.right }}
            className="fixed z-popover min-w-[12rem] overflow-hidden rounded-card border border-border bg-overlay p-1 shadow-e3 animate-scale-in"
          >
            {items.map((it, i) =>
              it.type === 'separator' ? (
                <div key={`sep-${i}`} role="separator" className="my-1 h-px bg-border" />
              ) : (
                <button
                  key={it.id || i}
                  ref={(el) => (itemRefs.current[i] = el)}
                  role="menuitem"
                  type="button"
                  disabled={it.disabled}
                  tabIndex={active === i ? 0 : -1}
                  onMouseEnter={() => !it.disabled && setActive(i)}
                  onClick={() => {
                    close();
                    it.onSelect?.();
                  }}
                  className={[
                    'flex w-full items-center gap-2.5 rounded-control px-2.5 py-2 text-left text-body transition-colors duration-fast',
                    'focus-visible:outline-none focus-visible:bg-elevated',
                    it.tone === 'danger' ? 'text-danger hover:bg-danger/10' : 'text-fg hover:bg-elevated',
                    it.disabled ? 'cursor-not-allowed opacity-50' : '',
                  ].join(' ')}
                >
                  {it.icon && <it.icon aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />}
                  <span className="min-w-0 flex-1 truncate">{it.label}</span>
                </button>
              )
            )}
          </div>,
          document.body
        )}
    </>
  );
}

// ── cells ───────────────────────────────────────────────────────────────────
function StatusCell({ row, full = false }) {
  const s = runStatus(row.lastStatus);
  const reason = runReason(row);
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <Chip tone={s.tone} dot pulse={s.pulse} size="sm" className="w-fit">
        {s.label}
      </Chip>
      {reason &&
        (full ? (
          <p className={`text-caption ${s.tone === 'danger' || s.tone === 'warn' ? 'text-danger' : 'text-muted'}`}>{reason}</p>
        ) : (
          <Tooltip content={reason}>
            <p className={`max-w-[60vw] truncate text-caption md:max-w-[12rem] 2xl:max-w-[22rem] ${s.tone === 'danger' || s.tone === 'warn' ? 'text-danger' : 'text-muted'}`}>{reason}</p>
          </Tooltip>
        ))}
    </div>
  );
}

function ScheduleCell({ row }) {
  const reading = describeCron(row.cron);
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-body-sm text-fg">
        {reading || 'Custom schedule'} <span className="text-muted">{tzLabel(row.timezone)}</span>
      </span>
      <code className="whitespace-nowrap font-mono text-caption text-muted">{row.cron}</code>
      {row.enabled ? (
        row.nextRunAt ? (
          <Tooltip content={absoluteTime(row.nextRunAt, row.timezone || BUSINESS_TZ)}>
            <time dateTime={row.nextRunAt} className="text-caption text-muted">
              Next {relativeTime(row.nextRunAt)}
            </time>
          </Tooltip>
        ) : (
          <span className="text-caption text-muted">No upcoming run</span>
        )
      ) : (
        <span className="text-caption text-muted">Paused</span>
      )}
    </div>
  );
}

function LastRunCell({ row }) {
  if (!row.lastRunAt) return <span className="text-muted">Never</span>;
  return (
    <Tooltip content={absoluteTime(row.lastRunAt, row.timezone || BUSINESS_TZ)}>
      <time dateTime={row.lastRunAt} className="text-fg">
        {relativeTime(row.lastRunAt)}
      </time>
    </Tooltip>
  );
}

function AgentCell({ agent, id }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      {agent ? (
        <AgentAvatar agent={agent} size={24} rounded="rounded-full" />
      ) : (
        <span aria-hidden="true" className="flex h-6 w-6 items-center justify-center rounded-full bg-elevated">
          <Bot className="h-3.5 w-3.5 text-muted" />
        </span>
      )}
      <span className="truncate">{agent ? agent.displayName || agent.name : id || '—'}</span>
    </span>
  );
}

// ── the edit dialog ─────────────────────────────────────────────────────────
function RunForm({ open, initial, agents, onClose, onSave }) {
  const [form, setForm] = useState(emptyForm);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const nameRef = useRef(null);
  // One close handler for the dialog's lifetime: ui/useFocusTrap re-runs, and
  // pulls focus back to Name, whenever onClose changes identity — which an
  // inline arrow does on every keystroke.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const savingRef = useRef(false);
  savingRef.current = saving;
  const requestClose = useCallback(() => {
    if (!savingRef.current) onCloseRef.current?.();
  }, []);

  useEffect(() => {
    if (open) {
      setForm(initial ? { ...emptyForm(), ...initial, description: initial.description || '', ownerUserId: initial.ownerUserId || '' } : emptyForm());
      setErrors({});
    }
  }, [open, initial]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e?.target ? e.target.value : e }));
  const reading = describeCron(form.cron);
  const tzChoices = useMemo(() => timezoneChoices(form.timezone, viewerTimezone()), [form.timezone]);

  const submit = async (e) => {
    e.preventDefault();
    const errs = validate(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true);
    try {
      await onSave({ ...form, maxRuntimeSeconds: Number(form.maxRuntimeSeconds) });
      onClose();
    } catch (err) {
      notify.error(humanize(err, { what: 'saving the run' }));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      isOpen={open}
      onClose={requestClose}
      size="xl"
      title={initial?.id ? 'Edit scheduled run' : 'New scheduled run'}
      description="An agent runs this prompt on the schedule you set, server-side, whether or not anyone is signed in."
      initialFocusRef={nameRef}
      footer={
        <>
          <Button variant="ghost" onClick={requestClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="scheduled-run-form" loading={saving}>
            {initial?.id ? 'Save changes' : 'Schedule it'}
          </Button>
        </>
      }
    >
      <form id="scheduled-run-form" onSubmit={submit} noValidate className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Name" required error={errors.name} className="sm:col-span-2">
          <Input ref={nameRef} value={form.name} onChange={set('name')} placeholder="Morning brief" />
        </Field>
        <Field
          label="Responsibility"
          error={errors.description}
          help="One or two plain sentences: what this run is responsible for. It’s the line people read in the Autonomous catalogue."
          className="sm:col-span-2"
        >
          <Textarea
            rows={2}
            maxLength={2000}
            value={form.description}
            onChange={set('description')}
            placeholder="Writes the morning brief: what needs attention today, one line each, with a recommendation."
          />
        </Field>
        <Field label="Agent" required error={errors.agentId}>
          <Select value={form.agentId} onChange={set('agentId')}>
            <option value="">Pick an agent…</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.displayName || a.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Max runtime (seconds)" required error={errors.maxRuntimeSeconds} help="The run is stopped after this long.">
          <Input type="number" min={5} max={3600} value={form.maxRuntimeSeconds} onChange={set('maxRuntimeSeconds')} />
        </Field>
        <Field label="Prompt" required error={errors.prompt} className="sm:col-span-2">
          <Textarea rows={4} value={form.prompt} onChange={set('prompt')} placeholder="What should the agent do each time?" />
        </Field>
        <Field
          label="Schedule (cron)"
          required
          error={errors.cron}
          help={reading ? `${reading} ${tzLabel(form.timezone)}` : 'Five fields: minute hour day-of-month month weekday'}
        >
          <Input value={form.cron} onChange={set('cron')} placeholder="0 13 * * *" className="font-mono" spellCheck={false} />
        </Field>
        <Field label="Time zone" help="Leave it on Eastern unless the run belongs somewhere else.">
          <Select value={form.timezone} onChange={set('timezone')}>
            {tzChoices.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Run as user (optional)" help="A user id when the run should act with someone's own permissions." className="sm:col-span-2">
          <Input value={form.ownerUserId} onChange={set('ownerUserId')} placeholder="UUID" className="font-mono" spellCheck={false} />
        </Field>
        <div className="flex items-center justify-between rounded-control border border-border bg-surface/60 px-3 py-2 sm:col-span-2">
          <div>
            <p className="text-body-sm font-medium text-fg">Enabled</p>
            <p className="text-caption text-muted">Disabled runs stay on the list and can still be run by hand.</p>
          </div>
          <Toggle checked={Boolean(form.enabled)} onChange={(v) => setForm((f) => ({ ...f, enabled: v }))} label="Enabled" />
        </div>
      </form>
    </Modal>
  );
}

// ── the detail sheet (prompt + recent history) ──────────────────────────────
function RunDetail({ run, agent, history, historyError, onClose, onRunNow, onEdit, onRetryHistory }) {
  const open = Boolean(run);
  return (
    <Sheet
      isOpen={open}
      onClose={onClose}
      side="right"
      title={run?.name}
      className="sm:max-w-xl"
      footer={
        run && (
          <>
            <Button variant="secondary" icon={Pencil} onClick={() => onEdit(run)}>
              Edit
            </Button>
            <Button icon={Play} onClick={() => onRunNow(run)}>
              Run now
            </Button>
          </>
        )
      }
    >
      {run && (
        <div className="space-y-5 pt-1">
          <StatusCell row={run} full />
          <div>
            <p className="mb-1 text-caption text-muted">Responsibility</p>
            {run.description ? (
              <p className="text-body text-fg-strong">{run.description}</p>
            ) : (
              <p className="text-body-sm text-subtle">
                No responsibility written yet.{' '}
                <Button variant="link" size="sm" onClick={() => onEdit(run)}>
                  Write one
                </Button>
              </p>
            )}
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <div>
              <dt className="text-caption text-muted">Agent</dt>
              <dd className="mt-1 text-body text-fg">
                <AgentCell agent={agent} id={run.agentId} />
              </dd>
            </div>
            <div>
              <dt className="text-caption text-muted">Schedule</dt>
              <dd className="mt-1">
                <ScheduleCell row={run} />
              </dd>
            </div>
            <div>
              <dt className="text-caption text-muted">Last run</dt>
              <dd className="mt-1 text-body text-fg">
                {run.lastRunAt ? absoluteTime(run.lastRunAt, run.timezone || BUSINESS_TZ) : 'Never'}
              </dd>
            </div>
            <div>
              <dt className="text-caption text-muted">Limits</dt>
              <dd className="mt-1 text-body text-fg">
                Stops after {run.maxRuntimeSeconds}s · {run.enabled ? 'enabled' : 'disabled'}
              </dd>
            </div>
            {run.ownerUserId && (
              <div className="sm:col-span-2">
                <dt className="text-caption text-muted">Runs as</dt>
                <dd className="mt-1 font-mono text-body-sm text-fg">{run.ownerUserId}</dd>
              </div>
            )}
          </dl>
          <div>
            <p className="mb-1.5 text-caption text-muted">Prompt</p>
            <p className="whitespace-pre-wrap rounded-control border border-border bg-surface p-3 text-body-sm text-fg">{run.prompt}</p>
          </div>
          <div>
            <SectionHeader title="Recent runs" description="Most recent first" />
            {historyError ? (
              <ErrorState compact title="Couldn’t load the history" detail={humanize(historyError, { what: 'loading the history' })} onRetry={onRetryHistory} />
            ) : !history ? (
              <LoadingState variant="list" count={3} label="Loading history" />
            ) : history.length === 0 ? (
              <EmptyState compact icon={History} title="No runs yet" description="The first run lands here with its result or its reason for failing." />
            ) : (
              <ol className="divide-y divide-border/60" aria-label="Run history">
                {history.map((h) => {
                  const s = runStatus(h.status);
                  const text = h.error || h.outputSummary;
                  return (
                    <li key={h.id} className="flex items-start gap-3 py-2.5">
                      <StatusDot status={s.dot} size="md" className="mt-1.5" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Chip tone={s.tone} size="xs">
                            {s.label}
                          </Chip>
                          <Tooltip content={absoluteTime(h.startedAt, run.timezone || BUSINESS_TZ)}>
                            <time dateTime={h.startedAt} className="text-caption text-muted">
                              {relativeTime(h.startedAt)}
                            </time>
                          </Tooltip>
                          {h.trigger && (
                            <span className="text-caption text-subtle">· {h.trigger === 'manual' ? 'run by hand' : 'on schedule'}</span>
                          )}
                          {h.toolCallsCount ? (
                            <span className="text-caption text-subtle">
                              · {h.toolCallsCount} tool call{h.toolCallsCount === 1 ? '' : 's'}
                            </span>
                          ) : null}
                        </div>
                        <p className={`mt-1 text-body-sm ${h.error ? 'text-danger' : 'text-fg'}`}>{text || 'No output was recorded.'}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}

// ── the page ────────────────────────────────────────────────────────────────
export default function ScheduledRuns() {
  const [items, setItems] = useState([]);
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [editing, setEditing] = useState(null); // null = closed, {} = new, {id…} = edit
  const [deleting, setDeleting] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const deleteBusyRef = useRef(false);
  deleteBusyRef.current = deleteBusy;
  // Stable dialog handlers (see RunForm): the page re-renders every 30 s.
  const closeEditor = useCallback(() => setEditing(null), []);
  const closeDetail = useCallback(() => setDetailId(null), []);
  const closeDelete = useCallback(() => {
    if (!deleteBusyRef.current) setDeleting(null);
  }, []);
  const [detailId, setDetailId] = useState(null);
  const [history, setHistory] = useState({});
  const [historyError, setHistoryError] = useState(null);

  const agentById = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [list, agentList] = await Promise.all([apiJson('/scheduled-runs'), apiJson('/agents')]);
      setItems(list?.items || []);
      setAgents(Array.isArray(agentList) ? agentList : agentList?.agents || agentList?.items || []);
    } catch (err) {
      if (!silent) setError(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load({ silent: true }), 30000);
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

  const loadHistory = useCallback(async (id) => {
    setHistoryError(null);
    try {
      const res = await apiJson(`/scheduled-runs/${encodeURIComponent(id)}/history`, { params: { limit: 50 } });
      setHistory((h) => ({ ...h, [id]: res?.items || [] }));
    } catch (err) {
      setHistoryError(err);
    }
  }, []);

  const openDetail = (row) => {
    setDetailId(row.id);
    setHistory((h) => ({ ...h, [row.id]: undefined }));
    loadHistory(row.id);
  };

  // Deep links from the palette and the Autonomous catalogue: act once, then
  // drop the param so a reload does not reopen the dialog.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const wantsNew = searchParams.get('new');
    const target = searchParams.get('edit') || searchParams.get('open');
    if (!wantsNew && !target) return;
    if (target && loading) return; // wait for the list
    const mode = searchParams.get('edit') ? 'edit' : 'open';
    const next = new URLSearchParams(searchParams);
    ['new', 'edit', 'open'].forEach((k) => next.delete(k));
    setSearchParams(next, { replace: true });
    if (wantsNew) {
      setEditing({});
      return;
    }
    const row = items.find((r) => r.id === target);
    if (!row) {
      if (!error) notify.error('That scheduled run isn’t here any more. It may have been deleted.');
      return;
    }
    if (mode === 'edit') setEditing(row);
    else openDetail(row);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, loading, items]);

  const save = async (form) => {
    const body = { ...form, description: String(form.description || '').trim() };
    if (!body.ownerUserId) delete body.ownerUserId;
    // A new run without a responsibility simply omits it; an edit sends '' so clearing it sticks.
    if (!editing?.id && !body.description) delete body.description;
    if (editing?.id) {
      await apiJson(`/scheduled-runs/${encodeURIComponent(editing.id)}`, { method: 'PUT', body: JSON.stringify(body) });
      notify.success(`“${form.name}” updated`);
    } else {
      await apiJson('/scheduled-runs', { method: 'POST', body: JSON.stringify(body) });
      notify.success(`“${form.name}” scheduled`);
    }
    await load({ silent: true });
  };

  const toggle = async (row, enabled) => {
    setItems((list) => list.map((r) => (r.id === row.id ? { ...r, enabled } : r)));
    try {
      await apiJson(`/scheduled-runs/${encodeURIComponent(row.id)}`, { method: 'PUT', body: JSON.stringify({ enabled }) });
      notify.success(`“${row.name}” ${enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      setItems((list) => list.map((r) => (r.id === row.id ? { ...r, enabled: !enabled } : r)));
      notify.error(humanize(err, { what: 'updating the run' }));
    }
  };

  const runNow = async (row) => {
    try {
      await apiJson(`/scheduled-runs/${encodeURIComponent(row.id)}/run-now`, { method: 'POST', body: JSON.stringify({}) });
      notify.success(`“${row.name}” is running`);
      await load({ silent: true });
      if (detailId === row.id) loadHistory(row.id);
    } catch (err) {
      notify.error(humanize(err, { what: 'starting the run' }));
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await apiJson(`/scheduled-runs/${encodeURIComponent(deleting.id)}`, { method: 'DELETE' });
      notify.success(`“${deleting.name}” deleted`);
      setItems((list) => list.filter((r) => r.id !== deleting.id));
      if (detailId === deleting.id) setDetailId(null);
      setDeleting(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'deleting the run' }));
    } finally {
      setDeleteBusy(false);
    }
  };

  const columns = [
    {
      key: 'name',
      label: 'Name',
      nowrap: false,
      render: (r) => (
        <div className="w-full min-w-[12rem] max-w-[20rem]">
          <button
            type="button"
            onClick={() => openDetail(r)}
            className="max-w-full text-left font-semibold text-fg-strong hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-chip"
          >
            {r.name}
          </button>
          {r.description && <p className="mt-0.5 line-clamp-2 whitespace-normal text-caption font-normal text-muted">{r.description}</p>}
        </div>
      ),
    },
    { key: 'agent', label: 'Agent', render: (r) => <AgentCell agent={agentById.get(r.agentId)} id={r.agentId} /> },
    { key: 'schedule', label: 'Schedule', nowrap: false, render: (r) => <ScheduleCell row={r} /> },
    {
      key: 'enabled',
      label: 'Enabled',
      render: (r) => <Toggle checked={Boolean(r.enabled)} onChange={(v) => toggle(r, v)} label={`${r.name} enabled`} />,
    },
    { key: 'lastRun', label: 'Last run', render: (r) => <LastRunCell row={r} /> },
    { key: 'status', label: 'Status', nowrap: false, render: (r) => <StatusCell row={r} /> },
    {
      key: 'actions',
      label: 'Actions',
      align: 'right',
      render: (r) => (
        <ActionMenu
          label={`Actions for ${r.name}`}
          items={[
            { id: 'run', label: 'Run now', icon: Play, onSelect: () => runNow(r) },
            { id: 'history', label: 'Prompt & history', icon: History, onSelect: () => openDetail(r) },
            { id: 'edit', label: 'Edit', icon: Pencil, onSelect: () => setEditing(r) },
            { type: 'separator' },
            { id: 'delete', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: () => setDeleting(r) },
          ]}
        />
      ),
    },
  ];

  const failing = items.filter((r) => isFailingStatus(r.lastStatus)).length;
  const description = loading
    ? 'Agents that run on a cron, server-side, and survive restarts'
    : items.length === 0
      ? 'Agents that run on a cron, server-side, and survive restarts'
      : `${items.length} run${items.length === 1 ? '' : 's'} · ${items.filter((r) => r.enabled).length} enabled${
          failing ? ` · ${failing} failing` : ''
        }`;

  let body;
  if (offline && !items.length) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = <LoadingState variant="table" count={5} label="Loading scheduled runs" />;
  } else if (error) {
    body = <ErrorState title="Couldn’t load the scheduled runs" detail={humanize(error, { what: 'loading the runs' })} onRetry={load} />;
  } else if (!items.length) {
    body = (
      <EmptyState
        icon={CalendarClock}
        title="No scheduled runs yet"
        description="Schedule an agent on a cron and it appears here with its last result and the reason when it fails."
        action={
          <Button icon={Plus} onClick={() => setEditing({})}>
            New scheduled run
          </Button>
        }
      />
    );
  } else {
    body = <DataTable columns={columns} rows={items} rowKey="id" caption="Scheduled runs" />;
  }

  const detailRun = detailId ? items.find((r) => r.id === detailId) : null;

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="System"
        title="Scheduled runs"
        description={description}
        actions={
          <>
            <Button variant="secondary" icon={RefreshCw} loading={refreshing} onClick={() => load({ silent: true })}>
              Refresh
            </Button>
            <Button icon={Plus} onClick={() => setEditing({})}>
              New
            </Button>
          </>
        }
      />

      {body}

      <RunForm open={editing !== null} initial={editing?.id ? editing : null} agents={agents} onClose={closeEditor} onSave={save} />

      <RunDetail
        run={detailRun}
        agent={detailRun ? agentById.get(detailRun.agentId) : null}
        history={detailRun ? history[detailRun.id] : null}
        historyError={historyError}
        onClose={closeDetail}
        onRunNow={runNow}
        onEdit={(r) => {
          setDetailId(null);
          setEditing(r);
        }}
        onRetryHistory={() => detailRun && loadHistory(detailRun.id)}
      />

      <Modal
        isOpen={Boolean(deleting)}
        onClose={closeDelete}
        tone="danger"
        size="sm"
        title="Delete this scheduled run?"
        description={deleting ? `“${deleting.name}” stops running and its history goes with it. This can’t be undone.` : ''}
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
