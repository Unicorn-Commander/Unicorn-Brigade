import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
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
  Menu,
  X as CloseIcon,
  Sparkles
} from 'lucide-react';
import { Tooltip } from 'react-tooltip';
import UserProfile from './auth/UserProfile';
import { BrigadeLogo } from './UnicornBrigadeLogo';
import { apiJson } from '../services/http';

const HEALTH_POLL_MS = 30000;

const Navigation = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [collapsedSections, setCollapsedSections] = useState(() => {
    const saved = localStorage.getItem('nav-collapsed-sections');
    return saved ? JSON.parse(saved) : {};
  });
  // 'online' | 'degraded' | 'offline' | 'checking' — drives the footer card.
  const [platformStatus, setPlatformStatus] = useState('checking');
  const [deployConfig, setDeployConfig] = useState(null);
  const location = useLocation();

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    localStorage.setItem('nav-collapsed-sections', JSON.stringify(collapsedSections));
  }, [collapsedSections]);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const health = await apiJson('/health', { redirectOn401: false });
        if (cancelled) return;
        const status = (health?.status || '').toLowerCase();
        setPlatformStatus(status === 'healthy' || status === 'operational' ? 'online' : 'degraded');
      } catch {
        if (!cancelled) setPlatformStatus('offline');
      }
    };
    check();
    const interval = setInterval(check, HEALTH_POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiJson('/auth/config', { redirectOn401: false })
      .then((cfg) => {
        if (!cancelled) setDeployConfig(cfg);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const toggleSection = (section) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const TOOLTIP_CONTENT = {
    '/dashboard': 'View system overview, recent activity, and quick stats',
    '/chat': 'Start a conversation with any agent',
    '/conversations': 'Browse and manage all conversation history',
    '/command': "The General's War Room — the whole Brigade as a clickable org chart",
    '/orchestration': 'Real-time agent orchestration and command center',
    '/workflows': 'Execute and monitor hierarchical workflow templates',
    '/ralph-monitor': 'Self-correcting workflow executions with automatic retry',
    '/knowledge': 'Explore the AI-native knowledge graph (FalkorDB)',
    '/library': 'Manage and configure all production agents',
    '/tools': 'Browse available tools and their capabilities',
    '/mcp-servers': 'Manage MCP servers and test tool integrations',
    '/mcp-docs': 'Learn about Model Context Protocol integration',
    '/langflow': 'Visual workflow builder for complex automations',
    '/docs': 'Explore API documentation and interactive testing',
    '/code-attribution': 'Track AI-generated code attribution and lineage',
    '/monitoring': 'System health, performance metrics, and logs',
    '/scheduled-runs': 'Cron-based agent invocations that survive container restarts',
    '/settings': 'Configure platform settings and preferences',
  };

  const navLinkClass = ({ isActive }) =>
    `flex items-center space-x-3 px-4 py-3 min-h-[44px] rounded-lg transition-all duration-200 ${
      isActive
        ? 'bg-purple-500/20 text-purple-400 border-l-2 border-purple-500'
        : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
    }`;

  const NavSection = ({ title, icon: Icon, isCollapsed, onToggle, children }) => (
    <div className="mt-6">
      <button
        onClick={onToggle}
        className="flex items-center justify-between w-full px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider hover:text-slate-300 transition-colors group"
      >
        <div className="flex items-center space-x-2">
          {Icon && <Icon className="w-4 h-4" />}
          <span>{title}</span>
        </div>
        <ChevronDown
          className={`w-4 h-4 transition-transform duration-200 ${
            isCollapsed ? '-rotate-90' : 'rotate-0'
          }`}
        />
      </button>
      <div
        className={`overflow-hidden transition-all duration-200 ${
          isCollapsed ? 'max-h-0' : 'max-h-[500px]'
        }`}
      >
        <div className="mt-2 space-y-1">
          {children}
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button
        onClick={() => setIsMobileMenuOpen((prev) => !prev)}
        className="lg:hidden fixed top-4 left-4 z-50 p-3 bg-slate-800/90 backdrop-blur-xl border border-slate-700/50 rounded-lg shadow-xl hover:bg-slate-700/90 transition-colors"
        aria-label="Toggle navigation menu"
      >
        {isMobileMenuOpen ? (
          <CloseIcon className="w-6 h-6 text-white" />
        ) : (
          <Menu className="w-6 h-6 text-white" />
        )}
      </button>

      {isMobileMenuOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside
        className={`fixed left-0 top-0 h-screen w-64 bg-slate-900/50 backdrop-blur-xl border-r border-slate-700/50 transition-transform duration-300 ease-in-out z-40 ${
          isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0`}
      >
        <div className="flex flex-col h-full">
        {/* Logo */}
        <div className="p-6 border-b border-slate-800/50">
          <div className="flex items-center space-x-3">
            <BrigadeLogo size={44} />
            <div>
              <h1 className="text-lg font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                Unicorn Brigade
              </h1>
              <p className="text-xs text-slate-500">Agent Infrastructure</p>
            </div>
          </div>
          {import.meta.env.DEV && (
            <div className="mt-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg px-3 py-2 text-xs text-yellow-200">
              ⚠️ Development Mode: Authentication Bypassed
            </div>
          )}
        </div>

        {/* Navigation Items */}
        <div className="flex-1 p-4 overflow-y-auto">
          <NavSection
            title="Main"
            icon={Home}
            isCollapsed={collapsedSections.main}
            onToggle={() => toggleSection('main')}
          >
            <NavLink
              to="/dashboard"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/dashboard']}
              data-tooltip-place="right"
            >
              <Home className="w-4 h-4" />
              <span className="text-sm font-medium">Dashboard</span>
            </NavLink>
            <NavLink
              to="/chat"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/chat']}
              data-tooltip-place="right"
            >
              <MessageSquare className="w-4 h-4" />
              <span className="text-sm font-medium">Chat</span>
            </NavLink>
            <NavLink
              to="/conversations"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/conversations']}
              data-tooltip-place="right"
            >
              <MessagesSquare className="w-4 h-4" />
              <span className="text-sm font-medium">Conversations</span>
            </NavLink>
          </NavSection>

          <NavSection
            title="Command"
            icon={Globe}
            isCollapsed={collapsedSections.command}
            onToggle={() => toggleSection('command')}
          >
            <NavLink
              to="/command"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/command']}
              data-tooltip-place="right"
            >
              <Shield className="w-4 h-4" />
              <span className="text-sm font-medium">Command Center</span>
            </NavLink>
            <NavLink
              to="/orchestration"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/orchestration']}
              data-tooltip-place="right"
            >
              <Globe className="w-4 h-4" />
              <span className="text-sm font-medium">Orchestration</span>
            </NavLink>
            <NavLink
              to="/workflows"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/workflows']}
              data-tooltip-place="right"
            >
              <GitBranch className="w-4 h-4" />
              <span className="text-sm font-medium">Workflows</span>
            </NavLink>
            <NavLink
              to="/ralph-monitor"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/ralph-monitor']}
              data-tooltip-place="right"
            >
              <Zap className="w-4 h-4" />
              <span className="text-sm font-medium">Self-Correction</span>
            </NavLink>
            <NavLink
              to="/knowledge"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/knowledge']}
              data-tooltip-place="right"
            >
              <Network className="w-4 h-4" />
              <span className="text-sm font-medium">Knowledge Graph</span>
            </NavLink>
          </NavSection>

          <NavSection
            title="Agents"
            icon={Bot}
            isCollapsed={collapsedSections.agents}
            onToggle={() => toggleSection('agents')}
          >
            <NavLink
              to="/library"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/library']}
              data-tooltip-place="right"
            >
              <BookOpen className="w-4 h-4" />
              <span className="text-sm font-medium">Agent Library</span>
            </NavLink>
            <NavLink
              to="/builder-chat"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content="Build new agents through conversation with Gunny"
              data-tooltip-place="right"
            >
              <Sparkles className="w-4 h-4" />
              <span className="text-sm font-medium">Agent Builder</span>
            </NavLink>
          </NavSection>

          <NavSection
            title="Tools"
            icon={Wrench}
            isCollapsed={collapsedSections.tools}
            onToggle={() => toggleSection('tools')}
          >
            <NavLink
              to="/tools"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/tools']}
              data-tooltip-place="right"
            >
              <Wrench className="w-4 h-4" />
              <span className="text-sm font-medium">Tool Library</span>
            </NavLink>
            <NavLink
              to="/mcp-servers"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/mcp-servers']}
              data-tooltip-place="right"
            >
              <Server className="w-4 h-4" />
              <span className="text-sm font-medium">MCP Servers</span>
            </NavLink>
            <NavLink
              to="/mcp-docs"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/mcp-docs']}
              data-tooltip-place="right"
            >
              <FileText className="w-4 h-4" />
              <span className="text-sm font-medium">MCP Docs</span>
            </NavLink>
            {deployConfig?.langflow_enabled && (
              <NavLink
                to="/langflow"
                className={navLinkClass}
                data-tooltip-id="nav-tooltip"
                data-tooltip-content={TOOLTIP_CONTENT['/langflow']}
                data-tooltip-place="right"
              >
                <Workflow className="w-4 h-4" />
                <span className="text-sm font-medium">Langflow Flows</span>
              </NavLink>
            )}
            <NavLink
              to="/docs"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/docs']}
              data-tooltip-place="right"
            >
              <Book className="w-4 h-4" />
              <span className="text-sm font-medium">API Docs</span>
            </NavLink>
          </NavSection>

          <NavSection
            title="System"
            icon={Settings}
            isCollapsed={collapsedSections.system}
            onToggle={() => toggleSection('system')}
          >
            <NavLink
              to="/code-attribution"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/code-attribution']}
              data-tooltip-place="right"
            >
              <FileCode className="w-4 h-4" />
              <span className="text-sm font-medium">Code Attribution</span>
            </NavLink>
            <NavLink
              to="/monitoring"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/monitoring']}
              data-tooltip-place="right"
            >
              <Activity className="w-4 h-4" />
              <span className="text-sm font-medium">Monitoring</span>
            </NavLink>
            <NavLink
              to="/scheduled-runs"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/scheduled-runs']}
              data-tooltip-place="right"
            >
              <CalendarClock className="w-4 h-4" />
              <span className="text-sm font-medium">Scheduled Runs</span>
            </NavLink>
            <NavLink
              to="/settings"
              className={navLinkClass}
              data-tooltip-id="nav-tooltip"
              data-tooltip-content={TOOLTIP_CONTENT['/settings']}
              data-tooltip-place="right"
            >
              <Settings className="w-4 h-4" />
              <span className="text-sm font-medium">Settings</span>
            </NavLink>
          </NavSection>
        </div>

        {/* User Profile */}
        <div className="p-4 border-t border-slate-800/50">
          <UserProfile />
        </div>

        <div className="px-4 pb-4">
          <button
            onClick={() => {
              localStorage.removeItem('wizard-completed');
              window.location.reload();
            }}
            className="w-full px-3 py-2 text-sm text-slate-400 hover:text-white transition-colors rounded-lg hover:bg-slate-800/50"
          >
            🎓 Getting Started Guide
          </button>
        </div>

        {/* Status — live, polled from /api/v1/health every 30s */}
        <div className="px-4 pb-4">
          {(() => {
            const statusStyles = {
              online: {
                card: 'bg-emerald-500/10 border-emerald-500/30',
                dot: 'bg-emerald-500 animate-pulse',
                text: 'text-emerald-400',
                label: 'Platform Online',
                detail: 'All systems operational',
              },
              degraded: {
                card: 'bg-amber-500/10 border-amber-500/30',
                dot: 'bg-amber-500 animate-pulse',
                text: 'text-amber-400',
                label: 'Degraded',
                detail: 'Some services unhealthy',
              },
              offline: {
                card: 'bg-red-500/10 border-red-500/30',
                dot: 'bg-red-500',
                text: 'text-red-400',
                label: 'API Unreachable',
                detail: 'Backend is not responding',
              },
              checking: {
                card: 'bg-slate-500/10 border-slate-600/30',
                dot: 'bg-slate-400 animate-pulse',
                text: 'text-slate-300',
                label: 'Checking…',
                detail: 'Contacting platform',
              },
            };
            const s = statusStyles[platformStatus] || statusStyles.checking;
            return (
              <div className={`card ${s.card}`}>
                <div className="flex items-center space-x-3">
                  <div className={`w-2 h-2 rounded-full ${s.dot}`}></div>
                  <div>
                    <p className={`text-sm font-medium ${s.text}`}>{s.label}</p>
                    <p className="text-xs text-slate-500">{s.detail}</p>
                  </div>
                </div>
              </div>
            );
          })()}
        </div>

        <Tooltip
          id="nav-tooltip"
          place="right"
          offset={10}
          className="z-50 max-w-xs"
          style={{
            backgroundColor: 'rgba(30, 41, 59, 0.95)',
            color: '#e2e8f0',
            borderRadius: '0.5rem',
            padding: '0.5rem 0.75rem',
            fontSize: '0.875rem',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(100, 116, 139, 0.3)',
          }}
        />
        </div>
      </aside>
    </>
  );
};

export default Navigation;
