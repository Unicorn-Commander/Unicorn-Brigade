/**
 * Autonomous — the Command Center view that catalogues every agent job that
 * runs on its own (Aaron, 2026-10-24: "we need a catalogue of what their
 * responsibility is"). Brigade's own scheduled runs AND the loops outside it —
 * cron on a server, a systemd timer, LaunchAgents on a Mac, Claude Code
 * routines, continuous watchers — grouped by the agent responsible.
 *
 * Each job leads with its RESPONSIBILITY (the sentence people read), then the
 * fleet audit's note when there is one, where and how it runs, when it runs
 * next, and how its last run went — with the reason, in words, when it failed.
 * Health (ok · failing · stale · never ran · paused) is the API's verdict.
 *
 * Built for the real fleet (~210 jobs, ~60 agents, a 70-job unclaimed infra
 * group): it opens on "Needs attention" when anything is failing, stale or
 * flagged by the audit (BROKEN / FAILING / ORPHAN); every group folds and says
 * its count and health in its header; the unclaimed jobs are sub-grouped by
 * owner and host; host and runner filters and a search narrow the rest.
 *
 * Data: the Command Center's single useAutonomy() instance (GET /autonomy,
 * every 60 s) arrives as `autonomy`, shared with the org-chart badges.
 * Writes: POST /scheduled-runs/{id}/run-now (Brigade items),
 * PUT / DELETE /autonomy/jobs/{key} (outside jobs), GET …/runs (history).
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowUpRight,
  BookOpen,
  CalendarClock,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  History,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Repeat,
  Search,
  Trash2,
} from 'lucide-react';
import notify from '../../utils/notify';
import { humanize } from '../../utils/errors';
import { apiJson } from '../../services/http';
import { roleLine } from '../../utils/agentClass';
import { describeSchedule, zoneLabel } from '../../utils/cron';
import {
  HEALTH,
  HEALTH_ORDER,
  NO_AGENT,
  NO_AGENT_ICON,
  domIdFor,
  durationText,
  groupByAgent,
  groupByOwnerAndHost,
  healthMeta,
  healthTally,
  hostLabel,
  isFailure,
  matchesQuery,
  needsAttention,
  nextRunText,
  noteFlag,
  reasonText,
  runStatusMeta,
  runnerIcon,
  runnerLabel,
  whereItRuns, itemHealth } from '../../utils/autonomy';
import { useAgo } from '../../hooks/useAgo';
import AgentAvatar from '../AgentAvatar';
import AutonomyNote from '../AutonomyNote';
import { relativeTime, absoluteTime } from '../ActivityFeed';
import AutonomyJobForm from './AutonomyJobForm';
import AutonomyRunsSheet from './AutonomyRunsSheet';
import { useReducedMotion } from './media';
import { Button, Card, Chip, EmptyState, ErrorState, IconButton, Input, Menu, Modal, OfflineState, SectionHeader, Select, StatusDot, Tabs, Tooltip } from '../ui';

const FILTERS = [
  { id: 'attention', label: 'Needs attention' },
  { id: 'all', label: 'All' },
  { id: 'brigade', label: 'In Brigade' },
  { id: 'external', label: 'Outside Brigade' },
];
const inFilter = (it, f) => f === 'all' || (f === 'attention' ? needsAttention(it) : it.source === f);
// Above this many groups, groups with nothing wrong start folded.
const FOLD_ABOVE_GROUPS = 6;
// Above this many unclaimed jobs, their owner·host sub-groups with nothing wrong start folded.
const FOLD_ABOVE_UNCLAIMED = 8;
const groupDomId = (key) => domIdFor('autonomy-group', key);

/** The schedule in words: "Daily at 06:00, 14:00 and 22:00 UTC", the note, or the raw cron. */
function scheduleText(item) {
  if (item.schedule) return describeSchedule(item.schedule, item.timezone) || `cron ${item.schedule} ${zoneLabel(item.timezone)}`;
  if (item.scheduleNote) return item.scheduleNote;
  return item.runner === 'continuous' ? 'Runs continuously' : 'No schedule recorded';
}

function HealthChip({ item }) {
  const h = itemHealth(item);
  return (
    <Tooltip content={h.why}>
      <span>
        <Chip tone={h.tone} size="xs" dot>
          {h.label}
        </Chip>
      </span>
    </Tooltip>
  );
}

