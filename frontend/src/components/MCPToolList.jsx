import { useMemo, useState } from 'react';
import { Copy, Search, Wrench, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import McpServerIcon from '../utils/mcpIcons';
import { Button, Chip, EmptyState, ErrorState, IconButton, Input, LoadingState, Modal } from './ui';

/**
 * MCPToolList — the tools a server declares, in a dialog (a bottom sheet on
 * phones, courtesy of Modal). Tools arrive from the detail endpoint, so the
 * page passes loading / error alongside the list.
 *
 *   <MCPToolList server={s} tools={[{name, description?, inputSchema?}]}
 *                loading error onRetry onClose />
 */
export default function MCPToolList({ server, tools = [], loading = false, error = null, onRetry, onClose }) {
  const [query, setQuery] = useState('');
  const title = server?.display_name || server?.name || 'Server';
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tools;
    return tools.filter((t) => String(t.name || '').toLowerCase().includes(q) || String(t.description || '').toLowerCase().includes(q));
  }, [tools, query]);

  const copy = async (name) => {
    try {
      await navigator.clipboard.writeText(name);
      notify.success('Tool name copied');
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };

  let body;
  if (loading) body = <LoadingState variant="list" count={4} label="Loading tools" />;
  else if (error) body = <ErrorState compact title="Couldn’t load the tools" detail={humanize(error, { what: 'loading the tools' })} onRetry={onRetry} />;
  else if (!tools.length) body = <EmptyState compact icon={Wrench} title="No tools declared" description="This server lists no capabilities in the registry. Start it to discover tools at runtime." />;
  else if (!filtered.length)
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No tools match"
        action={
          <Button size="sm" variant="secondary" icon={X} onClick={() => setQuery('')}>
            Clear search
          </Button>
        }
      />
    );
  else
    body = (
      <ul className="space-y-2" aria-label={`Tools of ${title}`}>
        {filtered.map((tool) => {
          const params = tool.inputSchema?.properties ? Object.keys(tool.inputSchema.properties) : [];
          const required = tool.inputSchema?.required || [];
          return (
            <li key={tool.name} className="flex items-start gap-3 rounded-control border border-border bg-surface/60 p-3">
              <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-elevated text-muted">
                <Wrench className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-mono text-body-sm font-medium text-fg-strong">{tool.name}</p>
                {tool.description && <p className="mt-0.5 line-clamp-2 text-body-sm text-muted">{tool.description}</p>}
                {params.length > 0 && (
                  <ul className="mt-1.5 flex flex-wrap gap-1" aria-label="Parameters">
                    {params.slice(0, 6).map((p) => (
                      <li key={p}>
                        <Chip size="xs" className="font-mono">
                          {p}
                          {required.includes(p) ? '*' : ''}
                        </Chip>
                      </li>
                    ))}
                    {params.length > 6 && (
                      <li>
                        <Chip size="xs">+{params.length - 6}</Chip>
                      </li>
                    )}
                  </ul>
                )}
              </div>
              <IconButton icon={Copy} label={`Copy ${tool.name}`} size="sm" onClick={() => copy(tool.name)} />
            </li>
          );
        })}
      </ul>
    );

  return (
    <Modal
      isOpen
      onClose={onClose}
      size="xl"
      title={
        <span className="inline-flex items-center gap-2">
          <McpServerIcon name={server?.name} className="h-5 w-5 text-accent" />
          {title}
        </span>
      }
      description={loading ? 'Loading declared tools…' : `${tools.length} declared tool${tools.length === 1 ? '' : 's'}${server?.transport ? ` · ${String(server.transport).toUpperCase()}` : ''}`}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Close
        </Button>
      }
    >
      {tools.length > 0 && !loading && !error && (
        <div className="relative mb-4">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input type="search" aria-label="Search tools" placeholder="Search tools…" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9" />
        </div>
      )}
      {body}
    </Modal>
  );
}
