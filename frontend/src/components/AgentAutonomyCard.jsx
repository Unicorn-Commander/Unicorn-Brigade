/**
 * "Runs on its own" — an agent's jobs from the autonomy catalogue, on its
 * Overview: what each is responsible for, the schedule in words, the next
 * and the last run (with the reason when it failed). Renders nothing when
 * the agent has no such jobs, or when the catalogue can't be read — it is a
 * side fact and fails on its own, quietly.
 */
import { Link } from 'react-router-dom';
import { ArrowRight, Repeat } from 'lucide-react';
import { describeSchedule, zoneLabel } from '../utils/cron';
import { durationText, healthMeta, isFailure, nextRunText, reasonText, runStatusMeta, whereItRuns, itemHealth } from '../utils/autonomy';
import { relativeTime, absoluteTime } from './ActivityFeed';
import AutonomyNote from './AutonomyNote';
import { Button, Card, CardHeader, Chip, StatusDot, Tooltip } from './ui';

function scheduleText(it) {
  if (it.schedule) return describeSchedule(it.schedule, it.timezone) || `cron ${it.schedule} ${zoneLabel(it.timezone)}`;
  return it.scheduleNote || (it.runner === 'continuous' ? 'Runs continuously' : 'No schedule recorded');
}

export default function AgentAutonomyCard({ agentId, items = [] }) {
  if (!agentId || !items.length) return null;
  const failing = items.filter((it) => it.health === 'failing').length;
  const stale = items.filter((it) => it.health === 'stale').length;
  const summary = [`${items.length} job${items.length === 1 ? '' : 's'}`, failing ? `${failing} failing` : null, stale ? `${stale} stale` : null]
    .filter(Boolean)
    .join(' · ');
  return (
    <Card variant="elevated">
      <CardHeader
        icon={Repeat}
        title="Runs on its own"
        description={summary}
        actions={
          <Button as={Link} to={`/command?view=autonomous&agent=${encodeURIComponent(agentId)}`} variant="link" size="sm" iconRight={ArrowRight}>
            Open the catalogue
          </Button>
        }
      />
      <ul className="divide-y divide-border/60" aria-label="Jobs this agent runs on its own">
        {items.map((it) => {
          const h = itemHealth(it);
          const s = runStatusMeta(it.lastStatus);
          // The API's health decides failing — a status outside the enum ("degraded") included.
          const failed = it.health === 'failing' || isFailure(it.lastStatus);
          const took = durationText(it.lastDurationMs);
          return (
            <li key={it.id} className="py-3 first:pt-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-body-sm font-semibold text-fg">{it.name}</span>
                <Chip tone={h.tone} size="xs" dot>
                  {h.label}
                </Chip>
              </div>
              <p className={`mt-1 ${it.responsibility ? 'text-body text-fg-strong' : 'text-body-sm text-subtle'}`}>{it.responsibility || 'No responsibility written yet.'}</p>
              <AutonomyNote notes={it.notes} className="mt-0.5" />
              <p className="mt-1 text-body-sm text-muted">
                {whereItRuns(it)} · {scheduleText(it)}
                {!it.enabled ? (
                  ' · paused'
                ) : it.nextRunAt ? (
                  <>
                    {' · '}
                    <Tooltip content={absoluteTime(it.nextRunAt, it.timezone)}>
                      <time dateTime={it.nextRunAt}>{nextRunText(it.nextRunAt, relativeTime)}</time>
                    </Tooltip>
                  </>
                ) : null}
              </p>
              {it.lastStatus === 'running' ? (
                <p className="mt-1 flex items-center gap-2 text-body-sm text-fg">
                  <StatusDot status="tool" /> Running now
                </p>
              ) : it.lastRunAt ? (
                <p className={`mt-1 flex flex-wrap items-center gap-x-1.5 text-body-sm ${failed ? 'text-danger' : 'text-muted'}`}>
                  {s.unknown ? (
                    <Chip tone="warn" size="xs">
                      {s.label}
                    </Chip>
                  ) : (
                    <StatusDot status={s.dot} label={s.label} />
                  )}
                  <span>
                    Last run{' '}
                    <Tooltip content={absoluteTime(it.lastRunAt, it.timezone)}>
                      <time dateTime={it.lastRunAt}>{relativeTime(it.lastRunAt)}</time>
                    </Tooltip>
                    {s.unknown ? '' : ` · ${s.label.toLowerCase()}`}
                    {took ? ` (${took})` : ''}
                    {failed ? `: ${reasonText(it.lastError || it.lastSummary) || 'no reason was reported'}` : ''}
                  </span>
                </p>
              ) : (
                <p className="mt-1 text-body-sm text-subtle">Never ran yet.</p>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
