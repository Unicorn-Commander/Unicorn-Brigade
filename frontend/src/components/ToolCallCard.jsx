/**
 * ToolCallCard — one tool call an agent made, live.
 *
 * Three states, on the shared status vocabulary:
 *   running  the call is out and no result is back yet (pulsing live dot)
 *   done     a result arrived; the card collapses, click to read it
 *   failed   the tool returned an error; the headline is in human words and
 *            the technical detail sits behind the disclosure, never in the
 *            person's face
 *
 * Also exports getToolIcon / TOOL_ICONS (the Agent Library uses them).
 */
import { useMemo, useState } from 'react';
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
  Copy,
  ExternalLink,
  Users,
} from 'lucide-react';
import PropTypes from 'prop-types';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { Button, Chip, IconButton, StatusDot } from './ui';

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

  // Delegation
  delegate: Users,
  delegate_to_agent: Users,

  // Default
  default: Wrench,
};

// Get the appropriate icon component for a tool name
const getToolIcon = (toolName) => {
  if (!toolName) return TOOL_ICONS.default;
  const normalizedName = String(toolName).toLowerCase().replace(/[-\s]/g, '_');
  if (TOOL_ICONS[normalizedName]) return TOOL_ICONS[normalizedName];
  for (const [key, icon] of Object.entries(TOOL_ICONS)) {
    if (key !== 'default' && (normalizedName.includes(key) || key.includes(normalizedName))) return icon;
  }
  return TOOL_ICONS.default;
};

// ── JSON, highlighted on the status tokens ───────────────────────────────────
const TOKEN_RE = /("(?:[^"\\]|\\.)*")(\s*:)?|(-?\d+\.?\d*(?:e[+-]?\d+)?)|\b(true|false|null)\b|([{}[\]:,])/gi;

function HighlightedJSON({ data }) {
  const lines = useMemo(() => {
    const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    return String(text ?? 'null')
      .split('\n')
      .map((line) => {
        const parts = [];
        let last = 0;
        let m;
        const re = new RegExp(TOKEN_RE.source, 'gi');
        while ((m = re.exec(line))) {
          if (m.index > last) parts.push({ t: 'plain', v: line.slice(last, m.index) });
          if (m[1]) parts.push({ t: m[2] ? 'key' : 'str', v: m[1] + (m[2] || '') });
          else if (m[3]) parts.push({ t: 'num', v: m[3] });
          else if (m[4]) parts.push({ t: 'bool', v: m[4] });
          else parts.push({ t: 'punct', v: m[5] });
          last = re.lastIndex;
        }
        if (last < line.length) parts.push({ t: 'plain', v: line.slice(last) });
        return parts;
      });
  }, [data]);
  const cls = { key: 'text-accent', str: 'text-ok', num: 'text-warn', bool: 'text-info', punct: 'text-muted', plain: 'text-fg' };
  return (
    <pre className="whitespace-pre font-mono text-caption leading-5">
      {lines.map((parts, i) => (
        <div key={i}>
          {parts.map((p, j) => (
            <span key={j} className={cls[p.t]}>
              {p.v}
            </span>
          ))}
        </div>
      ))}
    </pre>
  );
}

