/**
 * Navigation — the shell: a sidebar on desktop, a top bar + drawer on phones.
 *
 * Data-driven. NAV_SECTIONS below is THE list of pages; the command palette
 * (every page reachable from ⌘K) and the breadcrumbs (route names) read the
 * same array, so a page is added once. Tokens only; the active row is accent
 * text plus a 2px accent bar, never a wash.
 */
import { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import {
  Home,
  BookOpen,
  Wrench,
  Book,
  Activity,
  Settings,
  MessageSquare,
  MessagesSquare,
  Globe,
  Workflow,
  Network,
  Shield,
  GitBranch,
  Server,
  FileText,
  Zap,
  FileCode,
  CalendarClock,
  ChevronDown,
  Bot,
  Menu as MenuIcon,
  Sparkles,
  GraduationCap,
  AlertTriangle,
  Building2,
  Wallet,
  Search,
} from 'lucide-react';
import { Button, Chip, IconButton, Kbd, Sheet, StatusDot, Tooltip } from './ui';
import UserProfile from './auth/UserProfile';
import OrgSwitcher from './org/OrgSwitcher';
import { BrigadeLogo } from './UnicornBrigadeLogo';
import { apiJson } from '../services/http';

const HEALTH_POLL_MS = 30000;
const COLLAPSE_KEY = 'nav-collapsed-sections';
const IS_MAC = typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.platform || '');
/** The modifier key as people see it on their keyboard. */
export const MOD_KEY = IS_MAC ? '⌘' : 'Ctrl';

/** Open the command palette from anywhere (the palette listens for this). */
export function openCommandPalette(detail) {
  window.dispatchEvent(new CustomEvent('brigade:command-palette', { detail }));
}
/** Re-open the getting-started tour (App listens for this). */
export function openGettingStarted() {
  window.dispatchEvent(new CustomEvent('brigade:getting-started'));
}

export const NAV_SECTIONS = [
  {
    id: 'main',
    title: 'Main',
    icon: Home,
    items: [
      { path: '/dashboard', label: 'Dashboard', icon: Home, hint: 'Overview, quick actions and recent activity', keywords: ['home', 'overview'] },
      { path: '/chat', label: 'Chat', icon: MessageSquare, hint: 'Talk to any agent', keywords: ['conversation', 'talk', 'message'] },
      { path: '/conversations', label: 'Conversations', icon: MessagesSquare, hint: 'Every conversation, searchable', keywords: ['history'] },
    ],
  },
  {
    id: 'command',
    title: 'Command',
    icon: Globe,
    items: [
      { path: '/command', label: 'Command Center', icon: Shield, hint: 'The General’s war room: the whole Brigade as a live org chart', keywords: ['war room', 'org chart', 'activity', 'missions', 'orchestration', 'briefing', 'live', '3d'] },
      { path: '/workflows', label: 'Workflows', icon: GitBranch, hint: 'Run and watch hierarchical workflow templates', keywords: ['templates', 'pipeline'] },
      { path: '/ralph-monitor', label: 'Self-Correction', icon: Zap, hint: 'Self-correcting workflow runs with automatic retry', keywords: ['ralph', 'retry'] },
      { path: '/knowledge', label: 'Knowledge Graph', icon: Network, hint: 'Entities and relationships the agents know about', keywords: ['falkordb', 'graph', 'entities'] },
    ],
  },
  {
    id: 'agents',
    title: 'Agents',
    icon: Bot,
    items: [
      { path: '/library', label: 'Agent Library', icon: BookOpen, hint: 'Every agent: configure, edit, retire', keywords: ['roster', 'agents'] },
      { path: '/builder-chat', label: 'Agent Builder', icon: Sparkles, hint: 'Build a new agent in conversation with Gunny', keywords: ['gunny', 'create agent', 'new agent'] },
    ],
  },
  {
    id: 'tools',
    title: 'Tools',
    icon: Wrench,
    items: [
      { path: '/tools', label: 'Tool Library', icon: Wrench, hint: 'Every capability an agent can be given', keywords: ['capabilities'] },
      { path: '/mcp-servers', label: 'MCP Servers', icon: Server, hint: 'Start, stop and test MCP servers', keywords: ['mcp', 'servers'] },
      { path: '/mcp-docs', label: 'MCP Docs', icon: FileText, hint: 'How Model Context Protocol integration works', keywords: ['mcp', 'documentation'] },
      { path: '/langflow', label: 'Langflow Flows', icon: Workflow, hint: 'Visual flow builder', keywords: ['flows', 'visual'], when: (cfg) => Boolean(cfg?.langflow_enabled) },
      { path: '/docs', label: 'API Docs', icon: Book, hint: 'The REST API, with live requests', keywords: ['api', 'reference', 'swagger'] },
    ],
  },
  {
    id: 'system',
    title: 'System',
    icon: Settings,
    items: [
      { path: '/code-attribution', label: 'Code Attribution', icon: FileCode, hint: 'Which agent wrote which lines', keywords: ['trace', 'lineage', 'audit'], sidebar: false },
      { path: '/monitoring', label: 'Monitoring', icon: Activity, hint: 'Service health, resources and scheduled runs', keywords: ['health', 'status', 'metrics', 'uptime'] },
      { path: '/scheduled-runs', label: 'Scheduled Runs', icon: CalendarClock, hint: 'Cron-based agent runs that survive restarts', keywords: ['cron', 'schedule', 'jobs'] },
      { path: '/organization', label: 'Organization', icon: Building2, hint: 'Members, roles and invitations', keywords: ['team', 'members', 'invite', 'org'] },
      { path: '/billing', label: 'Usage & Billing', icon: Wallet, hint: 'Usage, spend and plan', keywords: ['plan', 'credits', 'spend', 'usage'] },
      { path: '/settings', label: 'Settings', icon: Settings, hint: 'Preferences, theme, API keys', keywords: ['preferences', 'theme', 'api keys'] },
    ],
  },
];

