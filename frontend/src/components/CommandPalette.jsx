/**
 * Command palette (⌘K / Ctrl-K) — every page, the app's actions and every agent,
 * from anywhere, including from inside inputs. "?" outside an input opens the
 * shortcuts sheet. Combobox + listbox semantics (aria-activedescendant), focus
 * is trapped while open and restored on close, Escape closes.
 */
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Search,
  MessageSquare,
  Sparkles,
  Network,
  LayoutGrid,
  Megaphone,
  CalendarClock,
  Monitor,
  Sun,
  Moon,
  SunMoon,
  LogOut,
  Keyboard,
  GraduationCap,
  Radio,
  Clock,
  CornerDownLeft,
  AlertCircle,
  Palette,
  Target,
  Repeat,
} from 'lucide-react';
import { IconButton, Kbd, Sheet } from './ui';
import useFocusTrap from './ui/useFocusTrap';
import AgentAvatar from './AgentAvatar';
import { roleLine } from '../utils/agentClass';
import { NAV_PAGES, MOD_KEY, openGettingStarted } from './Navigation';
import { apiJson } from '../services/http';
import useAuth from '../hooks/useAuth';
import { useCommsStore } from '../stores/useCommsStore';
import { applyTheme, applyThemeFamily, THEME_FAMILIES, normalizeFamily } from '../utils/theme';
import { getPreferences, savePreferences } from '../utils/preferences';
import notify from '../utils/notify';

const OPEN_EVENT = 'brigade:command-palette';
const RECENT_KEY = 'brigade-recent-pages';
const RECENT_MAX = 5;
const AGENT_MAX = 8;
// Mode cycles system → light → dark → system (utils/theme.js applies it).
const THEME_ORDER = ['system', 'light', 'dark'];
const THEME_LABEL = { system: 'System', light: 'Light', dark: 'Dark' };
const nextTheme = (t) => THEME_ORDER[(THEME_ORDER.indexOf(t) + 1) % THEME_ORDER.length];

/** Every keyboard shortcut in the app, for the "?" sheet. */
export const SHORTCUTS = [
  { group: 'Anywhere', keys: [[MOD_KEY, 'K']], label: 'Open or close the command palette' },
  { group: 'Anywhere', keys: [['?']], label: 'Show these shortcuts (outside an input)' },
  { group: 'Anywhere', keys: [['Esc']], label: 'Close a dialog, drawer, menu, dock window or the palette' },
  { group: 'Command palette', keys: [['↑'], ['↓']], label: 'Move through results' },
  { group: 'Command palette', keys: [['Home'], ['End']], label: 'Jump to the first or last result' },
  { group: 'Command palette', keys: [['↵']], label: 'Open the highlighted page, action or agent chat' },
  { group: 'Command palette', keys: [[MOD_KEY, '↵']], label: 'Open comms with the highlighted agent in the Command Center' },
  { group: 'Chat', keys: [['↵']], label: 'Send the message' },
  { group: 'Chat', keys: [['⇧', '↵']], label: 'New line' },
  { group: 'Chat', keys: [['Esc']], label: 'Stop a reply that is streaming' },
  { group: 'Command Center', keys: [['↵'], ['Space']], label: 'Open comms with the focused agent on the org chart' },
  { group: 'Command Center', keys: [[MOD_KEY, '↵']], label: 'Send the staff briefing' },
  { group: 'Lists, menus and tabs', keys: [['↑'], ['↓']], label: 'Move through a menu or list' },
  { group: 'Lists, menus and tabs', keys: [['←'], ['→']], label: 'Switch tabs' },
  { group: 'Lists, menus and tabs', keys: [['Home'], ['End']], label: 'First or last item' },
];

const PAGE_ITEMS = NAV_PAGES.map((p) => ({
  id: `page:${p.path}`,
  kind: 'page',
  label: p.label,
  subtitle: p.section,
  icon: p.icon,
  keywords: [p.hint || '', ...(p.keywords || [])],
  path: p.path,
}));

function readRecent() {
  try {
    const list = JSON.parse(localStorage.getItem(RECENT_KEY) || '[]');
    return Array.isArray(list) ? list.filter((p) => typeof p === 'string') : [];
  } catch {
    return [];
  }
}
function pushRecent(path) {
  try {
    const next = [path, ...readRecent().filter((p) => p !== path)].slice(0, RECENT_MAX);
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable */
  }
}

