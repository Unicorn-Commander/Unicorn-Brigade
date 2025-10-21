import { useState, useEffect } from 'react';
import { Search, Filter, Plus, Bot, ExternalLink, Eye, Edit, Trash2, Star, TrendingUp, MessageSquare, Shield, DollarSign, ArrowUpDown } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import AgentCard from '../components/AgentCard';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8112/api';

// Domain Icons and Colors
const domainConfig = {
  financial: { icon: '💰', color: 'emerald', emoji: '💰' },
  legal: { icon: '⚖️', color: 'blue', emoji: '⚖️' },
  medical: { icon: '🏥', color: 'red', emoji: '🏥' },
  technology: { icon: '💻', color: 'purple', emoji: '💻' },
  investigation: { icon: '🔍', color: 'amber', emoji: '🔍' },
  orchestration: { icon: '🎯', color: 'cyan', emoji: '🎯' },
  meta: { icon: '🎖️', color: 'orange', emoji: '🎖️' },
  intelligence: { icon: '🕵️', color: 'indigo', emoji: '🕵️' }
};

// Status Icons
const statusConfig = {
  active: { label: 'Active', icon: '✅', color: 'green' },
  draft: { label: 'Draft', icon: '🟡', color: 'yellow' },
  inactive: { label: 'Inactive', icon: '⚫', color: 'gray' },
  archived: { label: 'Archived', icon: '📦', color: 'slate' },
  busy: { label: 'Busy', icon: '⏳', color: 'orange' }
};

