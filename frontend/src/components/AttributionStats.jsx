import { useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  FileCode,
  User,
  Sparkles,
  TrendingUp,
  BarChart3,
  PieChart,
  Activity
} from 'lucide-react';
import PropTypes from 'prop-types';

/**
 * Simple Pie Chart Component
 */
const SimplePieChart = ({ data, colors }) => {
  let currentAngle = 0;
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <svg viewBox="0 0 100 100" className="w-full h-full">
      {data.map((item, index) => {
        const percentage = (item.value / total) * 100;
        const angle = (percentage / 100) * 360;
        const largeArcFlag = angle > 180 ? 1 : 0;

        const startAngle = currentAngle;
        const endAngle = currentAngle + angle;

        const x1 = 50 + 40 * Math.cos((Math.PI * startAngle) / 180);
        const y1 = 50 + 40 * Math.sin((Math.PI * startAngle) / 180);
        const x2 = 50 + 40 * Math.cos((Math.PI * endAngle) / 180);
        const y2 = 50 + 40 * Math.sin((Math.PI * endAngle) / 180);

        currentAngle = endAngle;

        const pathData = [
          `M 50 50`,
          `L ${x1} ${y1}`,
          `A 40 40 0 ${largeArcFlag} 1 ${x2} ${y2}`,
          `Z`
        ].join(' ');

        return (
          <path
            key={index}
            d={pathData}
            fill={colors[index % colors.length]}
            className="transition-opacity hover:opacity-80"
          />
        );
      })}
    </svg>
  );
};

SimplePieChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      value: PropTypes.number.isRequired
    })
  ).isRequired,
  colors: PropTypes.arrayOf(PropTypes.string).isRequired
};

/**
 * Simple Bar Chart Component
 */
