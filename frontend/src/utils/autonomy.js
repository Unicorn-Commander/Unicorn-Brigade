/**
 * The autonomy catalogue's shared vocabulary — every agent job that runs on
 * its own, in Brigade (scheduled runs) and outside it (cron on a server,
 * LaunchAgents on the Mac, Claude Code routines, continuous watchers).
 *
 * Used by the Command Center's Autonomous view, the org-chart badge and an
 * agent's "Runs on its own" card, so "stale" reads the same everywhere.
 * Shapes follow lane-reports/2026-10-24-brigade-uiux/autonomy/CONTRACT.md
 * (+ the coordinator's additions: `notes`, statuses outside the enum).
 */
import { Bot, CalendarClock, Cloud, Infinity as InfinityIcon, Laptop, Server, Terminal, Timer } from 'lucide-react';

// ── health (computed by the API; never by the browser) ──────────────────────
export const HEALTH = {
  failing: { tone: 'danger', label: 'Failing', short: 'failing', rank: 0, why: 'Its last run failed or timed out, or reported a problem.' },
  stale: { tone: 'warn', label: 'Stale', short: 'stale', rank: 1, why: 'It missed its schedule: no report for longer than one and a half intervals plus 15 minutes.' },
  never: { tone: 'neutral', label: 'No reports yet', short: 'no reports yet', rank: 2, why: 'Registered, but no run has been reported yet.' },
  ok: { tone: 'ok', label: 'OK', short: 'OK', rank: 3, why: 'Its last run went through and it reported on schedule.' },
  paused: { tone: 'neutral', label: 'Paused', short: 'paused', rank: 4, why: 'Turned off. A paused job is never flagged stale.' },
};
export const HEALTH_ORDER = ['failing', 'stale', 'never', 'ok', 'paused'];
export const healthMeta = (h) => HEALTH[h] || HEALTH.ok;

/**
 * The look of ONE item's health. "No reports yet" means different things by
 * source: a Brigade schedule that has never fired, versus an outside job that
 * runs every day but does not report yet (most of the fleet until its script
 * gets the report line). Say which, so a working cron never reads as idle.
 */
export function itemHealth(item) {
  const h = healthMeta(item?.health);
  if (item?.health !== 'never') return h;
  return item?.source === 'external'
    ? { ...h, label: 'Not reporting yet', why: 'It runs outside Brigade and has not reported a run yet. Add the report line to its script and each run lands here.' }
    : { ...h, label: 'Never ran', why: 'This Brigade schedule has not fired yet.' };
}

// ── notes: the fleet audit's observations ───────────────────────────────────
// A note that opens with one of these words is a finding, not a remark: it is
// tinted and it puts the job under "Needs attention" whatever its health says.
const NOTE_FLAGS = { BROKEN: 'danger', FAILING: 'danger', ORPHAN: 'warn' };
const NOTE_FLAG_RE = /^\s*(BROKEN|FAILING|ORPHAN)\b/i;

/** { word: 'BROKEN', tone: 'danger', rest: ': script missing…' } for a flagged note, else null. */
export function noteFlag(notes) {
  const m = NOTE_FLAG_RE.exec(String(notes || ''));
  if (!m) return null;
  const word = m[1].toUpperCase();
  return { word, tone: NOTE_FLAGS[word], rest: String(notes).slice(m.index + m[0].length) };
}

/** Failing, stale, or flagged by the audit (BROKEN / FAILING / ORPHAN). */
export const needsAttention = (it) => it.health === 'failing' || it.health === 'stale' || Boolean(noteFlag(it.notes));

/** Urgency for ordering: failing 0 · BROKEN/FAILING note 0.5 · stale 1 · ORPHAN note 1.5 · never 2 · ok 3 · paused 4. */
export function urgency(it) {
  const h = healthMeta(it.health).rank;
  const f = noteFlag(it.notes);
  if (!f) return h;
  return Math.min(h, f.tone === 'danger' ? 0.5 : 1.5);
}

