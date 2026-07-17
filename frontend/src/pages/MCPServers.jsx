import { useState, useEffect, useMemo } from 'react';
import { Search, Server, RefreshCw, CheckCircle, X, Package } from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import api from '../services/api';
import MCPServerCard from '../components/MCPServerCard';
import MCPToolList from '../components/MCPToolList';
import MCPServerControlPanel from '../components/MCPServerControlPanel';
import Breadcrumbs from '../components/Breadcrumbs';
import CardSkeleton from '../components/skeletons/CardSkeleton';

const MCPServers = () => {
  const [servers, setServers] = useState([]);
  const [filteredServers, setFilteredServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [serverStates, setServerStates] = useState({});
  const [controlServer, setControlServer] = useState(null);
  const [healthPolling, setHealthPolling] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid or list

  // Tool view
  const [selectedServer, setSelectedServer] = useState(null);
  const [serverTools, setServerTools] = useState([]);

  useEffect(() => {
    loadServers();
  }, []);

  useEffect(() => {
    if (!healthPolling) return;

    const pollHealth = async () => {
      try {
        const running = await api.getRunningMCPServers();
        const runningServers = running.servers || running.running_servers || [];
        const states = {};
        runningServers.forEach((server) => {
          if (server.name) {
            states[server.name] = 'running';
          }
        });
        setServerStates(states);
      } catch (error) {
        console.error('Failed to fetch MCP health:', error);
      }
    };

    pollHealth();
    const interval = setInterval(pollHealth, 10000);
    return () => clearInterval(interval);
  }, [healthPolling]);

  useEffect(() => {
    applyFilters();
  }, [servers, searchQuery, selectedCategory, selectedStatus, serverStates]);

  const loadServers = async () => {
    setLoading(true);
    try {
      const [response] = await Promise.all([
        api.getMCPServers(),
        new Promise(resolve => setTimeout(resolve, 300)),
      ]);
      setServers(response.servers || []);
    } catch (error) {
      console.error('Failed to load MCP servers:', error);
      toast.error('Failed to load MCP servers');
    } finally {
      setLoading(false);
    }
  };

  const refreshServers = async () => {
    setRefreshing(true);
    try {
      await loadServers();
      notify.success('Servers refreshed');
    } catch (error) {
      toast.error('Failed to refresh servers');
    } finally {
      setRefreshing(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...servers];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(server =>
        server.name?.toLowerCase().includes(query) ||
        server.display_name?.toLowerCase().includes(query) ||
        server.description?.toLowerCase().includes(query) ||
        server.category?.toLowerCase().includes(query)
      );
    }

    // Category filter
    if (selectedCategory) {
      filtered = filtered.filter(server => server.category === selectedCategory);
    }

    // Status filter
    if (selectedStatus) {
      filtered = filtered.filter(server => {
        const status = serverStates[server.name] || (server.running ? 'running' : 'stopped');
        return status === selectedStatus;
      });
    }

    setFilteredServers(filtered);
  };

  const handleStartServer = async (serverName) => {
    try {
      await api.startMCPServer(serverName);
      await loadServers(); // Reload to get updated status
    } catch (error) {
      throw error;
    }
  };

  const handleStopServer = async (serverName) => {
    try {
      await api.stopMCPServer(serverName);
      await loadServers(); // Reload to get updated status
    } catch (error) {
      throw error;
    }
  };

  const handleViewTools = async (server) => {
    setSelectedServer(server);
    // Load tools for this server
    try {
      const response = await api.getMCPServerDetails(server.name);
      const capabilities = response.capabilities || [];
      setServerTools(capabilities.map((name) => ({ name })));
    } catch (error) {
      console.error('Failed to load server tools:', error);
      toast.error('Failed to load server tools');
      setServerTools([]);
    }
  };

  // Extract unique categories (registry entries may not have one)
  const categories = useMemo(() => {
    const cats = new Set();
    servers.forEach(s => s.category && cats.add(s.category));
    return Array.from(cats).sort();
  }, [servers]);

  // Group servers by category (only used when the registry provides categories)
  const groupedServers = useMemo(() => {
    const grouped = {};
    filteredServers.forEach(server => {
      const category = server.category || 'Uncategorized';
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(server);
    });
    return grouped;
  }, [filteredServers]);

  // Stats — tool counts are declared capabilities, not runtime-discovered tools
  const stats = useMemo(() => {
    const running = servers.filter(
      s => (serverStates[s.name] || (s.running ? 'running' : 'stopped')) === 'running'
    ).length;
    const total = servers.length;
    const declaredTools = servers.reduce((sum, s) => sum + (s.capabilities?.length || 0), 0);
    return { running, total, declaredTools };
  }, [servers, serverStates]);

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gradient">MCP Servers</h1>
            <p className="text-slate-400 mt-1">
              {stats.running} running • {stats.total} total servers • {stats.declaredTools} declared tools
            </p>
          </div>

          <button
            onClick={refreshServers}
            disabled={refreshing}
            className="btn-primary flex items-center space-x-2"
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="card border-emerald-500/20 bg-emerald-500/5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Running Servers</p>
                <p className="text-2xl font-bold text-emerald-400">{stats.running}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-emerald-400" />
            </div>
          </div>

          <div className="card border-unicorn-500/20 bg-unicorn-500/5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Total Servers</p>
                <p className="text-2xl font-bold text-unicorn-400">{stats.total}</p>
              </div>
              <Server className="w-8 h-8 text-unicorn-400" />
            </div>
          </div>

          <div className="card border-cyan-500/20 bg-cyan-500/5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Declared Tools</p>
                <p className="text-2xl font-bold text-cyan-400">{stats.declaredTools}</p>
              </div>
              <Package className="w-8 h-8 text-cyan-400" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="card">
          <div className={`grid grid-cols-1 gap-4 ${categories.length > 0 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
            {/* Search */}
            <div className="relative md:col-span-1">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search servers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white placeholder-slate-500"
              />
            </div>

            {/* Category Filter (only when the registry provides categories) */}
            {categories.length > 0 && (
              <select
                aria-label="Filter by category"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
              >
                <option value="">All Categories</option>
                {categories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            )}

            {/* Status Filter */}
            <select
              aria-label="Filter by status"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
            >
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
            </select>
          </div>

          {/* Active Filters Display */}
          {(searchQuery || selectedCategory || selectedStatus) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-400">Active filters:</span>
              {searchQuery && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-unicorn-500/20 text-unicorn-400 text-xs">
                  Search: {searchQuery}
                  <button onClick={() => setSearchQuery('')} aria-label="Clear search filter" className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedCategory && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs">
                  Category: {selectedCategory}
                  <button onClick={() => setSelectedCategory('')} aria-label="Clear category filter" className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedStatus && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                  Status: {selectedStatus}
                  <button onClick={() => setSelectedStatus('')} aria-label="Clear status filter" className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCategory('');
                  setSelectedStatus('');
                }}
                className="text-xs text-slate-400 hover:text-white underline"
              >
                Clear all
              </button>
            </div>
          )}
        </div>

        {/* Loading State */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <CardSkeleton count={6} />
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredServers.length === 0 && (
          <div className="text-center py-12">
            <Server className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">No servers found</h3>
            <p className="text-slate-400">Try adjusting your filters</p>
          </div>
        )}

        {/* Servers — grouped by category when the registry provides one, flat grid otherwise */}
        {!loading && categories.length > 0 && Object.keys(groupedServers).map(category => {
          const categoryServers = groupedServers[category];

          return (
            <div key={category} className="space-y-4">
              {/* Category Header */}
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-xl font-bold text-white">{category}</h2>
                  <p className="text-sm text-slate-400">{categoryServers.length} servers</p>
                </div>
              </div>

              {/* Servers Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {categoryServers.map(server => (
                  <MCPServerCard
                    key={server.name}
                    server={server}
                    onStart={handleStartServer}
                    onStop={handleStopServer}
                    onViewTools={handleViewTools}
                    onManage={() => setControlServer(server)}
                    isLoading={loading}
                    statusOverride={serverStates[server.name]}
                  />
                ))}
              </div>
            </div>
          );
        })}

        {!loading && categories.length === 0 && filteredServers.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredServers.map(server => (
              <MCPServerCard
                key={server.name}
                server={server}
                onStart={handleStartServer}
                onStop={handleStopServer}
                onViewTools={handleViewTools}
                onManage={() => setControlServer(server)}
                isLoading={loading}
                statusOverride={serverStates[server.name]}
              />
            ))}
          </div>
        )}

        {/* Tool List Modal */}
        {selectedServer && (
          <MCPToolList
            server={selectedServer}
            tools={serverTools}
            onClose={() => {
              setSelectedServer(null);
              setServerTools([]);
            }}
          />
        )}

        {controlServer && (
          <MCPServerControlPanel
            server={controlServer}
            onClose={() => setControlServer(null)}
            onServerUpdated={(updated) => {
              setServers(prev =>
                prev.map(s => (s.name === updated.name ? { ...s, ...updated } : s))
              );
            }}
          />
        )}
      </div>
    </div>
  );
};

export default MCPServers;
