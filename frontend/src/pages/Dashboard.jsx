/**
 * Dashboard — home. Honest numbers from /stats, quick actions, The General's
 * live status from the orchestration stream, agents per domain, and the last
 * conversations. All four states, in the place the content goes.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bot,
  Sparkles,
  BookOpen,
  MessageSquare,
  MessagesSquare,
  RefreshCw,
  GitBranch,
  Wrench,
  Shield,
  ArrowRight,
  DollarSign,
  Scale,
  Stethoscope,
  Code2,
  Search,
  Target,
  Award,
  Eye,
} from 'lucide-react';
import { apiJson } from '../services/http';
import { humanize } from '../utils/errors';
import notify from '../utils/notify';
import { roleLine } from '../utils/agentClass';
import useOrchestrationStream from '../hooks/useOrchestrationStream';
import AgentAvatar from '../components/AgentAvatar';
import StatCard from '../components/ui/StatCard';
import BarList from '../components/ui/BarList';
import {
  Button,
  Card,
  CardHeader,
  Chip,
  Page,
  PageHeader,
  SectionHeader,
  EmptyState,
  ErrorState,
  LoadingState,
  OfflineState,
  StatusDot,
  statusMeta,
  Tooltip,
} from '../components/ui';

// Domain → lucide mark.
const DOMAIN_ICONS = {
  financial: DollarSign,
  legal: Scale,
  medical: Stethoscope,
  technology: Code2,
  investigation: Search,
  orchestration: Target,
  meta: Award,
  intelligence: Eye,
};

const QUICK_ACTIONS = [
  { icon: MessageSquare, label: 'New chat', description: 'Start a conversation with an agent', path: '/chat' },
  { icon: GitBranch, label: 'Workflows', description: 'Run a multi-agent workflow template', path: '/workflows' },
  { icon: BookOpen, label: 'Browse agents', description: 'The whole roster, by domain', path: '/library' },
  { icon: Sparkles, label: 'Build an agent', description: 'Design a new agent with Gunny', path: '/builder-chat' },
];

// /health → the header chip. An HTTP answer with a body is "degraded"; no answer is "unreachable".
const HEALTH = {
  checking: { tone: 'neutral', label: 'Checking…', pulse: false },
  ok: { tone: 'ok', label: 'All systems operational', pulse: false },
  degraded: { tone: 'warn', label: 'Degraded', pulse: true },
  down: { tone: 'danger', label: 'API unreachable', pulse: false },
};

function timeAgo(iso) {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '';
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  if (s < 60) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

const fmt = (n) => (typeof n === 'number' ? n.toLocaleString() : '—');

export default function Dashboard() {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [domains, setDomains] = useState([]);
  const [stats, setStats] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [health, setHealth] = useState('checking');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [offline, setOffline] = useState(typeof navigator !== 'undefined' && navigator.onLine === false);
  const { statuses, connected } = useOrchestrationStream();

  const checkHealth = useCallback(async () => {
    try {
      const h = await apiJson('/health', { redirectOn401: false });
      const s = String(h?.status || '').toLowerCase();
      setHealth(s === 'healthy' || s === 'operational' || s === 'ok' ? 'ok' : 'degraded');
    } catch (err) {
      setHealth(err?.status ? 'degraded' : 'down');
    }
  }, []);

  const load = useCallback(
    async ({ quiet = false } = {}) => {
      if (quiet) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        const [agentsRes, domainsRes, statsRes, convRes] = await Promise.allSettled([
          apiJson('/agents'),
          apiJson('/agents/domains'),
          apiJson('/stats'),
          apiJson('/conversations', { params: { limit: 5 } }),
        ]);
        if (agentsRes.status === 'rejected') throw agentsRes.reason;
        setAgents(agentsRes.value?.agents || []);
        setDomains(domainsRes.status === 'fulfilled' ? domainsRes.value?.domains || [] : []);
        setStats(statsRes.status === 'fulfilled' ? statsRes.value : null);
        setConversations(convRes.status === 'fulfilled' ? convRes.value?.conversations || [] : []);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
      checkHealth();
    },
    [checkHealth]
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const on = () => {
      setOffline(false);
      load({ quiet: true });
    };
    const off = () => setOffline(true);
    window.addEventListener('online', on);
    window.addEventListener('offline', off);
    return () => {
      window.removeEventListener('online', on);
      window.removeEventListener('offline', off);
    };
  }, [load]);

  const refresh = async () => {
    await load({ quiet: true });
    notify.success('Dashboard refreshed');
  };

  const general = useMemo(
    () => agents.find((a) => a.id === 'the-general') || agents.find((a) => a.reportsTo == null && /general/i.test(a.displayName || a.name || '')) || null,
    [agents]
  );
  const gunny = useMemo(() => agents.find((a) => a.id === 'gunny') || null, [agents]);
  const generalLive = general ? statuses[general.id] : null;
  const generalStatus = generalLive?.status || 'idle';
  const generalMeta = statusMeta(generalStatus);
  const agentById = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a])), [agents]);

  const totalAgents = stats?.totalAgents ?? agents.length;
  const activeAgents = stats?.activeAgents ?? agents.filter((a) => a.status === 'active').length;
  const h = HEALTH[health] || HEALTH.checking;

  const statCards = [
    { icon: Bot, label: 'Agents', value: fmt(totalAgents), change: `${fmt(activeAgents)} active` },
    { icon: MessagesSquare, label: 'Conversations', value: fmt(stats?.totalConversations), change: 'All time' },
    { icon: MessageSquare, label: 'Messages', value: fmt(stats?.totalMessages), change: 'All time' },
    { icon: Wrench, label: 'Tools registered', value: fmt(stats?.totalTools), change: stats?.totalModels != null ? `${fmt(stats.totalModels)} models available` : 'Models unknown' },
  ];

  // ── the four states ──────────────────────────────────────────────────────
  let body;
  if (offline && !agents.length) {
    body = <OfflineState onRetry={() => load()} />;
  } else if (loading) {
    body = (
      <div className="space-y-6">
        <LoadingState variant="stats" label="Loading dashboard" />
        <section aria-label="Quick actions" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {QUICK_ACTIONS.map((a) => (
            <QuickAction key={a.path} action={a} />
          ))}
        </section>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Agents by domain" description="Click a domain to filter the library" />
            <LoadingState variant="list" count={5} label="Loading domains" />
          </Card>
          <div className="space-y-6">
            <Card>
              <CardHeader title="The General" description="Commanding" />
              <LoadingState variant="text" count={3} label="Loading The General" />
            </Card>
            <Card>
              <CardHeader title="Gunny" description="Agent builder" />
              <LoadingState variant="text" count={2} label="Loading Gunny" />
            </Card>
          </div>
        </div>
        <Card>
          <CardHeader title="Recent conversations" />
          <LoadingState variant="list" count={3} label="Loading conversations" />
        </Card>
      </div>
    );
  } else if (error) {
    body = <ErrorState title="Couldn’t load the dashboard" detail={humanize(error, { what: 'loading the dashboard' })} onRetry={() => load()} />;
  } else if (!agents.length) {
    body = (
      <EmptyState
        icon={Bot}
        title="No agents yet"
        description="Build your first agent with Gunny, or import one from the library. The dashboard fills in as your Brigade grows."
        action={
          <Button icon={Sparkles} onClick={() => navigate('/builder-chat')}>
            Build an agent
          </Button>
        }
        secondary={
          <Button variant="ghost" icon={BookOpen} onClick={() => navigate('/library')}>
            Browse the library
          </Button>
        }
      />
    );
  } else {
    body = (
      <div className="space-y-6">
        <section aria-label="Key numbers" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {statCards.map((m) => (
            <StatCard key={m.label} icon={m.icon} label={m.label} value={m.value} change={m.change} />
          ))}
        </section>

        <section aria-label="Quick actions" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {QUICK_ACTIONS.map((a) => (
            <QuickAction key={a.path} action={a} />
          ))}
        </section>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader
              title="Agents by domain"
              description="Click a domain to filter the library"
              actions={
                <Button variant="link" size="xs" iconRight={ArrowRight} onClick={() => navigate('/library')}>
                  All agents
                </Button>
              }
            />
            {domains.length ? (
              <BarList
                items={domains.map((d) => {
                  const Icon = DOMAIN_ICONS[d.name] || Bot;
                  return {
                    key: d.name,
                    label: d.name,
                    value: d.count,
                    icon: <Icon className="h-4 w-4" aria-hidden="true" />,
                    onClick: () => navigate(`/library?domain=${encodeURIComponent(d.name)}`),
                  };
                })}
                renderValue={(item) => `${item.value} agent${item.value === 1 ? '' : 's'}`}
              />
            ) : (
              <EmptyState compact icon={Bot} title="No domains yet" description="Agents are grouped by domain once they have one." />
            )}
          </Card>

          <div className="space-y-6">
            <Card>
              <div className="flex items-start gap-3">
                {general ? (
                  <span className="relative shrink-0">
                    <AgentAvatar agent={general} size={56} rounded="rounded-card" status={generalStatus} />
                    <span className="absolute -bottom-0.5 -right-0.5">
                      <StatusDot status={generalStatus} size="md" ring />
                    </span>
                  </span>
                ) : null}
                <div className="min-w-0 flex-1">
                  <h3 className="text-lead font-semibold text-fg-strong">{general?.displayName || 'The General'}</h3>
                  <p className="text-body-sm text-muted">{general ? roleLine(general) : 'Commanding'}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <Chip tone={generalMeta.tone} size="xs" dot pulse={generalMeta.pulse}>
                      {generalMeta.label}
                    </Chip>
                    {generalLive?.detail && (
                      <span className="truncate text-caption text-muted">{generalLive.detail}</span>
                    )}
                  </div>
                </div>
              </div>
              <p className="mt-3 text-body-sm text-muted">
                {general?.bio || 'Orchestrator of orchestrators: breaks a task into subtasks, delegates to specialists and synthesizes the result.'}
              </p>
              <p className="mt-2 text-caption text-subtle">
                {connected ? 'Live feed connected' : 'Live feed reconnecting — status updates when it returns'}
              </p>
              <Button className="mt-4 w-full" icon={Shield} onClick={() => navigate('/command')}>
                Open Command Center
              </Button>
            </Card>

            <Card>
              <div className="flex items-start gap-3">
                {gunny ? <AgentAvatar agent={gunny} size={56} rounded="rounded-card" status={statuses[gunny.id]?.status || 'idle'} /> : null}
                <div className="min-w-0 flex-1">
                  <h3 className="text-lead font-semibold text-fg-strong">{gunny?.displayName || 'Gunny'}</h3>
                  <p className="text-body-sm text-muted">{gunny ? roleLine(gunny) : 'Agent builder'}</p>
                </div>
              </div>
              <p className="mt-3 text-body-sm text-muted">Builds new agents in conversation: job, personality, tools, model, deploy.</p>
              <Button variant="secondary" className="mt-4 w-full" icon={Sparkles} onClick={() => navigate('/builder-chat')}>
                Build an agent with Gunny
              </Button>
            </Card>
          </div>
        </div>

        <Card>
          <CardHeader
            title="Recent conversations"
            description={conversations.length ? `The last ${conversations.length}` : undefined}
            actions={
              <Button variant="secondary" size="sm" icon={MessageSquare} onClick={() => navigate('/chat')}>
                New chat
              </Button>
            }
          />
          {conversations.length ? (
            <ul className="divide-y divide-border/60" aria-label="Recent conversations">
              {conversations.map((c) => {
                const agent = agentById[c.agent_id] || c.agent || null;
                const name = agent?.displayName || agent?.name || 'Agent';
                return (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => navigate(`/chat?conversation=${encodeURIComponent(c.id)}`)}
                      className="flex min-h-touch w-full items-center gap-3 rounded-control px-2 py-2 text-left transition-colors duration-fast hover:bg-elevated/60"
                    >
                      <AgentAvatar agent={agent || { id: c.agent_id, name }} size={36} rounded="rounded-control" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-body font-medium text-fg">{c.title || 'Untitled conversation'}</span>
                        <span className="block truncate text-caption text-muted">
                          {name} · {fmt(c.message_count || 0)} message{c.message_count === 1 ? '' : 's'}
                        </span>
                      </span>
                      <span className="shrink-0 text-caption text-subtle">{timeAgo(c.updated_at)}</span>
                      <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0 text-subtle" />
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState
              compact
              icon={MessagesSquare}
              title="No conversations yet"
              description="Start one and it shows up here."
              action={
                <Button size="sm" icon={MessageSquare} onClick={() => navigate('/chat')}>
                  Start a chat
                </Button>
              }
            />
          )}
        </Card>
      </div>
    );
  }

  return (
    <Page width="wide">
      <PageHeader
        eyebrow="Home"
        title="Dashboard"
        description={
          loading
            ? 'Your Brigade at a glance'
            : error
              ? 'Your Brigade at a glance'
              : `${fmt(totalAgents)} agent${totalAgents === 1 ? '' : 's'} · ${fmt(stats?.totalConversations ?? 0)} conversations · ${fmt(domains.length)} domain${domains.length === 1 ? '' : 's'}`
        }
        actions={
          <>
            <Tooltip content="Open Monitoring">
              <Link to="/monitoring" className="rounded-chip focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg">
                <Chip tone={h.tone} dot pulse={h.pulse}>
                  {h.label}
                </Chip>
              </Link>
            </Tooltip>
            <Button variant="secondary" icon={RefreshCw} loading={refreshing} onClick={refresh} disabled={loading}>
              Refresh
            </Button>
          </>
        }
      />
      {body}
    </Page>
  );
}

function QuickAction({ action }) {
  const navigate = useNavigate();
  const Icon = action.icon;
  return (
    <Card as="button" type="button" interactive className="group h-full w-full" onClick={() => navigate(action.path)}>
      <span aria-hidden="true" className="mb-3 flex h-10 w-10 items-center justify-center rounded-control bg-accent/10 text-accent">
        <Icon className="h-5 w-5" />
      </span>
      <span className="block text-body font-semibold text-fg-strong">{action.label}</span>
      <span className="mt-0.5 block text-body-sm text-muted">{action.description}</span>
    </Card>
  );
}
