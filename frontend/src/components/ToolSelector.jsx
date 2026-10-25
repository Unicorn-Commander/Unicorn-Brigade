import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, Wrench, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import ToolCard from './ToolCard';
import { Button, Chip, EmptyState, ErrorState, Input, LoadingState } from './ui';

const toolId = (t) => (typeof t === 'string' ? t : t?.id || t?.name || t?.toolId || null);
const normalize = (list) => (Array.isArray(list) ? list.map(toolId).filter(Boolean) : []);
const prettyName = (id) => String(id).replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/**
 * ToolSelector — attach and detach tools on an agent.
 *
 * Assigned tools sit at the top as removable chips; the library below is
 * searchable and keyboard-first: Enter in the search adds the first match,
 * ArrowDown moves into the list. Every change goes straight to the API
 * (POST / DELETE /agents/:id/tools) and the caller is told through onUpdate.
 *
 *   <ToolSelector agentId={id} assignedTools={agent.tools} onUpdate={reload} />
 */
export default function ToolSelector({ agentId, assignedTools = [], onUpdate }) {
  const navigate = useNavigate();
  const [available, setAvailable] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(null);
  const assignedKey = normalize(assignedTools).join('|');
  const [assignedIds, setAssignedIds] = useState(() => normalize(assignedTools));
  const listRef = useRef(null);

  useEffect(() => {
    setAssignedIds(assignedKey ? assignedKey.split('|') : []);
  }, [assignedKey]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson('/tools');
      const tools = Array.isArray(data) ? data : data?.tools || [];
      setAvailable(tools.filter((t) => toolId(t)));
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byId = useMemo(() => new Map(available.map((t) => [toolId(t), t])), [available]);
  const assigned = useMemo(
    () => assignedIds.map((id) => byId.get(id) || { id, name: prettyName(id) }),
    [assignedIds, byId]
  );
  const candidates = useMemo(() => {
    const q = query.trim().toLowerCase();
    return available.filter((t) => {
      if (assignedIds.includes(toolId(t))) return false;
      if (!q) return true;
      return (
        String(t.name || '').toLowerCase().includes(q) ||
        String(t.description || '').toLowerCase().includes(q) ||
        String(toolId(t)).toLowerCase().includes(q)
      );
    });
  }, [available, assignedIds, query]);

  const add = async (tool) => {
    const id = toolId(tool);
    setBusy(id);
    try {
      await apiJson(`/agents/${agentId}/tools`, { method: 'POST', body: JSON.stringify({ toolId: id }) });
      setAssignedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
      notify.success(`${tool.name || prettyName(id)} added`);
      onUpdate?.();
    } catch (err) {
      notify.error(humanize(err, { what: 'adding the tool' }));
    } finally {
      setBusy(null);
    }
  };

  const remove = async (tool) => {
    const id = toolId(tool);
    setBusy(id);
    try {
      await apiJson(`/agents/${agentId}/tools/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setAssignedIds((prev) => prev.filter((x) => x !== id));
      notify.success(`${tool.name || prettyName(id)} removed`);
      onUpdate?.();
    } catch (err) {
      notify.error(humanize(err, { what: 'removing the tool' }));
    } finally {
      setBusy(null);
    }
  };

  const onSearchKey = (e) => {
    if (e.key === 'Enter' && candidates[0]) {
      e.preventDefault();
      add(candidates[0]);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      listRef.current?.querySelector('button')?.focus();
    }
  };

  let list;
  if (loading) {
    list = <LoadingState variant="list" count={4} label="Loading tools" />;
  } else if (error) {
    list = <ErrorState compact title="Couldn’t load the tool library" detail={humanize(error, { what: 'loading tools' })} onRetry={load} />;
  } else if (!available.length) {
    list = (
      <EmptyState
        compact
        icon={Wrench}
        title="No tools in the library yet"
        description="Tools arrive through MCP servers and the built-in Python library."
        action={
          <Button size="sm" variant="secondary" onClick={() => navigate('/mcp-servers')}>
            Open MCP servers
          </Button>
        }
      />
    );
  } else if (!candidates.length) {
    list = (
      <EmptyState
        compact
        icon={Search}
        title={query ? 'No tools match' : 'Every tool is already attached'}
        description={query ? 'Try another word.' : undefined}
        action={
          query ? (
            <Button size="sm" variant="secondary" icon={X} onClick={() => setQuery('')}>
              Clear search
            </Button>
          ) : undefined
        }
      />
    );
  } else {
    list = (
      <ul ref={listRef} className="flex max-h-96 flex-col gap-2 overflow-y-auto pr-1" aria-label="Available tools">
        {candidates.map((tool) => (
          <li key={toolId(tool)}>
            <ToolCard tool={tool} action="add" busy={busy === toolId(tool)} onAction={() => add(tool)} />
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-body font-semibold text-fg-strong">Attached</h3>
          <span className="text-caption text-muted">
            {assigned.length} tool{assigned.length === 1 ? '' : 's'}
          </span>
        </div>
        {assigned.length ? (
          <ul className="flex flex-wrap gap-1.5" aria-label="Attached tools">
            {assigned.map((tool) => (
              <li key={toolId(tool)} className="inline-flex">
                <Chip
                  tone="accent"
                  size="md"
                  icon={X}
                  onClick={() => remove(tool)}
                  disabled={busy === toolId(tool)}
                  aria-label={`Remove ${tool.name || prettyName(toolId(tool))}`}
                >
                  {tool.name || prettyName(toolId(tool))}
                </Chip>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body-sm text-muted">Nothing attached yet. Add a tool from the library below.</p>
        )}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-body font-semibold text-fg-strong">Library</h3>
          {!loading && !error && (
            <span className="text-caption text-muted">
              {candidates.length} available
            </span>
          )}
        </div>
        <div className="relative mb-3">
          <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            type="search"
            aria-label="Search the tool library"
            placeholder="Search tools… Enter adds the first match"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onSearchKey}
            className="pl-9"
          />
        </div>
        {list}
      </div>
    </div>
  );
}
