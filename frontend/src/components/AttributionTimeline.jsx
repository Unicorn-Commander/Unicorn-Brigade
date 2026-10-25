import { useMemo } from 'react';
import { Calendar, Clock, FileCode, GitCommit, Sparkles, User } from 'lucide-react';
import PropTypes from 'prop-types';
import { Card, Chip, EmptyState } from './ui';

/**
 * AttributionTimeline — attributions in chronological groups, one day per
 * group, newest first. Each item opens the file's attributions.
 */
const dayKey = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? 'Unknown date' : d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
};
const fmtTime = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};
const fileName = (p = '') => p.split('/').pop() || p;

export default function AttributionTimeline({ attributions, onItemClick }) {
  const groups = useMemo(() => {
    const sorted = [...attributions].sort((a, b) => new Date(b.timestamp || 0) - new Date(a.timestamp || 0));
    const map = new Map();
    for (const a of sorted) {
      const k = dayKey(a.timestamp);
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(a);
    }
    return [...map.entries()];
  }, [attributions]);

  if (groups.length === 0) {
    return <EmptyState compact icon={Calendar} title="No activity in this window" description="Widen the date range, or check back after an agent has written code." />;
  }

  const clickable = typeof onItemClick === 'function';

  return (
    <div className="space-y-8">
      {groups.map(([date, items]) => (
        <section key={date} aria-label={date}>
          <div className="sticky top-0 z-raised mb-3 bg-bg/95 py-2 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <Calendar aria-hidden="true" className="h-4 w-4 text-accent" />
              <h3 className="text-body font-semibold text-fg-strong">{date}</h3>
              <span className="text-caption text-muted">
                {items.length} {items.length === 1 ? 'change' : 'changes'}
              </span>
            </div>
          </div>
          <ol className="relative space-y-3 pl-7">
            <span aria-hidden="true" className="absolute bottom-2 left-2 top-2 w-px bg-border" />
            {items.map((a, i) => (
              <li key={a.id || `${a.file_path}-${i}`} className="relative">
                <span aria-hidden="true" className="absolute -left-[22px] top-4 h-2.5 w-2.5 rounded-full bg-accent ring-2 ring-bg" />
                <Card
                  as={clickable ? 'button' : 'div'}
                  type={clickable ? 'button' : undefined}
                  interactive={clickable}
                  padding="sm"
                  className="w-full"
                  onClick={clickable ? () => onItemClick(a) : undefined}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <FileCode aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />
                        <span className="truncate text-body font-semibold text-fg-strong">{fileName(a.file_path)}</span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-muted">
                        <span className="inline-flex items-center gap-1">
                          <User aria-hidden="true" className="h-3 w-3" />
                          {a.agent_name || a.agent_id}
                        </span>
                        {a.model && (
                          <span className="inline-flex items-center gap-1">
                            <Sparkles aria-hidden="true" className="h-3 w-3" />
                            {a.model}
                          </span>
                        )}
                        {a.start_line != null && a.end_line != null && (
                          <span className="inline-flex items-center gap-1 font-mono">
                            <GitCommit aria-hidden="true" className="h-3 w-3" />
                            {a.start_line}–{a.end_line}
                          </span>
                        )}
                      </div>
                      {a.prompt && <p className="mt-2 line-clamp-2 text-caption text-muted">{a.prompt}</p>}
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-1">
                      <Chip tone="accent" size="xs" className="tabular-nums">
                        {a.lines_count ?? 0} lines
                      </Chip>
                      <span className="inline-flex items-center gap-1 text-caption text-muted">
                        <Clock aria-hidden="true" className="h-3 w-3" />
                        {fmtTime(a.timestamp)}
                      </span>
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

AttributionTimeline.propTypes = {
  attributions: PropTypes.arrayOf(
    PropTypes.shape({
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
    })
  ).isRequired,
  onItemClick: PropTypes.func,
};