/** "2 failing · 1 stale · 5 OK" as quiet chips — what a folded group is hiding. */
function HealthSummary({ items, className = '' }) {
  const t = healthTally(items);
  const flaggedOnly = items.filter((it) => noteFlag(it.notes) && it.health !== 'failing' && it.health !== 'stale').length;
  return (
    <span className={`flex-wrap items-center gap-1 ${className}`}>
      {HEALTH_ORDER.filter((h) => t[h]).map((h) => (
        <Chip key={h} tone={HEALTH[h].tone} size="xs" dot>
          {t[h]} {HEALTH[h].short}
        </Chip>
      ))}
      {flaggedOnly > 0 && (
        <Chip tone="warn" size="xs">
          {flaggedOnly} flagged
        </Chip>
      )}
    </span>
  );
}

/** How the last run went — and why it failed, in danger text. */
function LastRun({ item }) {
  if (item.lastStatus === 'running') {
    return (
      <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm text-fg">
        <StatusDot status="tool" size="md" />
        <span className="font-medium">Running now</span>
        {item.lastRunAt && (
          <Tooltip content={absoluteTime(item.lastRunAt, item.timezone)}>
            <time dateTime={item.lastRunAt} className="text-muted">
              started {relativeTime(item.lastRunAt)}
            </time>
          </Tooltip>
        )}
      </p>
    );
  }
  if (!item.lastRunAt) {
    return (
      <p className="mt-2 text-body-sm text-subtle">
        {item.source === 'external' ? 'Not reporting yet. It runs outside Brigade; add the report line to its script and each run lands here.' : 'Never ran yet. The first run lands here.'}
      </p>
    );
  }
  const s = runStatusMeta(item.lastStatus);
  const took = durationText(item.lastDurationMs);
  // The API's health decides "failing" — a status outside the enum ("degraded") included.
  const failing = item.health === 'failing';
  const verb = s.unknown
    ? null
    : item.lastStatus === 'success'
      ? `succeeded${took ? ` in ${took}` : ''}`
      : item.lastStatus === 'error'
        ? `failed${took ? ` after ${took}` : ''}`
        : item.lastStatus === 'timeout'
          ? `timed out${took ? ` after ${took}` : ''}`
          : item.lastStatus === 'skipped'
            ? 'skipped'
            : 'reported in';
  const reason = reasonText(item.lastError || (failing ? item.lastSummary : null));
  return (
    <div className="mt-2 space-y-1">
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-body-sm text-muted">
        {!s.unknown && <StatusDot status={s.dot} size="md" label={s.label} className="mr-0.5" />}
        <span>Last run</span>
        <Tooltip content={absoluteTime(item.lastRunAt, item.timezone)}>
          <time dateTime={item.lastRunAt} className="text-fg">
            {relativeTime(item.lastRunAt)}
          </time>
        </Tooltip>
        <span aria-hidden="true">·</span>
        {s.unknown ? (
          <>
            <Tooltip content="A status outside the usual set, shown as the job reported it">
              <span>
                <Chip tone="warn" size="xs">
                  {s.label}
                </Chip>
              </span>
            </Tooltip>
            {took && <span>after {took}</span>}
          </>
        ) : (
          <span className={isFailure(item.lastStatus) ? 'font-medium text-danger' : 'text-fg'}>{verb}</span>
        )}
      </p>
      {failing ? (
        <p className="text-body-sm text-danger">
          {reason || `No reason was reported. Check the job’s own log${item.host && item.host !== 'brigade' ? ` on ${item.host}` : ''}.`}
        </p>
      ) : item.lastSummary ? (
        <p className="line-clamp-2 text-body-sm text-muted">{reasonText(item.lastSummary)}</p>
      ) : null}
    </div>
  );
}

