/**
 * Chat — talk to one agent and watch it work.
 *
 *   /chat                       first active agent
 *   /chat?agent=<id>            deep link from the roster / org chart / dock
 *   /chat?conversation=<id>     resume a saved conversation
 *
 * The header is the agent's portrait, name and role with a live StatusDot
 * (thinking · running a tool · responding) fed by the stream; the model and
 * tools are one click away; the agent switcher is a searchable picker. Replies
 * stream token by token, tool calls appear as cards the moment the agent makes
 * them, Escape stops a reply, a failed send is an inline error with "Try again".
 * Every state of the page is designed: loading (skeleton), no agents, agents
 * failed, offline, conversation missing.
 *
 * Capabilities kept from the old page: streaming, tool calls, model override
 * (now a picker, honouring the Settings default), conversation persistence
 * (create / save / resume), voice calls (LiveKit), the ?agent= deep link,
 * abort. The duplicated send path is gone; one `send` does it all.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  ArrowDown,
  Bot,
  Check,
  ChevronDown,
  Cpu,
  MessageSquarePlus,
  MoreHorizontal,
  Search,
  Send,
  Sparkles,
  Square,
  Wrench,
} from 'lucide-react';
import { humanize } from '../utils/errors';
import { getPreferences } from '../utils/preferences';
import { prettyDomain, roleLine } from '../utils/agentClass';
import api from '../services/api';
import { apiJson } from '../services/http';
import AgentAvatar from '../components/AgentAvatar';
import ChatMessage, { shortModel } from '../components/ChatMessage';
import { getToolIcon } from '../components/ToolCallCard';
import VoiceCallButton from '../components/VoiceCallButton';
import VoiceCallModal from '../components/VoiceCallModal';
import {
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Field,
  IconButton,
  Input,
  Kbd,
  Menu,
  OfflineState,
  Select,
  Sheet,
  StatusDot,
  statusMeta,
  Tooltip,
} from '../components/ui';

const SUGGESTIONS = ['Tell me about yourself', 'What can you help with?', 'What are you working on right now?'];
const MAX_COMPOSER_PX = 148; // ~6 lines of body text plus padding

const agentName = (a) => a?.displayName || a?.name || 'Agent';

/** The agent's tools as { name, label, provider, paid } however the roster states them. */
function toolList(agent) {
  if (!agent) return [];
  const details = Array.isArray(agent.toolDetails) && agent.toolDetails.length ? agent.toolDetails : null;
  const source = details || (Array.isArray(agent.tools) && agent.tools.length ? agent.tools : agent.agentTools) || [];
  return source
    .map((t) => {
      if (typeof t === 'string') return { name: t, label: t, provider: null, paid: false };
      const name = t?.name || t?.tool?.name || t?.toolId || '';
      return { name, label: t?.displayName || t?.tool?.displayName || name, provider: t?.provider || t?.tool?.provider || null, paid: Boolean(t?.costTier && t.costTier !== 'free') };
    })
    .filter((t) => t.name);
}

/** A stored message's tool_calls + tool_results, merged back into live cards. */
function storedToolCalls(msg) {
  const calls = Array.isArray(msg.tool_calls) ? msg.tool_calls : [];
  const results = Array.isArray(msg.tool_results) ? msg.tool_results : [];
  const used = new Set();
  return calls.map((c, i) => {
    let r = results.find((x, j) => !used.has(j) && (c.id ? x.id === c.id : x.name === c.name));
    if (!r && results[i] && !used.has(i)) r = results[i];
    if (r) used.add(results.indexOf(r));
    const errored = r && (r.error || r.success === false);
    return {
      id: c.id || `${msg.id}-${i}`,
      name: c.name || c.function?.name || 'tool',
      arguments: c.arguments || c.function?.arguments || {},
      result: r ? r.result ?? r.output ?? r.content ?? null : null,
      error: errored ? r.error || 'The tool reported a failure.' : undefined,
    };
  });
}

/** Attach a tool_result event to its call: by id first, then the first unfilled call with that name. */
function attachResult(calls, ev) {
  let matched = false;
  return calls.map((tc) => {
    if (matched) return tc;
    const hit = ev.id ? tc.id === ev.id : tc.name === ev.name && tc.result === undefined && !tc.error;
    if (!hit) return tc;
    matched = true;
    return { ...tc, result: ev.result ?? null, error: ev.error || (ev.success === false ? 'The tool reported a failure.' : undefined) };
  });
}

