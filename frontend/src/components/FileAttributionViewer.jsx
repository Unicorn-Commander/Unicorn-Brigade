import { useMemo, useState } from 'react';
import { Calendar, Copy, FileCode, MessageSquare, Sparkles, User } from 'lucide-react';
import PropTypes from 'prop-types';
import notify from '../utils/notify';
import { Button, Card, Chip, IconButton, Modal } from './ui';

/**
 * FileAttributionViewer — every attribution recorded for one file, each with
 * the exact lines the agent generated, in a dialog.
 *
 * GET /trace/files/{path} returns the attributions (with generatedCode per
 * range) but NOT the full file, so the file view is built from the attributed
 * ranges. When a caller does pass `code` (the whole file), it is rendered with
 * the attributed lines highlighted. Code is always rendered as text — never
 * injected as HTML.
 */
const fileName = (p = '') => p.split('/').pop() || p;
const fmtDateTime = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text);
    notify.success(what);
  } catch {
    notify.error('Couldn’t copy — your browser blocked clipboard access.');
  }
}

function Snippet({ code, startLine = 1, label, copyLabel }) {
  const lines = (code || '').replace(/\n$/, '').split('\n');
  return (
    <div className="overflow-hidden rounded-control border border-border bg-surface/70">
      <div className="flex items-center gap-2 border-b border-border bg-elevated/50 py-1 pl-3 pr-1">
        <span className="min-w-0 flex-1 truncate font-mono text-caption text-muted">{label}</span>
        <IconButton icon={Copy} label={copyLabel} size="xs" onClick={() => copy(code || '', 'Code copied')} />
      </div>
      <pre className="max-h-80 overflow-auto p-3 font-mono text-body-sm leading-5 text-fg">
        {lines.map((line, i) => (
          <div key={i} className="flex">
            <span aria-hidden="true" className="w-10 shrink-0 select-none pr-3 text-right text-subtle">
              {startLine + i}
            </span>
            <code className="min-w-0 flex-1 whitespace-pre">{line || ' '}</code>
          </div>
        ))}
      </pre>
    </div>
  );
}