function JobRow({ item, runBusy, onRunNow, onEdit, onHistory, onRemove }) {
  const RunnerIcon = runnerIcon(item.runner);
  const brigade = item.source === 'brigade';
  const sched = scheduleText(item);
  const menu = brigade ? null : (
    <Menu
      align="end"
      trigger={({ props }) => <IconButton icon={MoreHorizontal} label={`More for ${item.name}`} size="sm" variant="ghost" {...props} />}
      items={[
        { id: 'edit', label: 'Edit', icon: Pencil, onSelect: () => onEdit(item) },
        { id: 'history', label: 'Run history', icon: History, onSelect: () => onHistory(item) },
        { type: 'separator' },
        { id: 'remove', label: 'Remove from the catalogue', icon: Trash2, tone: 'danger', onSelect: () => onRemove(item) },
      ]}
    />
  );
  const hasPhoneActions = brigade || Boolean(item.runbookUrl);
  return (
    <li className="grid grid-cols-1 gap-3 px-4 py-4 sm:px-5 md:grid-cols-[minmax(0,1fr)_auto] md:gap-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="min-w-0 break-words text-body-sm font-semibold text-fg">{item.name}</h4>
          <HealthChip item={item} />
          {item.lastStatus === 'running' && (
            <Chip tone="live" size="xs" dot pulse>
              Running
            </Chip>
          )}
          {menu && <div className="-my-1 ml-auto md:hidden">{menu}</div>}
        </div>
        {item.responsibility ? (
          <p className="mt-1 text-lead text-fg-strong">{item.responsibility}</p>
        ) : (
          <p className="mt-1 text-body text-subtle">
            No responsibility written yet.{' '}
            {brigade && (
              <Button as={Link} to={`/scheduled-runs?edit=${encodeURIComponent(item.scheduledRunId || item.key)}`} variant="link" size="sm">
                Write one
              </Button>
            )}
          </p>
        )}
        <AutonomyNote notes={item.notes} className="mt-1" />
        <p className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-body-sm text-muted">
          <span className="inline-flex items-center gap-1.5">
            <RunnerIcon aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-subtle" />
            {whereItRuns(item)}
          </span>
          <span aria-hidden="true">·</span>
          {item.schedule ? (
            <Tooltip content={`cron ${item.schedule} · ${item.timezone || 'UTC'}`}>
              <span>{sched}</span>
            </Tooltip>
          ) : (
            <span>{sched}</span>
          )}
          {!item.enabled ? (
            <>
              <span aria-hidden="true">·</span>
              <span>paused, no next run</span>
            </>
          ) : item.nextRunAt ? (
            <>
              <span aria-hidden="true">·</span>
              <Tooltip content={absoluteTime(item.nextRunAt, item.timezone)}>
                <time dateTime={item.nextRunAt}>{nextRunText(item.nextRunAt, relativeTime)}</time>
              </Tooltip>
            </>
          ) : null}
          {item.owner && item.agentId && !brigade && (
            <>
              <span aria-hidden="true">·</span>
              <span>owner {item.owner}</span>
            </>
          )}
        </p>
        <LastRun item={item} />
      </div>

      <div className={`${hasPhoneActions ? 'flex' : 'hidden md:flex'} flex-wrap items-start gap-2 md:justify-end`}>
        {brigade ? (
          <>
            <Tooltip content={item.enabled ? 'Run it now, outside its schedule' : 'It’s paused: this runs it once without turning the schedule back on'}>
              <Button size="sm" variant="secondary" icon={Play} loading={runBusy} onClick={() => onRunNow(item)}>
                {item.enabled ? 'Run now' : 'Run once'}
              </Button>
            </Tooltip>
            <Button as={Link} to={`/scheduled-runs?open=${encodeURIComponent(item.scheduledRunId || item.key)}`} size="sm" variant="ghost" icon={CalendarClock}>
              Open schedule
            </Button>
          </>
        ) : (
          <>
            {item.runbookUrl && (
              <Button as="a" href={item.runbookUrl} target="_blank" rel="noreferrer" size="sm" variant="ghost" icon={BookOpen}>
                Runbook
              </Button>
            )}
            <div className="hidden md:block">{menu}</div>
          </>
        )}
      </div>
    </li>
  );
}

/**
 * An accordion header (a real button in a heading): chevron, face, title,
 * the health of what it holds, and its job count. `trailing` sits outside the
 * button (a link can't live inside one).
 */