const SimpleBarChart = ({ data }) => {
  const maxValue = Math.max(...data.map(d => d.value));

  return (
    <div className="space-y-3">
      {data.map((item, index) => (
        <div key={index}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-400 truncate flex-1">
              {item.name}
            </span>
            <span className="text-xs text-slate-300 font-medium ml-2">
              {item.value.toLocaleString()}
            </span>
          </div>
          <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(item.value / maxValue) * 100}%` }}
              transition={{ duration: 0.5, delay: index * 0.05 }}
              className="h-full bg-gradient-to-r from-unicorn-600 to-unicorn-500 rounded-full"
            />
          </div>
        </div>
      ))}
    </div>
  );
};

SimpleBarChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      name: PropTypes.string.isRequired,
      value: PropTypes.number.isRequired
    })
  ).isRequired
};

/**
 * AttributionStats - Statistics dashboard for code attributions
 */
const AttributionStats = ({ statistics }) => {
  // Process data for charts
  const modelData = useMemo(() => {
    if (!statistics?.models) return [];
    return Object.entries(statistics.models)
      .map(([name, count]) => ({ name, value: count }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [statistics?.models]);

  const agentData = useMemo(() => {
    if (!statistics?.agents) return [];
    return Object.entries(statistics.agents)
      .map(([name, count]) => ({ name, value: count }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [statistics?.agents]);

  const fileData = useMemo(() => {
    if (!statistics?.files) return [];
    return Object.entries(statistics.files)
      .map(([name, count]) => ({ name: name.split('/').pop(), value: count }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 10);
  }, [statistics?.files]);

  const pieColors = [
    'rgba(168, 85, 247, 0.8)',  // purple-500
    'rgba(236, 72, 153, 0.8)',  // pink-500
    'rgba(59, 130, 246, 0.8)',  // blue-500
    'rgba(34, 197, 94, 0.8)',   // green-500
    'rgba(251, 146, 60, 0.8)',  // orange-500
    'rgba(14, 165, 233, 0.8)',  // sky-500
    'rgba(139, 92, 246, 0.8)',  // violet-500
    'rgba(244, 114, 182, 0.8)'  // pink-400
  ];

  if (!statistics) {
    return (
      <div className="text-center py-12">
        <BarChart3 className="w-12 h-12 text-slate-700 mx-auto mb-3" />
        <p className="text-slate-400">No statistics available</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Lines */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0 }}
          className="card"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 mb-1">Total Lines</p>
              <p className="text-2xl font-bold text-unicorn-400">
                {(statistics.total_lines || 0).toLocaleString()}
              </p>
            </div>
            <div className="p-2 bg-unicorn-500/20 rounded-lg">
              <FileCode className="w-5 h-5 text-unicorn-400" />
            </div>
          </div>
          <div className="flex items-center gap-1 mt-2 text-xs text-emerald-400">
            <TrendingUp className="w-3 h-3" />
            <span>AI-generated code</span>
          </div>
        </motion.div>

        {/* Files Modified */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 mb-1">Files Modified</p>
              <p className="text-2xl font-bold text-unicorn-400">
                {(statistics.total_files || 0).toLocaleString()}
              </p>
            </div>
            <div className="p-2 bg-unicorn-500/20 rounded-lg">
              <FileCode className="w-5 h-5 text-unicorn-400" />
            </div>
          </div>
          <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
            <Activity className="w-3 h-3" />
            <span>Unique files</span>
          </div>
        </motion.div>

        {/* Active Agents */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="card"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 mb-1">Active Agents</p>
              <p className="text-2xl font-bold text-blue-400">
                {(statistics.total_agents || 0).toLocaleString()}
              </p>
            </div>
            <div className="p-2 bg-blue-500/20 rounded-lg">
              <User className="w-5 h-5 text-blue-400" />
            </div>
          </div>
          <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
            <Activity className="w-3 h-3" />
            <span>Contributing agents</span>
          </div>
        </motion.div>

        {/* Models Used */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="card"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-slate-400 mb-1">Models Used</p>
              <p className="text-2xl font-bold text-emerald-400">
                {(statistics.total_models || 0).toLocaleString()}
              </p>
            </div>
            <div className="p-2 bg-emerald-500/20 rounded-lg">
              <Sparkles className="w-5 h-5 text-emerald-400" />
            </div>
          </div>
          <div className="flex items-center gap-1 mt-2 text-xs text-slate-400">
            <Activity className="w-3 h-3" />
            <span>Different models</span>
          </div>
        </motion.div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Usage Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="card"
        >
          <div className="flex items-center gap-2 mb-4">
            <PieChart className="w-5 h-5 text-unicorn-400" />
            <h3 className="text-lg font-semibold text-slate-200">
              Model Usage
            </h3>
          </div>

          {modelData.length > 0 ? (
            <div className="grid grid-cols-2 gap-4">
              {/* Pie Chart */}
              <div className="flex items-center justify-center">
                <div className="w-40 h-40">
                  <SimplePieChart data={modelData.slice(0, 8)} colors={pieColors} />
                </div>
              </div>

              {/* Legend */}
              <div className="space-y-2">
                {modelData.slice(0, 8).map((item, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-sm flex-shrink-0"
                      style={{ backgroundColor: pieColors[index] }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-slate-300 truncate">
                        {item.name}
                      </p>
                      <p className="text-xs text-slate-400">
                        {item.value} lines
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-400 text-sm">
              No model data available
            </div>
          )}
        </motion.div>

        {/* Top Agents */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="card"
        >
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-unicorn-400" />
            <h3 className="text-lg font-semibold text-slate-200">
              Most Active Agents
            </h3>
          </div>

          {agentData.length > 0 ? (
            <SimpleBarChart data={agentData} />
          ) : (
            <div className="text-center py-8 text-slate-400 text-sm">
              No agent data available
            </div>
          )}
        </motion.div>
      </div>

      {/* Most Modified Files */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="card"
      >
        <div className="flex items-center gap-2 mb-4">
          <FileCode className="w-5 h-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-slate-200">
            Most Modified Files
          </h3>
        </div>

        {fileData.length > 0 ? (
          <SimpleBarChart data={fileData} />
        ) : (
          <div className="text-center py-8 text-slate-400 text-sm">
            No file data available
          </div>
        )}
      </motion.div>
    </div>
  );
};

AttributionStats.propTypes = {
  statistics: PropTypes.shape({
    total_lines: PropTypes.number,
    total_files: PropTypes.number,
    total_agents: PropTypes.number,
    total_models: PropTypes.number,
    models: PropTypes.object,
    agents: PropTypes.object,
    files: PropTypes.object
  })
};

export default AttributionStats;