// ── the outcome of one run ──────────────────────────────────────────────────
export const RUN_STATUS = {
  success: { tone: 'ok', label: 'Succeeded', dot: 'done' },
  error: { tone: 'danger', label: 'Failed', dot: 'error' },
  timeout: { tone: 'danger', label: 'Timed out', dot: 'error' },
  running: { tone: 'live', label: 'Running', dot: 'tool', pulse: true },
  skipped: { tone: 'neutral', label: 'Skipped', dot: 'idle' },
};
/**
 * The look of a run status. A status outside the contract's enum (real data
 * has "degraded") is shown as itself, in the warn tone — never guessed at;
 * the API's `health` decides whether it counts as failing.
 */
export function runStatusMeta(s) {
  if (RUN_STATUS[s]) return RUN_STATUS[s];
  if (s) return { tone: 'warn', label: String(s), dot: 'idle', unknown: true };
  return { tone: 'neutral', label: 'No result', dot: 'idle' };
}
export const isFailure = (s) => s === 'error' || s === 'timeout';

// ── runners: where and how a job runs ───────────────────────────────────────
export const RUNNERS = [
  { id: 'cron', label: 'cron', hint: 'A crontab line on the host', icon: Server },
  { id: 'systemd', label: 'systemd timer', hint: 'A .timer unit on a Linux host', icon: Server },
  { id: 'launchd', label: 'launchd (LaunchAgent)', hint: 'A LaunchAgent or LaunchDaemon on a Mac', icon: Laptop },
  { id: 'claude-routine', label: 'Claude Code routine', hint: 'A scheduled Claude Code agent', icon: Cloud },
  { id: 'continuous', label: 'Continuous watcher', hint: 'Always on; wakes on an event', icon: InfinityIcon },
  { id: 'other', label: 'Something else', hint: 'Any other scheduler', icon: Terminal },
];
const RUNNER_BY_ID = Object.fromEntries(RUNNERS.map((r) => [r.id, r]));
export const runnerLabel = (id) => (id === 'brigade-scheduler' ? 'Brigade scheduler' : RUNNER_BY_ID[id]?.label || id);
export const hostLabel = (host) => (host === 'brigade' ? 'Brigade' : host);

/** "Brigade scheduler" · "cron on build-server" · "launchd on studio-mac" · "Claude Code routine" · "continuous on build-server". */
export function whereItRuns(item) {
  const host = item.host && item.host !== 'brigade' ? item.host : null;
  switch (item.runner) {
    case 'brigade-scheduler':
      return 'Brigade scheduler';
    case 'cron':
    case 'systemd':
    case 'launchd':
      return host ? `${item.runner} on ${host}` : item.runner;
    case 'claude-routine':
      return host && host !== 'cloud' ? `Claude Code routine on ${host}` : 'Claude Code routine';
    case 'continuous':
      return host ? `continuous on ${host}` : 'continuous';
    default:
      return host ? `runs on ${host}` : 'runs outside Brigade';
  }
}
export function runnerIcon(runner) {
  if (runner === 'brigade-scheduler') return CalendarClock;
  return RUNNER_BY_ID[runner]?.icon || Timer;
}

// ── durations, reasons, next runs ───────────────────────────────────────────
/** 940 → "940 ms" · 94000 → "1 min 34 s" · 7200000 → "2 h"; null when no duration was recorded. */
export function durationText(ms) {
  if (ms === null || ms === undefined || ms === '') return null;
  const n = Number(ms);
  if (!Number.isFinite(n) || n < 0) return null;
  if (n < 1000) return `${Math.round(n)} ms`;
  if (n < 10000) return `${(n / 1000).toFixed(1)} s`;
  const s = Math.round(n / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return s % 60 ? `${m} min ${s % 60} s` : `${m} min`;
  const h = Math.floor(m / 60);
  return m % 60 ? `${h} h ${m % 60} min` : `${h} h`;
}

/** A reason or summary for display: Brigade's "error: …" / "degraded: …" prefix dropped, first letter up. */
export function reasonText(text) {
  const t = String(text || '')
    .replace(/^\s*(error|failed|skipped|degraded|warning)\s*:\s*/i, '')
    .trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : null;
}

/** "next run in 3 hours" — or "due now" once the time has passed and the next read hasn't landed yet. */
export function nextRunText(iso, relativeTime) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return t <= Date.now() ? 'next run due now' : `next run ${relativeTime(iso)}`;
}