function FoldHeader({ as: Heading = 'h3', bodyId, open, onToggle, lead, title, subtitle, items, trailing, tone = 'group' }) {
  const count = `${items.length} job${items.length === 1 ? '' : 's'}`;
  return (
    <div className={`flex items-center gap-2 ${tone === 'group' ? 'px-3 py-2.5 sm:px-4' : 'border-t border-border/60 bg-surface/40 px-3 py-1.5 sm:px-4'}`}>
      <Heading className="min-w-0 flex-1">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={onToggle}
          className="flex min-h-touch w-full min-w-0 items-center gap-3 rounded-control px-1 text-left transition-colors duration-fast hover:bg-elevated/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronRight aria-hidden="true" className={`h-4 w-4 shrink-0 text-muted transition-transform duration-fast ${open ? 'rotate-90' : ''}`} />
          {lead}
          <span className="min-w-0 flex-1">
            <span className={`block truncate ${tone === 'group' ? 'text-lead font-semibold text-fg-strong' : 'text-body-sm font-semibold text-fg'}`}>{title}</span>
            {subtitle && <span className="block truncate text-body-sm text-muted">{subtitle}</span>}
            <HealthSummary items={items} className="mt-1 flex sm:hidden" />
          </span>
          <HealthSummary items={items} className="hidden justify-end sm:flex" />
          <span className="shrink-0 text-caption tabular-nums text-muted">{count}</span>
        </button>
      </Heading>
      {trailing}
    </div>
  );
}

function AgentGroup({ group, open, onToggle, isSubOpen, onToggleSub, highlighted, rowProps }) {
  const { agent, agentId, items } = group;
  const none = group.key === NO_AGENT;
  const name = none ? 'No agent assigned' : agent?.displayName || agent?.name || agentId;
  const sub = none
    ? 'Unclaimed scripts and watchers, by owner and host.'
    : agent
      ? roleLine(agent)
      : 'Not in the roster — the agent may have been removed or renamed.';
  const Icon = NO_AGENT_ICON;
  const domId = groupDomId(group.key);
  const rows = (list) => (
    <ul className="divide-y divide-border/60" aria-label={`${name}: jobs that run on their own`}>
      {list.map((it) => (
        <JobRow key={it.id} item={it} runBusy={rowProps.runningIds.has(it.id)} {...rowProps} />
      ))}
    </ul>
  );
  return (
    <Card as="section" padding="none" id={domId} aria-label={name} className={`scroll-mt-4 overflow-hidden transition-shadow duration-slow ${highlighted ? 'ring-2 ring-accent' : ''}`}>
      <FoldHeader
        bodyId={`${domId}-body`}
        open={open}
        onToggle={onToggle}
        lead={
          agent ? (
            <AgentAvatar agent={agent} size={40} rounded="rounded-full" />
          ) : (
            <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-elevated text-muted">
              <Icon className="h-5 w-5" />
            </span>
          )
        }
        title={name}
        subtitle={sub}
        items={items}
        trailing={
          agent ? (
            <IconButton as={Link} to={`/agent/${encodeURIComponent(agentId)}`} icon={ArrowUpRight} label={`Open ${name}’s page`} size="sm" variant="ghost" />
          ) : null
        }
      />
      {open && (
        <div id={`${domId}-body`} className="border-t border-border">
          {none
            ? groupByOwnerAndHost(items).map((s) => {
                const subOpen = isSubOpen(s, items.length);
                const subId = `${domId}-${encodeURIComponent(s.key)}`;
                return (
                  <div key={s.key}>
                    <FoldHeader
                      as="h4"
                      tone="sub"
                      bodyId={subId}
                      open={subOpen}
                      onToggle={() => onToggleSub(s, items.length)}
                      title={
                        <>
                          {s.owner || 'No owner named'}
                          <span className="font-normal text-muted"> · {s.host ? `on ${s.host}` : 'no host'}</span>
                        </>
                      }
                      items={s.items}
                    />
                    {subOpen && <div id={subId}>{rows(s.items)}</div>}
                  </div>
                );
              })
            : rows(items)}
        </div>
      )}
    </Card>
  );
}

