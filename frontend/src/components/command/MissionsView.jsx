/**
 * Missions — the Command Center view that replaced the separate Orchestration
 * page (Aaron, 2026-10-24: fold Orchestration into the Command Center).
 *
 * A mission is a task handed to The General, who picks the crew and
 * delegates. This view lists every mission with its status, progress, crew
 * (live faces from the same SSE stream as the board) and — when one failed —
 * the reason in human words; "Start a mission" posts a new one. The live
 * activity feed sits beside it so a delegation can be watched as it happens.
 *
 * Data: GET /orchestration/state (missions) every 30s and on demand;
 * POST /orchestration/missions to start one. Live agent status and events come
 * from the Command Center's single orchestration stream (props).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Play, RefreshCw, Target } from 'lucide-react';
import notify from '../../utils/notify';
import { humanize } from '../../utils/errors';
import { apiJson } from '../../services/http';
import AgentAvatar from '../AgentAvatar';
import { relativeTime, absoluteTime } from '../ActivityFeed';
import ActivityFeed from './ActivityFeed';
import {
  AGENT_STATUS,
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  LoadingState,
  Modal,
  SectionHeader,
  Textarea,
  Tooltip,
} from '../ui';

const REFRESH_MS = 30000;
const MISSION_STATUS = {
  active: { tone: 'live', label: 'Active', pulse: true },
  running: { tone: 'live', label: 'Active', pulse: true },
  pending: { tone: 'neutral', label: 'Queued' },
  completed: { tone: 'ok', label: 'Completed' },
  failed: { tone: 'danger', label: 'Failed' },
  cancelled: { tone: 'neutral', label: 'Cancelled' },
};
const missionStatus = (s) => MISSION_STATUS[s] || { tone: 'neutral', label: String(s || 'unknown') };
const isActive = (m) => m.status === 'active' || m.status === 'running';
const missionProgress = (m) => {
  if (m.status === 'completed') return 100;
  const p = Number(m.progress);
  if (!Number.isFinite(p)) return 0;
  return Math.round(p <= 1 ? p * 100 : p);
};

/** "updated 12s ago" that keeps itself current. */
function useAgo(since) {
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, []);
  if (!since) return 'updating…';
  const s = Math.max(0, Math.round((Date.now() - since) / 1000));
  if (s < 5) return 'updated just now';
  if (s < 60) return `updated ${s}s ago`;
  return `updated ${Math.round(s / 60)}m ago`;
}

function MissionCard({ mission, agentById, statusOf, onOpen }) {
  const s = missionStatus(mission.status);
  const pct = missionProgress(mission);
  const crew = (mission.agents || []).map((id) => agentById.get(id) || { id, name: id, unknown: true });
  const reason = mission.error || mission.reason || mission.lastError;
  return (
    <li className="rounded-card border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-body font-semibold text-fg-strong">{mission.name}</p>
          {mission.description && <p className="mt-0.5 line-clamp-2 text-body-sm text-muted">{mission.description}</p>}
        </div>
        <Chip tone={s.tone} size="xs" dot pulse={s.pulse}>
          {s.label}
        </Chip>
      </div>
      {mission.status === 'failed' && (
        <p className="mt-2 text-body-sm text-danger">{reason || 'No reason was recorded for this failure.'}</p>
      )}
      {isActive(mission) && (
        <div
          className="mt-3 h-1.5 overflow-hidden rounded-full bg-elevated"
          role="progressbar"
          aria-label={`${mission.name} progress`}
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div className="h-full rounded-full bg-accent-fill transition-[width] duration-slow ease-standard" style={{ width: `${pct}%` }} />
        </div>
      )}
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center -space-x-1.5">
          {crew.slice(0, 6).map((a) => (
            <Tooltip key={a.id} content={`${a.displayName || a.name} — open comms`}>
              <button
                type="button"
                onClick={() => !a.unknown && onOpen?.(a)}
                aria-label={`Open comms with ${a.displayName || a.name}`}
                className="relative inline-flex rounded-full ring-2 ring-card focus-visible:outline-none focus-visible:ring-ring [@media(pointer:coarse)]:after:absolute [@media(pointer:coarse)]:after:-inset-2.5 [@media(pointer:coarse)]:after:content-['']"
              >
                <AgentAvatar agent={a} size={24} rounded="rounded-full" status={statusOf(a.id)} />
              </button>
            </Tooltip>
          ))}
          {crew.length > 6 && <Chip size="xs" className="ml-2">+{crew.length - 6}</Chip>}
          {crew.length === 0 && <span className="text-caption text-subtle">The General is picking the crew</span>}
        </div>
        {mission.createdAt && (
          <Tooltip content={absoluteTime(mission.createdAt)}>
            <time dateTime={mission.createdAt} className="shrink-0 text-micro text-subtle">
              {relativeTime(mission.createdAt)}
            </time>
          </Tooltip>
        )}
      </div>
    </li>
  );
}

