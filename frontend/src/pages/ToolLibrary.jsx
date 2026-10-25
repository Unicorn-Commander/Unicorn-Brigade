/**
 * Tool Library — THE WORKED EXEMPLAR of the design system.
 *
 * Every page in Brigade should read like this one. Copy its shape:
 *   1. <Page> + <PageHeader eyebrow/title/description/actions>  — one frame
 *   2. a toolbar of <Field>-less controls (search, selects) in a <Card>
 *   3. ALL FOUR STATES: loading (skeleton, same grid), error (human words +
 *      retry), empty (what is missing + the next step), offline
 *   4. content on <Card interactive> with <Chip> for type/status
 *   5. detail in a <Modal title description footer> — no hand-rolled frame
 *   6. zero raw palette classes, zero hex, zero arbitrary font sizes,
 *      every icon control named, keyboard reachable, no dead-end buttons
 *
 * frontend/docs/DESIGN-SYSTEM.md walks through each numbered block.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Wrench, Plus, ExternalLink, Copy, Server, Bot, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import api from '../services/api';
import Breadcrumbs from '../components/Breadcrumbs';
import {
  Button,
  IconButton,
  Card,
  Chip,
  Input,
  Select,
  Modal,
  Page,
  PageHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  Tooltip,
} from '../components/ui';

// Tool types carry meaning: MCP = external server, Python = built-in code,
// anything else = an integration. One tone each, everywhere.
const TYPE_TONE = { MCP: 'accent', Python: 'info' };
const typeTone = (type) => TYPE_TONE[type] || 'ok';

export default function ToolLibrary() {
  const navigate = useNavigate();
  const [tools, setTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const [domain, setDomain] = useState('');
  const [selected, setSelected] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getTools();
      setTools(data?.tools || (Array.isArray(data) ? data : []));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Offline is a state of the page, not a toast: show it where the data goes.
  useEffect(() => {
    const on = () => {
      setOffline(false);
      load();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  const types = useMemo(() => [...new Set(tools.map((t) => t.type).filter(Boolean))].sort(), [tools]);
  const domains = useMemo(() => [...new Set(tools.map((t) => t.domain).filter(Boolean))].sort(), [tools]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tools.filter((t) => {
      if (type && t.type !== type) return false;
      if (domain && t.domain !== domain) return false;
      if (!q) return true;
      const caps = Array.isArray(t.capabilities) ? t.capabilities : [];
      return (
        (t.name || '').toLowerCase().includes(q) ||
        (t.description || '').toLowerCase().includes(q) ||
        caps.some((c) => String(c).toLowerCase().includes(q))
      );
    });
  }, [tools, query, type, domain]);

  const hasFilters = Boolean(query || type || domain);
  const clearFilters = () => {
    setQuery('');
    setType('');
    setDomain('');
  };

  const copyUsage = async (tool) => {
    try {
      await navigator.clipboard.writeText(`agent.use_tool("${tool.id}", {params})`);
      notify.success('Usage example copied');
    } catch {
      notify.error('Couldn’t copy — your browser blocked clipboard access.');
    }
  };

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !tools.length) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = <LoadingState variant="cards" count={6} label="Loading tools" />;
  } else if (error) {
    body = <ErrorState title="Couldn’t load the tool library" detail={humanize(error, { what: 'loading tools' })} onRetry={load} />;
  } else if (!tools.length) {
    body = (
      <EmptyState
        icon={Wrench}
        title="No tools registered yet"
        description="Tools arrive through MCP servers and the built-in Python library. Start an MCP server and its tools appear here."
        action={
          <Button icon={Server} onClick={() => navigate('/mcp-servers')}>
            Open MCP servers
          </Button>
        }
      />
    );
  } else if (!filtered.length) {
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No tools match"
        description="Try another word, or clear the type and domain filters."
        action={
          <Button variant="secondary" size="sm" icon={X} onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else {
    body = (
      <ul className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Tools">
        {filtered.map((tool) => {
          const caps = Array.isArray(tool.capabilities) ? tool.capabilities : [];
          return (
            <li key={tool.id}>
              <Card as="button" type="button" interactive className="h-full w-full" onClick={() => setSelected(tool)}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-control bg-elevated text-title">
                      {tool.icon || <Wrench className="h-5 w-5 text-muted" />}
                    </span>
                    <div className="min-w-0">
                      <h3 className="truncate text-body font-semibold text-fg-strong">{tool.name}</h3>
                      <p className="truncate text-caption text-muted">{tool.provider}</p>
                    </div>
                  </div>
                  <Chip tone={typeTone(tool.type)} size="xs" uppercase>
                    {tool.type}
                  </Chip>
                </div>
                <p className="mb-3 line-clamp-2 text-body-sm text-muted">{tool.description}</p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {caps.slice(0, 2).map((cap) => (
                    <Chip key={cap} size="xs">
                      {cap}
                    </Chip>
                  ))}
                  {caps.length > 2 && (
                    <Chip size="xs" className="text-subtle">
                      +{caps.length - 2} more
                    </Chip>
                  )}
                  <span className="ml-auto">
                    <Chip tone={tool.status === 'active' ? 'ok' : 'warn'} size="xs" dot>
                      {tool.status === 'active' ? 'Ready' : 'Beta'}
                    </Chip>
                  </span>
                </div>
              </Card>
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <Page>
      <PageHeader
        breadcrumbs={<Breadcrumbs />}
        eyebrow="Tools"
        title="Tool Library"
        description={
          loading
            ? 'Every capability an agent can be given'
            : `${filtered.length === tools.length ? tools.length : `${filtered.length} of ${tools.length}`} tools available`
        }
        actions={
          <Tooltip content="Custom tools are added by registering an MCP server">
            <Button icon={Plus} onClick={() => navigate('/mcp-servers')}>
              Add a tool
            </Button>
          </Tooltip>
        }
      />

      {/* Toolbar */}
      <Card padding="sm" className="mb-5">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input
              type="search"
              aria-label="Search tools"
              placeholder="Search tools, capabilities…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select aria-label="Filter by type" value={type} onChange={(e) => setType(e.target.value)} className="md:w-44">
            <option value="">All types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by domain" value={domain} onChange={(e) => setDomain(e.target.value)} className="md:w-48">
            <option value="">All domains</option>
            {domains.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </Select>
        </div>
        {hasFilters && !loading && (
          <div className="mt-2 flex items-center gap-2 text-caption text-muted">
            <span>
              {filtered.length} match{filtered.length === 1 ? '' : 'es'}
            </span>
            <Button variant="link" size="xs" onClick={clearFilters}>
              Clear
            </Button>
          </div>
        )}
      </Card>

      {body}

      {/* Detail */}
      <Modal
        isOpen={Boolean(selected)}
        onClose={() => setSelected(null)}
        size="2xl"
        title={selected?.name}
        description={selected?.provider}
        footer={
          selected && (
            <>
              <Button variant="secondary" icon={ExternalLink} onClick={() => navigate('/docs')}>
                Docs
              </Button>
              <Button icon={Bot} onClick={() => navigate('/library')}>
                Attach to an agent
              </Button>
            </>
          )
        }
      >
        {selected && (
          <div className="space-y-5">
            <p className="text-body text-fg">{selected.description}</p>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="mb-1.5 text-caption text-muted">Type</dt>
                <dd>
                  <Chip tone={typeTone(selected.type)} uppercase>
                    {selected.type}
                  </Chip>
                </dd>
              </div>
              <div>
                <dt className="mb-1.5 text-caption text-muted">Domain</dt>
                <dd>
                  <Chip className="capitalize">{selected.domain || 'general'}</Chip>
                </dd>
              </div>
            </dl>
            {Array.isArray(selected.capabilities) && selected.capabilities.length > 0 && (
              <div>
                <p className="mb-1.5 text-caption text-muted">Capabilities</p>
                <div className="flex flex-wrap gap-1.5">
                  {selected.capabilities.map((cap) => (
                    <Chip key={cap}>{cap}</Chip>
                  ))}
                </div>
              </div>
            )}
            {Array.isArray(selected.parameters) && selected.parameters.length > 0 && (
              <div>
                <p className="mb-1.5 text-caption text-muted">Parameters</p>
                <pre className="overflow-x-auto rounded-control border border-border bg-surface p-3 font-mono text-body-sm text-fg">
                  {selected.parameters.join(',\n')}
                </pre>
              </div>
            )}
            <div>
              <p className="mb-1.5 text-caption text-muted">Usage</p>
              <div className="relative rounded-control border border-border bg-surface p-3 pr-12 font-mono text-body-sm text-fg">
                <code>
                  agent.use_tool(<span className="text-ok">&quot;{selected.id}&quot;</span>, &#123;params&#125;)
                </code>
                <span className="absolute right-1.5 top-1.5">
                  <IconButton icon={Copy} label="Copy usage example" size="sm" onClick={() => copyUsage(selected)} />
                </span>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </Page>
  );
}
