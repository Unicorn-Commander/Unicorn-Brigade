import { NavLink } from 'react-router-dom';
import {
  Home,
  BookOpen,
  Sparkles,
  Wrench,
  Book,
  Activity,
  Settings
} from 'lucide-react';

const Navigation = () => {
  const navItems = [
    { path: '/', icon: Home, label: 'Dashboard' },
    { path: '/library', icon: BookOpen, label: 'Agent Library' },
    { path: '/builder-chat', icon: Sparkles, label: 'Build Agent' },
    { path: '/tools', icon: Wrench, label: 'Tool Library' },
    { path: '/docs', icon: Book, label: 'API Docs' },
    { path: '/monitoring', icon: Activity, label: 'Monitoring' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <nav className="fixed left-0 top-0 h-full w-64 glass border-r border-slate-800/50">
      <div className="flex flex-col h-full">
        {/* Logo */}
        <div className="p-6 border-b border-slate-800/50">
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 rounded-lg overflow-hidden flex-shrink-0">
              <img
                src="/The_General_Logo.png"
                alt="The General - Unicorn Brigade"
                className="w-full h-full object-cover"
              />
            </div>
            <div>
              <h1 className="text-lg font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                Unicorn Brigade
              </h1>
              <p className="text-xs text-slate-500">Agent Infrastructure</p>
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <div className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`
              }
            >
              <item.icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </NavLink>
          ))}
        </div>

        {/* Status */}
        <div className="p-4 border-t border-slate-800/50">
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