export default function MissionsView({ agents = [], statuses = {}, events = [], connected, onOpen }) {
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [form, setForm] = useState(null); // null | { name, task }
  const [formErrors, setFormErrors] = useState({});
  const [creating, setCreating] = useState(false);
  const ago = useAgo(updatedAt);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (silent) setRefreshing(true);
    else setLoading(true);
    try {
      const state = await apiJson('/orchestration/state');
      setMissions(Array.isArray(state?.missions) ? state.missions : []);
      setUpdatedAt(Date.now());
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(() => load({ silent: true }), REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const agentById = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
  const statusOf = useCallback((id) => (AGENT_STATUS[statuses[id]?.status] ? statuses[id].status : 'idle'), [statuses]);

  // Active first, then queued, then the rest newest first.
  const ordered = useMemo(() => {
    const rank = (m) => (isActive(m) ? 0 : m.status === 'pending' ? 1 : m.status === 'failed' ? 2 : 3);
    return [...missions].sort((a, b) => rank(a) - rank(b) || String(b.createdAt || '').localeCompare(String(a.createdAt || '')));
  }, [missions]);
  const activeCount = missions.filter(isActive).length;
  const failedCount = missions.filter((m) => m.status === 'failed').length;

  const openForm = () => {
    setForm({ name: '', task: '' });
    setFormErrors({});
  };

  const submit = async (e) => {
    e.preventDefault();
    const name = form.name.trim();
    const task = form.task.trim();
    const errs = {};
    if (!name) errs.name = 'Give the mission a name you will recognise in the feed.';
    if (!task) errs.task = 'Describe what the mission should accomplish; The General picks the agents.';
    setFormErrors(errs);
    if (Object.keys(errs).length) return;
    setCreating(true);
    try {
      const data = await apiJson('/orchestration/missions', {
        method: 'POST',
        body: JSON.stringify({ name, task, auto_assign: true }),
      });
      if (data?.mission) setMissions((prev) => [data.mission, ...prev.filter((m) => m.id !== data.mission.id)]);
      notify.success(data?.message || `Mission “${name}” started`);
      setForm(null);
      load({ silent: true });
    } catch (err) {
      notify.error(humanize(err, { what: 'starting the mission' }));
    } finally {
      setCreating(false);
    }
  };

  let list;
  if (loading && !missions.length) {
    list = <LoadingState variant="list" count={4} label="Loading missions" />;
  } else if (error && !missions.length) {
    list = (
      <ErrorState
        title="Couldn’t load missions"
        detail={humanize(error, { what: 'loading missions' })}
        onRetry={() => load()}
      />
    );
  } else if (!missions.length) {
    list = (
      <EmptyState
        icon={Target}
        title="No missions yet"
        description="Hand The General a task. He picks the agents, delegates, and you watch it unfold here and on the board."
        action={
          <Button icon={Play} onClick={openForm}>
            Start a mission
          </Button>
        }
      />
    );
  } else {
    list = (
      <ul className="grid grid-cols-1 gap-3 xl:grid-cols-2" aria-label="Missions">
        {ordered.map((m) => (
          <MissionCard key={m.id} mission={m} agentById={agentById} statusOf={statusOf} onOpen={onOpen} />
        ))}
      </ul>
    );
  }

  const summary = !missions.length
    ? 'Tasks handed to The General, with the crew he picked'
    : [
        activeCount ? `${activeCount} active` : 'Nothing running',
        failedCount ? `${failedCount} failed` : null,
        `${missions.length} total`,
      ]
        .filter(Boolean)
        .join(' · ');

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        <SectionHeader
          title="Missions"
          description={summary}
          actions={
            <>
              <Tooltip content={error ? humanize(error, { what: 'refreshing missions' }) : 'Missions refresh every 30 seconds'}>
                <span>
                  <Chip tone={error ? 'warn' : 'live'} size="sm" dot pulse={!error && refreshing}>
                    {error ? 'Refresh failed' : ago}
                  </Chip>
                </span>
              </Tooltip>
              <IconButton icon={RefreshCw} label="Refresh missions" size="sm" variant="ghost" onClick={() => load({ silent: true })} loading={refreshing} />
              <Button size="sm" icon={Play} onClick={openForm}>
                Start a mission
              </Button>
            </>
          }
        />
        {list}
      </div>
      <div className="max-h-[45%] min-h-0 shrink-0 border-t border-border bg-surface/50 lg:max-h-none lg:w-80 lg:border-l lg:border-t-0">
        <ActivityFeed events={events} agents={agents} connected={connected} onOpen={onOpen} />
      </div>

      <Modal
        isOpen={Boolean(form)}
        onClose={() => !creating && setForm(null)}
        title="Start a mission"
        description="The General reads the task, picks the agents and delegates. You watch it here."
        footer={
          <>
            <Button variant="ghost" onClick={() => setForm(null)} disabled={creating}>
              Cancel
            </Button>
            <Button type="submit" form="mission-form" icon={Play} loading={creating}>
              Start mission
            </Button>
          </>
        }
      >
        {form && (
          <form id="mission-form" onSubmit={submit} noValidate className="space-y-4">
            <Field label="Name" required error={formErrors.name}>
              <Input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Q4 diligence: Contoso Robotics"
                data-autofocus
              />
            </Field>
            <Field label="Task" required error={formErrors.task}>
              <Textarea
                rows={4}
                value={form.task}
                onChange={(e) => setForm((f) => ({ ...f, task: e.target.value }))}
                placeholder="What should this mission accomplish?"
              />
            </Field>
          </form>
        )}
      </Modal>
    </div>
  );
}
