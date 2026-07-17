import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileCode,
  User,
  Sparkles,
  Calendar,
  MessageSquare,
  X,
  ChevronDown,
  ChevronRight,
  Copy,
  Check
} from 'lucide-react';
import PropTypes from 'prop-types';

/**
 * Syntax highlighting for code with attribution overlays
 */
const SyntaxHighlightedCode = ({ code, language = 'javascript' }) => {
  const lines = code.split('\n');

  // Basic syntax highlighting (can be enhanced with a library like prism.js)
  const highlightLine = (line) => {
    // This is a simplified highlighter - in production, use a proper library
    let highlighted = line;

    // Keywords
    const keywords = ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'import', 'export', 'from', 'async', 'await'];
    keywords.forEach(keyword => {
      const regex = new RegExp(`\\b${keyword}\\b`, 'g');
      highlighted = highlighted.replace(regex, `<span class="text-unicorn-400">${keyword}</span>`);
    });

    // Strings
    highlighted = highlighted.replace(/(["'`])(.*?)\1/g, '<span class="text-emerald-400">$1$2$1</span>');

    // Comments
    highlighted = highlighted.replace(/(\/\/.*$)/g, '<span class="text-slate-500">$1</span>');

    // Numbers
    highlighted = highlighted.replace(/\b(\d+)\b/g, '<span class="text-amber-400">$1</span>');

    return highlighted;
  };

  return (
    <div className="font-mono text-sm">
      {lines.map((line, index) => (
        <div key={index} className="flex hover:bg-slate-800/30">
          <span className="text-slate-600 select-none w-12 text-right pr-4 flex-shrink-0">
            {index + 1}
          </span>
          <span
            className="flex-1"
            dangerouslySetInnerHTML={{ __html: highlightLine(line) || '&nbsp;' }}
          />
        </div>
      ))}
    </div>
  );
};

SyntaxHighlightedCode.propTypes = {
  code: PropTypes.string.isRequired,
  language: PropTypes.string
};

/**
 * FileAttributionViewer - Shows code with line-by-line attribution
 */
const FileAttributionViewer = ({ filePath, attributions, code, onClose }) => {
  const [selectedAttribution, setSelectedAttribution] = useState(null);
  const [copied, setCopied] = useState(false);

  // Create a map of line numbers to attributions
  const lineAttributions = useMemo(() => {
    const map = {};
    attributions.forEach(attr => {
      for (let i = attr.start_line; i <= attr.end_line; i++) {
        map[i] = attr;
      }
    });
    return map;
  }, [attributions]);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const copyCode = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getFileName = (path) => {
    return path.split('/').pop() || path;
  };

  const codeLines = code.split('\n');

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-slate-900/95 backdrop-blur-sm overflow-auto"
    >
      <div className="min-h-screen p-6">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="flex items-start justify-between mb-6">
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2">
                <FileCode className="w-6 h-6 text-unicorn-400" />
                <h1 className="text-2xl font-bold text-slate-200">
                  {getFileName(filePath)}
                </h1>
              </div>
              <p className="text-sm text-slate-500">{filePath}</p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={copyCode}
                className="btn btn-secondary btn-sm flex items-center gap-2"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    Copy Code
                  </>
                )}
              </button>
              <button
                onClick={onClose}
                className="btn btn-secondary btn-sm"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Code View */}
            <div className="lg:col-span-2">
              <div className="card p-0 overflow-hidden">
                <div className="bg-slate-800/50 px-4 py-2 border-b border-slate-700/50">
                  <p className="text-xs font-medium text-slate-400">Code with Attributions</p>
                </div>

                <div className="overflow-x-auto custom-scrollbar">
                  <div className="p-4 bg-slate-900/60">
                    <div className="font-mono text-sm">
                      {codeLines.map((line, index) => {
                        const lineNumber = index + 1;
                        const attribution = lineAttributions[lineNumber];

                        return (
                          <div
                            key={index}
                            className={`
                              flex group hover:bg-slate-800/40 cursor-pointer
                              ${attribution ? 'border-l-2 border-unicorn-500/30' : ''}
                              ${selectedAttribution && selectedAttribution.id === attribution?.id ? 'bg-unicorn-500/10' : ''}
                            `}
                            onClick={() => attribution && setSelectedAttribution(attribution)}
                          >
                            <span className="text-slate-600 select-none w-12 text-right pr-4 flex-shrink-0">
                              {lineNumber}
                            </span>
                            <span className="flex-1 text-slate-300">
                              {line || ' '}
                            </span>
                            {attribution && (
                              <span className="opacity-0 group-hover:opacity-100 transition-opacity text-xs text-unicorn-400 px-2">
                                {attribution.agent_name || attribution.agent_id}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Attribution Sidebar */}
            <div className="space-y-4">
              {/* Summary */}
              <div className="card">
                <h3 className="text-sm font-semibold text-slate-200 mb-3">
                  Attribution Summary
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Total Lines:</span>
                    <span className="text-slate-200 font-medium">{codeLines.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">AI-Generated:</span>
                    <span className="text-unicorn-400 font-medium">
                      {Object.keys(lineAttributions).length}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Agents:</span>
                    <span className="text-slate-200 font-medium">
                      {new Set(attributions.map(a => a.agent_id)).size}
                    </span>
                  </div>
                </div>
              </div>

              {/* Selected Attribution Details */}
              <AnimatePresence>
                {selectedAttribution && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="card border-unicorn-500/30"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <h3 className="text-sm font-semibold text-unicorn-400">
                        Selected Attribution
                      </h3>
                      <button
                        onClick={() => setSelectedAttribution(null)}
                        className="text-slate-500 hover:text-slate-300"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="space-y-3">
                      {/* Lines */}
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Lines</p>
                        <p className="text-sm text-slate-200">
                          {selectedAttribution.start_line}-{selectedAttribution.end_line}
                          <span className="text-slate-500 ml-2">
                            ({selectedAttribution.lines_count} lines)
                          </span>
                        </p>
                      </div>

                      {/* Agent */}
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Agent</p>
                        <div className="flex items-center gap-2">
                          <User className="w-3 h-3 text-unicorn-400" />
                          <p className="text-sm text-slate-200">
                            {selectedAttribution.agent_name || selectedAttribution.agent_id}
                          </p>
                        </div>
                      </div>

                      {/* Model */}
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Model</p>
                        <div className="flex items-center gap-2">
                          <Sparkles className="w-3 h-3 text-unicorn-400" />
                          <p className="text-sm text-slate-200">
                            {selectedAttribution.model}
                          </p>
                        </div>
                      </div>

                      {/* Date */}
                      <div>
                        <p className="text-xs text-slate-500 mb-1">Generated</p>
                        <div className="flex items-center gap-2">
                          <Calendar className="w-3 h-3 text-unicorn-400" />
                          <p className="text-sm text-slate-200">
                            {formatDate(selectedAttribution.timestamp)}
                          </p>
                        </div>
                      </div>

                      {/* Prompt */}
                      {selectedAttribution.prompt && (
                        <div>
                          <p className="text-xs text-slate-500 mb-1">Original Prompt</p>
                          <div className="flex items-start gap-2">
                            <MessageSquare className="w-3 h-3 text-unicorn-400 mt-1 flex-shrink-0" />
                            <p className="text-xs text-slate-300 leading-relaxed">
                              {selectedAttribution.prompt}
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* All Attributions List */}
              <div className="card">
                <h3 className="text-sm font-semibold text-slate-200 mb-3">
                  All Attributions ({attributions.length})
                </h3>
                <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
                  {attributions.map((attr, index) => (
                    <button
                      key={attr.id || index}
                      onClick={() => setSelectedAttribution(attr)}
                      className={`
                        w-full text-left p-2.5 rounded-lg border transition-all
                        ${selectedAttribution?.id === attr.id
                          ? 'border-unicorn-500/50 bg-unicorn-500/10'
                          : 'border-slate-700/50 hover:border-slate-600 bg-slate-800/30'
                        }
                      `}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400">
                          Lines {attr.start_line}-{attr.end_line}
                        </span>
                        <span className="text-xs text-slate-500">
                          {attr.lines_count} lines
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 truncate">
                        {attr.agent_name || attr.agent_id}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

FileAttributionViewer.propTypes = {
  filePath: PropTypes.string.isRequired,
  attributions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string,
      agent_id: PropTypes.string.isRequired,
      agent_name: PropTypes.string,
      model: PropTypes.string.isRequired,
      timestamp: PropTypes.string.isRequired,
      start_line: PropTypes.number.isRequired,
      end_line: PropTypes.number.isRequired,
      lines_count: PropTypes.number.isRequired,
      prompt: PropTypes.string
    })
  ).isRequired,
  code: PropTypes.string.isRequired,
  onClose: PropTypes.func.isRequired
};

export default FileAttributionViewer;
