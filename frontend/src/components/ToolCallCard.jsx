import { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search,
  Calculator,
  Mail,
  Brain,
  Globe,
  Code,
  Clock,
  FileJson,
  Terminal,
  FileText,
  Image,
  Database,
  Bell,
  QrCode,
  Wrench,
  ChevronRight,
  Check,
  X,
  Loader2,
  Copy,
  ExternalLink
} from 'lucide-react';
import PropTypes from 'prop-types';

// Tool icon mapping - maps tool names to appropriate Lucide icons
const TOOL_ICONS = {
  // Search & Web
  web_search: Search,
  search: Search,
  google_search: Search,
  serper: Search,

  // Browser & HTTP
  browser: Globe,
  http_request: Globe,
  http: Globe,
  fetch: Globe,
  screenshot: Image,

  // Math & Calculations
  calculator: Calculator,
  math: Calculator,
  compute: Calculator,

  // Communication
  email: Mail,
  send_email: Mail,
  mail: Mail,
  notify: Bell,
  notification: Bell,

  // Memory & Knowledge
  memory: Brain,
  memory_store: Brain,
  memory_recall: Brain,
  remember: Brain,
  knowledge_store: Brain,
  knowledge_query: Brain,

  // Code & Development
  code: Code,
  code_sandbox: Code,
  execute_code: Code,
  python: Code,
  javascript: Code,
  shell: Terminal,
  bash: Terminal,
  terminal: Terminal,

  // Time & Date
  datetime: Clock,
  time: Clock,
  date: Clock,
  schedule: Clock,

  // Data & Files
  json: FileJson,
  json_parse: FileJson,
  file: FileText,
  file_read: FileText,
  file_write: FileText,
  text: FileText,

  // Database
  database: Database,
  db: Database,
  sql: Database,
  query: Database,

  // Image
  image: Image,
  generate_image: Image,
  analyze_image: Image,

  // QR Code
  qrcode: QrCode,
  qr: QrCode,

  // Default
  default: Wrench
};

// Get the appropriate icon component for a tool name
const getToolIcon = (toolName) => {
  if (!toolName) return TOOL_ICONS.default;

  const normalizedName = toolName.toLowerCase().replace(/[-_\s]/g, '_');

  // Check for exact match first
  if (TOOL_ICONS[normalizedName]) {
    return TOOL_ICONS[normalizedName];
  }

  // Check for partial matches
  for (const [key, icon] of Object.entries(TOOL_ICONS)) {
    if (normalizedName.includes(key) || key.includes(normalizedName)) {
      return icon;
    }
  }

  return TOOL_ICONS.default;
};

// Simple syntax highlighting for JSON
const SyntaxHighlightedJSON = ({ data, isError = false }) => {
  const highlighted = useMemo(() => {
    if (data === null || data === undefined) {
      return <span className="text-slate-500">null</span>;
    }

    const jsonString = typeof data === 'string' ? data : JSON.stringify(data, null, 2);

    // Split into lines for better formatting
    const lines = jsonString.split('\n');

    return lines.map((line, lineIndex) => {
      // Tokenize the line
      const tokens = [];
      let remaining = line;
      let tokenIndex = 0;

      while (remaining.length > 0) {
        // Match string (key or value)
        const stringMatch = remaining.match(/^("(?:[^"\\]|\\.)*")/);
        if (stringMatch) {
          const str = stringMatch[1];
          const isKey = remaining.slice(str.length).trimStart().startsWith(':');
          tokens.push(
            <span
              key={`${lineIndex}-${tokenIndex++}`}
              className={isKey ? 'text-purple-400' : isError ? 'text-red-300' : 'text-emerald-400'}
            >
              {str}
            </span>
          );
          remaining = remaining.slice(str.length);
          continue;
        }

        // Match number
        const numberMatch = remaining.match(/^(-?\d+\.?\d*(?:e[+-]?\d+)?)/i);
        if (numberMatch) {
          tokens.push(
            <span key={`${lineIndex}-${tokenIndex++}`} className="text-amber-400">
              {numberMatch[1]}
            </span>
          );
          remaining = remaining.slice(numberMatch[1].length);
          continue;
        }

        // Match boolean/null
        const boolMatch = remaining.match(/^(true|false|null)/);
        if (boolMatch) {
          tokens.push(
            <span key={`${lineIndex}-${tokenIndex++}`} className="text-cyan-400">
              {boolMatch[1]}
            </span>
          );
          remaining = remaining.slice(boolMatch[1].length);
          continue;
        }

        // Match punctuation
        const punctMatch = remaining.match(/^([{}\[\]:,])/);
        if (punctMatch) {
          tokens.push(
            <span key={`${lineIndex}-${tokenIndex++}`} className="text-slate-500">
              {punctMatch[1]}
            </span>
          );
          remaining = remaining.slice(1);
          continue;
        }

        // Whitespace or other characters
        tokens.push(
          <span key={`${lineIndex}-${tokenIndex++}`} className="text-slate-400">
            {remaining[0]}
          </span>
        );
        remaining = remaining.slice(1);
      }

      return (
        <div key={lineIndex} className="leading-relaxed">
          {tokens}
        </div>
      );
    });
  }, [data, isError]);

  return <div className="font-mono text-[11px]">{highlighted}</div>;
};

SyntaxHighlightedJSON.propTypes = {
  data: PropTypes.any,
  isError: PropTypes.bool
};

