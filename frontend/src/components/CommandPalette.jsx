import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Home,
  MessageSquare,
  BookOpen,
  Wrench,
  Activity,
  Settings,
  Bot,
  ArrowRight,
  Command
} from 'lucide-react';
import { apiJson } from '../services/http';

const PAGES = [
  { id: 'dashboard', name: 'Dashboard', icon: Home, path: '/dashboard', type: 'page' },
  { id: 'chat', name: 'Chat', icon: MessageSquare, path: '/chat', type: 'page' },
  { id: 'library', name: 'Agent Library', icon: BookOpen, path: '/library', type: 'page' },
  { id: 'tools', name: 'Tool Library', icon: Wrench, path: '/tools', type: 'page' },
  { id: 'monitoring', name: 'Monitoring', icon: Activity, path: '/monitoring', type: 'page' },
  { id: 'settings', name: 'Settings', icon: Settings, path: '/settings', type: 'page' },
];

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [agents, setAgents] = useState([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef(null);
  const navigate = useNavigate();

  // Load agents once. The palette stays usable (pages still searchable) if the
  // roster fails to load — but don't swallow the failure silently.
  useEffect(() => {
    apiJson('/agents')
      .then(data => setAgents(data?.agents || []))
      .catch(err => {
        console.warn('CommandPalette: failed to load agents', err);
      });
  }, []);

  // Keyboard shortcut
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen(prev => !prev);
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Build results
  const getResults = useCallback(() => {
    const q = query.toLowerCase().trim();

    const pageResults = PAGES.filter(p =>
      !q || p.name.toLowerCase().includes(q)
    ).map(p => ({ ...p, category: 'Pages' }));

    const agentResults = agents
      .filter(a => !q || (a.displayName || a.name).toLowerCase().includes(q) || a.domain?.toLowerCase().includes(q))
      .slice(0, 8)
      .map(a => ({
        id: a.id,
        name: a.displayName || a.name,
        icon: null,
        emoji: a.avatar || '🦄',
        path: `/agent/${a.id}`,
        type: 'agent',
        subtitle: a.domain,
        category: 'Agents'
      }));

    return [...pageResults, ...agentResults];
  }, [query, agents]);

  const results = getResults();

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleSelect = (item) => {
    setIsOpen(false);
    navigate(item.path);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      handleSelect(results[selectedIndex]);
    }
  };

  // Group results by category
  const grouped = results.reduce((acc, item) => {
    if (!acc[item.category]) acc[item.category] = [];
    acc[item.category].push(item);
    return acc;
  }, {});

  let flatIndex = 0;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={() => setIsOpen(false)}
          />

          {/* Palette */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.15 }}
            className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-lg z-50"
          >
            <div className="bg-slate-800 border border-slate-700/50 rounded-xl shadow-2xl shadow-black/50 overflow-hidden">
              {/* Search Input */}
              <div className="flex items-center px-4 border-b border-slate-700/50">
                <Search className="w-5 h-5 text-slate-400 flex-shrink-0" />
                <input
                  ref={inputRef}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Search pages, agents..."
                  aria-label="Search pages and agents"
                  className="flex-1 bg-transparent px-3 py-4 text-sm text-white placeholder-slate-500 focus:outline-none"
                />
                <kbd className="hidden sm:flex items-center px-1.5 py-0.5 rounded bg-slate-700 text-[10px] text-slate-400 font-mono">
                  ESC
                </kbd>
              </div>

              {/* Results */}
              <div className="max-h-80 overflow-y-auto py-2">
                {results.length === 0 ? (
                  <div className="px-4 py-8 text-center text-sm text-slate-400">
                    No results found
                  </div>
                ) : (
                  Object.entries(grouped).map(([category, items]) => (
                    <div key={category}>
                      <p className="px-4 pt-2 pb-1 text-[10px] font-semibold tracking-widest text-slate-600 uppercase">
                        {category}
                      </p>
                      {items.map((item) => {
                        const idx = flatIndex++;
                        return (
                          <button
                            key={item.id}
                            onClick={() => handleSelect(item)}
                            onMouseEnter={() => setSelectedIndex(idx)}
                            className={`w-full flex items-center space-x-3 px-4 py-2.5 text-left transition-colors ${
                              selectedIndex === idx
                                ? 'bg-unicorn-500/15 text-white'
                                : 'text-slate-300 hover:bg-slate-700/50'
                            }`}
                          >
                            {item.icon ? (
                              <item.icon className="w-4 h-4 text-slate-400 flex-shrink-0" />
                            ) : (
                              <span className="text-lg flex-shrink-0">{item.emoji}</span>
                            )}
                            <div className="flex-1 min-w-0">
                              <span className="text-sm font-medium truncate block">{item.name}</span>
                              {item.subtitle && (
                                <span className="text-xs text-slate-400">{item.subtitle}</span>
                              )}
                            </div>
                            {selectedIndex === idx && (
                              <ArrowRight className="w-4 h-4 text-unicorn-400 flex-shrink-0" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  ))
                )}
              </div>

              {/* Footer hint */}
              <div className="px-4 py-2 border-t border-slate-700/50 flex items-center space-x-4 text-[10px] text-slate-600">
                <span className="flex items-center space-x-1">
                  <kbd className="px-1 py-0.5 bg-slate-700 rounded font-mono">↑↓</kbd>
                  <span>Navigate</span>
                </span>
                <span className="flex items-center space-x-1">
                  <kbd className="px-1 py-0.5 bg-slate-700 rounded font-mono">↵</kbd>
                  <span>Open</span>
                </span>
                <span className="flex items-center space-x-1">
                  <kbd className="px-1 py-0.5 bg-slate-700 rounded font-mono">esc</kbd>
                  <span>Close</span>
                </span>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
