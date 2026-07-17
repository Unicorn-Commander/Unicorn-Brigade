import { useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  FileCode,
  User,
  Clock,
  Sparkles,
  GitCommit,
  Calendar
} from 'lucide-react';
import PropTypes from 'prop-types';

/**
 * AttributionTimeline - Displays code attributions in a chronological timeline
 */
const AttributionTimeline = ({ attributions, onItemClick }) => {
  // Group attributions by date
  const groupedByDate = useMemo(() => {
    const groups = {};

    attributions.forEach(attr => {
      const date = new Date(attr.timestamp).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });

      if (!groups[date]) {
        groups[date] = [];
      }
      groups[date].push(attr);
    });

    return groups;
  }, [attributions]);

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getFileName = (path) => {
    return path.split('/').pop() || path;
  };

  return (
    <div className="space-y-8">
      {Object.entries(groupedByDate).map(([date, items]) => (
        <div key={date} className="relative">
          {/* Date Header */}
          <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur-sm py-2 mb-4">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-unicorn-400" />
              <h3 className="text-sm font-semibold text-slate-200">{date}</h3>
              <span className="text-xs text-slate-500">
                ({items.length} {items.length === 1 ? 'change' : 'changes'})
              </span>
            </div>
          </div>

          {/* Timeline Items */}
          <div className="relative pl-8 space-y-4">
            {/* Timeline Line */}
            <div className="absolute left-2 top-0 bottom-0 w-px bg-gradient-to-b from-unicorn-500/50 via-unicorn-500/20 to-transparent" />

            {items.map((attr, index) => (
              <motion.div
                key={attr.id || `${attr.file_path}-${index}`}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="relative"
              >
                {/* Timeline Dot */}
                <div className="absolute left-[-26px] top-3">
                  <div className="w-3 h-3 rounded-full bg-unicorn-500 ring-4 ring-slate-900" />
                </div>

                {/* Timeline Item Card */}
                <div
                  className="card p-3 hover:border-unicorn-500/30 transition-all cursor-pointer group"
                  onClick={() => onItemClick && onItemClick(attr)}
                >
                  {/* Time Badge */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                      <Clock className="w-3 h-3" />
                      {formatTime(attr.timestamp)}
                    </div>
                    <span className="badge badge-purple text-xs">
                      {attr.lines_count} lines
                    </span>
                  </div>

                  {/* File Path */}
                  <div className="flex items-center gap-2 mb-2">
                    <FileCode className="w-4 h-4 text-unicorn-400" />
                    <span className="text-sm font-medium text-slate-200">
                      {getFileName(attr.file_path)}
                    </span>
                  </div>

                  {/* Agent & Model */}
                  <div className="flex items-center gap-4 text-xs text-slate-400 mb-2">
                    <div className="flex items-center gap-1.5">
                      <User className="w-3 h-3" />
                      <span>{attr.agent_name || attr.agent_id}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Sparkles className="w-3 h-3" />
                      <span className="truncate">{attr.model}</span>
                    </div>
                  </div>

                  {/* Prompt */}
                  {attr.prompt && (
                    <div className="mt-2 p-2 bg-slate-800/40 rounded border border-slate-700/50">
                      <p className="text-xs text-slate-400 line-clamp-2">
                        {attr.prompt}
                      </p>
                    </div>
                  )}

                  {/* Line Range */}
                  {attr.start_line && attr.end_line && (
                    <div className="flex items-center gap-2 mt-2 text-xs text-slate-500">
                      <GitCommit className="w-3 h-3" />
                      <span>Lines {attr.start_line}-{attr.end_line}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      ))}

      {/* Empty State */}
      {Object.keys(groupedByDate).length === 0 && (
        <div className="text-center py-12">
          <Calendar className="w-12 h-12 text-slate-700 mx-auto mb-3" />
          <p className="text-slate-500">No activity in this time period</p>
        </div>
      )}
    </div>
  );
};

AttributionTimeline.propTypes = {
  attributions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string,
      file_path: PropTypes.string.isRequired,
      agent_id: PropTypes.string.isRequired,
      agent_name: PropTypes.string,
      model: PropTypes.string.isRequired,
      timestamp: PropTypes.string.isRequired,
      lines_count: PropTypes.number,
      start_line: PropTypes.number,
      end_line: PropTypes.number,
      prompt: PropTypes.string
    })
  ).isRequired,
  onItemClick: PropTypes.func
};

export default AttributionTimeline;
