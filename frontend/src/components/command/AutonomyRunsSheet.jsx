/**
 * An outside job's details and recent runs (GET /api/v1/autonomy/jobs/{key}/runs).
 * Newest first; a failure shows its reason in words. All four states: a
 * skeleton while it loads, an error with a retry, an empty "no runs yet",
 * and the list.
 */
import { useCallback, useEffect, useState } from 'react';
import { History, Pencil } from 'lucide-react';
import { humanize } from '../../utils/errors';
import { apiJson } from '../../services/http';
import { describeSchedule, zoneLabel } from '../../utils/cron';
import { durationText, healthMeta, isFailure, reasonText, runStatusMeta, whereItRuns, itemHealth } from '../../utils/autonomy';
import { relativeTime, absoluteTime } from '../ActivityFeed';
import AutonomyNote from '../AutonomyNote';
import { Button, Chip, EmptyState, ErrorState, LoadingState, SectionHeader, Sheet, StatusDot, Tooltip } from '../ui';

const LIMIT = 20;

function Detail({ label, children, mono = false }) {
  return (
    <div className="min-w-0">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className={`mt-0.5 break-words text-body-sm text-fg ${mono ? 'font-mono' : ''}`}>{children}</dd>
    </div>
  );
}

export default function AutonomyRunsSheet({ item, onClose, onEdit }) {
  const [state, setState] = useState({ status: 'idle', runs: [], error: null });
  const key = item?.key;

  const load = useCallback(async () => {
    if (!key) return;
    setState({ status: 'loading', runs: [], error: null });
    try {
      const res = await apiJson(`/autonomy/jobs/${encodeURIComponent(key)}/runs`, { params: { limit: LIMIT } });
      setState({ status: 'ready', runs: Array.isArray(res?.runs) ? res.runs : [], error: null });
    } catch (err) {
      setState({ status: 'error', runs: [], error: err });
    }
  }, [key]);

  useEffect(() => {
    if (key) load();
  }, [key, load]);

  const h = item ? itemHealth(item) : null;
  let list;
  if (state.status === 'loading' || state.status === 'idle') {
    list = <LoadingState variant="list" count={4} label="Loading run history" />;
  } else if (state.status === 'error') {
    list = (
      <ErrorState
        compact
        title="Couldn’t load the run history"
        detail={state.error?.status === 404 ? 'This job isn’t in the catalogue any more.' : humanize(state.error, { what: 'loading the run history' })}
        onRetry={state.error?.status === 404 ? undefined : load}
      />
    );
  } else if (!state.runs.length) {
    list = <EmptyState compact icon={History} title="No runs reported yet" description="Each report from the script lands here, newest first, with its summary or its reason for failing." />;
  } else {
    list = (
      <ol className="divide-y divide-border/60" aria-label={`Recent runs of ${item?.name}`}>
        {state.runs.map((r) => {
          const s = runStatusMeta(r.status);
          const took = durationText(r.durationMs);
          const text = reasonText(isFailure(r.status) ? r.error || r.summary : r.summary || r.error);
          return (
            <li key={r.id} className="flex items-start gap-3 py-2.5">
              <StatusDot status={s.dot} size="md" label={s.label} className="mt-1.5" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                  <Chip tone={s.tone} size="xs" pulse={s.pulse} dot={s.pulse}>
                    {s.label}
                  </Chip>
                  <Tooltip content={absoluteTime(r.startedAt, item?.timezone)}>
                    <time dateTime={r.startedAt} className="text-caption text-muted">
                      {relativeTime(r.startedAt)}
                    </time>
                  </Tooltip>
                  {took && <span className="text-caption text-subtle">· {took}</span>}
                  {r.runId && <span className="truncate font-mono text-caption text-subtle">· {r.runId}</span>}
                </div>
                <p className={`mt-1 text-body-sm ${isFailure(r.status) ? 'text-danger' : 'text-fg'}`}>
                  {text || (r.status === 'running' ? 'Still running.' : isFailure(r.status) ? 'No reason was reported.' : 'No summary was reported.')}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    );
  }

  return (
    <Sheet
      isOpen={Boolean(item)}
      onClose={onClose}
      side="right"
      title={item?.name}
      className="sm:max-w-xl"
      footer={
        item && (
          <Button variant="secondary" icon={Pencil} onClick={() => onEdit(item)}>
            Edit job
          </Button>
        )
      }
    >
      {item && (
        <div className="space-y-5 pt-1">
          <div className="space-y-2">
            <Chip tone={h.tone} size="sm" dot>
              {h.label}
            </Chip>
            <p className="text-lead text-fg-strong">{item.responsibility}</p>
            <AutonomyNote notes={item.notes} clamp={false} />
          </div>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
            <Detail label="Where it runs">{whereItRuns(item)}</Detail>
            <Detail label="Schedule">
              {item.schedule ? describeSchedule(item.schedule, item.timezone) || `cron ${item.schedule} ${zoneLabel(item.timezone)}` : item.scheduleNote || 'No schedule recorded'}
              {item.schedule && <span className="block font-mono text-caption text-muted">{item.schedule}</span>}
            </Detail>
            <Detail label="Next run">{!item.enabled ? 'Paused' : item.nextRunAt ? absoluteTime(item.nextRunAt, item.timezone) : 'Not on a clock'}</Detail>
            <Detail label="Owner">{item.owner || 'Nobody named'}</Detail>
            <Detail label="Key" mono>
              {item.key}
            </Detail>
            {item.command && (
              <Detail label="Command" mono>
                {item.command}
              </Detail>
            )}
            {item.runbookUrl && (
              <Detail label="Runbook">
                <a href={item.runbookUrl} target="_blank" rel="noreferrer" className="break-all text-accent underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-chip">
                  {item.runbookUrl}
                </a>
              </Detail>
            )}
          </dl>
          <div>
            <SectionHeader title="Recent runs" description={`Newest first · up to the last ${LIMIT}`} />
            {list}
          </div>
        </div>
      )}
    </Sheet>
  );
}