// ── grouping ────────────────────────────────────────────────────────────────
export const NO_AGENT = '__no-agent__';

/** The agent to draw for an item: the roster's (richer, has the emoji) over the API's brief one. */
export function agentFor(item, rosterById) {
  if (!item.agentId) return null;
  return rosterById?.get(item.agentId) || item.agent || null;
}

/** { failing, stale, never, ok, paused, flagged } for a set of items. */
export function healthTally(items) {
  const t = { failing: 0, stale: 0, never: 0, ok: 0, paused: 0, flagged: 0 };
  for (const it of items) {
    if (t[it.health] !== undefined) t[it.health] += 1;
    if (noteFlag(it.notes)) t.flagged += 1;
  }
  return t;
}

const byUrgency = (list) =>
  list
    .map((it, i) => [it, i])
    .sort((a, b) => urgency(a[0]) - urgency(b[0]) || a[1] - b[1])
    .map(([it]) => it);
const worst = (list) => Math.min(...list.map(urgency));

/**
 * Items → [{ key, agent, agentId, items }] — one group per agent, the most
 * urgent first (a failing job puts its agent at the top), then by name; the
 * "No agent assigned" group always last. Inside a group the most urgent job
 * comes first, otherwise the API's order is kept.
 */
export function groupByAgent(items, rosterById) {
  const groups = new Map();
  for (const it of items) {
    const key = it.agentId || NO_AGENT;
    if (!groups.has(key)) groups.set(key, { key, agentId: it.agentId || null, agent: agentFor(it, rosterById), items: [] });
    groups.get(key).items.push(it);
  }
  const name = (g) => String(g.agent?.displayName || g.agent?.name || g.agentId || '').toLowerCase();
  return [...groups.values()]
    .map((g) => ({ ...g, items: byUrgency(g.items) }))
    .sort((a, b) => {
      if (a.key === NO_AGENT) return 1;
      if (b.key === NO_AGENT) return -1;
      return worst(a.items) - worst(b.items) || name(a).localeCompare(name(b));
    });
}

/** The unclaimed jobs, sub-grouped by owner and host: [{ key, owner, host, items }], most urgent first. */
export function groupByOwnerAndHost(items) {
  const subs = new Map();
  for (const it of items) {
    const owner = it.owner || '';
    const host = it.host || '';
    const key = `${owner}\u0000${host}`;
    if (!subs.has(key)) subs.set(key, { key, owner: owner || null, host: host || null, items: [] });
    subs.get(key).items.push(it);
  }
  return [...subs.values()]
    .map((s) => ({ ...s, items: byUrgency(s.items) }))
    .sort(
      (a, b) =>
        worst(a.items) - worst(b.items) ||
        String(a.owner || '~').localeCompare(String(b.owner || '~')) ||
        String(a.host || '').localeCompare(String(b.host || ''))
    );
}

/** Per-agent tallies for the org-chart badge: Map(agentId → { total, failing, stale }). */
export function countsByAgent(items) {
  const m = new Map();
  for (const it of items || []) {
    if (!it.agentId) continue;
    const c = m.get(it.agentId) || { total: 0, failing: 0, stale: 0 };
    c.total += 1;
    if (it.health === 'failing') c.failing += 1;
    if (it.health === 'stale') c.stale += 1;
    m.set(it.agentId, c);
  }
  return m;
}

