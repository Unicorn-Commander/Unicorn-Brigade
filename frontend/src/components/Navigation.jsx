import { NavLink } from 'react-router-dom';
import {
  Home,
  BookOpen,
  Sparkles,
  Wrench,
  Book,
  Activity,
  Settings,
  MessageSquare,
  MessagesSquare,
  Globe,
  Workflow,
  Network,
  GitBranch,
  Server,
  FileText,
  Zap,
  FileCode
} from 'lucide-react';
import UserProfile from './auth/UserProfile';
import { BrigadeLogo } from './UnicornBrigadeLogo';

const Navigation = () => {
  const navItems = [
    { path: '/dashboard', icon: Home, label: 'Dashboard', section: 'MAIN' },
    { path: '/chat', icon: MessageSquare, label: 'Chat', section: 'MAIN' },
    { path: '/conversations', icon: MessagesSquare, label: 'Conversations', section: 'MAIN' },
    { path: '/orchestration', icon: Globe, label: 'Orchestration', section: 'COMMAND' },
    { path: '/workflows', icon: GitBranch, label: 'Workflows', section: 'COMMAND' },
    { path: '/ralph-monitor', icon: Zap, label: 'Ralph Monitor', section: 'COMMAND' },
    { path: '/knowledge', icon: Network, label: 'Knowledge Graph', section: 'COMMAND' },
    { path: '/library', icon: BookOpen, label: 'Agent Library', section: 'AGENTS' },
    { path: '/tools', icon: Wrench, label: 'Tool Library', section: 'TOOLS' },
    { path: '/mcp-servers', icon: Server, label: 'MCP Servers', section: 'TOOLS' },
    { path: '/mcp-docs', icon: FileText, label: 'MCP Docs', section: 'TOOLS' },
    { path: '/langflow', icon: Workflow, label: 'Langflow Flows', section: 'TOOLS' },
    { path: '/docs', icon: Book, label: 'API Docs', section: 'TOOLS' },
    { path: '/code-attribution', icon: FileCode, label: 'Code Attribution', section: 'SYSTEM' },
    { path: '/monitoring', icon: Activity, label: 'Monitoring', section: 'SYSTEM' },
    { path: '/settings', icon: Settings, label: 'Settings', section: 'SYSTEM' },
  ];

  const sections = ['MAIN', 'COMMAND', 'AGENTS', 'TOOLS', 'SYSTEM'];

  return (
    <nav className="fixed left-0 top-0 h-full w-64 glass border-r border-slate-800/50">
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
        </div>

        {/* Navigation Items */}
        <div className="flex-1 p-4 space-y-1 overflow-y-auto">
          {sections.map((section) => (
            <div key={section}>
              <p className="px-4 pt-4 pb-1 text-[10px] font-semibold tracking-widest text-slate-600 uppercase">
                {section}
              </p>
              {navItems
                .filter((item) => item.section === section)
                .map((item) => (
                  <NavLink
                    key={item.path + item.label}
                    to={item.path}
                    className={({ isActive }) =>
                      `flex items-center space-x-3 px-4 py-2.5 rounded-lg transition-all duration-200 ${
                        isActive
                          ? 'bg-purple-500/20 text-purple-400 border-l-2 border-purple-500'
                          : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                      }`
                    }
                  >
                    <item.icon className="w-4 h-4" />
                    <span className="text-sm font-medium">{item.label}</span>
                  </NavLink>
                ))}
            </div>
          ))}
        </div>

        {/* User Profile */}
        <div className="p-4 border-t border-slate-800/50">
          <UserProfile />
        </div>

        {/* Status */}
        <div className="px-4 pb-4">
          <div className="card bg-emerald-500/10 border-emerald-500/30">
            <div className="flex items-center space-x-3">
              <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
              <div>
                <p className="text-sm font-medium text-emerald-400">Platform Online</p>
                <p className="text-xs text-slate-500">All systems operational</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navigation;