/** Fuzzy-ish match: exact > prefix > word start > substring > subsequence; every query word must hit. */
function scoreItem(query, item) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return 1;
  const label = String(item.label).toLowerCase();
  const hay = [label, item.subtitle || '', ...(item.keywords || [])].join(' ').toLowerCase();
  let total = 0;
  for (const w of words) {
    let s = 0;
    if (label === w) s = 100;
    else if (label.startsWith(w)) s = 80;
    else if (hay.split(/[\s/–—·-]+/).some((t) => t.startsWith(w))) s = 60;
    else if (hay.includes(w)) s = 40;
    else {
      let i = 0;
      for (const ch of label) if (ch === w[i]) i += 1;
      if (i === w.length) s = 20;
    }
    if (!s) return 0;
    total += s;
  }
  return total;
}

function isEditable(el) {
  if (!el || el === document.body) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable || el.closest?.('[role="textbox"]');
}

function Keys({ keys }) {
  return (
    <span className="inline-flex items-center gap-1">
      {keys.map((combo, i) => (
        <span key={i} className="inline-flex items-center gap-0.5">
          {i > 0 && <span className="px-0.5 text-subtle">/</span>}
          {combo.map((k) => (
            <Kbd key={k}>{k}</Kbd>
          ))}
        </span>
      ))}
    </span>
  );
}