/** "Runs on its own · 2 jobs · 1 failing" — the badge tooltip and the node's spoken line. */
export function autonomyLine(c) {
  if (!c?.total) return '';
  const parts = [`Runs on its own · ${c.total} job${c.total === 1 ? '' : 's'}`];
  if (c.failing) parts.push(`${c.failing} failing`);
  if (c.stale) parts.push(`${c.stale} stale`);
  return parts.join(' · ');
}

// ── search ──────────────────────────────────────────────────────────────────
export function matchesQuery(item, agent, q) {
  if (!q) return true;
  const hay = [
    item.name, item.responsibility, item.notes, item.key, item.host, item.runner, item.command, item.owner, item.scheduleNote,
    whereItRuns(item), agent?.displayName, agent?.name, agent?.title, item.agentId,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((w) => hay.includes(w));
}

// ── registering an outside job ──────────────────────────────────────────────
export const KEY_RE = /^[a-z0-9][a-z0-9-]{1,118}[a-z0-9]$/;

/** "Build Log refresh!" → "build-log-refresh". */
export function slugify(name) {
  return String(name || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120)
    .replace(/-+$/g, '');
}

// The API's secret check (app/services/autonomy.py, backend lane), mirrored so
// the form says it before the server does. Key shapes are anchored at a token
// boundary with a minimum length: real commands contain "sk-" inside words
// (disk-guard.sh, kiosk-chromium-refresh) and must not be refused. ubk- is
// Brigade's own key format and sbk- Stable's — the keys a script is handed.
const SECRET_RES = [
  /(password|passwd|secret|token|api[_-]?key)\s*[=:]/i,
  /:\/\/[^/\s:]+:[^@\s]+@/,
  /(?<![A-Za-z0-9])(?:(?:sk|ubk|sbk)-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abposr]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})/,
];
/** The API's words for a secret in each field it checks. */
export const SECRET_MESSAGES = {
  command: 'Don’t store secrets in the command; reference them by name.',
  runbookUrl: 'Don’t store secrets in the runbook URL; reference them by name.',
  notes: 'Don’t store secrets in the notes; reference them by name.',
};
export const SECRET_MESSAGE = SECRET_MESSAGES.command;
export const looksLikeSecret = (text) => Boolean(text) && SECRET_RES.some((re) => re.test(text));

/** The PUT /autonomy/jobs/{key} body from the form (camelCase, empty → null). */
export function jobBody(f) {
  const opt = (v) => {
    const t = String(v ?? '').trim();
    return t ? t : null;
  };
  return {
    name: String(f.name || '').trim(),
    responsibility: String(f.responsibility || '').trim(),
    agentId: opt(f.agentId),
    host: String(f.host || '').trim(),
    runner: f.runner,
    schedule: opt(f.schedule),
    timezone: opt(f.timezone) || 'UTC',
    scheduleNote: opt(f.scheduleNote),
    command: opt(f.command),
    runbookUrl: opt(f.runbookUrl),
    owner: opt(f.owner),
    notes: opt(f.notes),
    enabled: f.enabled !== false,
  };
}

/** The form's starting values: an existing item's, or a blank outside job. */
export function jobForm(item) {
  if (!item) {
    return { key: '', name: '', responsibility: '', agentId: '', host: '', runner: 'cron', schedule: '', timezone: 'UTC', scheduleNote: '', command: '', runbookUrl: '', owner: '', notes: '', enabled: true };
  }
  return {
    key: item.key,
    name: item.name || '',
    responsibility: item.responsibility || '',
    agentId: item.agentId || '',
    host: item.host || '',
    runner: item.runner || 'other',
    schedule: item.schedule || '',
    timezone: item.timezone || 'UTC',
    scheduleNote: item.scheduleNote || '',
    command: item.command || '',
    runbookUrl: item.runbookUrl || '',
    owner: item.owner || '',
    notes: item.notes || '',
    enabled: item.enabled !== false,
  };
}