/** Every sidebar page, flat, with its section name. */
export const NAV_PAGES = NAV_SECTIONS.flatMap((s) => s.items.map((it) => ({ ...it, section: s.title })));

/** The page record for a pathname (exact first, then the longest prefix). */
export function pageFor(pathname) {
  return (
    NAV_PAGES.find((p) => p.path === pathname) ||
    NAV_PAGES
      .filter((p) => pathname.startsWith(`${p.path}/`))
      .sort((a, b) => b.path.length - a.path.length)[0] ||
    null
  );
}

// 'checking' | 'online' | 'degraded' | 'offline' → the footer status row.
const PLATFORM = {
  checking: { dot: 'idle', label: 'Checking platform…' },
  online: { dot: 'done', label: 'All systems operational' },
  degraded: { dot: 'thinking', label: 'Degraded — open Monitoring' },
  offline: { dot: 'error', label: 'API unreachable' },
};

function usePlatformStatus() {
  const [status, setStatus] = useState('checking');
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const health = await apiJson('/health', { redirectOn401: false });
        if (cancelled) return;
        const s = String(health?.status || '').toLowerCase();
        setStatus(s === 'healthy' || s === 'operational' || s === 'ok' ? 'online' : 'degraded');
      } catch (err) {
        if (cancelled) return;
        // An HTTP answer (503 and a body) is the API saying it is degraded; no answer at all is offline.
        setStatus(err?.status ? 'degraded' : 'offline');
      }
    };
    check();
    const t = setInterval(check, HEALTH_POLL_MS);
    window.addEventListener('online', check);
    return () => {
      cancelled = true;
      clearInterval(t);
      window.removeEventListener('online', check);
    };
  }, []);
  return status;
}

