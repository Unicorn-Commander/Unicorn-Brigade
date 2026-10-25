import { Calendar, Clock, FileCode, GitCommit, Sparkles, User } from 'lucide-react';
import PropTypes from 'prop-types';
import { Card, Chip } from './ui';

/**
 * CodeAttributionCard — one attribution: which agent wrote which lines of
 * which file, when, and from what prompt. Clickable when `onClick` is given.
 */
const fmtDate = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
};
const fmtTime = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};
const fileName = (p = '') => p.split('/').pop() || p;
const dirName = (p = '') => p.split('/').slice(0, -1).join('/') || '/';

export default function CodeAttributionCard({ attribution: a, onClick, compact = false }) {
  const clickable = typeof onClick === 'function';
  return (
    <Card
      as={clickable ? 'button' : 'div'}
      type={clickable ? 'button' : undefined}
      interactive={clickable}
      padding={compact ? 'sm' : 'md'}
      className="h-full w-full"
      onClick={clickable ? () => onClick(a) : undefined}
      aria-label={clickable ? `Open attributions for ${fileName(a.file_path)}` : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <FileCode aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-body font-semibold text-fg-strong">{fileName(a.file_path)}</p>
              <p className="truncate font-mono text-caption text-muted">{dirName(a.file_path)}</p>
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
            <span className="inline-flex items-center gap-1">
              <User aria-hidden="true" className="h-3 w-3" />
              {a.agent_name || a.agent_id}
            </span>
            {a.model && (
              <span className="inline-flex min-w-0 items-center gap-1">
                <Sparkles aria-hidden="true" className="h-3 w-3" />
                <span className="truncate">{a.model}</span>
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <Chip tone="accent" size="xs" className="tabular-nums">
            {a.lines_count ?? 0} lines
          </Chip>
          {a.timestamp && (
            <span className="inline-flex items-center gap-1 text-caption text-muted">
              <Clock aria-hidden="true" className="h-3 w-3" />
              {fmtTime(a.timestamp)}
            </span>
          )}
        </div>
      </div>

      {!compact && (
        <>
          {a.timestamp && (
            <p className="mt-3 inline-flex items-center gap-1.5 text-caption text-muted">
              <Calendar aria-hidden="true" className="h-3 w-3" />
              {fmtDate(a.timestamp)}
            </p>
          )}
          {a.prompt && (
            <p className="mt-3 line-clamp-2 rounded-control border border-border bg-elevated/50 px-2.5 py-2 text-caption text-muted">{a.prompt}</p>
          )}
          {a.start_line != null && a.end_line != null && (
            <p className="mt-3 inline-flex items-center gap-1.5 font-mono text-caption text-muted">
              <GitCommit aria-hidden="true" className="h-3 w-3" />
              Lines {a.start_line}–{a.end_line}
            </p>
          )}
        </>
      )}
    </Card>
  );
}

CodeAttributionCard.propTypes = {
  attribution: PropTypes.shape({
    id: PropTypes.string,
    file_path: PropTypes.string.isRequired,
    agent_id: PropTypes.string,
    agent_name: PropTypes.string,
    model: PropTypes.string,
    timestamp: PropTypes.string,
    lines_count: PropTypes.number,
    start_line: PropTypes.number,
    end_line: PropTypes.number,
    prompt: PropTypes.string,
  }).isRequired,
  onClick: PropTypes.func,
  compact: PropTypes.bool,
};
