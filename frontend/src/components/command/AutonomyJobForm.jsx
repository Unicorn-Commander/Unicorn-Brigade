/**
 * Register / edit an outside job (PUT /api/v1/autonomy/jobs/{key}).
 *
 * Every field of the contract's PUT body, with human validation that mirrors
 * the API's rules (slug key, five-field cron, IANA zone, no secrets in the
 * command) so the form says it before the server does; a 422 from the server
 * lands on the field it names. The key is slugged from the name while you
 * type and is read-only once the job exists — it is how the script reports in.
 *
 * "How a script reports its runs" shows the contract's two curl lines filled
 * with this job's key and body. The reporter key stays a variable
 * ($BRIGADE_REPORTER_KEY): a key value never belongs in a script.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { Check, ChevronRight, Copy } from 'lucide-react';
import notify from '../../utils/notify';
import { humanize } from '../../utils/errors';
import { apiJson } from '../../services/http';
import { bareHost } from '../../services/apiBase';
import { describeSchedule, isValidTimezone, timezoneChoices, validateCron, viewerTimezone } from '../../utils/cron';
import { KEY_RE, RUNNERS, SECRET_MESSAGES, jobBody, jobForm, looksLikeSecret, reportingSnippets, serverErrors, slugify } from '../../utils/autonomy';
import { Button, Field, IconButton, Input, Modal, Select, Textarea, Toggle } from '../ui';

const DEFAULT_HOSTS = ['cloud'];

function validate(f, { creating, existingKeys }) {
  const e = {};
  const name = f.name.trim();
  if (!name) e.name = 'Name the job so people can find it — “Build Log refresh”.';
  else if (name.length > 255) e.name = 'Keep the name under 255 characters.';
  if (creating) {
    if (!f.key) e.key = 'The key is how the script reports in; it fills in from the name.';
    else if (!KEY_RE.test(f.key)) e.key = 'Use 3–120 lowercase letters, digits and dashes, starting and ending with a letter or digit.';
    else if (existingKeys.has(f.key)) e.key = 'A job already uses this key. Pick another, or edit that job instead.';
  }
  const resp = f.responsibility.trim();
  if (!resp) e.responsibility = 'Say what this job is responsible for, in a sentence or two.';
  else if (resp.length > 2000) e.responsibility = 'Keep it under 2,000 characters; one or two sentences is the goal.';
  const host = f.host.trim();
  if (!host) e.host = 'Name the machine it runs on, or “cloud” for a hosted routine.';
  else if (host.length > 120) e.host = 'Keep the host name under 120 characters.';
  if (!RUNNERS.some((r) => r.id === f.runner)) e.runner = 'Pick how it runs.';
  if (f.schedule.trim()) {
    const problem = validateCron(f.schedule);
    if (problem) e.schedule = problem;
  }
  if (!isValidTimezone(f.timezone.trim() || 'UTC')) e.timezone = 'That isn’t a time zone the browser knows. Use an IANA name like America/New_York or UTC.';
  if (f.scheduleNote.trim().length > 255) e.scheduleNote = 'Keep the note under 255 characters.';
  if (f.command.trim().length > 500) e.command = 'Keep the command under 500 characters; point at a script instead.';
  else if (looksLikeSecret(f.command)) e.command = SECRET_MESSAGES.command;
  const url = f.runbookUrl.trim();
  if (url.length > 500) e.runbookUrl = 'Keep the link under 500 characters.';
  else if (url && !/^https?:\/\/\S+$/i.test(url)) e.runbookUrl = 'Use a full link that starts with https://.';
  else if (looksLikeSecret(url)) e.runbookUrl = SECRET_MESSAGES.runbookUrl;
  if (f.owner.trim().length > 255) e.owner = 'Keep the owner under 255 characters.';
  if (f.notes.trim().length > 2000) e.notes = 'Keep the note under 2,000 characters.';
  else if (looksLikeSecret(f.notes)) e.notes = SECRET_MESSAGES.notes;
  return e;
}

/** A copyable code sample (the docs CodeBlock lives with the API docs page; this is the dialog-sized one). */
function Snippet({ label, code }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      notify.success('Copied to the clipboard');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify.error('Couldn’t copy — the browser blocked clipboard access. Select the text instead.');
    }
  };
  return (
    <div className="overflow-hidden rounded-control border border-border">
      <div className="flex items-center gap-2 border-b border-border bg-elevated/50 py-1 pl-3 pr-1">
        <span className="min-w-0 flex-1 truncate text-caption text-muted">{label}</span>
        <IconButton icon={copied ? Check : Copy} label={`Copy: ${label}`} size="sm" onClick={copy} />
      </div>
      <pre className="overflow-x-auto bg-surface/70 p-3 font-mono text-caption text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}

function ReportingHelp({ jobKey, body }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const origin = bareHost() || (typeof window !== 'undefined' ? window.location.origin : '');
  const { register, report } = reportingSnippets(jobKey, body);
  return (
    <div className="rounded-control border border-border bg-surface/60 sm:col-span-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-touch w-full items-center gap-2 rounded-control px-3 text-left text-body-sm font-medium text-fg transition-colors duration-fast hover:bg-elevated/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronRight aria-hidden="true" className={`h-4 w-4 shrink-0 text-muted transition-transform duration-fast ${open ? 'rotate-90' : ''}`} />
        How a script reports its runs
      </button>
      {open && (
        <div id={id} className="space-y-3 px-3 pb-3">
          <p className="text-body-sm text-muted">
            The script registers itself (safe to repeat on every run), then reports each run’s outcome. It needs a reporter key: an API key with the{' '}
            <code className="font-mono text-fg">autonomy:report</code> permission, which can register jobs and report runs and nothing else. Keep the key in
            the host’s secret store and read it as <code className="font-mono text-fg">$BRIGADE_REPORTER_KEY</code>; minting one is a deliberate step for an
            admin. Set <code className="font-mono text-fg">BRIGADE_URL</code> to <code className="break-words font-mono text-fg">{origin}</code>.
          </p>
          <Snippet label="Register — once, or on every run" code={register} />
          <Snippet label="Report — at the end of each run" code={report} />
        </div>
      )}
    </div>
  );
}

export default function AutonomyJobForm({ open, item, agents = [], existingKeys = new Set(), knownHosts = [], onClose, onSaved }) {
  const creating = !item;
  const [form, setForm] = useState(() => jobForm(null));
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [keyTouched, setKeyTouched] = useState(false);
  const nameRef = useRef(null);
  const hostsId = useId();
  const zonesId = useId();
  // ui/useFocusTrap re-runs — and pulls focus back to the first field — whenever
  // the dialog's onClose changes identity, so the dialog gets ONE close handler
  // that reads the latest props through refs.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const savingRef = useRef(false);
  savingRef.current = saving;
  const requestClose = useCallback(() => {
    if (!savingRef.current) onCloseRef.current?.();
  }, []);

  useEffect(() => {
    if (!open) return;
    setForm(jobForm(item));
    setErrors({});
    setFormError(null);
    setKeyTouched(Boolean(item));
  }, [open, item]);

  const set = (k) => (e) => {
    const v = e?.target ? e.target.value : e;
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === 'name' && creating && !keyTouched) next.key = slugify(v);
      return next;
    });
    if (errors[k]) setErrors((x) => ({ ...x, [k]: undefined }));
  };

  const roster = useMemo(
    () => [...agents].sort((a, b) => String(a.displayName || a.name).localeCompare(String(b.displayName || b.name))),
    [agents]
  );
  const unknownAgent = form.agentId && !roster.some((a) => a.id === form.agentId);
  const hosts = useMemo(() => [...new Set([...knownHosts, ...DEFAULT_HOSTS])], [knownHosts]);
  const zones = useMemo(() => timezoneChoices(form.timezone, viewerTimezone()).map(([v]) => v), [form.timezone]);
  const reading = form.schedule.trim() && !validateCron(form.schedule) ? describeSchedule(form.schedule, form.timezone.trim() || 'UTC') : null;
  const body = useMemo(() => jobBody(form), [form]);

  const submit = async (e) => {
    e.preventDefault();
    const errs = validate(form, { creating, existingKeys });
    setErrors(errs);
    setFormError(null);
    if (Object.values(errs).some(Boolean)) return;
    setSaving(true);
    try {
      const res = await apiJson(`/autonomy/jobs/${encodeURIComponent(form.key)}`, { method: 'PUT', body: JSON.stringify(body) });
      const name = res?.item?.name || body.name;
      notify.success(
        res?.created
          ? `“${name}” is in the catalogue. It shows its first run once the script reports.`
          : `“${name}” saved`
      );
      onSaved?.(res?.item || null, Boolean(res?.created));
      onCloseRef.current?.();
    } catch (err) {
      if (err?.status === 422) {
        const { fields, form: whole } = serverErrors(err);
        setErrors((x) => ({ ...x, ...fields }));
        setFormError(whole);
      } else {
        setFormError(humanize(err, { what: creating ? 'registering the job' : 'saving the job' }));
      }
    } finally {
      setSaving(false);
    }
  };

  const runnerHint = RUNNERS.find((r) => r.id === form.runner)?.hint;

  return (
    <Modal
      isOpen={open}
      onClose={requestClose}
      size="2xl"
      title={creating ? 'Register an outside job' : `Edit “${item?.name}”`}
      description={
        creating
          ? 'A loop that runs outside Brigade — a cron, a systemd timer, a LaunchAgent, a routine, a watcher. Once it’s registered its script reports each run, and the catalogue shows how it went.'
          : 'Changes apply to the catalogue at once. The script’s next registration overwrites them, so keep its PUT body in step.'
      }
      initialFocusRef={nameRef}
      footer={
        <>
          <Button variant="ghost" onClick={requestClose} disabled={saving}>
            Cancel
          </Button>
          <Button type="submit" form="autonomy-job-form" loading={saving}>
            {creating ? 'Register job' : 'Save changes'}
          </Button>
        </>
      }
    >
      <form id="autonomy-job-form" onSubmit={submit} noValidate className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {formError && (
          <p role="alert" className="rounded-control border border-danger/30 bg-danger/10 px-3 py-2 text-body-sm text-danger sm:col-span-2">
            {formError}
          </p>
        )}
        <Field label="Name" required error={errors.name}>
          <Input ref={nameRef} value={form.name} onChange={set('name')} placeholder="Build Log refresh" maxLength={255} />
        </Field>
        <Field
          label="Key"
          required
          error={errors.key}
          help={creating ? 'How the script reports in. Filled in from the name; you can change it now, not later.' : 'Fixed once registered — the script reports to this key.'}
        >
          <Input
            value={form.key}
            onChange={(e) => {
              setKeyTouched(true);
              set('key')({ target: { value: e.target.value.toLowerCase() } });
            }}
            readOnly={!creating}
            aria-readonly={!creating || undefined}
            placeholder="build-log-refresh"
            className="font-mono"
            spellCheck={false}
            autoCapitalize="off"
            maxLength={120}
          />
        </Field>
        <Field
          label="Responsibility"
          required
          error={errors.responsibility}
          help="One or two plain sentences: what this job is responsible for. It’s the line people read first in the catalogue."
          className="sm:col-span-2"
        >
          <Textarea
            rows={2}
            value={form.responsibility}
            onChange={set('responsibility')}
            maxLength={2000}
            placeholder="Turns the day’s commits into Build Log stories and redeploys the Build Log page."
          />
        </Field>
        <Field label="Agent" error={errors.agentId} help="The agent this job works for. Leave it empty for a plain script.">
          <Select value={form.agentId} onChange={set('agentId')}>
            <option value="">No agent</option>
            {unknownAgent && <option value={form.agentId}>{form.agentId} (not in the roster)</option>}
            {roster.map((a) => (
              <option key={a.id} value={a.id}>
                {a.displayName || a.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Owner" error={errors.owner} help="Who to ask when it breaks.">
          <Input value={form.owner} onChange={set('owner')} placeholder="Ops team" maxLength={255} />
        </Field>
        <Field label="Host" required error={errors.host} help="The machine it runs on.">
          <Input value={form.host} onChange={set('host')} list={hostsId} placeholder="build-server" spellCheck={false} autoCapitalize="off" maxLength={120} />
        </Field>
        <datalist id={hostsId}>
          {hosts.map((h) => (
            <option key={h} value={h} />
          ))}
        </datalist>
        <Field label="Runs as" required error={errors.runner} help={runnerHint}>
          <Select value={form.runner} onChange={set('runner')}>
            {RUNNERS.map((r) => (
              <option key={r.id} value={r.id}>
                {r.label}
              </option>
            ))}
          </Select>
        </Field>
        <Field
          label="Schedule (cron)"
          error={errors.schedule}
          help={reading || (form.schedule.trim() ? 'A custom schedule — the catalogue shows the raw cron.' : 'Five fields: minute hour day-of-month month weekday. Leave it empty for a watcher or an event-driven job.')}
        >
          <Input value={form.schedule} onChange={set('schedule')} placeholder="0 6,14,22 * * *" className="font-mono" spellCheck={false} autoCapitalize="off" maxLength={120} />
        </Field>
        <Field label="Time zone" error={errors.timezone} help="The zone of the host’s clock. Servers are usually UTC.">
          <Input value={form.timezone} onChange={set('timezone')} list={zonesId} placeholder="UTC" spellCheck={false} autoCapitalize="off" maxLength={64} />
        </Field>
        <datalist id={zonesId}>
          {zones.map((z) => (
            <option key={z} value={z} />
          ))}
        </datalist>
        <Field
          label="Schedule note"
          error={errors.scheduleNote}
          help="For a job without a cron: “continuous”, “on every push”, “when a recording lands”."
          className="sm:col-span-2"
        >
          <Input value={form.scheduleNote} onChange={set('scheduleNote')} placeholder="Continuous: wakes when a recording lands in the archive" maxLength={255} />
        </Field>
        <Field label="Command" error={errors.command} help="The script path or entry point. Never a secret: reference keys by name." className="sm:col-span-2">
          <Input
            value={form.command}
            onChange={set('command')}
            placeholder="/opt/jobs/nightly-report.sh"
            className="font-mono"
            spellCheck={false}
            autoCapitalize="off"
            maxLength={500}
          />
        </Field>
        <Field label="Runbook link" error={errors.runbookUrl} help="Where to look when it fails." className="sm:col-span-2">
          <Input type="url" value={form.runbookUrl} onChange={set('runbookUrl')} placeholder="https://…" spellCheck={false} autoCapitalize="off" maxLength={500} />
        </Field>
        <Field
          label="Notes"
          error={errors.notes}
          help="What an audit found: where it lives, what is wrong with it. Start with BROKEN, FAILING or ORPHAN to flag it — a flagged job counts as needing attention."
          className="sm:col-span-2"
        >
          <Textarea
            rows={2}
            value={form.notes}
            onChange={set('notes')}
            maxLength={2000}
            placeholder="BROKEN: the script is missing. Found in: build-server crontab, line 7."
          />
        </Field>
        <div className="flex items-center justify-between gap-3 rounded-control border border-border bg-surface/60 px-3 py-2 sm:col-span-2">
          <div>
            <p className="text-body-sm font-medium text-fg">Enabled</p>
            <p className="text-caption text-muted">A paused job stays in the catalogue, has no next run and is never flagged stale.</p>
          </div>
          <Toggle checked={Boolean(form.enabled)} onChange={(v) => setForm((f) => ({ ...f, enabled: v }))} label="Enabled" />
        </div>
        <ReportingHelp jobKey={form.key} body={body} />
      </form>
    </Modal>
  );
}