function useMediaQuery(query) {
  const [matches, setMatches] = useState(() => typeof window !== 'undefined' && window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = (e) => setMatches(e.matches);
    mq.addEventListener('change', on);
    setMatches(mq.matches);
    return () => mq.removeEventListener('change', on);
  }, [query]);
  return matches;
}

// ── agent picker: search + listbox, portraits, full keyboard ─────────────────
function AgentPicker({ agents, selected, onSelect, status, disabled, isPhone }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const rootRef = useRef(null);
  const triggerRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return agents;
    return agents.filter(
      (a) => agentName(a).toLowerCase().includes(q) || String(a.domain || '').toLowerCase().includes(q) || String(a.title || '').toLowerCase().includes(q)
    );
  }, [agents, query]);

  const groups = useMemo(() => {
    const m = new Map();
    for (const a of filtered) {
      const d = prettyDomain(a.domain);
      if (!m.has(d)) m.set(d, []);
      m.get(d).push(a);
    }
    return [...m.entries()];
  }, [filtered]);

  useEffect(() => {
    if (!open) return undefined;
    setQuery('');
    setActive(Math.max(0, agents.findIndex((a) => a.id === selected?.id)));
    const raf = requestAnimationFrame(() => inputRef.current?.focus());
    const onDoc = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('mousedown', onDoc);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (open) setActive(0);
  }, [query, open]);

  useEffect(() => {
    if (!open) return;
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView?.({ block: 'nearest' });
  }, [active, open]);

  const close = (restore = true) => {
    setOpen(false);
    if (restore) triggerRef.current?.focus();
  };
  const choose = (a) => {
    onSelect(a);
    close();
  };
  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((i) => Math.min(filtered.length - 1, i + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(0, i - 1)); }
    else if (e.key === 'Home') { e.preventDefault(); setActive(0); }
    else if (e.key === 'End') { e.preventDefault(); setActive(Math.max(0, filtered.length - 1)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (filtered[active]) choose(filtered[active]); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
    else if (e.key === 'Tab' && !isPhone) { close(false); }
  };

  const activeId = filtered[active] ? `agent-opt-${filtered[active].id}` : undefined;
  const search = (
    <div className="relative shrink-0 border-b border-border p-2">
      <Search aria-hidden="true" className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
      <Input
        ref={inputRef}
        type="search"
        size={isPhone ? 'lg' : 'sm'}
        role="combobox"
        aria-label="Search agents"
        aria-expanded="true"
        aria-controls="agent-picker-list"
        aria-activedescendant={activeId}
        aria-autocomplete="list"
        placeholder="Search agents…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={onKeyDown}
        className="pl-8"
      />
    </div>
  );
  const list = (
    <div id="agent-picker-list" ref={listRef} role="listbox" aria-label="Agents" className={`overflow-y-auto p-1 ${isPhone ? 'max-h-[60dvh]' : 'max-h-80'}`}>
      {groups.length === 0 && <p className="px-3 py-6 text-center text-body-sm text-muted">No agent matches “{query}”.</p>}
      {groups.map(([domain, items]) => (
        <div key={domain} role="group" aria-label={domain}>
          <p className="px-2.5 pb-1 pt-2 text-micro font-semibold uppercase tracking-wider text-subtle">{domain}</p>
          {items.map((a) => {
            const idx = filtered.indexOf(a);
            const isSel = a.id === selected?.id;
            return (
              <button
                key={a.id}
                id={`agent-opt-${a.id}`}
                role="option"
                type="button"
                aria-selected={isSel}
                data-index={idx}
                tabIndex={-1}
                onMouseEnter={() => setActive(idx)}
                onClick={() => choose(a)}
                className={`flex w-full items-center gap-2.5 rounded-control px-2 text-left transition-colors duration-fast ${isPhone ? 'min-h-touch py-2' : 'py-1.5'} ${
                  idx === active ? 'bg-elevated' : ''
                }`}
              >
                <AgentAvatar agent={a} size={28} rounded="rounded-chip" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body text-fg">{agentName(a)}</span>
                  <span className="block truncate text-caption text-muted">{roleLine(a)}</span>
                </span>
                {isSel && <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-accent" />}
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );

  return (
    <div ref={rootRef} className="relative min-w-0">
      <button
        ref={triggerRef}
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={selected ? `${agentName(selected)}, ${statusMeta(status).label}. Change agent` : 'Choose an agent'}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); }
        }}
        className="flex min-h-touch min-w-0 max-w-full items-center gap-2.5 rounded-control py-1 pl-1 pr-2 text-left transition-colors duration-fast hover:bg-elevated/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
      >
        {selected ? (
          <>
            <span className="relative shrink-0">
              <AgentAvatar agent={selected} size={36} rounded="rounded-control" status={status} />
              <StatusDot status={status} size="md" ring className="absolute -bottom-0.5 -right-0.5" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-body font-semibold text-fg-strong">{agentName(selected)}</span>
              <span className="hidden truncate text-caption text-muted sm:block">
                {roleLine(selected)} · {statusMeta(status).label}
              </span>
            </span>
          </>
        ) : (
          <span className="text-body text-muted">Choose an agent</span>
        )}
        <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
      </button>

      {open && isPhone && (
        <Sheet isOpen onClose={() => close()} title="Choose an agent" side="bottom">
          {search}
          {list}
        </Sheet>
      )}
      {open && !isPhone && (
        <div className="absolute left-0 top-full z-popover mt-1 flex w-[min(22rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-card border border-border bg-overlay shadow-e3 animate-scale-in">
          {search}
          {list}
        </div>
      )}
    </div>
  );
}

// ── skeleton of the real shape: header + three turns ─────────────────────────
const Bone = ({ className = '' }) => <div className={`rounded-chip bg-elevated/80 ${className}`} />;
function ChatSkeleton({ header = false, turns = true }) {
  return (
    <div role="status" aria-busy="true" aria-label="Loading" className="animate-pulse">
      {header && (
        <div className="flex items-center gap-3 px-5 py-3">
          <Bone className="h-9 w-9 rounded-control" />
          <div className="space-y-2">
            <Bone className="h-3.5 w-32" />
            <Bone className="h-3 w-24" />
          </div>
          <div className="ml-auto flex gap-2">
            <Bone className="h-8 w-28 rounded-control" />
            <Bone className="h-8 w-20 rounded-control" />
          </div>
        </div>
      )}
      {turns && (
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6">
        <div className="flex justify-end">
          <Bone className="h-10 w-1/2 rounded-pane" />
        </div>
        <div className="flex gap-3">
          <Bone className="h-8 w-8 rounded-control" />
          <div className="flex-1 space-y-2 pt-1">
            <Bone className="h-3 w-24" />
            <Bone className="h-3.5 w-full" />
            <Bone className="h-3.5 w-5/6" />
            <Bone className="h-3.5 w-2/3" />
          </div>
        </div>
        <div className="flex justify-end">
          <Bone className="h-10 w-1/3 rounded-pane" />
        </div>
      </div>
      )}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

// ── the page ─────────────────────────────────────────────────────────────────
export default function AgentChat() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const isPhone = useMediaQuery('(max-width: 639px)');

  // roster
  const [agents, setAgents] = useState([]);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [agentsError, setAgentsError] = useState(null);
  const [agent, setAgent] = useState(null);
  const [models, setModels] = useState([]);
  const [modelOverride, setModelOverride] = useState('');

  // conversation
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState(null);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [conversationError, setConversationError] = useState(null);

  // live
  const [streaming, setStreaming] = useState(false);
  const [phase, setPhase] = useState('idle'); // idle · thinking · tool · responding · error
  const [currentTool, setCurrentTool] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const [atBottom, setAtBottom] = useState(true);

  // dialogs
  const [showTools, setShowTools] = useState(false);
  const [showModelSheet, setShowModelSheet] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [inCall, setInCall] = useState(false);

  const messagesRef = useRef(messages);
  const conversationIdRef = useRef(null);
  const loadedConversationRef = useRef(null);
  const abortRef = useRef(null);
  const sendingRef = useRef(false);
  const idRef = useRef(0);
  const scrollRef = useRef(null);
  const stickRef = useRef(true);
  const textareaRef = useRef(null);
  const nextId = () => `m-${(idRef.current += 1)}`;

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  useEffect(() => {
    conversationIdRef.current = conversationId;
  }, [conversationId]);

  const agentById = useMemo(() => new Map(agents.map((a) => [a.id, a])), [agents]);
  const tools = useMemo(() => toolList(agent), [agent]);
  const effectiveModel = modelOverride || getPreferences().defaultModel || agent?.model || '';
  const status = offline ? 'offline' : phase;

  // ── roster ──────────────────────────────────────────────────────────────
  const loadAgents = useCallback(async () => {
    setAgentsLoading(true);
    setAgentsError(null);
    try {
      const data = await apiJson('/agents');
      const list = data?.agents || (Array.isArray(data) ? data : []);
      setAgents(list);
      setAgent((current) => {
        if (current && list.some((a) => a.id === current.id)) return list.find((a) => a.id === current.id);
        if (searchParams.get('conversation')) return current;
        const wanted = searchParams.get('agent');
        return (wanted && list.find((a) => a.id === wanted)) || list.find((a) => a.status === 'active') || list[0] || null;
      });
    } catch (err) {
      setAgentsError(err);
    } finally {
      setAgentsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadAgents();
    apiJson('/chat/models')
      .then((data) => setModels((data?.models || []).filter((m) => m && m.id && m.available !== false)))
      .catch(() => setModels([]));
  }, [loadAgents]);

  // ?agent= changes after mount (palette, dock, org chart) switch the agent.
  useEffect(() => {
    const wanted = searchParams.get('agent');
    if (!wanted || agentsLoading || wanted === agent?.id) return;
    const found = agentById.get(wanted);
    if (found) setAgent(found);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, agentsLoading]);

  // Offline is a state of the page: show it where the messages go.
  useEffect(() => {
    const on = () => {
      setOffline(false);
      if (agentsError) loadAgents();
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [agentsError, loadAgents]);

  // ── persistence ─────────────────────────────────────────────────────────
  const createConversation = useCallback(
    async (agentId, model) => {
      try {
        const data = await apiJson('/conversations', { method: 'POST', body: JSON.stringify({ agent_id: agentId, model }) });
        if (data?.id) {
          setConversationId(data.id);
          conversationIdRef.current = data.id;
          loadedConversationRef.current = data.id;
          setSearchParams({ conversation: data.id }, { replace: true });
        }
        return data?.id || null;
      } catch {
        return null; // the chat still works without persistence
      }
    },
    [setSearchParams]
  );

  const saveMessage = useCallback((convId, body) => {
    if (!convId) return;
    apiJson(`/conversations/${convId}/messages`, { method: 'POST', body: JSON.stringify(body) }).catch(() => {});
  }, []);

  const loadConversation = useCallback(
    async (convId) => {
      setLoadingConversation(true);
      setConversationError(null);
      try {
        const data = await apiJson(`/conversations/${convId}`);
        loadedConversationRef.current = convId;
        setConversationId(data.id);
        conversationIdRef.current = data.id;
        setConversationTitle(data.title || null);
        if (data.model) setModelOverride('');
        const known = data.agent_id ? agentById.get(data.agent_id) : null;
        if (known) setAgent(known);
        else if (data.agent) setAgent({ ...data.agent, id: data.agent_id || data.agent.id });
        const loaded = (data.messages || [])
          .filter((m) => m.role === 'user' || m.role === 'assistant')
          .map((m, i) => ({
            id: m.id || `loaded-${i}`,
            role: m.role,
            content: m.content || '',
            model: m.model,
            toolCalls: storedToolCalls(m),
            timestamp: m.created_at,
            agentId: data.agent_id,
            isStreaming: false,
          }));
        stickRef.current = true;
        setMessages(loaded);
      } catch (err) {
        setConversationError(err);
      } finally {
        setLoadingConversation(false);
      }
    },
    [agentById]
  );

  useEffect(() => {
    const convId = searchParams.get('conversation');
    if (!convId || agentsLoading || convId === loadedConversationRef.current) return;
    loadConversation(convId);
  }, [searchParams, agentsLoading, loadConversation]);

  // ── chat ────────────────────────────────────────────────────────────────
  const stop = useCallback(() => abortRef.current?.abort(), []);

  const resetConversation = useCallback(
    (nextAgent) => {
      stop();
      setMessages([]);
      setConversationId(null);
      conversationIdRef.current = null;
      loadedConversationRef.current = null;
      setConversationTitle(null);
      setConversationError(null);
      setPhase('idle');
      setCurrentTool(null);
      const params = {};
      if (nextAgent?.id) params.agent = nextAgent.id;
      setSearchParams(params, { replace: true });
      requestAnimationFrame(() => textareaRef.current?.focus());
    },
    [setSearchParams, stop]
  );

  const newChat = useCallback(() => resetConversation(agent), [agent, resetConversation]);
  const selectAgent = useCallback(
    (a) => {
      if (a.id === agent?.id) return;
      setAgent(a);
      setModelOverride('');
      resetConversation(a);
    },
    [agent, resetConversation]
  );

  const send = useCallback(
    async (rawText, base) => {
      const text = (rawText ?? '').trim();
      if (!text || !agent || sendingRef.current || offline) return;
      sendingRef.current = true;

      const prefs = getPreferences();
      const model = modelOverride || prefs.defaultModel || agent.model;
      const streamLive = prefs.streamResponses !== false;
      const prior = base || messagesRef.current;
      const history = prior.filter((m) => !m.isError && m.content).map((m) => ({ role: m.role, content: m.content }));

      const userMsg = { id: nextId(), role: 'user', content: text, timestamp: new Date().toISOString() };
      const assistantId = nextId();
      const assistantMsg = {
        id: assistantId,
        role: 'assistant',
        content: '',
        toolCalls: [],
        agentId: agent.id,
        model,
        timestamp: new Date().toISOString(),
        isStreaming: true,
      };
      stickRef.current = true;
      setMessages([...prior, userMsg, assistantMsg]);
      setInput('');
      setStreaming(true);
      setPhase('thinking');
      setCurrentTool(null);

      let convId = conversationIdRef.current;
      if (!convId && prior.length === 0) convId = await createConversation(agent.id, model);
      saveMessage(convId, { role: 'user', content: text });

      const controller = new AbortController();
      abortRef.current = controller;
      const patch = (fn) => setMessages((prev) => prev.map((m) => (m.id === assistantId ? fn(m) : m)));

      let acc = '';
      let gotToken = false;
      let finalModel = model;
      let completed = false;
      let failed = false;
      let calls = [];

      try {
        const res = await api.streamAgentChat(
          agent.id,
          { message: text, stream: true, history, model, temperature: agent.temperature },
          { signal: controller.signal }
        );
        if (!res.ok || !res.body) {
          const err = new Error(`HTTP ${res.status}`);
          err.status = res.status;
          err.data = await res.json().catch(() => null);
          throw err;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6).trim();
            if (!payload || payload === '[DONE]') continue;
            let ev;
            try {
              ev = JSON.parse(payload);
            } catch {
              continue;
            }
            if (ev.type === 'tool_call') {
              setPhase('tool');
              setCurrentTool(ev.name);
              calls = [...calls, { id: ev.id, name: ev.name, arguments: ev.arguments }];
              patch((m) => ({ ...m, toolCalls: calls }));
            } else if (ev.type === 'tool_result') {
              setPhase('thinking');
              setCurrentTool(null);
              calls = attachResult(calls, ev);
              patch((m) => ({ ...m, toolCalls: calls }));
            } else if (ev.type === 'token') {
              acc += ev.content || '';
              if (streamLive) {
                if (!gotToken) {
                  gotToken = true;
                  setPhase('responding');
                }
                patch((m) => ({ ...m, content: acc }));
              }
            } else if (ev.type === 'complete') {
              completed = true;
              finalModel = ev.model || model;
              acc = ev.content || acc;
              if (Array.isArray(ev.toolCalls) && ev.toolCalls.length) calls = ev.toolCalls;
              patch((m) => ({ ...m, content: acc, model: finalModel, toolCalls: calls, isStreaming: false }));
              saveMessage(convId, {
                role: 'assistant',
                content: acc,
                model: finalModel,
                tokens_used: ev.usage?.total_tokens,
                tool_calls: calls.length ? calls.map(({ id, name, arguments: args }) => ({ id, name, arguments: args })) : undefined,
                tool_results: calls.length ? calls.map(({ id, name, result, error }) => ({ id, name, result, error: error || null, success: !error })) : undefined,
              });
            } else if (ev.type === 'error') {
              const err = new Error(ev.error || 'The agent hit a problem.');
              err.data = { detail: ev.error };
              throw err;
            }
          }
        }
        patch((m) => ({ ...m, content: m.content || acc, isStreaming: false }));
        if (!completed && acc) saveMessage(convId, { role: 'assistant', content: acc, model: finalModel });
      } catch (err) {
        if (controller.signal.aborted) {
          setMessages((prev) =>
            prev.flatMap((m) => (m.id !== assistantId ? [m] : acc || m.toolCalls.length ? [{ ...m, content: acc, isStreaming: false, stopped: true }] : []))
          );
          if (acc) saveMessage(convId, { role: 'assistant', content: acc, model: finalModel });
        } else {
          failed = true;
          patch((m) => ({ ...m, content: acc, isStreaming: false, isError: true, error: humanize(err, { what: 'getting a reply' }) }));
        }
      } finally {
        setStreaming(false);
        setPhase(failed ? 'error' : 'idle');
        setCurrentTool(null);
        abortRef.current = null;
        sendingRef.current = false;
      }
    },
    [agent, modelOverride, offline, createConversation, saveMessage]
  );

  const retry = useCallback(
    (failedMsg) => {
      if (streaming) return;
      const list = messagesRef.current;
      const idx = list.findIndex((m) => m.id === failedMsg.id);
      const user = idx > 0 && list[idx - 1].role === 'user' ? list[idx - 1] : null;
      if (!user) return;
      const base = list.filter((m) => m.id !== failedMsg.id && m.id !== user.id);
      send(user.content, base);
    },
    [send, streaming]
  );

  // ── composer ────────────────────────────────────────────────────────────
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_COMPOSER_PX)}px`;
  }, [input]);

  const onComposerKeyDown = (e) => {
    if (e.key === 'Escape' && streaming) {
      e.preventDefault();
      stop();
    } else if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent?.isComposing) {
      e.preventDefault();
      send(input);
    }
  };

  // ── scrolling: follow the stream only while the reader is at the bottom ─
  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 64;
    stickRef.current = near;
    setAtBottom(near);
  };
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (el && stickRef.current) el.scrollTop = el.scrollHeight;
  }, [messages, phase, loadingConversation]);
  const jumpToLatest = () => {
    const el = scrollRef.current;
    if (!el) return;
    stickRef.current = true;
    setAtBottom(true);
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  };

  // ── derived ─────────────────────────────────────────────────────────────
  const composerDisabled = !agent || offline || loadingConversation || Boolean(agentsError) || agentsLoading;
  const canSend = Boolean(input.trim()) && !composerDisabled && !streaming;
  const hint = offline
    ? 'You’re offline. Messages send again when the connection is back.'
    : agentsLoading
      ? 'Loading your agents…'
      : agentsError
        ? 'Your agents couldn’t be loaded — retry above.'
      : !agent
        ? 'Pick an agent to start.'
        : loadingConversation
          ? 'Opening the conversation…'
          : streaming
            ? `${statusMeta(phase).label}${currentTool ? ` · ${currentTool}` : ''}`
            : '';

  const modelItems = useMemo(() => {
    const items = [
      { id: 'default', label: `Agent default · ${shortModel(agent?.model) || 'auto'}`, icon: modelOverride ? undefined : Check, onSelect: () => setModelOverride('') },
    ];
    if (models.length) {
      items.push({ type: 'separator' });
      for (const m of models) {
        items.push({ id: m.id, label: m.display_name || m.name || m.id, icon: modelOverride === m.id ? Check : undefined, onSelect: () => setModelOverride(m.id) });
      }
    }
    return items;
  }, [agent, models, modelOverride]);

  const headerActions = agent && (
    <>
      <div className="hidden items-center gap-1.5 sm:flex">
        <Menu
          align="end"
          items={modelItems}
          trigger={({ props }) => (
            <Tooltip content="Model for this chat">
              <Button variant="secondary" size="sm" icon={Cpu} iconRight={ChevronDown} {...props}>
                {shortModel(effectiveModel) || 'Auto'}
              </Button>
            </Tooltip>
          )}
        />
        {tools.length ? (
          <Button variant="secondary" size="sm" icon={Wrench} onClick={() => setShowTools(true)}>
            {tools.length} {tools.length === 1 ? 'tool' : 'tools'}
          </Button>
        ) : (
          <Tooltip content="This agent has no tools attached">
            <Chip size="md" icon={Wrench}>
              No tools
            </Chip>
          </Tooltip>
        )}
        <Button variant="ghost" size="sm" icon={MessageSquarePlus} onClick={newChat}>
          New chat
        </Button>
      </div>
      <VoiceCallButton onClick={() => setShowVoice(true)} isConnected={inCall} disabled={streaming} className="min-h-touch min-w-touch sm:min-h-0 sm:min-w-0" />
      <div className="sm:hidden">
        <Menu
          align="end"
          trigger={({ props }) => <IconButton icon={MoreHorizontal} label="More" className="min-h-touch min-w-touch" {...props} />}
          items={[
            { id: 'new', label: 'New chat', icon: MessageSquarePlus, onSelect: newChat },
            { id: 'model', label: `Model · ${shortModel(effectiveModel) || 'Auto'}`, icon: Cpu, onSelect: () => setShowModelSheet(true) },
            { id: 'tools', label: tools.length ? `Tools (${tools.length})` : 'No tools attached', icon: Wrench, disabled: !tools.length, onSelect: () => setShowTools(true) },
          ]}
        />
      </div>
    </>
  );

  // ── the four states of the page ─────────────────────────────────────────
  let body;
  if (agentsLoading) {
    body = <ChatSkeleton />;
  } else if (agentsError) {
    body = (
      <ErrorState
        title="Couldn’t load your agents"
        detail={humanize(agentsError, { what: 'loading the roster' })}
        onRetry={loadAgents}
      />
    );
  } else if (!agents.length) {
    body = (
      <EmptyState
        icon={Bot}
        title="No agents yet"
        description="Build your first agent with Gunny and it shows up here, ready to talk."
        action={
          <Button icon={Sparkles} onClick={() => navigate('/builder-chat')}>
            Build an agent
          </Button>
        }
      />
    );
  } else if (loadingConversation) {
    body = <ChatSkeleton />;
  } else if (conversationError) {
    body = (
      <ErrorState
        title="Couldn’t open that conversation"
        detail={humanize(conversationError, { what: 'opening the conversation' })}
        onRetry={() => loadConversation(searchParams.get('conversation'))}
      />
    );
  } else if (!messages.length) {
    body = agent ? (
      <div className="flex min-h-[55vh] flex-col items-center justify-center text-center animate-fade-in">
        <AgentAvatar agent={agent} size={96} rounded="rounded-pane" className="mb-4 shadow-e2" />
        <h2 className="text-heading text-fg-strong">Chat with {agentName(agent)}</h2>
        <p className="mt-1 text-body-sm text-muted">{roleLine(agent)}</p>
        <p className="mt-3 max-w-md text-body text-muted">{agent.bio || agent.title || 'Ask anything. Every reply streams in as it is written.'}</p>
        {tools.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5">
            {tools.slice(0, 4).map((t) => (
              <Chip key={t.name} size="xs" icon={getToolIcon(t.name)}>
                {t.label}
              </Chip>
            ))}
            <Chip size="xs" tone="accent" onClick={() => setShowTools(true)}>
              {tools.length > 4 ? `+${tools.length - 4} more` : 'All tools'}
            </Chip>
          </div>
        )}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2" aria-label="Suggested messages">
          {SUGGESTIONS.map((s) => (
            <Chip key={s} size="md" className="min-h-touch sm:min-h-0" onClick={() => send(s)}>
              {s}
            </Chip>
          ))}
        </div>
      </div>
    ) : (
      <EmptyState icon={Bot} title="Pick an agent" description="Choose who to talk to from the picker above." compact />
    );
  } else {
    body = (
      <div className="space-y-7">
        {messages.map((m) => (
          <ChatMessage
            key={m.id}
            message={m}
            agent={m.role === 'assistant' ? agentById.get(m.agentId) || agent : undefined}
            onRetry={m.isError ? retry : undefined}
            retryDisabled={streaming}
          />
        ))}
        {streaming && phase !== 'responding' && (
          <div className="flex items-center gap-2.5 pl-11" role="status" aria-live="polite">
            <StatusDot status={phase} size="md" />
            <span className="text-body-sm text-muted">
              {phase === 'tool' ? (
                <>
                  Running <span className="font-mono text-fg">{currentTool}</span>…
                </>
              ) : (
                `${agentName(agent)} is thinking…`
              )}
            </span>
          </div>
        )}
      </div>
    );
  }

  return (
    // contain:inline-size keeps a wide table or a long unbroken token from
    // growing the shell's <main> (a flex item) past the viewport on phones.
    <div className="flex h-[calc(100dvh-4rem)] flex-col bg-bg [contain:inline-size] lg:h-dvh">
      {/* Header */}
      <header className="relative z-raised shrink-0 border-b border-border bg-surface">
        {agentsLoading ? (
          <ChatSkeleton header turns={false} />
        ) : (
          <div className="flex items-center gap-2 px-3 py-2 sm:px-5">
            <div className="min-w-0 flex-1">
              <AgentPicker agents={agents} selected={agent} onSelect={selectAgent} status={status} disabled={!agents.length} isPhone={isPhone} />
            </div>
            {conversationTitle && (
              <Tooltip content={conversationTitle}>
                <Chip size="sm" className="hidden max-w-[16rem] md:inline-flex">
                  <span className="truncate">{conversationTitle}</span>
                </Chip>
              </Tooltip>
            )}
            {headerActions}
          </div>
        )}
      </header>

      {/* Messages */}
      <div className="relative min-h-0 flex-1">
        <div ref={scrollRef} onScroll={onScroll} className="h-full overflow-y-auto scrollbar-thin">
          <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6 sm:py-8">
            {offline && (
              <div className="mb-4 rounded-card border border-border bg-card">
                <OfflineState compact onRetry={agentsError ? loadAgents : undefined} />
              </div>
            )}
            {body}
          </div>
        </div>
        {!atBottom && messages.length > 0 && (
          <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center">
            <span className="pointer-events-auto shadow-e3">
              <Chip tone="accent" solid size="md" icon={ArrowDown} className="min-h-touch sm:min-h-0" onClick={jumpToLatest}>
                Jump to latest
              </Chip>
            </span>
          </div>
        )}
      </div>

      {/* Composer: one pane-shaped shell carries the border and the focus ring;
          the textarea inside is bare so there is exactly one edge and one ring. */}
      <footer className="shrink-0 border-t border-border bg-surface/80 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="mx-auto w-full max-w-3xl px-3 pb-2 pt-3 sm:px-6"
        >
          <div
            className={`flex items-end gap-2 rounded-pane border bg-card p-1.5 pl-4 shadow-e1 transition-[border-color,box-shadow] duration-fast ease-standard focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/35 ${
              composerDisabled ? 'border-border opacity-70' : 'border-border-strong/70 hover:border-border-strong'
            }`}
          >
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKeyDown}
              aria-label={agent ? `Message ${agentName(agent)}` : 'Message'}
              placeholder={agent ? `Message ${agentName(agent)}…` : 'Pick an agent to start…'}
              disabled={composerDisabled}
              className="max-h-40 min-h-touch w-full flex-1 resize-none bg-transparent py-2.5 text-body text-fg placeholder:text-subtle focus-visible:outline-none disabled:cursor-not-allowed sm:min-h-[40px]"
            />
            {streaming ? (
              <Tooltip content="Stop the reply (Esc)">
                <Button type="button" variant="secondary" size="lg" iconOnly icon={Square} aria-label="Stop" onClick={stop} />
              </Tooltip>
            ) : (
              <Button type="submit" size="lg" iconOnly icon={Send} aria-label="Send" disabled={!canSend} />
            )}
          </div>
          <div className="mt-1.5 flex min-h-5 items-center justify-between gap-3 px-1 text-micro text-subtle">
            <span aria-live="polite" className="truncate">
              {hint}
            </span>
            <span className="hidden shrink-0 items-center gap-1 sm:inline-flex">
              <Kbd>Enter</Kbd> send · <Kbd>⇧</Kbd>
              <Kbd>Enter</Kbd> new line
              {streaming && (
                <>
                  {' '}
                  · <Kbd>Esc</Kbd> stop
                </>
              )}
            </span>
          </div>
        </form>
      </footer>

      {/* Tools */}
      <Sheet isOpen={showTools && Boolean(agent)} onClose={() => setShowTools(false)} side={isPhone ? 'bottom' : 'right'} title={`${agentName(agent)}’s tools`}>
        <p className="mb-3 text-body-sm text-muted">
          {tools.length} {tools.length === 1 ? 'tool' : 'tools'}. The agent decides when to use one; every call shows up in the conversation as it runs.
        </p>
        <ul className="space-y-1.5" aria-label="Tools">
          {tools.map((t) => {
            const Icon = getToolIcon(t.name);
            return (
              <li key={t.name} className="flex items-center gap-3 rounded-control border border-border bg-card px-3 py-2">
                <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-chip bg-elevated text-muted">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-body text-fg">{t.label}</span>
                  {(t.provider || t.label !== t.name) && <span className="block truncate font-mono text-caption text-muted">{t.provider || t.name}</span>}
                </span>
                {t.paid && (
                  <Chip tone="warn" size="xs">
                    paid
                  </Chip>
                )}
              </li>
            );
          })}
        </ul>
      </Sheet>

      {/* Model (phones) */}
      <Sheet isOpen={showModelSheet} onClose={() => setShowModelSheet(false)} side="bottom" title="Model for this chat">
        <Field label="Model" help="The agent’s own model unless you pick another one here.">
          <Select size="lg" value={modelOverride} onChange={(e) => setModelOverride(e.target.value)}>
            <option value="">Agent default · {shortModel(agent?.model) || 'auto'}</option>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name || m.name || m.id}
              </option>
            ))}
          </Select>
        </Field>
      </Sheet>

      {/* Voice */}
      <VoiceCallModal
        isOpen={showVoice}
        onClose={() => setShowVoice(false)}
        agent={agent}
        onCallStart={() => setInCall(true)}
        onCallEnd={() => setInCall(false)}
      />
    </div>
  );
}