// Tool Call Card Component
const ToolCallCard = ({ toolCall, compact = false }) => {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const hasResult = toolCall.result !== undefined || toolCall.error;
  const isError = !!toolCall.error;
  const isLoading = !hasResult;

  const IconComponent = getToolIcon(toolCall.name);

  const copyToClipboard = async (e) => {
    e.stopPropagation();
    const content = {
      name: toolCall.name,
      arguments: toolCall.arguments,
      result: isError ? { error: toolCall.error } : toolCall.result
    };
    await navigator.clipboard.writeText(JSON.stringify(content, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Status colors and styles
  const statusConfig = {
    loading: {
      border: 'border-yellow-500/30',
      bg: 'bg-yellow-500/5',
      iconColor: 'text-yellow-400',
      badge: 'bg-yellow-500/20 text-yellow-400',
      badgeText: 'running'
    },
    success: {
      border: 'border-emerald-500/30',
      bg: 'bg-emerald-500/5',
      iconColor: 'text-emerald-400',
      badge: 'bg-emerald-500/20 text-emerald-400',
      badgeText: 'completed'
    },
    error: {
      border: 'border-red-500/30',
      bg: 'bg-red-500/5',
      iconColor: 'text-red-400',
      badge: 'bg-red-500/20 text-red-400',
      badgeText: 'failed'
    }
  };

  const status = isLoading ? 'loading' : isError ? 'error' : 'success';
  const config = statusConfig[status];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className={`
        my-2 rounded-lg border overflow-hidden transition-all duration-200
        ${config.border} ${config.bg}
        ${expanded ? 'shadow-lg shadow-black/20' : 'shadow-sm'}
      `}
    >
      {/* Header - Always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`
          w-full flex items-center gap-2.5 px-3 py-2.5 text-left
          hover:bg-slate-700/20 transition-colors group
        `}
      >
        {/* Tool Icon */}
        <div className={`
          flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center
          ${isLoading ? 'bg-yellow-500/20' : isError ? 'bg-red-500/20' : 'bg-emerald-500/20'}
        `}>
          {isLoading ? (
            <Loader2 className={`w-4 h-4 ${config.iconColor} animate-spin`} />
          ) : (
            <IconComponent className={`w-4 h-4 ${config.iconColor}`} />
          )}
        </div>

        {/* Tool Name */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-slate-200 truncate">
              {toolCall.name}
            </span>
            <span className={`
              text-[10px] px-1.5 py-0.5 rounded-full font-medium
              ${config.badge}
            `}>
              {config.badgeText}
            </span>
          </div>

          {/* Compact preview of arguments */}
          {!expanded && toolCall.arguments && (
            <p className="text-[11px] text-slate-500 truncate mt-0.5">
              {Object.entries(toolCall.arguments).slice(0, 2).map(([k, v]) =>
                `${k}: ${typeof v === 'string' ? v.slice(0, 30) : JSON.stringify(v).slice(0, 30)}`
              ).join(', ')}
              {Object.keys(toolCall.arguments).length > 2 && '...'}
            </p>
          )}
        </div>

        {/* Status Icon */}
        <div className="flex items-center gap-2">
          {hasResult && !isError && (
            <Check className="w-4 h-4 text-emerald-400" />
          )}
          {isError && (
            <X className="w-4 h-4 text-red-400" />
          )}
          <ChevronRight
            className={`
              w-4 h-4 text-slate-500 transition-transform duration-200
              ${expanded ? 'rotate-90' : ''}
            `}
          />
        </div>
      </button>

      {/* Expandable Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-3 border-t border-slate-700/30">
              {/* Arguments Section */}
              <div className="pt-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                    Arguments
                  </span>
                  <button
                    onClick={copyToClipboard}
                    className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <div className="bg-slate-900/60 rounded-md p-2.5 overflow-x-auto max-h-32 custom-scrollbar">
                  <SyntaxHighlightedJSON data={toolCall.arguments} />
                </div>
              </div>

              {/* Result Section */}
              {hasResult && (
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`
                      text-[10px] font-semibold uppercase tracking-wider
                      ${isError ? 'text-red-500' : 'text-slate-500'}
                    `}>
                      {isError ? 'Error' : 'Result'}
                    </span>
                    {!isError && toolCall.result?.url && (
                      <a
                        href={toolCall.result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-[10px] text-purple-400 hover:text-purple-300 transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-3 h-3" />
                        Open
                      </a>
                    )}
                  </div>
                  <div className={`
                    bg-slate-900/60 rounded-md p-2.5 overflow-x-auto max-h-48 custom-scrollbar
                    ${isError ? 'border border-red-500/20' : ''}
                  `}>
                    {isError ? (
                      <p className="text-[11px] text-red-400 font-mono whitespace-pre-wrap">
                        {toolCall.error}
                      </p>
                    ) : (
                      <SyntaxHighlightedJSON data={toolCall.result} />
                    )}
                  </div>
                </div>
              )}

              {/* Loading indicator for result */}
              {isLoading && (
                <div className="flex items-center gap-2 py-2 text-slate-500">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-[11px]">Waiting for result...</span>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

ToolCallCard.propTypes = {
  toolCall: PropTypes.shape({
    name: PropTypes.string.isRequired,
    arguments: PropTypes.object,
    result: PropTypes.any,
    error: PropTypes.string
  }).isRequired,
  compact: PropTypes.bool
};

// Export both the component and the icon getter for reuse
export { ToolCallCard, getToolIcon, TOOL_ICONS };
export default ToolCallCard;
