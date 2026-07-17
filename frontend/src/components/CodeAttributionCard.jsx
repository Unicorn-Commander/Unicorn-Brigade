import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  FileCode,
  User,
  Calendar,
  Clock,
  Code,
  ChevronRight,
  ExternalLink,
  GitCommit,
  Sparkles
} from 'lucide-react';
import PropTypes from 'prop-types';

/**
 * CodeAttributionCard - Displays a single code attribution
 * Shows which agent generated which code, when, and with what prompt
 */
const CodeAttributionCard = ({ attribution, onClick, compact = false }) => {
  const [expanded, setExpanded] = useState(false);

  const handleClick = () => {
    if (onClick) {
      onClick(attribution);
    } else {
      setExpanded(!expanded);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  const formatTime = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Get file name from path
  const getFileName = (path) => {
    return path.split('/').pop() || path;
  };

  // Get relative path without file name
  const getFilePath = (path) => {
    const parts = path.split('/');
    return parts.slice(0, -1).join('/') || '/';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={`
        card hover:border-unicorn-500/30 transition-all cursor-pointer group
        ${compact ? 'p-3' : 'p-4'}
      `}
      onClick={handleClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          {/* File Info */}
          <div className="flex items-center gap-2 mb-2">
            <FileCode className="w-4 h-4 text-unicorn-400 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-slate-200 truncate">
                {getFileName(attribution.file_path)}
              </p>
              <p className="text-xs text-slate-500 truncate">
                {getFilePath(attribution.file_path)}
              </p>
            </div>
          </div>

          {/* Agent & Model */}
          <div className="flex items-center gap-4 text-xs text-slate-400">
            <div className="flex items-center gap-1.5">
              <User className="w-3 h-3" />
              <span>{attribution.agent_name || attribution.agent_id}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Sparkles className="w-3 h-3" />
              <span>{attribution.model}</span>
            </div>
          </div>
        </div>

        {/* Stats Badge */}
        <div className="flex flex-col items-end gap-1">
          <span className="badge badge-purple text-xs">
            {attribution.lines_count} lines
          </span>
          <div className="flex items-center gap-1 text-xs text-slate-500">
            <Clock className="w-3 h-3" />
            {formatTime(attribution.timestamp)}
          </div>
        </div>
      </div>

      {!compact && (
        <>
          {/* Date */}
          <div className="flex items-center gap-1.5 mt-3 text-xs text-slate-500">
            <Calendar className="w-3 h-3" />
            {formatDate(attribution.timestamp)}
          </div>

          {/* Prompt Preview */}
          {attribution.prompt && (
            <div className="mt-3 p-2.5 bg-slate-800/40 rounded-lg border border-slate-700/50">
              <p className="text-xs text-slate-400 line-clamp-2">
                {attribution.prompt}
              </p>
            </div>
          )}

          {/* Line Range */}
          {attribution.start_line && attribution.end_line && (
            <div className="flex items-center gap-2 mt-3 text-xs">
              <GitCommit className="w-3 h-3 text-slate-500" />
              <span className="text-slate-400">
                Lines {attribution.start_line}-{attribution.end_line}
              </span>
            </div>
          )}

          {/* Expand Indicator */}
          <div className="flex items-center justify-end mt-3 text-xs text-unicorn-400 opacity-0 group-hover:opacity-100 transition-opacity">
            <span>View details</span>
            <ChevronRight className="w-3 h-3 ml-1" />
          </div>
        </>
      )}
    </motion.div>
  );
};

CodeAttributionCard.propTypes = {
  attribution: PropTypes.shape({
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
  }).isRequired,
  onClick: PropTypes.func,
  compact: PropTypes.bool
};

export default CodeAttributionCard;
