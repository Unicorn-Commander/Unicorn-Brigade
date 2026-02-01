import { useState, useEffect, useMemo } from 'react';
import { Search, Filter, Server, RefreshCw, AlertCircle, CheckCircle, X, Package } from 'lucide-react';
import { toast } from 'react-hot-toast';
import mcpService from '../services/mcpService';
import MCPServerCard from '../components/MCPServerCard';
import MCPToolList from '../components/MCPToolList';

const MCPServers = () => {
  const [servers, setServers] = useState([]);
  const [filteredServers, setFilteredServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedPhase, setSelectedPhase] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid or list

  // Tool view
  const [selectedServer, setSelectedServer] = useState(null);
  const [serverTools, setServerTools] = useState([]);

  useEffect(() => {
    loadServers();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [servers, searchQuery, selectedCategory, selectedPhase, selectedStatus]);

  const loadServers = async () => {
    setLoading(true);
    try {
      const response = await mcpService.listServers();
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
      toast.success('Servers refreshed');
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

    // Phase filter
    if (selectedPhase) {
      filtered = filtered.filter(server => server.phase === selectedPhase);
    }

    // Status filter
    if (selectedStatus) {
      filtered = filtered.filter(server => server.status === selectedStatus);
    }

    setFilteredServers(filtered);
  };

  const handleStartServer = async (serverName) => {
    try {
      await mcpService.startServer(serverName);
      await loadServers(); // Reload to get updated status
    } catch (error) {
      throw error;
    }
  };

  const handleStopServer = async (serverName) => {
    try {
      await mcpService.stopServer(serverName);
      await loadServers(); // Reload to get updated status
    } catch (error) {
      throw error;
    }
  };

  const handleViewTools = async (server) => {
    setSelectedServer(server);
    // Load tools for this server
    try {
      const response = await mcpService.getServer(server.name);
      setServerTools(response.tools || []);
    } catch (error) {
      console.error('Failed to load server tools:', error);
      toast.error('Failed to load server tools');
      setServerTools([]);
    }
  };

  // Extract unique categories and phases
  const categories = useMemo(() => {
    const cats = new Set();
    servers.forEach(s => s.category && cats.add(s.category));
    return Array.from(cats).sort();
  }, [servers]);

  const phases = useMemo(() => {
    const p = new Set();
    servers.forEach(s => s.phase && p.add(s.phase));
    return Array.from(p).sort();
  }, [servers]);

  // Group servers by category
  const groupedServers = useMemo(() => {
    const grouped = {};
    filteredServers.forEach(server => {
      const category = server.category || 'Other';
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(server);
    });
    return grouped;
  }, [filteredServers]);

  // Stats
  const stats = useMemo(() => {
    const running = servers.filter(s => s.status === 'running').length;
    const total = servers.length;
    const totalTools = servers.reduce((sum, s) => sum + (s.tool_count || 0), 0);
    return { running, total, totalTools };
  }, [servers]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gradient">MCP Servers</h1>
            <p className="text-slate-400 mt-1">
              {stats.running} running • {stats.total} total servers • {stats.totalTools} tools
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

          <div className="card border-purple-500/20 bg-purple-500/5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Total Servers</p>
                <p className="text-2xl font-bold text-purple-400">{stats.total}</p>
              </div>
              <Server className="w-8 h-8 text-purple-400" />
            </div>
          </div>

          <div className="card border-cyan-500/20 bg-cyan-500/5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-400">Available Tools</p>
                <p className="text-2xl font-bold text-cyan-400">{stats.totalTools}</p>
              </div>
              <Package className="w-8 h-8 text-cyan-400" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="card">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="relative md:col-span-1">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search servers..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white placeholder-slate-500"
              />
            </div>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white"
            >
              <option value="">All Categories</option>
              {categories.map(cat => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>

            {/* Phase Filter */}
            <select
              value={selectedPhase}
              onChange={(e) => setSelectedPhase(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white"
            >
              <option value="">All Phases</option>
              {phases.map(phase => (
                <option key={phase} value={phase}>Phase {phase}</option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white"
            >
              <option value="">All Status</option>
              <option value="running">Running</option>
              <option value="stopped">Stopped</option>
            </select>
          </div>

          {/* Active Filters Display */}
          {(searchQuery || selectedCategory || selectedPhase || selectedStatus) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-500">Active filters:</span>
              {searchQuery && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-purple-500/20 text-purple-400 text-xs">
                  Search: {searchQuery}
                  <button onClick={() => setSearchQuery('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedCategory && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs">
                  Category: {selectedCategory}
                  <button onClick={() => setSelectedCategory('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedPhase && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-cyan-500/20 text-cyan-400 text-xs">
                  Phase: {selectedPhase}
                  <button onClick={() => setSelectedPhase('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedStatus && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
                  Status: {selectedStatus}
                  <button onClick={() => setSelectedStatus('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCategory('');
                  setSelectedPhase('');
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
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
            <p className="text-slate-400 mt-4">Loading MCP servers...</p>
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

        {/* Servers Grouped by Category */}
        {!loading && Object.keys(groupedServers).map(category => {
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
                    isLoading={loading}
                  />
                ))}
              </div>
            </div>
          );
        })}

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
      </div>
    </div>
  );
};

export default MCPServers;