/** The loading state: agent cards with job rows, no spinner, no layout shift. */
function CatalogueSkeleton() {
  const Bone = ({ className = '' }) => <div className={`rounded-chip bg-elevated/80 ${className}`} />;
  return (
    <div role="status" aria-busy="true" aria-label="Loading the catalogue" className="animate-pulse space-y-4">
      {[2, 1, 2].map((rows, g) => (
        <div key={g} className="overflow-hidden rounded-card border border-border bg-card">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3 sm:px-5">
            <Bone className="h-10 w-10 rounded-full" />
            <div className="flex-1 space-y-2">
              <Bone className="h-4 w-40" />
              <Bone className="h-3 w-56 max-w-full" />
            </div>
            <Bone className="hidden h-4 w-24 sm:block" />
          </div>
          {Array.from({ length: rows }).map((_, i) => (
            <div key={i} className="space-y-2.5 border-b border-border/60 px-4 py-4 last:border-b-0 sm:px-5">
              <div className="flex items-center gap-2">
                <Bone className="h-3.5 w-32" />
                <Bone className="h-4 w-14" />
              </div>
              <Bone className="h-4 w-3/4" />
              <Bone className="h-3 w-1/2" />
              <Bone className="h-3 w-2/5" />
            </div>
          ))}
        </div>
      ))}
      <span className="sr-only">Loading the catalogue…</span>
    </div>
  );
}