function useDeployConfig() {
  const [cfg, setCfg] = useState(null);
  useEffect(() => {
    let cancelled = false;
    apiJson('/auth/config', { redirectOn401: false })
      .then((v) => !cancelled && setCfg(v))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return cfg;
}

function readCollapsed() {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {};
  } catch {
    return {};
  }
}

function ModK() {
  return (
    <span className="inline-flex items-center gap-0.5" aria-hidden="true">
      <Kbd>{MOD_KEY}</Kbd>
      <Kbd>K</Kbd>
    </span>
  );
}

function NavItem({ item, mobile }) {
  const Icon = item.icon;
  const link = (
    <NavLink
      to={item.path}
      className={({ isActive }) =>
        [
          'relative flex items-center gap-3 rounded-control px-3 text-body-sm font-medium transition-colors duration-fast',
          mobile ? 'min-h-touch' : 'min-h-10',
          isActive ? 'bg-elevated/50 text-accent' : 'text-muted hover:bg-elevated/50 hover:text-fg',
        ].join(' ')
      }
    >
      {({ isActive }) => (
        <>
          {isActive && <span aria-hidden="true" className="absolute bottom-2 left-0 top-2 w-0.5 rounded-full bg-accent" />}
          <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
          <span className="truncate">{item.label}</span>
        </>
      )}
    </NavLink>
  );
  if (mobile || !item.hint) return link;
  return (
    <Tooltip content={item.hint} side="right">
      {link}
    </Tooltip>
  );
}

function NavSection({ section, items, collapsed, onToggle, mobile }) {
  const Icon = section.icon;
  const panelId = `nav-${section.id}${mobile ? '-m' : ''}`;
  return (
    <div className="mt-4 first:mt-0">
      <button
        type="button"
        aria-expanded={!collapsed}
        aria-controls={panelId}
        onClick={onToggle}
        className="flex h-8 w-full items-center justify-between rounded-control px-3 text-micro font-semibold uppercase tracking-wider text-muted transition-colors duration-fast hover:text-fg"
      >
        <span className="flex items-center gap-2">
          <Icon aria-hidden="true" className="h-3.5 w-3.5" />
          {section.title}
        </span>
        <ChevronDown aria-hidden="true" className={`h-3.5 w-3.5 transition-transform duration-fast ${collapsed ? '-rotate-90' : ''}`} />
      </button>
      <ul id={panelId} hidden={collapsed} className="mt-1 space-y-0.5">
        {items.map((it) => (
          <li key={it.path}>
            <NavItem item={it} mobile={mobile} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlatformStatusRow({ status, mobile }) {
  const m = PLATFORM[status] || PLATFORM.checking;
  const row = (
    <Link
      to="/monitoring"
      className={`flex items-center gap-2.5 rounded-control px-3 text-body-sm text-muted transition-colors duration-fast hover:bg-elevated/50 hover:text-fg ${
        mobile ? 'min-h-touch' : 'min-h-10'
      }`}
    >
      <span aria-hidden="true" className="flex">
        <StatusDot status={m.dot} size="sm" />
      </span>
      <span className="truncate">{m.label}</span>
    </Link>
  );
  return mobile ? row : <Tooltip content="Open Monitoring" side="right">{row}</Tooltip>;
}

function Wordmark({ size = 36 }) {
  return (
    <Link to="/dashboard" className="flex min-w-0 items-center gap-3 rounded-control">
      <BrigadeLogo size={size} />
      <span className="min-w-0">
        <span className="block truncate text-lead font-bold leading-tight text-gradient">Unicorn Brigade</span>
        <span className="block text-micro font-medium uppercase tracking-wider text-muted">AI Agent Factory</span>
      </span>
    </Link>
  );
}

function DevBanner() {
  if (!import.meta.env.DEV) return null;
  return (
    <Chip tone="warn" size="xs" icon={AlertTriangle} className="w-full justify-center">
      Development mode · auth bypassed
    </Chip>
  );
}

function NavBody({ sections, collapsed, onToggle, status, mobile }) {
  return (
    <>
      <nav aria-label="Primary">
        {sections.map((s) => (
          <NavSection
            key={s.id}
            section={s}
            items={s.items}
            collapsed={Boolean(collapsed[s.id])}
            onToggle={() => onToggle(s.id)}
            mobile={mobile}
          />
        ))}
      </nav>
      <div className="mt-3 space-y-2 border-t border-border pt-3">
        <UserProfile />
        <Button variant="outline" size={mobile ? 'lg' : 'sm'} icon={GraduationCap} className="w-full" onClick={openGettingStarted}>
          Getting started
        </Button>
        <PlatformStatusRow status={status} mobile={mobile} />
      </div>
    </>
  );
}

export default function Navigation() {
  const location = useLocation();
  const status = usePlatformStatus();
  const cfg = useDeployConfig();
  const [open, setOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readCollapsed);

  // The drawer closes on every route change.
  useEffect(() => {
    setOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsed));
    } catch {
      /* storage unavailable — the state still works for this session */
    }
  }, [collapsed]);

  const toggle = (id) => setCollapsed((prev) => ({ ...prev, [id]: !prev[id] }));
  // `sidebar: false` pages stay in the palette and breadcrumbs, out of the sidebar.
  const sections = NAV_SECTIONS.map((s) => ({ ...s, items: s.items.filter((it) => (!it.when || it.when(cfg)) && it.sidebar !== false) }));

  return (
    <>
      {/* Phones: a 56px top bar with the drawer trigger, the wordmark and ⌘K. */}
      <header className="fixed inset-x-0 top-0 z-nav flex h-14 items-center gap-1 border-b border-border bg-surface/90 px-2 backdrop-blur-xl lg:hidden">
        <IconButton icon={MenuIcon} label="Open navigation" size="lg" onClick={() => setOpen(true)} aria-expanded={open} tooltip={false} />
        <Link to="/dashboard" className="flex min-w-0 items-center gap-2 rounded-control px-1">
          <BrigadeLogo size={28} />
          <span className="truncate text-body font-bold text-gradient">Unicorn Brigade</span>
        </Link>
        <span className="flex-1" />
        <IconButton icon={Search} label="Search and commands" size="lg" onClick={() => openCommandPalette()} tooltip={false} />
      </header>

      <Sheet isOpen={open} onClose={() => setOpen(false)} side="right" title="Menu">
        <div className="space-y-3 pb-4">
          <DevBanner />
          <OrgSwitcher />
          <NavBody sections={sections} collapsed={collapsed} onToggle={toggle} status={status} mobile />
        </div>
      </Sheet>

      {/* Desktop: the sidebar. */}
      <aside className="fixed inset-y-0 left-0 z-nav hidden w-64 flex-col border-r border-border bg-surface/80 backdrop-blur-xl lg:flex">
        <div className="space-y-3 px-4 pb-3 pt-5">
          <Wordmark />
          <DevBanner />
        </div>
        <div className="px-3 pb-2">
          <OrgSwitcher />
        </div>
        <div className="px-3 pb-3">
          <button
            type="button"
            onClick={() => openCommandPalette()}
            aria-keyshortcuts="Meta+K Control+K"
            className="flex h-9 w-full items-center gap-2 rounded-control border border-border bg-surface/60 px-3 text-body-sm text-muted transition-colors duration-fast hover:border-border-strong hover:text-fg"
          >
            <Search aria-hidden="true" className="h-4 w-4 shrink-0" />
            <span className="flex-1 text-left">Search or jump to…</span>
            <ModK />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
          <NavBody sections={sections} collapsed={collapsed} onToggle={toggle} status={status} />
        </div>
      </aside>
    </>
  );
}