export default function FileAttributionViewer({ filePath, attributions, code, onClose }) {
  const [selectedId, setSelectedId] = useState(attributions[0]?.id || null);

  const sorted = useMemo(() => [...attributions].sort((a, b) => (a.start_line || 0) - (b.start_line || 0)), [attributions]);
  const lineOwner = useMemo(() => {
    const map = new Map();
    for (const a of attributions) {
      if (a.start_line == null || a.end_line == null) continue;
      for (let i = a.start_line; i <= a.end_line; i += 1) map.set(i, a);
    }
    return map;
  }, [attributions]);
  const attributedLines = lineOwner.size;
  const agents = new Set(attributions.map((a) => a.agent_name || a.agent_id)).size;
  const hasFile = typeof code === 'string' && code.length > 0;
  const allCode = hasFile ? code : sorted.map((a) => a.generated_code || '').filter(Boolean).join('\n\n');

  return (
    <Modal
      isOpen
      onClose={onClose}
      size="3xl"
      title={fileName(filePath)}
      description={filePath}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
          <Button variant="secondary" icon={Copy} onClick={() => copy(allCode, hasFile ? 'File copied' : 'Attributed code copied')} disabled={!allCode}>
            {hasFile ? 'Copy file' : 'Copy attributed code'}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="accent" size="sm" className="tabular-nums">
            {attributions.length} attribution{attributions.length === 1 ? '' : 's'}
          </Chip>
          <Chip size="sm" className="tabular-nums">
            {attributedLines.toLocaleString()} lines attributed
          </Chip>
          <Chip size="sm" className="tabular-nums">
            {agents} agent{agents === 1 ? '' : 's'}
          </Chip>
          {!hasFile && <span className="text-caption text-muted">Showing the attributed ranges; the trace service doesn’t store the whole file.</span>}
        </div>

        {hasFile && (
          <div className="overflow-hidden rounded-control border border-border bg-surface/70">
            <div className="border-b border-border bg-elevated/50 px-3 py-1 font-mono text-caption text-muted">Full file · attributed lines marked</div>
            <pre className="max-h-96 overflow-auto p-3 font-mono text-body-sm leading-5 text-fg">
              {code.split('\n').map((line, i) => {
                const n = i + 1;
                const owner = lineOwner.get(n);
                const selected = owner && owner.id === selectedId;
                return (
                  <div
                    key={n}
                    className={`flex ${owner ? 'border-l-2 border-accent/40' : 'border-l-2 border-transparent'} ${selected ? 'bg-accent/10' : ''}`}
                    onClick={owner ? () => setSelectedId(owner.id) : undefined}
                  >
                    <span aria-hidden="true" className="w-10 shrink-0 select-none pr-3 text-right text-subtle">
                      {n}
                    </span>
                    <code className="min-w-0 flex-1 whitespace-pre">{line || ' '}</code>
                  </div>
                );
              })}
            </pre>
          </div>
        )}

        <ol className="space-y-3" aria-label="Attributions">
          {sorted.map((a, i) => {
            const selected = a.id === selectedId;
            return (
              <li key={a.id || i}>
                <Card padding="sm" className={selected ? 'border-accent/50' : ''}>
                  <button type="button" className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-chip" onClick={() => setSelectedId(a.id)} aria-pressed={selected}>
                    <Chip tone="accent" size="xs" className="font-mono tabular-nums">
                      {a.start_line != null ? `${a.start_line}–${a.end_line}` : 'range unknown'}
                    </Chip>
                    <span className="inline-flex items-center gap-1 text-body-sm font-medium text-fg-strong">
                      <User aria-hidden="true" className="h-3.5 w-3.5 text-muted" />
                      {a.agent_name || a.agent_id}
                    </span>
                    {a.model && (
                      <span className="inline-flex items-center gap-1 text-caption text-muted">
                        <Sparkles aria-hidden="true" className="h-3 w-3" />
                        {a.model}
                      </span>
                    )}
                    {a.change_type && (
                      <Chip size="xs" className="capitalize">
                        {a.change_type}
                      </Chip>
                    )}
                    {a.timestamp && (
                      <span className="ml-auto inline-flex items-center gap-1 text-caption text-muted">
                        <Calendar aria-hidden="true" className="h-3 w-3" />
                        {fmtDateTime(a.timestamp)}
                      </span>
                    )}
                  </button>
                  {a.prompt && (
                    <p className="mt-2 flex items-start gap-1.5 text-caption text-muted">
                      <MessageSquare aria-hidden="true" className="mt-0.5 h-3 w-3 shrink-0" />
                      {a.prompt}
                    </p>
                  )}
                  {a.generated_code ? (
                    <div className="mt-2">
                      <Snippet code={a.generated_code} startLine={a.start_line || 1} label={`${a.lines_count ?? ''} lines by ${a.agent_name || a.agent_id}`} copyLabel={`Copy lines ${a.start_line}–${a.end_line}`} />
                    </div>
                  ) : (
                    <p className="mt-2 inline-flex items-center gap-1.5 text-caption text-subtle">
                      <FileCode aria-hidden="true" className="h-3 w-3" />
                      No code snippet was stored for this range.
                    </p>
                  )}
                </Card>
              </li>
            );
          })}
        </ol>
      </div>
    </Modal>
  );
}

FileAttributionViewer.propTypes = {
  filePath: PropTypes.string.isRequired,
  attributions: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string,
      agent_id: PropTypes.string,
      agent_name: PropTypes.string,
      model: PropTypes.string,
      timestamp: PropTypes.string,
      start_line: PropTypes.number,
      end_line: PropTypes.number,
      lines_count: PropTypes.number,
      prompt: PropTypes.string,
      generated_code: PropTypes.string,
      change_type: PropTypes.string,
    })
  ).isRequired,
  code: PropTypes.string,
  onClose: PropTypes.func.isRequired,
};