export default function AutonomousView({ autonomy, agents = [], focusAgentId = null, onFocusHandled }) {
  const navigate = useNavigate();
  const reducedMotion = useReducedMotion();
  const { data, items, loading, refreshing, error: loadError, updatedAt, reload, removeItem } = autonomy;
  const ago = useAgo(updatedAt);

  const [filter, setFilter] = useState(null); // decided once the first list lands
  const [host, setHost] = useState('');
  const [runner, setRunner] = useState('');
  const [query, setQuery] = useState('');
  const [openGroups, setOpenGroups] = useState({}); // key → open, once the person has chosen
  const [openSubs, setOpenSubs] = useState({});
  const [editing, setEditing] = useState(null); // null | { item: null } (register) | { item } (edit)
  const [historyFor, setHistoryFor] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [removeBusy, setRemoveBusy] = useState(false);
  const [runningIds, setRunningIds] = useState(() => new Set());
  const [highlight, setHighlight] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const timers = useRef([]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      reload({ silent: true });
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
      timers.current.forEach(clearTimeout);
    };
  }, [reload]);

  // Open on what needs a person: "Needs attention" when anything is failing,
  // stale or flagged by the audit, otherwise everything. Decided once.
  useEffect(() => {
    if (filter === null && data) setFilter(data.items.some(needsAttention) ? 'attention' : 'all');
  }, [filter, data]);
  const activeFilter = filter || 'all';

  const rosterById = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
  const q = query.trim();
  // Host, runner and search narrow everything; the tabs then split what is left.
  const narrowed = useMemo(
    () =>
      items.filter(
        (it) => (!host || it.host === host) && (!runner || it.runner === runner) && matchesQuery(it, rosterById.get(it.agentId) || it.agent, q)
      ),
    [items, host, runner, q, rosterById]
  );
  const tabCounts = useMemo(() => {
    const c = { all: narrowed.length, attention: 0, brigade: 0, external: 0 };
    for (const it of narrowed) {
      if (needsAttention(it)) c.attention += 1;
      c[it.source] = (c[it.source] || 0) + 1;
    }
    return c;
  }, [narrowed]);
  const visible = useMemo(() => narrowed.filter((it) => inFilter(it, activeFilter)), [narrowed, activeFilter]);
  const groups = useMemo(() => groupByAgent(visible, rosterById), [visible, rosterById]);
  const totals = useMemo(() => healthTally(items), [items]);
  const flaggedOnly = useMemo(() => items.filter((it) => noteFlag(it.notes) && it.health !== 'failing' && it.health !== 'stale').length, [items]);
  const hosts = useMemo(() => [...new Set(items.map((it) => it.host).filter(Boolean))].sort((a, b) => (a === 'brigade' ? -1 : b === 'brigade' ? 1 : a.localeCompare(b))), [items]);
  const runners = useMemo(() => [...new Set(items.map((it) => it.runner).filter(Boolean))].sort((a, b) => runnerLabel(a).localeCompare(runnerLabel(b))), [items]);
  const existingKeys = useMemo(() => new Set(items.filter((it) => it.source === 'external').map((it) => it.key)), [items]);
  const knownHosts = useMemo(() => hosts.filter((h) => h !== 'brigade'), [hosts]);

  // Folding: at scale, a group with nothing wrong starts folded; the person's
  // own choice (a click, Expand all, Collapse all) always wins.
  const many = groups.length > FOLD_ABOVE_GROUPS;
  const isOpen = useCallback((g) => openGroups[g.key] ?? (!many || g.items.some(needsAttention)), [openGroups, many]);
  const toggleGroup = (g) => setOpenGroups((s) => ({ ...s, [g.key]: !isOpen(g) }));
  const isSubOpen = useCallback((s, unclaimed) => openSubs[s.key] ?? (unclaimed <= FOLD_ABOVE_UNCLAIMED || s.items.some(needsAttention)), [openSubs]);
  const toggleSub = (s, unclaimed) => setOpenSubs((m) => ({ ...m, [s.key]: !isSubOpen(s, unclaimed) }));
  const setAllOpen = (open) => {
    setOpenGroups(Object.fromEntries(groups.map((g) => [g.key, open])));
    const unclaimed = groups.find((g) => g.key === NO_AGENT);
    setOpenSubs(unclaimed ? Object.fromEntries(groupByOwnerAndHost(unclaimed.items).map((s) => [s.key, open])) : {});
  };

  // Deep link from the org chart's clock badge or an agent's page: show that
  // agent's card — unfolded, scrolled into view and ringed for a moment. The
  // request is taken into a ref (and acknowledged) at once and carried out on
  // the first render that has data, so a slow first load still lands on it.
  const pendingFocus = useRef(null);
  useEffect(() => {
    if (!focusAgentId) return;
    pendingFocus.current = focusAgentId;
    onFocusHandled?.();
  }, [focusAgentId, onFocusHandled]);
  useEffect(() => {
    const id = pendingFocus.current;
    if (!id || !data) return;
    pendingFocus.current = null;
    setFilter('all');
    setHost('');
    setRunner('');
    setQuery('');
    setOpenGroups((s) => ({ ...s, [id]: true }));
    // Two frames: one for the filter reset to render, one for layout.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        document.getElementById(groupDomId(id))?.scrollIntoView({ block: 'start', behavior: reducedMotion ? 'auto' : 'smooth' });
        setHighlight(id);
        timers.current.push(setTimeout(() => setHighlight(null), 2600));
      })
    );
  });

  const runNow = useCallback(
    async (item) => {
      setRunningIds((s) => new Set(s).add(item.id));
      try {
        await apiJson(`/scheduled-runs/${encodeURIComponent(item.scheduledRunId || item.key)}/run-now`, {
          method: 'POST',
          body: JSON.stringify(item.enabled ? {} : { allowDisabled: true }),
        });
        notify.success(`“${item.name}” is running`);
        reload({ silent: true });
        // One follow-up read so the result lands without waiting a minute.
        timers.current.push(setTimeout(() => reload({ silent: true }), 8000));
      } catch (err) {
        notify.error(humanize(err, { what: 'starting the run' }));
      } finally {
        setRunningIds((s) => {
          const n = new Set(s);
          n.delete(item.id);
          return n;
        });
      }
    },
    [reload]
  );

  const confirmRemove = async () => {
    if (!removing) return;
    setRemoveBusy(true);
    try {
      await apiJson(`/autonomy/jobs/${encodeURIComponent(removing.key)}`, { method: 'DELETE' });
      notify.success(`“${removing.name}” is out of the catalogue`);
      removeItem(removing.id);
      setRemoving(null);
      reload({ silent: true });
    } catch (err) {
      notify.error(humanize(err, { what: 'removing the job' }));
    } finally {
      setRemoveBusy(false);
    }
  };

  const openRegister = () => setEditing({ item: null });
  // Dialog close handlers keep one identity for the view's lifetime: ui/useFocusTrap
  // re-runs (and moves focus) whenever onClose changes, and this view re-renders
  // every 5 s for its "updated Ns ago" chip.
  const removeBusyRef = useRef(false);
  removeBusyRef.current = removeBusy;
  const closeEditor = useCallback(() => setEditing(null), []);
  const closeHistory = useCallback(() => setHistoryFor(null), []);
  const closeRemove = useCallback(() => {
    if (!removeBusyRef.current) setRemoving(null);
  }, []);
  const editFromHistory = useCallback((item) => {
    setHistoryFor(null);
    setEditing({ item });
  }, []);
  const reloadSilently = useCallback(() => reload({ silent: true }), [reload]);
  const narrowing = Boolean(host || runner || q);
  const clearFilters = () => {
    setHost('');
    setRunner('');
    setQuery('');
    setFilter('all');
  };

  const summary = !items.length
    ? 'Every agent job that runs on its own, in Brigade and outside it'
    : [
        `${items.length} job${items.length === 1 ? ' runs on its own' : 's run on their own'}`,
        totals.failing ? `${totals.failing} failing` : null,
        totals.stale ? `${totals.stale} stale` : null,
        flaggedOnly ? `${flaggedOnly} flagged by the audit` : null,
      ]
        .filter(Boolean)
        .join(' · ');

  const missingEndpoint = loadError?.status === 404;
  let body;
  if (offline && !items.length) {
    body = <OfflineState onRetry={() => reload()} />;
  } else if (loading && !data) {
    body = <CatalogueSkeleton />;
  } else if (loadError && !data) {
    body = (
      <ErrorState
        title={missingEndpoint ? 'This server doesn’t have the catalogue yet' : 'Couldn’t load the catalogue'}
        detail={
          missingEndpoint
            ? 'The Brigade API here has no /autonomy endpoint. It ships with the autonomy catalogue backend; once that is deployed, this view fills in.'
            : humanize(loadError, { what: 'loading the catalogue' })
        }
        onRetry={() => reload()}
      />
    );
  } else if (!items.length) {
    body = (
      <EmptyState
        icon={Repeat}
        title="Nothing runs on its own yet"
        description="This is the catalogue of every job an agent does without being asked: Brigade’s scheduled runs, and loops that live outside Brigade — a cron job on a server, a LaunchAgent on a Mac, a Claude Code routine, a watcher that never sleeps. Schedule one here, or register an outside job so its runs report in."
        action={
          <Button icon={Plus} onClick={openRegister}>
            Register an outside job
          </Button>
        }
        secondary={
          <Button variant="secondary" icon={CalendarClock} onClick={() => navigate('/scheduled-runs?new=1')}>
            New Brigade schedule
          </Button>
        }
      />
    );
  } else if (!groups.length) {
    const calm = activeFilter === 'attention' && !narrowing;
    body = (
      <EmptyState
        compact
        icon={Search}
        title={calm ? 'Nothing needs attention' : q ? `No job matches “${q}”` : 'No job matches these filters'}
        description={
          calm
            ? 'No job is failing, stale or flagged by the audit right now.'
            : 'Try another host or runner, or a word from the name, the responsibility, the host or the owner.'
        }
        action={
          calm ? (
            <Button variant="secondary" size="sm" onClick={() => setFilter('all')}>
              Show all {items.length} jobs
            </Button>
          ) : (
            <Button variant="secondary" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          )
        }
      />
    );
  } else {
    body = (
      <div className="space-y-4">
        {groups.map((g) => (
          <AgentGroup
            key={g.key}
            group={g}
            open={isOpen(g)}
            onToggle={() => toggleGroup(g)}
            isSubOpen={isSubOpen}
            onToggleSub={toggleSub}
            highlighted={highlight === g.key}
            rowProps={{
              runningIds,
              onRunNow: runNow,
              onEdit: (item) => setEditing({ item }),
              onHistory: setHistoryFor,
              onRemove: setRemoving,
            }}
          />
        ))}
      </div>
    );
  }

  const showToolbar = Boolean(items.length);
  return (
    <div role="tabpanel" aria-labelledby="cc-view-autonomous" className="h-full overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl p-4 sm:p-6">
        <SectionHeader
          title="Autonomous jobs"
          description={summary}
          actions={
            <>
              {data && (
                <Tooltip content={loadError ? humanize(loadError, { what: 'refreshing the catalogue' }) : 'The catalogue refreshes every minute'}>
                  <span>
                    <Chip tone={loadError ? 'warn' : 'live'} size="sm" dot pulse={!loadError && refreshing}>
                      {loadError ? 'Refresh failed' : ago}
                    </Chip>
                  </span>
                </Tooltip>
              )}
              <IconButton icon={RefreshCw} label="Refresh the catalogue" size="sm" variant="ghost" onClick={() => reload({ silent: Boolean(data) })} loading={refreshing} />
              <Button size="sm" icon={Plus} onClick={openRegister}>
                Register an outside job
              </Button>
            </>
          }
        />

        {showToolbar && (
          <div className="mb-4 space-y-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="max-w-full overflow-x-auto">
                <Tabs
                  variant="segmented"
                  size="sm"
                  label="Filter the catalogue"
                  idBase="autonomy-filter"
                  value={activeFilter}
                  onChange={setFilter}
                  tabs={FILTERS.map((f) => ({ ...f, count: tabCounts[f.id] }))}
                />
              </div>
              <div className="relative md:w-72">
                <Search aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <Input
                  type="search"
                  size="sm"
                  aria-label="Search autonomous jobs"
                  placeholder="Search jobs, hosts, owners…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-8"
                />
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="w-[calc(50%-0.25rem)] sm:w-44">
                <Select size="sm" aria-label="Filter by host" value={host} onChange={(e) => setHost(e.target.value)}>
                  <option value="">All hosts</option>
                  {hosts.map((h) => (
                    <option key={h} value={h}>
                      {hostLabel(h)}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="w-[calc(50%-0.25rem)] sm:w-52">
                <Select size="sm" aria-label="Filter by runner" value={runner} onChange={(e) => setRunner(e.target.value)}>
                  <option value="">All runners</option>
                  {runners.map((r) => (
                    <option key={r} value={r}>
                      {runnerLabel(r)}
                    </option>
                  ))}
                </Select>
              </div>
              <p className="text-caption text-muted" aria-live="polite">
                {visible.length === items.length ? `All ${items.length} jobs` : `${visible.length} of ${items.length} jobs`} · {groups.length} group{groups.length === 1 ? '' : 's'}
              </p>
              {narrowing && (
                <Button variant="link" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              )}
              <div className="ml-auto flex items-center gap-1">
                <IconButton icon={ChevronsUpDown} label="Unfold every group" size="sm" variant="ghost" onClick={() => setAllOpen(true)} disabled={!groups.length} />
                <IconButton icon={ChevronsDownUp} label="Fold every group" size="sm" variant="ghost" onClick={() => setAllOpen(false)} disabled={!groups.length} />
              </div>
            </div>
          </div>
        )}

        {body}

        {showToolbar && groups.length > 0 && (
          <section aria-labelledby="autonomy-legend" className="mt-6 rounded-card border border-border bg-surface/60 p-4">
            <h3 id="autonomy-legend" className="mb-2.5 text-micro font-semibold uppercase tracking-wider text-muted">
              What the states mean
            </h3>
            <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
              {Object.entries(HEALTH).map(([id, h]) => (
                <div key={id} className="flex items-start gap-2">
                  <dt className="shrink-0">
                    <Chip tone={h.tone} size="xs" dot>
                      {h.label}
                    </Chip>
                  </dt>
                  <dd className="text-caption text-muted">{h.why}</dd>
                </div>
              ))}
              <div className="flex items-start gap-2">
                <dt className="shrink-0">
                  <Chip tone="warn" size="xs">
                    Flagged
                  </Chip>
                </dt>
                <dd className="text-caption text-muted">The fleet audit’s note opens with BROKEN, FAILING or ORPHAN. It counts as needing attention whatever the health says.</dd>
              </div>
            </dl>
          </section>
        )}
      </div>

      <AutonomyJobForm
        open={Boolean(editing)}
        item={editing?.item || null}
        agents={agents}
        existingKeys={existingKeys}
        knownHosts={knownHosts}
        onClose={closeEditor}
        onSaved={reloadSilently}
      />

      <AutonomyRunsSheet item={historyFor} onClose={closeHistory} onEdit={editFromHistory} />

      <Modal
        isOpen={Boolean(removing)}
        onClose={closeRemove}
        tone="danger"
        size="sm"
        title="Remove this job from the catalogue?"
        description={
          removing
            ? `“${removing.name}” and its run history leave the catalogue. The job itself keeps running on ${removing.host} — and if its script registers itself on every run, it comes back. To retire it, remove it from the host first.`
            : ''
        }
        footer={
          <>
            <Button variant="ghost" onClick={closeRemove} disabled={removeBusy}>
              Keep it
            </Button>
            <Button variant="danger" icon={Trash2} loading={removeBusy} onClick={confirmRemove}>
              Remove
            </Button>
          </>
        }
      />
    </div>
  );
}
