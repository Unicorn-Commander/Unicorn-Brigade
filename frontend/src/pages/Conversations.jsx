/**
 * Conversations — every saved chat with an agent.
 *
 * Shaped on the Tool Library exemplar: <Page> + <PageHeader>, a toolbar Card
 * (search · sort · agent filter), ALL FOUR STATES in the place the list goes,
 * rows as Cards with the agent's real portrait, and a per-row Menu with only
 * the actions the API supports (GET / PATCH title / DELETE in
 * app/api/conversation_routes.py): Open · Rename · Delete.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Cpu, MessageSquare, MessageSquarePlus, MoreHorizontal, Pencil, Search, Trash2, X } from 'lucide-react';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { apiJson } from '../services/http';
import AgentAvatar from '../components/AgentAvatar';
import { formatAbsolute, formatRelative, shortModel } from '../components/ChatMessage';
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  Input,
  LoadingState,
  Menu,
  Modal,
  OfflineState,
  PageHeader,
  Page,
  Select,
  Tooltip,
} from '../components/ui';

// One tone per conversation status, everywhere.
const STATUS = {
  active: { tone: 'ok', label: 'Active' },
  completed: { tone: 'info', label: 'Completed' },
  archived: { tone: 'neutral', label: 'Archived' },
};
const statusOf = (s) => STATUS[s] || { tone: 'neutral', label: s || 'Unknown' };
const agentLabel = (c) => c.agent?.displayName || c.agent?.name || c.agent_id || 'Unknown agent';
const titleOf = (c) => c.title || 'Untitled conversation';
const when = (c) => c.updated_at || c.created_at;

export default function Conversations() {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('newest');
  const [agentFilter, setAgentFilter] = useState('');

  const [renaming, setRenaming] = useState(null); // conversation
  const [renameValue, setRenameValue] = useState('');
  const [renameBusy, setRenameBusy] = useState(false);
  const [renameError, setRenameError] = useState(null);
  const [deleting, setDeleting] = useState(null); // conversation
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const renameInputRef = useRef(null);

  // The roster supplies each face. A conversation record carries the agent's
  // id and name but not its portrait link, so drawing from it missed real
  // portraits (Majik showed the emoji fallback). Best-effort: if the roster
  // fails, rows fall back to the conversation's own agent record.
  const [roster, setRoster] = useState(() => new Map());
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = {
      limit: 50,
      q: query.trim() || undefined,
      agent_id: agentFilter || undefined,
    };
    // Both before the first render, so every row's face comes from the roster.
    const [convs, agents] = await Promise.allSettled([apiJson('/conversations', { params }), apiJson('/agents')]);
    if (agents.status === 'fulfilled') {
      const d = agents.value;
      setRoster(new Map((d?.agents || (Array.isArray(d) ? d : [])).map((a) => [a.id, a])));
    }
    if (convs.status === 'fulfilled') {
      setConversations(convs.value?.conversations || []);
      setTotal(Number(convs.value?.total ?? convs.value?.conversations?.length ?? 0));
    }
    else setError(convs.reason);
    setLoading(false);
  }, [agentFilter, query]);

  useEffect(() => {
    load();
  }, [load]);

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

  const agentsInList = useMemo(() => {
    const m = new Map();
    for (const agent of roster.values()) {
      if (agent.id) m.set(agent.id, agent.displayName || agent.name || agent.id);
    }
    for (const c of conversations) {
      const id = c.agent?.id || c.agent_id;
      if (id && !m.has(id)) m.set(id, agentLabel(c));
    }
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [conversations, roster]);

  const filtered = useMemo(() => {
    const list = [...conversations];
    const time = (c) => new Date(when(c) || 0).getTime();
    list.sort((a, b) => {
      if (sort === 'oldest') return time(a) - time(b);
      if (sort === 'most-messages') return (b.message_count || 0) - (a.message_count || 0);
      if (sort === 'a-z') return titleOf(a).localeCompare(titleOf(b));
      return time(b) - time(a);
    });
    return list;
  }, [conversations, sort]);

  const hasFilters = Boolean(query.trim() || agentFilter);
  const clearFilters = () => {
    setQuery('');
    setAgentFilter('');
  };

  const open = (c) => navigate(`/chat?conversation=${encodeURIComponent(c.id)}`);

  const startRename = (c) => {
    setRenaming(c);
    setRenameValue(c.title || '');
    setRenameError(null);
  };
  const submitRename = async (e) => {
    e?.preventDefault?.();
    if (!renaming) return;
    const title = renameValue.trim();
    if (!title) {
      setRenameError('Give the conversation a name.');
      return;
    }
    setRenameBusy(true);
    setRenameError(null);
    try {
      const updated = await apiJson(`/conversations/${renaming.id}`, { method: 'PATCH', body: JSON.stringify({ title }) });
      setConversations((prev) => prev.map((c) => (c.id === renaming.id ? { ...c, ...(updated || {}), title } : c)));
      setRenaming(null);
      notify.success('Renamed');
    } catch (err) {
      setRenameError(humanize(err, { what: 'renaming the conversation' }));
    } finally {
      setRenameBusy(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await apiJson(`/conversations/${deleting.id}`, { method: 'DELETE' });
      setConversations((prev) => prev.filter((c) => c.id !== deleting.id));
      setTotal((count) => Math.max(0, count - 1));
      setDeleting(null);
      notify.success('Conversation deleted');
    } catch (err) {
      setDeleteError(humanize(err, { what: 'deleting the conversation' }));
    } finally {
      setDeleteBusy(false);
    }
  };

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !conversations.length) {
    body = <OfflineState onRetry={load} />;
  } else if (loading) {
    body = <LoadingState variant="list" count={6} label="Loading conversations" />;
  } else if (error) {
    body = <ErrorState title="Couldn’t load your conversations" detail={humanize(error, { what: 'loading conversations' })} onRetry={load} />;
  } else if (!conversations.length && !hasFilters) {
    body = (
      <EmptyState
        icon={MessageSquare}
        title="No conversations yet"
        description="Talk to an agent and the conversation is saved here, with every tool call it made."
        action={
          <Button icon={MessageSquarePlus} onClick={() => navigate('/chat')}>
            Start a chat
          </Button>
        }
      />
    );
  } else if (!filtered.length) {
    body = (
      <EmptyState
        compact
        icon={Search}
        title="No conversations match"
        description="Try another title, or clear the search and the agent filter."
        action={
          <Button variant="secondary" size="sm" icon={X} onClick={clearFilters}>
            Clear filters
          </Button>
        }
      />
    );
  } else {
    body = (
      <ul className="space-y-2" aria-label="Conversations">
        {filtered.map((c) => {
          const st = statusOf(c.status);
          const title = titleOf(c);
          const ts = when(c);
          return (
            <li key={c.id}>
              <Card
                padding="none"
                className="relative flex items-start gap-3 p-3 transition-[border-color,box-shadow] duration-base ease-standard hover:border-border-strong hover:shadow-e2 focus-within:border-border-strong focus-within:shadow-e2 sm:items-center sm:gap-4 sm:px-4"
              >
                <AgentAvatar agent={roster.get(c.agent?.id || c.agent_id) || c.agent || { id: c.agent_id }} size={40} rounded="rounded-control" className="mt-0.5 sm:mt-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex min-w-0 items-baseline gap-2">
                    <Tooltip content={title}>
                      {/* The title is the row's link: its ::after stretches over the card so the whole row opens the conversation. */}
                      <button
                        type="button"
                        onClick={() => open(c)}
                        className="min-w-0 truncate text-left text-body font-semibold text-fg-strong after:absolute after:inset-0 after:rounded-card after:content-[''] hover:text-accent focus-visible:outline-none"
                      >
                        {title}
                      </button>
                    </Tooltip>
                  </div>
                  <p className="truncate text-body-sm text-muted">with {agentLabel(c)}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <Chip size="xs">
                      {c.message_count || 0} {c.message_count === 1 ? 'message' : 'messages'}
                    </Chip>
                    {c.model && (
                      <Chip size="xs" icon={Cpu}>
                        {shortModel(c.model)}
                      </Chip>
                    )}
                    {c.status && (
                      <Chip size="xs" tone={st.tone} dot>
                        {st.label}
                      </Chip>
                    )}
                    {c.total_tokens > 0 && <span className="text-micro text-subtle">{c.total_tokens.toLocaleString()} tokens</span>}
                  </div>
                </div>
                <div className="relative z-raised flex shrink-0 items-center gap-1 self-start sm:self-center">
                  {ts && (
                    <Tooltip content={formatAbsolute(ts)}>
                      <time dateTime={ts} tabIndex={0} className="rounded-chip text-caption text-muted">
                        {formatRelative(ts)}
                      </time>
                    </Tooltip>
                  )}
                  <Menu
                    align="end"
                    trigger={({ props }) => (
                      <Button variant="ghost" size="sm" iconOnly icon={MoreHorizontal} aria-label={`Actions for ${title}`} className="min-h-touch min-w-touch sm:min-h-0 sm:min-w-0" {...props} />
                    )}
                    items={[
                      { id: 'open', label: 'Open', icon: MessageSquare, onSelect: () => open(c) },
                      { id: 'rename', label: 'Rename', icon: Pencil, onSelect: () => startRename(c) },
                      { type: 'separator' },
                      { id: 'delete', label: 'Delete', icon: Trash2, tone: 'danger', onSelect: () => { setDeleteError(null); setDeleting(c); } },
                    ]}
                  />
                </div>
              </Card>
            </li>
          );
        })}
      </ul>
    );
  }

  const description = loading
    ? 'Every chat with an agent, saved with its tool calls'
    : total === 0 && !hasFilters
      ? 'Nothing saved yet'
      : hasFilters
        ? `${total} matching ${total === 1 ? 'conversation' : 'conversations'}`
        : `${total} ${total === 1 ? 'conversation' : 'conversations'}`;

  return (
    <Page width="wide" className="[contain:inline-size]">
      <PageHeader
        eyebrow="Main"
        title="Conversations"
        description={description}
        actions={
          <Button icon={MessageSquarePlus} className="min-h-touch sm:min-h-0" onClick={() => navigate('/chat')}>
            New chat
          </Button>
        }
      />

      {/* Toolbar */}
      <Card padding="sm" className="mb-5">
        <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_auto_auto]">
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <Input
              type="search"
              aria-label="Search conversations"
              placeholder="Search by title…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="min-h-touch pl-9 sm:min-h-0"
            />
          </div>
          <Select aria-label="Sort conversations" value={sort} onChange={(e) => setSort(e.target.value)} className="min-h-touch sm:min-h-0 md:w-44">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="most-messages">Most messages</option>
            <option value="a-z">A to Z</option>
          </Select>
          <Select aria-label="Filter by agent" value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)} className="min-h-touch sm:min-h-0 md:w-52">
            <option value="">All agents</option>
            {agentsInList.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </Select>
        </div>
        {hasFilters && !loading && (
          <div className="mt-2 flex items-center gap-2 text-caption text-muted">
            <span>
              {total} match{total === 1 ? '' : 'es'}
            </span>
            <Button variant="link" size="xs" onClick={clearFilters}>
              Clear
            </Button>
          </div>
        )}
      </Card>

      {body}

      {/* Rename */}
      <Modal
        isOpen={Boolean(renaming)}
        onClose={() => (renameBusy ? null : setRenaming(null))}
        title="Rename conversation"
        description={renaming ? `with ${agentLabel(renaming)}` : undefined}
        initialFocusRef={renameInputRef}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRenaming(null)} disabled={renameBusy}>
              Cancel
            </Button>
            <Button onClick={submitRename} loading={renameBusy}>
              Save
            </Button>
          </>
        }
      >
        <form onSubmit={submitRename}>
          <Field label="Title" error={renameError}>
            <Input ref={renameInputRef} value={renameValue} onChange={(e) => setRenameValue(e.target.value)} maxLength={200} autoComplete="off" />
          </Field>
        </form>
      </Modal>

      {/* Delete */}
      <Modal
        isOpen={Boolean(deleting)}
        onClose={() => (deleteBusy ? null : setDeleting(null))}
        tone="danger"
        title="Delete this conversation?"
        description={deleting ? `“${titleOf(deleting)}” with ${agentLabel(deleting)} and its ${deleting.message_count || 0} messages will be removed. This can’t be undone.` : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)} disabled={deleteBusy}>
              Cancel
            </Button>
            <Button variant="danger" icon={Trash2} onClick={confirmDelete} loading={deleteBusy}>
              Delete
            </Button>
          </>
        }
      >
        {deleteError && (
          <p role="alert" className="text-body-sm text-danger">
            {deleteError}
          </p>
        )}
      </Modal>
    </Page>
  );
}