export function ShortcutsSheet({ isOpen, onClose }) {
  const groups = [...new Set(SHORTCUTS.map((s) => s.group))];
  return (
    <Sheet isOpen={isOpen} onClose={onClose} side="right" title="Keyboard shortcuts">
      <div className="space-y-5 pb-4">
        {groups.map((g) => (
          <section key={g} aria-labelledby={`sc-${g.replace(/\W+/g, '-')}`}>
            <h3 id={`sc-${g.replace(/\W+/g, '-')}`} className="mb-2 text-micro font-semibold uppercase tracking-wider text-muted">
              {g}
            </h3>
            <dl className="divide-y divide-border rounded-card border border-border bg-card">
              {SHORTCUTS.filter((s) => s.group === g).map((s) => (
                <div key={s.label} className="flex items-center justify-between gap-4 px-3 py-2">
                  <dt className="text-body-sm text-fg">{s.label}</dt>
                  <dd className="shrink-0">
                    <Keys keys={s.keys} />
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Sheet>
  );
}

export default function CommandPalette() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((s) => s.user);
  const logout = useAuth((s) => s.logout);
  const openWindow = useCommsStore((s) => s.openWindow);

  const [open, setOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const [theme, setTheme] = useState(() => getPreferences().theme);
  const [recent, setRecent] = useState(readRecent);
  const [agents, setAgents] = useState([]);
  const [agentState, setAgentState] = useState('idle'); // idle | loading | ready | error
  const inputRef = useRef(null);
  const listId = useId();

  const close = useCallback(() => setOpen(false), []);
  const panelRef = useFocusTrap({ isOpen: open, onClose: close, initialFocusRef: inputRef });

  // ⌘K / Ctrl-K toggles from anywhere (inputs included); "?" outside an input opens the shortcuts.
  useEffect(() => {
    const onKey = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && !e.altKey && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setShortcutsOpen(false);
        setOpen((v) => !v);
        return;
      }
      if (e.key === '?' && !mod && !e.altKey && !isEditable(e.target) && !open) {
        e.preventDefault();
        setShortcutsOpen(true);
      }
    };
    const onOpenEvent = (e) => {
      setShortcutsOpen(false);
      if (typeof e?.detail?.query === 'string') setQuery(e.detail.query);
      setOpen(true);
    };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener(OPEN_EVENT, onOpenEvent);
    return () => {
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener(OPEN_EVENT, onOpenEvent);
    };
  }, [open]);

  // Remember visited pages for the "Recent" group.
  useEffect(() => {
    const page = PAGE_ITEMS.find((p) => p.path === location.pathname);
    if (page) {
      pushRecent(page.path);
      setRecent(readRecent());
    }
  }, [location.pathname]);

  // Reset on open; load the roster the first time the palette opens (not on every page mount).
  useEffect(() => {
    if (!open) return;
    setQuery('');
    setActive(0);
    setTheme(getPreferences().theme);
    if (agentState === 'idle') {
      setAgentState('loading');
      apiJson('/agents', { redirectOn401: false })
        .then((d) => {
          setAgents(Array.isArray(d?.agents) ? d.agents : []);
          setAgentState('ready');
        })
        .catch(() => setAgentState('error'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const chooseTheme = useCallback((choice) => {
    savePreferences({ ...getPreferences(), theme: choice });
    applyTheme(choice);
    setTheme(choice);
    notify.success(choice === 'system' ? 'Theme follows your system' : `Theme: ${choice}`);
  }, []);

  // Theme family (Brigade / Business / Graphite) — the same preference Settings writes.
  const [family, setFamily] = useState(() => normalizeFamily(getPreferences().themeFamily));
  const chooseFamily = useCallback((id) => {
    const next = normalizeFamily(id);
    savePreferences({ ...getPreferences(), themeFamily: next });
    applyThemeFamily(next);
    setFamily(next);
    const meta = THEME_FAMILIES.find((f) => f.id === next);
    notify.success(`Theme family: ${meta?.label || next}`);
  }, []);

  const actions = useMemo(
    () => [
      { id: 'act:new-chat', label: 'New chat', subtitle: 'Start a conversation with an agent', icon: MessageSquare, keywords: ['conversation', 'talk', 'message', 'start'], run: () => navigate('/chat') },
      { id: 'act:build', label: 'Build an agent', subtitle: 'Design a new agent with Gunny', icon: Sparkles, keywords: ['create', 'new agent', 'gunny', 'builder'], run: () => navigate('/builder-chat') },
      { id: 'act:cc-chart', label: 'Command Center → Org chart', subtitle: 'The whole Brigade as a clickable chart', icon: Network, keywords: ['war room', 'hierarchy', 'command'], run: () => navigate('/command?view=chart') },
      { id: 'act:cc-activity', label: 'Command Center → Activity', subtitle: 'Who is working on what, live', icon: LayoutGrid, keywords: ['live', 'feed', 'command'], run: () => navigate('/command?view=activity') },
      { id: 'act:cc-missions', label: 'Command Center → Missions', subtitle: 'Hand The General a task and watch the crew work', icon: Target, keywords: ['missions', 'orchestration', 'task', 'start mission', 'command'], run: () => navigate('/command?view=missions') },
      { id: 'act:cc-autonomous', label: 'Command Center → Autonomous', subtitle: 'Every job that runs on its own: whose it is, what it’s responsible for, how it last went', icon: Repeat, keywords: ['autonomous', 'schedule', 'cron', 'catalogue', 'catalog', 'responsibility', 'jobs', 'loops', 'launchd', 'systemd', 'routine', 'stale', 'failing', 'command'], run: () => navigate('/command?view=autonomous') },
      { id: 'act:cc-briefing', label: 'Command Center → Briefing', subtitle: 'Brief the staff and promote answers to comms', icon: Megaphone, keywords: ['brief', 'staff', 'command'], run: () => navigate('/command?view=briefing') },
      { id: 'act:runs-new', label: 'Scheduled runs → New', subtitle: 'Schedule an agent on a cron', icon: CalendarClock, keywords: ['cron', 'schedule', 'job', 'new run'], run: () => navigate('/scheduled-runs?new=1') },
      { id: 'act:theme-toggle', label: 'Toggle theme', subtitle: `${THEME_LABEL[theme] || 'System'} now → ${THEME_LABEL[nextTheme(theme)]} next`, icon: SunMoon, keywords: ['theme', 'appearance', 'toggle', 'cycle', 'dark', 'light', 'system', 'mode'], run: () => chooseTheme(nextTheme(theme)) },
      { id: 'act:theme-system', label: 'Theme: match the system', subtitle: theme === 'system' ? 'Current' : 'Follow the OS light / dark setting', icon: Monitor, keywords: ['theme', 'appearance', 'toggle', 'system', 'auto'], run: () => chooseTheme('system') },
      { id: 'act:theme-light', label: 'Theme: light', subtitle: theme === 'light' ? 'Current' : 'Light canvas', icon: Sun, keywords: ['theme', 'appearance', 'toggle', 'light'], run: () => chooseTheme('light') },
      { id: 'act:theme-dark', label: 'Theme: dark', subtitle: theme === 'dark' ? 'Current' : 'Dark canvas', icon: Moon, keywords: ['theme', 'appearance', 'toggle', 'dark'], run: () => chooseTheme('dark') },
      ...THEME_FAMILIES.map((f) => ({
        id: `act:family-${f.id}`,
        label: `Theme family: ${f.label}`,
        subtitle: family === f.id ? 'Current' : f.blurb,
        icon: Palette,
        keywords: ['theme', 'family', 'appearance', 'palette', 'colors', 'business', 'graphite', 'brigade', f.id],
        run: () => chooseFamily(f.id),
      })),
      { id: 'act:shortcuts', label: 'Keyboard shortcuts', subtitle: 'Every shortcut in Brigade', icon: Keyboard, keywords: ['help', 'keys', 'hotkeys'], run: () => setShortcutsOpen(true) },
      { id: 'act:tour', label: 'Getting started guide', subtitle: 'The four-step tour', icon: GraduationCap, keywords: ['onboarding', 'tour', 'wizard', 'help', 'welcome'], run: () => openGettingStarted() },
      { id: 'act:signout', label: 'Sign out', subtitle: user?.email || 'End this session', icon: LogOut, keywords: ['logout', 'log out', 'exit', 'leave'], run: async () => { await logout(); navigate('/login'); } },
    ].map((a) => ({ ...a, kind: 'action' })),
    [navigate, theme, chooseTheme, family, chooseFamily, user, logout]
  );

  const agentItems = useMemo(
    () =>
      agents.map((a) => ({
        id: `agent:${a.id}`,
        kind: 'agent',
        label: a.displayName || a.name || a.id,
        subtitle: roleLine(a),
        keywords: [a.domain || '', a.title || '', a.rank || '', a.id || ''],
        agent: a,
        run: () => navigate(`/chat?agent=${encodeURIComponent(a.id)}`),
        secondary: {
          label: 'Open comms',
          run: () => {
            openWindow(a);
            navigate('/command');
          },
        },
      })),
    [agents, navigate, openWindow]
  );

  const pageItems = useMemo(
    () => PAGE_ITEMS.map((p) => ({ ...p, run: () => navigate(p.path) })),
    [navigate]
  );

  // Groups → a flat list for keyboard navigation.
  const groups = useMemo(() => {
    const q = query.trim();
    if (!q) {
      const recentItems = recent
        .map((path) => pageItems.find((p) => p.path === path))
        .filter(Boolean)
        .map((p) => ({ ...p, id: `recent:${p.path}`, icon: p.icon }));
      return [
        { id: 'recent', title: 'Recent', items: recentItems },
        { id: 'actions', title: 'Actions', items: actions },
        { id: 'pages', title: 'Pages', items: pageItems },
        { id: 'agents', title: 'Agents', items: agentItems.slice(0, AGENT_MAX) },
      ].filter((g) => g.items.length || g.id === 'agents');
    }
    const rank = (list) =>
      list
        .map((it) => ({ it, s: scoreItem(q, it) }))
        .filter((x) => x.s > 0)
        .sort((a, b) => b.s - a.s)
        .map((x) => x.it);
    return [
      { id: 'pages', title: 'Pages', items: rank(pageItems) },
      { id: 'actions', title: 'Actions', items: rank(actions) },
      { id: 'agents', title: 'Agents', items: rank(agentItems).slice(0, AGENT_MAX) },
    ].filter((g) => g.items.length);
  }, [query, recent, pageItems, actions, agentItems]);

  const flat = useMemo(() => groups.flatMap((g) => g.items), [groups]);
  const activeItem = flat[active] || null;
  const optionId = (item) => `${listId}-${item.id.replace(/[^\w-]/g, '_')}`;
  const activeId = activeItem ? optionId(activeItem) : undefined;

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView({ block: 'nearest' });
  }, [activeId]);

  const select = (item, secondary = false) => {
    if (!item) return;
    close();
    const fn = secondary && item.secondary ? item.secondary.run : item.run;
    fn?.();
  };

  const onKeyDown = (e) => {
    const n = flat.length;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (n) setActive((i) => (i + 1) % n);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (n) setActive((i) => (i - 1 + n) % n);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActive(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setActive(Math.max(0, n - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      select(activeItem, e.metaKey || e.ctrlKey);
    }
  };

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-modal flex items-start justify-center bg-bg/70 p-3 pt-[10vh] backdrop-blur-sm animate-fade-in sm:pt-[14vh]"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) close();
          }}
        >
          <div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            tabIndex={-1}
            onMouseDown={(e) => e.stopPropagation()}
            className="flex w-full max-w-xl flex-col overflow-hidden rounded-pane border border-border bg-overlay shadow-e4 animate-scale-in focus:outline-none"
          >
            <div className="flex items-center gap-3 border-b border-border px-4 transition-colors duration-fast focus-within:border-accent/50">
              <Search aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
              <input
                ref={inputRef}
                role="combobox"
                aria-expanded="true"
                aria-controls={listId}
                aria-activedescendant={activeId}
                aria-autocomplete="list"
                aria-label="Search pages, actions and agents"
                autoComplete="off"
                spellCheck={false}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Search pages, actions, agents…"
                className="h-12 w-full min-w-0 bg-transparent text-body text-fg placeholder:text-subtle focus-visible:outline-none"
              />
              <Kbd>esc</Kbd>
            </div>

            <div id={listId} role="listbox" aria-label="Results" className="max-h-[60vh] overflow-y-auto p-2">
              {flat.length === 0 && agentState !== 'loading' && (
                <div className="px-4 py-10 text-center" role="status">
                  <p className="text-body font-semibold text-fg-strong">Nothing matches “{query.trim()}”</p>
                  <p className="mt-1 text-body-sm text-muted">Try a page name, an action like “theme”, or an agent.</p>
                </div>
              )}
              {groups.map((g) => (
                <div key={g.id} role="group" aria-labelledby={`${listId}-g-${g.id}`} className="pb-1">
                  <div id={`${listId}-g-${g.id}`} role="presentation" className="px-3 pb-1 pt-2 text-micro font-semibold uppercase tracking-wider text-subtle">
                    {g.title}
                  </div>
                  {g.items.map((item) => {
                    const idx = flat.indexOf(item);
                    const isActive = idx === active;
                    const Icon = item.icon;
                    return (
                      <div
                        key={item.id}
                        id={optionId(item)}
                        role="option"
                        aria-selected={isActive}
                        onMouseMove={() => !isActive && setActive(idx)}
                        onClick={() => select(item)}
                        className={`flex min-h-10 cursor-pointer items-center gap-3 rounded-control px-3 py-1.5 transition-colors duration-fast ${
                          isActive ? 'bg-elevated text-fg-strong' : 'text-fg'
                        }`}
                      >
                        {item.kind === 'agent' ? (
                          <AgentAvatar agent={item.agent} size={28} rounded="rounded-control" />
                        ) : (
                          <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-control bg-surface text-muted">
                            {g.id === 'recent' ? <Clock className="h-4 w-4" /> : Icon ? <Icon className="h-4 w-4" /> : null}
                          </span>
                        )}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-body">{item.label}</span>
                          {item.subtitle && <span className="block truncate text-caption text-muted">{item.subtitle}</span>}
                        </span>
                        {item.kind === 'agent' && (
                          <span className="flex shrink-0 items-center gap-1">
                            {isActive && (
                              <span className="hidden items-center gap-0.5 text-micro text-subtle sm:inline-flex" aria-hidden="true">
                                <Kbd>{MOD_KEY}</Kbd>
                                <Kbd>↵</Kbd>
                                <span className="ml-1">comms</span>
                              </span>
                            )}
                            <IconButton
                              icon={Radio}
                              label={`Open comms with ${item.label}`}
                              size="sm"
                              tabIndex={-1}
                              onClick={(e) => {
                                e.stopPropagation();
                                select(item, true);
                              }}
                            />
                          </span>
                        )}
                        {isActive && item.kind !== 'agent' && <CornerDownLeft aria-hidden="true" className="h-4 w-4 shrink-0 text-subtle" />}
                      </div>
                    );
                  })}
                  {g.id === 'agents' && agentState === 'loading' && (
                    <div className="px-3 py-2 text-caption text-muted" role="status">
                      Loading agents…
                    </div>
                  )}
                  {g.id === 'agents' && agentState === 'error' && (
                    <div className="flex items-center gap-2 px-3 py-2 text-caption text-muted" role="status">
                      <AlertCircle aria-hidden="true" className="h-3.5 w-3.5 text-warn" />
                      Agents couldn’t be loaded right now — pages and actions still work.
                    </div>
                  )}
                  {g.id === 'agents' && agentState === 'ready' && g.items.length === 0 && !query.trim() && (
                    <div className="px-3 py-2 text-caption text-muted">No agents yet — “Build an agent” is one action up.</div>
                  )}
                </div>
              ))}
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-4 py-2 text-caption text-muted">
              <span className="inline-flex items-center gap-1">
                <Kbd>↑</Kbd>
                <Kbd>↓</Kbd> navigate
              </span>
              <span className="inline-flex items-center gap-1">
                <Kbd>↵</Kbd> open
              </span>
              <span className="inline-flex items-center gap-1">
                <Kbd>esc</Kbd> close
              </span>
              <span className="ml-auto inline-flex items-center gap-1">
                <Kbd>?</Kbd> shortcuts
              </span>
            </div>
          </div>
        </div>
      )}
      <ShortcutsSheet isOpen={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />
    </>
  );
}