const AgentLibrary = () => {
  const navigate = useNavigate();
  const [agents, setAgents] = useState([]);
  const [filteredAgents, setFilteredAgents] = useState([]);
  const [domains, setDomains] = useState([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid or list
  const [sortBy, setSortBy] = useState('newest'); // newest, most-used, a-z

  useEffect(() => {
    loadAgents();
    loadDomains();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [agents, searchQuery, selectedDomain, selectedStatus, selectedType, sortBy]);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/agents`);
      setAgents(response.data.agents || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
      toast.error('Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  const loadDomains = async () => {
    try {
      const response = await axios.get(`${API_BASE}/agents/domains`);
      setDomains(response.data.domains || []);
    } catch (error) {
      console.error('Failed to load domains:', error);
    }
  };

  const applyFilters = () => {
    let filtered = [...agents];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(agent =>
        agent.name?.toLowerCase().includes(query) ||
        agent.title?.toLowerCase().includes(query) ||
        agent.bio?.toLowerCase().includes(query) ||
        agent.domain?.toLowerCase().includes(query)
      );
    }

    // Domain filter
    if (selectedDomain) {
      filtered = filtered.filter(agent => agent.domain === selectedDomain);
    }

    // Status filter
    if (selectedStatus) {
      filtered = filtered.filter(agent => agent.status === selectedStatus);
    }

    // Type filter
    if (selectedType) {
      filtered = filtered.filter(agent => agent.type === selectedType);
    }

    // Sort
    filtered.sort((a, b) => {
      if (sortBy === 'newest') {
        return new Date(b.createdAt || 0) - new Date(a.createdAt || 0);
      } else if (sortBy === 'most-used') {
        return (b._count?.messages || 0) - (a._count?.messages || 0);
      } else if (sortBy === 'a-z') {
        return (a.displayName || a.name || '').localeCompare(b.displayName || b.name || '');
      }
      return 0;
    });

    setFilteredAgents(filtered);
  };

  const getDomainConfig = (domain) => {
    return domainConfig[domain] || { icon: '🤖', color: 'slate', emoji: '🤖' };
  };

  const getStatusConfig = (status) => {
    return statusConfig[status] || { label: status, icon: '⚪', color: 'gray' };
  };

  const groupByDomain = () => {
    const grouped = {};
    filteredAgents.forEach(agent => {
      const domain = agent.domain || 'other';
      if (!grouped[domain]) {
        grouped[domain] = [];
      }
      grouped[domain].push(agent);
    });
    return grouped;
  };

  const groupedAgents = groupByDomain();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gradient">Agent Library</h1>
            <p className="text-slate-400 mt-1">
              {filteredAgents.length} of {agents.length} agents
            </p>
          </div>

          <button
            onClick={() => navigate('/builder-chat')}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Build New Agent</span>
          </button>
        </div>

        {/* Filters */}
        <div className="card">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Search */}
            <div className="relative md:col-span-2">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search agents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
              />
            </div>

            {/* Domain Filter */}
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
            >
              <option value="">All Domains</option>
              {domains.map(d => (
                <option key={d.name} value={d.name}>
                  {d.name} ({d.count})
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
            >
              <option value="">All Status</option>
              <option value="active">Active ✅</option>
              <option value="draft">Draft 🟡</option>
              <option value="inactive">Inactive ⚫</option>
              <option value="archived">Archived 📦</option>
            </select>
          </div>

          <div className="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-400">Type:</span>
              <button
                onClick={() => setSelectedType('')}
                className={`px-3 py-1 rounded-lg text-sm ${!selectedType ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300'}`}
              >
                All
              </button>
              <button
                onClick={() => setSelectedType('individual')}
                className={`px-3 py-1 rounded-lg text-sm ${selectedType === 'individual' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300'}`}
              >
                Individual
              </button>
              <button
                onClick={() => setSelectedType('team_lead')}
                className={`px-3 py-1 rounded-lg text-sm ${selectedType === 'team_lead' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300'}`}
              >
                Team Lead
              </button>
              <button
                onClick={() => setSelectedType('orchestrator')}
                className={`px-3 py-1 rounded-lg text-sm ${selectedType === 'orchestrator' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300'}`}
              >
                Orchestrator
              </button>
            </div>

            <div className="flex items-center space-x-3">
              {/* Sort Dropdown */}
              <div className="flex items-center space-x-2">
                <ArrowUpDown className="w-4 h-4 text-slate-400" />
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="px-3 py-1 bg-slate-800/50 border border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
                >
                  <option value="newest">Newest First</option>
                  <option value="most-used">Most Used</option>
                  <option value="a-z">A-Z</option>
                </select>
              </div>

              {/* View Mode Toggle */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 rounded ${viewMode === 'grid' ? 'bg-unicorn-500' : 'bg-slate-800'}`}
                >
                  <div className="w-4 h-4 grid grid-cols-2 gap-0.5">
                    <div className="bg-white rounded-sm"></div>
                    <div className="bg-white rounded-sm"></div>
                    <div className="bg-white rounded-sm"></div>
                    <div className="bg-white rounded-sm"></div>
                  </div>
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`p-2 rounded ${viewMode === 'list' ? 'bg-unicorn-500' : 'bg-slate-800'}`}
                >
                  <div className="w-4 h-4 flex flex-col gap-1">
                    <div className="h-0.5 bg-white rounded"></div>
                    <div className="h-0.5 bg-white rounded"></div>
                    <div className="h-0.5 bg-white rounded"></div>
                  </div>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-unicorn-500"></div>
            <p className="text-slate-400 mt-4">Loading agents...</p>
          </div>
        )}

        {/* Agents Grouped by Domain */}
        {!loading && Object.keys(groupedAgents).length === 0 && (
          <div className="text-center py-12">
            <Bot className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">No agents found</h3>
            <p className="text-slate-400 mb-6">Start by building your first agent</p>
            <button
              onClick={() => navigate('/builder-chat')}
              className="btn-primary flex items-center space-x-2 mx-auto"
            >
              <Plus className="w-5 h-5" />
              <span>Build Agent</span>
            </button>
          </div>
        )}

        {!loading && Object.keys(groupedAgents).map(domain => {
          const config = getDomainConfig(domain);
          const domainAgents = groupedAgents[domain];

          return (
            <div key={domain} className="space-y-4">
              {/* Domain Header */}
              <div className="flex items-center space-x-3">
                <span className="text-3xl">{config.emoji}</span>
                <div>
                  <h2 className="text-xl font-bold capitalize">{domain}</h2>
                  <p className="text-sm text-slate-400">{domainAgents.length} agents</p>
                </div>
              </div>

              {/* Agents Grid/List */}
              {viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {domainAgents.map(agent => (
                    <AgentCard
                      key={agent.id}
                      agent={agent}
                      onClick={() => navigate(`/agent/${agent.id}`)}
                    />
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {domainAgents.map(agent => (
                    <AgentListItem key={agent.id} agent={agent} navigate={navigate} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

// Agent List Item Component
const AgentListItem = ({ agent, navigate }) => {
  const statusConfig = getStatusConfig(agent.status);

  return (
    <div
      className="card group hover:shadow-lg hover:shadow-unicorn-500/10 transition-all cursor-pointer"
      onClick={() => navigate(`/agent/${agent.id}`)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4 flex-1">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center text-xl">
            {agent.avatar || '🦄'}
          </div>
          <div className="flex-1">
            <h3 className="font-semibold group-hover:text-unicorn-400 transition-colors">
              {agent.displayName || agent.name}
            </h3>
            <p className="text-sm text-slate-400">
              {agent.rank && `${agent.rank} • `}
              {agent.title || agent.type}
            </p>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs bg-${statusConfig.color}-500/20 text-${statusConfig.color}-400`}>
            {statusConfig.icon} {statusConfig.label}
          </span>
        </div>
      </div>
    </div>
  );
};

// Helper function
function getStatusConfig(status) {
  return statusConfig[status] || { label: status, icon: '⚪', color: 'gray' };
}

export default AgentLibrary;