/**
 * A 422 from the API → { fields: { name: '…' }, form: '…' }. FastAPI sends a
 * string `detail` for the hand-written checks (secrets, unknown agent, bad
 * cron) and pydantic's list ({ loc, msg }) for schema errors.
 */
const FIELD_ALIASES = { agent_id: 'agentId', schedule_note: 'scheduleNote', runbook_url: 'runbookUrl' };
const STRING_DETAIL_FIELDS = [
  [/runbook/i, 'runbookUrl'],
  [/\bnotes\b/i, 'notes'],
  [/command/i, 'command'],
  [/schedule note|scheduleNote/i, 'scheduleNote'],
  [/schedule|cron/i, 'schedule'],
  [/time ?zone/i, 'timezone'],
  [/agent/i, 'agentId'],
  [/\bkey\b|slug/i, 'key'],
  [/responsibility/i, 'responsibility'],
  [/\bhost\b/i, 'host'],
  [/runner/i, 'runner'],
  [/owner/i, 'owner'],
  [/\bname\b/i, 'name'],
];
export function serverErrors(err) {
  const detail = err?.data?.detail;
  const fields = {};
  if (Array.isArray(detail)) {
    for (const d of detail) {
      const loc = Array.isArray(d?.loc) ? d.loc : [];
      const raw = String(loc[loc.length - 1] ?? '');
      const name = FIELD_ALIASES[raw] || raw;
      const msg = String(d?.msg || '').replace(/^Value error,\s*/i, '');
      if (name && msg && !fields[name]) fields[name] = msg.endsWith('.') ? msg : `${msg}.`;
    }
    return { fields, form: Object.keys(fields).length ? null : 'Some of the details aren’t valid. Check the highlighted fields.' };
  }
  if (typeof detail === 'string' && detail) {
    // The API's hand-written messages name their field; the first match wins
    // ("…in the command; reference them by name" is the command, not the name).
    const field = STRING_DETAIL_FIELDS.find(([re]) => re.test(detail))?.[1];
    return field ? { fields: { [field]: detail }, form: null } : { fields, form: detail };
  }
  return { fields, form: null };
}

// ── "How a script reports its runs" ─────────────────────────────────────────
/** A JSON body inside single quotes for a POSIX shell (' becomes '\''), one field per line. */
const shellJson = (obj) => `'${JSON.stringify(obj, null, 2).replace(/\n/g, '\n  ').replace(/'/g, `'\\''`)}'`;

/**
 * The two curl lines from the contract, filled with this job's key and body.
 * $BRIGADE_URL and $BRIGADE_REPORTER_KEY stay variables: the key is never
 * written into a script (house rule — reference secrets by name).
 */
export function reportingSnippets(key, body) {
  const k = key || 'build-log-refresh';
  // Fields left empty are simply not sent (the API reads a missing field as empty).
  const sent = Object.fromEntries(Object.entries(body || {}).filter(([, v]) => v !== null && v !== undefined && v !== ''));
  const register = `# once, or on every run (idempotent)
curl -fsS -X PUT "$BRIGADE_URL/api/v1/autonomy/jobs/${k}" \\
  -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \\
  -d ${shellJson(sent)}`;
  const report = `# at the end of each run
curl -fsS -X POST "$BRIGADE_URL/api/v1/autonomy/jobs/${k}/runs" \\
  -H "X-API-Key: $BRIGADE_REPORTER_KEY" -H 'Content-Type: application/json' \\
  -d '{"status":"success","summary":"3 new day stories"}'
# when it fails, say why in words:
#   -d '{"status":"error","error":"git fetch failed: Forgejo answered 502"}'`;
  return { register, report };
}

/** The no-agent group's face. */
export const NO_AGENT_ICON = Bot;

/** An id as an HTML id fragment: ids can hold dots, slashes or spaces ("cpl.-colophon"), so encode, never splice. */
export const domIdFor = (prefix, id) => `${prefix}-${encodeURIComponent(String(id))}`;