function previewArgs(args) {
  if (!args || typeof args !== 'object') return '';
  const entries = Object.entries(args);
  const head = entries
    .slice(0, 2)
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`.slice(0, 48))
    .join(' · ');
  return entries.length > 2 ? `${head} · …` : head;
}

const STATE = {
  running: { status: 'tool', tone: 'live', label: 'Running', border: 'border-live/30', icon: 'bg-live/10 text-live' },
  done: { status: 'done', tone: 'ok', label: 'Done', border: 'border-border', icon: 'bg-ok/10 text-ok' },
  failed: { status: 'error', tone: 'danger', label: 'Failed', border: 'border-danger/30', icon: 'bg-danger/10 text-danger' },
};

const errorText = (error) => {
  if (!error) return '';
  if (typeof error === 'string') return error;
  return error.message || error.error || error.detail || JSON.stringify(error);
};

// Tool Call Card Component
const ToolCallCard = ({ toolCall, defaultExpanded = false }) => {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const isError = Boolean(toolCall.error);
  const hasResult = toolCall.result !== undefined || isError;
  const state = !hasResult ? 'running' : isError ? 'failed' : 'done';
  const meta = STATE[state];
  const Icon = getToolIcon(toolCall.name);
  const raw = errorText(toolCall.error);
  const reason = isError ? humanize({ message: raw }, { what: 'running the tool' }) : '';
  const resultUrl = !isError && toolCall.result && typeof toolCall.result === 'object' ? toolCall.result.url : null;

  const copy = async (e) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(
        JSON.stringify({ name: toolCall.name, arguments: toolCall.arguments, result: isError ? { error: toolCall.error } : toolCall.result }, null, 2)
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };

  return (
    <div className={`my-1.5 overflow-hidden rounded-control border bg-card/60 ${meta.border}`}>
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        className="flex min-h-touch w-full items-center gap-2.5 px-2.5 py-1.5 text-left sm:min-h-10 transition-colors duration-fast hover:bg-elevated/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span aria-hidden="true" className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-chip ${meta.icon}`}>
          <Icon className="h-4 w-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2">
            <span className="truncate font-mono text-body-sm font-medium text-fg-strong">{toolCall.name}</span>
            <Chip tone={meta.tone} size="xs" dot pulse={state === 'running'}>
              {meta.label}
            </Chip>
          </span>
          {!expanded && (
            <span className="block truncate text-caption text-muted">
              {state === 'failed' ? reason : state === 'running' ? 'Waiting for the result…' : previewArgs(toolCall.arguments)}
            </span>
          )}
        </span>
        <ChevronRight
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-muted transition-transform duration-fast ${expanded ? 'rotate-90' : ''}`}
        />
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border px-3 pb-3 pt-2.5">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-micro font-semibold uppercase tracking-wider text-muted">Arguments</span>
              <IconButton icon={copied ? Check : Copy} label={copied ? 'Copied' : 'Copy tool call'} size="xs" onClick={copy} />
            </div>
            <div className="max-h-40 overflow-auto rounded-chip bg-surface p-2.5">
              <HighlightedJSON data={toolCall.arguments ?? {}} />
            </div>
          </div>

          {state === 'running' && (
            <p className="flex items-center gap-2 text-caption text-muted" role="status">
              <StatusDot status="tool" size="sm" />
              Running {toolCall.name}…
            </p>
          )}

          {state === 'done' && (
            <div>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-micro font-semibold uppercase tracking-wider text-muted">Result</span>
                {resultUrl && (
                  <Button as="a" href={resultUrl} target="_blank" rel="noopener noreferrer" variant="link" size="xs" icon={ExternalLink}>
                    Open
                  </Button>
                )}
              </div>
              <div className="max-h-56 overflow-auto rounded-chip bg-surface p-2.5">
                {typeof toolCall.result === 'string' ? (
                  <p className="whitespace-pre-wrap font-mono text-caption leading-5 text-fg">{toolCall.result}</p>
                ) : (
                  <HighlightedJSON data={toolCall.result} />
                )}
              </div>
            </div>
          )}

          {state === 'failed' && (
            <div className="rounded-chip border border-danger/30 bg-danger/5 p-2.5">
              <p className="text-body-sm font-medium text-danger">{toolCall.name} couldn’t finish</p>
              <p className="mt-0.5 text-caption text-fg">{reason}</p>
              {raw && raw !== reason && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-micro font-semibold uppercase tracking-wider text-muted">Technical details</summary>
                  <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap font-mono text-caption leading-5 text-muted">{raw}</pre>
                </details>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

ToolCallCard.propTypes = {
  toolCall: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string.isRequired,
    arguments: PropTypes.object,
    result: PropTypes.any,
    error: PropTypes.any,
  }).isRequired,
  defaultExpanded: PropTypes.bool,
};

// Export both the component and the icon getter for reuse
export { ToolCallCard, getToolIcon, TOOL_ICONS };
export default ToolCallCard;
