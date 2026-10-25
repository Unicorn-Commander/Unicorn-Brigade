import { useMemo } from 'react';
import { BarChart3, FileCode, GitCommit, Layers, User } from 'lucide-react';
import PropTypes from 'prop-types';
import { BarList, Card, CardHeader, Chip, EmptyState, StatCard } from './ui';

/**
 * AttributionStats — the numbers /trace/stats actually reports: lines and
 * attributions, unique files and agents, the top agents and files, and the
 * breakdown by operation. (The old "Models used" tile and model pie chart read
 * fields the API never sends and always showed 0 / "No model data".)
 */
const OP_TONE = { generation: 'ok', edit: 'info', deletion: 'danger', refactor: 'warn' };
const fileName = (p = '') => p.split('/').pop() || p;

export default function AttributionStats({ statistics }) {
  const agents = useMemo(
    () =>
      Object.entries(statistics?.agents || {})
        .map(([name, lines]) => ({ key: name, label: <span className="normal-case">{name}</span>, value: Number(lines) || 0 }))
        .slice(0, 10),
    [statistics?.agents]
  );
  const files = useMemo(
    () =>
      Object.entries(statistics?.files || {})
        .map(([path, count]) => ({ key: path, label: <span className="normal-case">{fileName(path)}</span>, value: Number(count) || 0, path }))
        .slice(0, 10),
    [statistics?.files]
  );
  const ops = useMemo(() => Object.entries(statistics?.byOperation || {}).sort(([, a], [, b]) => b - a), [statistics?.byOperation]);

  if (!statistics || (!statistics.total_attributions && !statistics.total_lines)) {
    return <EmptyState compact icon={BarChart3} title="No statistics yet" description="Statistics build up as agents write code through the trace service." />;
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={GitCommit} label="Lines attributed" value={(statistics.total_lines || 0).toLocaleString()} />
        <StatCard icon={Layers} label="Attributions" value={(statistics.total_attributions || 0).toLocaleString()} />
        <StatCard icon={FileCode} label="Files touched" value={(statistics.total_files || 0).toLocaleString()} />
        <StatCard icon={User} label="Contributing agents" value={(statistics.total_agents || 0).toLocaleString()} />
      </div>

      {ops.length > 0 && (
        <Card padding="sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-caption text-muted">By operation</span>
            {ops.map(([op, n]) => (
              <Chip key={op} tone={OP_TONE[op] || 'neutral'} size="sm" className="capitalize tabular-nums">
                {op} · {n}
              </Chip>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader icon={User} title="Most active agents" description="Lines attributed per agent" />
          <BarList items={agents} renderValue={(i) => `${i.value.toLocaleString()} lines`} />
        </Card>
        <Card>
          <CardHeader icon={FileCode} title="Most modified files" description="Attributions per file" />
          <BarList items={files} renderValue={(i) => `${i.value.toLocaleString()} attribution${i.value === 1 ? '' : 's'}`} />
        </Card>
      </div>
    </div>
  );
}

AttributionStats.propTypes = {
  statistics: PropTypes.shape({
    total_lines: PropTypes.number,
    total_attributions: PropTypes.number,
    total_files: PropTypes.number,
    total_agents: PropTypes.number,
    byOperation: PropTypes.object,
    agents: PropTypes.object,
    files: PropTypes.object,
  }),
};
