/**
 * Agent detail — one agent: who it is, how it is built, what it may use, how
 * to call it. Numbers come only from endpoints that state them (the agent's
 * own tool list, /agents/:id/stats, and /agents/:id/api-keys); anything the API
 * does not record is labelled as such instead of shown as zero.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import { ArrowLeft, Clock, Code, Key, LayoutDashboard, MessageSquare, Network, Pencil, Plus, Radio, Save, Settings, Trash2, Wrench, X } from 'lucide-react';
import { apiJson } from '../services/http';
import notify from '../utils/notify';
import { humanize } from '../utils/errors';
import { prettyDomain, roleLine } from '../utils/agentClass';
import AgentAvatar from '../components/AgentAvatar';
import { AffiliationChip, ModelTierChip, PaidToolsBadge } from '../components/AgentBadges';
import AgentArchitectureDiagram from '../components/AgentArchitectureDiagram';
import AgentTimeline from '../components/AgentTimeline';
import ToolSelector from '../components/ToolSelector';
import ApiKeyCard from '../components/ApiKeyCard';
import GenerateApiKeyModal from '../components/GenerateApiKeyModal';
import KeyRevealModal from '../components/KeyRevealModal';
import AgentConfigurationTab from '../components/AgentConfigurationTab';
import AgentEditModal from '../components/AgentEditModal';
import AgentDeleteConfirmModal from '../components/AgentDeleteConfirmModal';
import AgentAutonomyCard from '../components/AgentAutonomyCard';
import { useAutonomy } from '../hooks/useAutonomy';
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  Page,
  PageHeader,
  SectionHeader,
  Tabs,
  Textarea,
} from '../components/ui';

const TABS = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'architecture', label: 'Architecture', icon: Network },
  { id: 'build-history', label: 'Build history', icon: Clock },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'configuration', label: 'Configuration', icon: Settings },
  { id: 'system-prompt', label: 'System prompt', icon: Code },
  { id: 'api-keys', label: 'API keys', icon: Key },
];

// ReactMarkdown output styled through the type scale (no typography plugin).
const MARKDOWN =
  'text-body text-fg [&_p]:mb-3 [&_p:last-child]:mb-0 [&_h1]:text-heading [&_h1]:text-fg-strong [&_h2]:text-lead [&_h2]:font-semibold [&_h2]:text-fg-strong [&_h3]:text-body [&_h3]:font-semibold [&_h3]:text-fg-strong [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mb-1 [&_code]:rounded-chip [&_code]:bg-elevated [&_code]:px-1 [&_code]:font-mono [&_code]:text-body-sm [&_pre]:mb-3 [&_pre]:overflow-x-auto [&_pre]:rounded-control [&_pre]:border [&_pre]:border-border [&_pre]:bg-surface [&_pre]:p-3 [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_a]:text-accent [&_a]:underline [&_strong]:text-fg-strong';

const LIFECYCLE = { active: 'ok', draft: 'warn', inactive: 'neutral', archived: 'neutral', busy: 'live' };
const toolIds = (agent) => (Array.isArray(agent?.tools) ? agent.tools.map((t) => (typeof t === 'string' ? t : t?.id || t?.name)).filter(Boolean) : []);

// A small fact tile; `value` null means the source did not answer.
function Fact({ label, value, note }) {
  return (
    <div className="rounded-control border border-border bg-surface/60 p-3">
      <dt className="text-caption text-muted">{label}</dt>
      <dd className={`mt-0.5 tabular-nums ${value == null ? 'text-body text-subtle' : 'text-heading text-fg-strong'}`}>{value == null ? 'Not recorded' : value.toLocaleString()}</dd>
      {note && <dd className="mt-0.5 text-micro text-subtle">{note}</dd>}
    </div>
  );
}

export default function AgentDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = TABS.some((t) => t.id === params.get('tab')) ? params.get('tab') : 'overview';
  const setTab = (next) => setParams(next === 'overview' ? {} : { tab: next }, { replace: true });

  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);

  const [catalog, setCatalog] = useState([]);
  const [keys, setKeys] = useState({ state: 'loading', list: [], error: null });
  const [stats, setStats] = useState({ state: 'loading', data: null, error: null });
  const [session, setSession] = useState({ state: 'idle', data: null });

  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [revealedKey, setRevealedKey] = useState(null);
  const [promptDraft, setPromptDraft] = useState(null); // null = not editing
  const [savingPrompt, setSavingPrompt] = useState(false);

  // The jobs this agent runs on its own (one read of the autonomy catalogue).
  const autonomy = useAutonomy({ refreshMs: 0 });
  const ownJobs = useMemo(() => autonomy.items.filter((it) => it.agentId === id), [autonomy.items, id]);

  const loadStats = useCallback(async () => {
    setStats((s) => ({ ...s, state: 'loading', error: null }));
    try {
      const data = await apiJson(`/agents/${encodeURIComponent(id)}/stats`);
      setStats({ state: 'ready', data, error: null });
    } catch (err) {
      setStats({ state: 'error', data: null, error: err });
    }
  }, [id]);

  const loadKeys = useCallback(async () => {
    setKeys((k) => ({ ...k, state: 'loading', error: null }));
    try {
      const data = await apiJson(`/agents/${encodeURIComponent(id)}/api-keys`);
      setKeys({ state: 'ready', list: Array.isArray(data) ? data : data?.keys || [], error: null });
    } catch (err) {
      setKeys({ state: 'error', list: [], error: err });
    }
  }, [id]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson(`/agents/${encodeURIComponent(id)}`);
      setAgent(data);
      if (data?.sessionId) {
        setSession({ state: 'loading', data: null });
        apiJson(`/agent-builder/session/${data.sessionId}`)
          .then((s) => setSession({ state: 'ready', data: s }))
          .catch(() => setSession({ state: 'ready', data: null }));
      } else {
        setSession({ state: 'ready', data: null });
      }
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
    // Side facts: each answers on its own and fails on its own.
    loadStats();
    loadKeys();
    apiJson('/tools')
      .then((d) => setCatalog(Array.isArray(d) ? d : d?.tools || []))
      .catch(() => setCatalog([]));
  }, [id, loadKeys, loadStats]);

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

  const saveAgent = async (patch) => {
    const updated = await apiJson(`/agents/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(patch) });
    setAgent((a) => ({ ...a, ...patch, ...(updated || {}) }));
    notify.success('Agent updated');
  };

  const savePrompt = async () => {
    setSavingPrompt(true);
    try {
      await saveAgent({ systemPrompt: promptDraft });
      setPromptDraft(null);
    } catch (err) {
      notify.error(humanize(err, { what: 'saving the system prompt' }));
    } finally {
      setSavingPrompt(false);
    }
  };

  const revokeKey = async (key) => {
    try {
      await apiJson(`/agents/${encodeURIComponent(id)}/api-keys/${encodeURIComponent(key.id)}`, { method: 'DELETE' });
      notify.success('API key revoked');
      loadKeys();
    } catch (err) {
      notify.error(humanize(err, { what: 'revoking the key' }));
      throw err;
    }
  };

  const attached = useMemo(() => {
    const byId = new Map(catalog.map((t) => [t.id || t.name, t]));
    return toolIds(agent).map((tid) => byId.get(tid) || { id: tid, name: tid.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) });
  }, [agent, catalog]);

  // ── page states ──────────────────────────────────────────────────────────
  if (offline && !agent) {
    return (
      <Page>
        <OfflineState onRetry={load} />
      </Page>
    );
  }
  if (loading && !agent) {
    return (
      <Page>
        <LoadingState variant="list" count={1} label="Loading agent" className="mb-6" />
        <LoadingState variant="text" count={6} />
      </Page>
    );
  }
  if (error && !agent) {
    const gone = error.status === 404;
    return (
      <Page>
        <ErrorState
          title={gone ? 'That agent isn’t here' : 'Couldn’t load the agent'}
          detail={gone ? 'It may have been deleted or renamed.' : humanize(error, { what: 'loading the agent' })}
          onRetry={gone ? undefined : load}
        />
        <div className="flex justify-center">
          <Button variant="secondary" icon={ArrowLeft} onClick={() => navigate('/library')}>
            Back to the library
          </Button>
        </div>
      </Page>
    );
  }
  if (!agent) return null;

  const name = agent.displayName || agent.name;
  const statValue = (key) => (stats.state === 'ready' && stats.data?.[key] != null ? Number(stats.data[key]) : null);
  const lastUsed = stats.state === 'ready' && stats.data?.lastUsedAt ? new Date(stats.data.lastUsedAt).toLocaleString() : null;
  const statsNote = stats.state === 'error' ? 'couldn’t load' : undefined;

  // ── tab panels ───────────────────────────────────────────────────────────
  let panel;
  if (tab === 'overview') {
    panel = (
      <div className="space-y-6">
        {agent.bio && <p className="max-w-3xl text-body text-fg">{agent.bio}</p>}
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Fact label="Tools attached" value={attached.length} />
          <Fact label="API keys" value={statValue('apiKeys')} note={statsNote} />
          <Fact label="Conversations" value={statValue('conversations')} note={statsNote} />
          <Fact label="Messages" value={statValue('messages')} note={statsNote} />
          <Fact label="Last used" value={lastUsed} note={statsNote} />
        </dl>
        <AgentAutonomyCard agentId={agent.id} items={ownJobs} />
        <div>
          <SectionHeader title="Capabilities" />
          {Array.isArray(agent.capabilities) && agent.capabilities.length ? (
            <ul className="flex flex-wrap gap-1.5" aria-label="Capabilities">
              {agent.capabilities.map((cap) => (
                <li key={cap}>
                  <Chip>{cap}</Chip>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-body-sm text-muted">No capabilities listed. Edit the agent to add some.</p>
          )}
        </div>
        <div>
          <SectionHeader
            title="Tools"
            description={attached.length ? `${attached.length} attached` : undefined}
            actions={
              <Button variant="ghost" size="sm" icon={Wrench} onClick={() => setTab('tools')}>
                Manage tools
              </Button>
            }
          />
          {attached.length ? (
            <ul className="grid grid-cols-1 gap-2 md:grid-cols-2" aria-label="Attached tools">
              {attached.map((t) => (
                <li key={t.id || t.name} className="flex items-start gap-3 rounded-control border border-border bg-surface/60 p-3">
                  <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-elevated text-body">
                    {t.icon || <Wrench className="h-4 w-4 text-muted" />}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-body font-medium text-fg-strong">{t.name}</span>
                    {t.description && <span className="block line-clamp-1 text-caption text-muted">{t.description}</span>}
                  </span>
                  {t.type && (
                    <Chip size="xs" className="ml-auto" uppercase>
                      {t.type}
                    </Chip>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              compact
              icon={Wrench}
              title="No tools attached"
              description="This agent can only talk. Attach tools to let it act."
              action={
                <Button size="sm" variant="secondary" onClick={() => setTab('tools')}>
                  Attach a tool
                </Button>
              }
            />
          )}
        </div>
      </div>
    );
  } else if (tab === 'architecture') {
    panel = <AgentArchitectureDiagram agent={{ ...agent, toolDetails: attached.map((t) => ({ name: t.id, displayName: t.name })) }} />;
  } else if (tab === 'build-history') {
    panel = session.state === 'loading' ? <LoadingState variant="list" count={3} label="Loading build history" /> : <AgentTimeline session={session.data} agentName={name} />;
  } else if (tab === 'tools') {
    panel = (
      <div className="space-y-5">
        <SectionHeader title="Tools" description="What this agent may use. Changes apply immediately." />
        <ToolSelector agentId={id} assignedTools={toolIds(agent)} onUpdate={load} />
      </div>
    );
  } else if (tab === 'configuration') {
    panel = <AgentConfigurationTab agent={agent} onSave={saveAgent} />;
  } else if (tab === 'system-prompt') {
    const isEditing = promptDraft != null;
    panel = (
      <div className="space-y-4">
        <SectionHeader
          title="System prompt"
          description="The standing instructions sent with every request."
          actions={
            isEditing ? (
              <>
                <Button variant="ghost" size="sm" icon={X} onClick={() => setPromptDraft(null)} disabled={savingPrompt}>
                  Cancel
                </Button>
                <Button size="sm" icon={Save} loading={savingPrompt} onClick={savePrompt}>
                  Save
                </Button>
              </>
            ) : (
              <Button variant="secondary" size="sm" icon={Pencil} onClick={() => setPromptDraft(agent.systemPrompt || '')}>
                Edit prompt
              </Button>
            )
          }
        />
        {isEditing ? (
          <Textarea aria-label="System prompt" rows={18} value={promptDraft} onChange={(e) => setPromptDraft(e.target.value)} disabled={savingPrompt} className="font-mono text-body-sm" />
        ) : agent.systemPrompt ? (
          <div className={`rounded-control border border-border bg-surface/60 p-4 ${MARKDOWN}`}>
            <ReactMarkdown>{agent.systemPrompt}</ReactMarkdown>
          </div>
        ) : (
          <EmptyState compact icon={Code} title="No system prompt" description="The agent runs on its persona alone. Add standing instructions to shape every reply." action={<Button size="sm" variant="secondary" onClick={() => setPromptDraft('')}>Write one</Button>} />
        )}
      </div>
    );
  } else if (tab === 'api-keys') {
    let list;
    if (keys.state === 'loading') list = <LoadingState variant="list" count={2} label="Loading API keys" />;
    else if (keys.state === 'error') list = <ErrorState compact title="Couldn’t load the keys" detail={humanize(keys.error, { what: 'loading API keys' })} onRetry={loadKeys} />;
    else if (!keys.list.length)
      list = (
        <EmptyState
          compact
          icon={Key}
          title="No API keys yet"
          description="Generate one to let an external system call this agent. The full key is shown once."
          action={
            <Button size="sm" icon={Plus} onClick={() => setShowKeyModal(true)}>
              Generate a key
            </Button>
          }
        />
      );
    else
      list = (
        <ul className="space-y-2" aria-label="API keys">
          {keys.list.map((key) => (
            <li key={key.id}>
              <ApiKeyCard apiKey={key} onRevoke={revokeKey} />
            </li>
          ))}
        </ul>
      );
    panel = (
      <div className="space-y-4">
        <SectionHeader
          title="API keys"
          description="Credentials that let other systems call this agent directly."
          actions={
            <Button size="sm" icon={Plus} onClick={() => setShowKeyModal(true)}>
              Generate key
            </Button>
          }
        />
        {list}
      </div>
    );
  }

  return (
    <Page>
      <div className="mb-3">
        <Button variant="link" size="xs" icon={ArrowLeft} onClick={() => navigate('/library')}>
          Agent Library
        </Button>
      </div>
      <PageHeader
        eyebrow="Agents"
        title={
          <span className="flex items-center gap-3">
            <AgentAvatar agent={agent} size={56} rounded="rounded-card" />
            <span>{name}</span>
          </span>
        }
        description={
          <>
            <span className="block">{roleLine(agent)}</span>
            <span className="mt-2 flex flex-wrap items-center gap-1.5">
              {agent.rank && <Chip size="xs">{agent.rank}</Chip>}
              <Chip size="xs">{prettyDomain(agent.domain)}</Chip>
              {agent.status && (
                <Chip size="xs" dot tone={LIFECYCLE[agent.status] || 'neutral'}>
                  {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                </Chip>
              )}
              <AffiliationChip agent={agent} size="xs" />
              <ModelTierChip agent={agent} size="xs" />
              <PaidToolsBadge agent={agent} size="xs" />
            </span>
          </>
        }
        actions={
          <>
            <Button icon={MessageSquare} onClick={() => navigate(`/chat?agent=${encodeURIComponent(agent.id)}`)}>
              Open chat
            </Button>
            <Button variant="secondary" icon={Radio} onClick={() => navigate('/command')}>
              Open comms
            </Button>
            <Button variant="secondary" icon={Pencil} onClick={() => setEditing(true)}>
              Edit
            </Button>
            <Button variant="ghost" icon={Trash2} onClick={() => setDeleting(true)}>
              Delete
            </Button>
          </>
        }
        tabs={
          // w-0 + min-w-full keeps the non-wrapping strip from widening the
          // page on phones; the strip itself scrolls sideways.
          <div className="w-0 min-w-full">
            <Tabs tabs={TABS} value={tab} onChange={setTab} label="Agent sections" idBase="agent-tab" />
          </div>
        }
      />

      <Card role="tabpanel" aria-labelledby={`agent-tab-${tab}`}>
        {panel}
      </Card>

      {editing && (
        <AgentEditModal
          agent={agent}
          onClose={() => setEditing(false)}
          onSave={(updated, meta) => {
            const snapshot = agent;
            setAgent((a) => ({ ...a, ...updated }));
            return () => setAgent(snapshot);
          }}
        />
      )}
      {deleting && (
        <AgentDeleteConfirmModal
          agent={agent}
          onClose={() => setDeleting(false)}
          onDelete={(_, meta) => {
            if (!meta?.optimistic) navigate('/library');
            return () => {};
          }}
        />
      )}
      {showKeyModal && (
        <GenerateApiKeyModal
          agentId={id}
          onClose={() => setShowKeyModal(false)}
          onSuccess={(key) => {
            setShowKeyModal(false);
            setRevealedKey({ ...key, agentId: key?.agentId || id });
            loadKeys();
          }}
        />
      )}
      {revealedKey && <KeyRevealModal apiKey={revealedKey} onClose={() => setRevealedKey(null)} />}
    </Page>
  );
}
