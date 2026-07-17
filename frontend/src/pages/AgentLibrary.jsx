import { useState, useEffect, useMemo } from 'react';
import { Search, Filter, Plus, Bot, ExternalLink, Eye, Edit, Trash2, Star, TrendingUp, MessageSquare, Shield, DollarSign, ArrowUpDown, Wrench, Zap, CheckCircle, AlertCircle, X } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { apiJson } from '../services/http';
import AgentCard from '../components/AgentCard';
import AgentEditModal from '../components/AgentEditModal';
import AgentDeleteConfirmModal from '../components/AgentDeleteConfirmModal';
import { getToolIcon } from '../components/ToolCallCard';
import Breadcrumbs from '../components/Breadcrumbs';
import CardSkeleton from '../components/skeletons/CardSkeleton';
import ListSkeleton from '../components/skeletons/ListSkeleton';

// Defensive: agents can arrive with non-array tools/capabilities (bad seed
// data / JSON columns) — always hand callers a real array to slice/map.
const agentToolList = (agent) => {
  if (Array.isArray(agent?.tools)) return agent.tools;
  if (Array.isArray(agent?.agentTools)) return agent.agentTools;
  return [];
};
const agentCapabilityList = (agent) =>
  Array.isArray(agent?.capabilities) ? agent.capabilities : [];

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
  const [filterLoading, setFilterLoading] = useState(false);
  const [editingAgent, setEditingAgent] = useState(null);
  const [deletingAgent, setDeletingAgent] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedStatus, setSelectedStatus] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [selectedTool, setSelectedTool] = useState('');
  const [viewMode, setViewMode] = useState('grid'); // grid or list
  const [sortBy, setSortBy] = useState('newest'); // newest, most-used, a-z

  // Extract all unique tools from agents
  const allTools = useMemo(() => {
    const toolSet = new Set();
    agents.forEach(agent => {
      const tools = agentToolList(agent);
      tools.forEach(tool => {
        const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name);
        if (toolName) toolSet.add(toolName);
      });
    });
    return Array.from(toolSet).sort();
  }, [agents]);

  // Extract all unique capabilities
  const allCapabilities = useMemo(() => {
    const capSet = new Set();
    agents.forEach(agent => {
      agentCapabilityList(agent).forEach(cap => capSet.add(cap));
    });
    return Array.from(capSet).sort();
  }, [agents]);

  useEffect(() => {
    loadAgents();
    loadDomains();
  }, []);

  useEffect(() => {
    setFilterLoading(true);
    const timer = setTimeout(() => {
      applyFilters();
      setFilterLoading(false);
    }, 150);
    return () => clearTimeout(timer);
  }, [agents, searchQuery, selectedDomain, selectedStatus, selectedType, selectedTool, sortBy]);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const [data] = await Promise.all([
        apiJson('/agents'),
        new Promise(resolve => setTimeout(resolve, 300)),
      ]);
      setAgents(data.agents || []);
    } catch (error) {
      console.error('Failed to load agents:', error);
      toast.error('Failed to load agents');
    } finally {
      setLoading(false);
    }
  };

  const loadDomains = async () => {
    try {
      const data = await apiJson('/agents/domains');
      setDomains(data.domains || []);
    } catch (error) {
      console.error('Failed to load domains:', error);
    }
  };

  const applyFilters = () => {
    let filtered = [...agents];

    // Search filter - now also searches capabilities and tools
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(agent => {
        // Basic text search
        if (agent.name?.toLowerCase().includes(query) ||
            agent.displayName?.toLowerCase().includes(query) ||
            agent.title?.toLowerCase().includes(query) ||
            agent.bio?.toLowerCase().includes(query) ||
            agent.domain?.toLowerCase().includes(query)) {
          return true;
        }
        // Search in capabilities
        if (agentCapabilityList(agent).some(cap => cap.toLowerCase().includes(query))) {
          return true;
        }
        // Search in tools
        const tools = agentToolList(agent);
        if (tools.some(tool => {
          const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name);
          return toolName?.toLowerCase().includes(query);
        })) {
          return true;
        }
        return false;
      });
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

    // Tool filter
    if (selectedTool) {
      filtered = filtered.filter(agent => {
        const tools = agentToolList(agent);
        return tools.some(tool => {
          const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name);
          return toolName === selectedTool;
        });
      });
    }

    // Sort
    filtered.sort((a, b) => {
      if (sortBy === 'newest') {
        return new Date(b.createdAt || 0) - new Date(a.createdAt || 0);
      } else if (sortBy === 'most-used') {
        return (b._count?.messages || 0) - (a._count?.messages || 0);
      } else if (sortBy === 'a-z') {
        return (a.displayName || a.name || '').localeCompare(b.displayName || b.name || '');
      } else if (sortBy === 'most-tools') {
        return agentToolList(b).length - agentToolList(a).length;
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

  const handleAgentUpdated = (updatedAgent, meta = {}) => {
    const snapshot = agents;
    setAgents((prev) => prev.map((agent) => (agent.id === updatedAgent.id ? updatedAgent : agent)));
    if (!meta.optimistic) {
      setEditingAgent(null);
    }
    return () => {
      setAgents(snapshot);
    };
  };

  const handleAgentDeleted = (agentToDelete, meta = {}) => {
    const snapshot = agents;
    const deletedId = typeof agentToDelete === 'string' ? agentToDelete : agentToDelete?.id;
    setAgents((prev) => prev.filter((agent) => agent.id !== deletedId));
    if (!meta.optimistic) {
      setDeletingAgent(null);
    }
    return () => {
      setAgents(snapshot);
    };
  };

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
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
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {/* Search */}
            <div className="relative md:col-span-2">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search agents, tools, or capabilities..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white placeholder-slate-500"
              />
            </div>

            {/* Domain Filter */}
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
            >
              <option value="">All Domains</option>
              {domains.map(d => (
                <option key={d.name} value={d.name}>
                  {d.name} ({d.count})
                </option>
              ))}
            </select>

            {/* Tool Filter */}
            <select
              value={selectedTool}
              onChange={(e) => setSelectedTool(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
            >
              <option value="">All Tools</option>
              {allTools.map(tool => (
                <option key={tool} value={tool}>
                  {tool}
                </option>
              ))}
            </select>

            {/* Status Filter */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="draft">Draft</option>
              <option value="inactive">Inactive</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          {/* Active filters display */}
          {(selectedDomain || selectedStatus || selectedType || selectedTool || searchQuery) && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-500">Active filters:</span>
              {searchQuery && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-unicorn-500/20 text-unicorn-400 text-xs">
                  Search: {searchQuery}
                  <button onClick={() => setSearchQuery('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedDomain && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 text-xs">
                  Domain: {selectedDomain}
                  <button onClick={() => setSelectedDomain('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              {selectedTool && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-cyan-500/20 text-cyan-400 text-xs">
                  Tool: {selectedTool}
                  <button onClick={() => setSelectedTool('')} className="hover:text-white">
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
              {selectedType && (
                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-amber-500/20 text-amber-400 text-xs">
                  Type: {selectedType}
                  <button onClick={() => setSelectedType('')} className="hover:text-white">
                    <X className="w-3 h-3" />
                  </button>
                </span>
              )}
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedDomain('');
                  setSelectedStatus('');
                  setSelectedType('');
                  setSelectedTool('');
                }}
                className="text-xs text-slate-400 hover:text-white underline"
              >
                Clear all
              </button>
            </div>
          )}

          <div className="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div className="flex items-center flex-wrap gap-2">
              <Filter className="w-4 h-4 text-slate-400" />
              <span className="text-sm text-slate-400">Type:</span>
              <button
                onClick={() => setSelectedType('')}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${!selectedType ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                All
              </button>
              <button
                onClick={() => setSelectedType('individual')}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${selectedType === 'individual' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                Individual
              </button>
              <button
                onClick={() => setSelectedType('team_lead')}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${selectedType === 'team_lead' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                Team Lead
              </button>
              <button
                onClick={() => setSelectedType('orchestrator')}
                className={`px-3 py-1 rounded-lg text-sm transition-colors ${selectedType === 'orchestrator' ? 'bg-unicorn-500 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
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
                  className="px-3 py-1 bg-slate-800/50 border border-slate-700 rounded-lg text-sm focus:ring-2 focus:ring-unicorn-500 focus:border-transparent text-white"
                >
                  <option value="newest">Newest First</option>
                  <option value="most-used">Most Used</option>
                  <option value="most-tools">Most Tools</option>
                  <option value="a-z">A-Z</option>
                </select>
              </div>

              {/* View Mode Toggle */}
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`p-2 rounded transition-colors ${viewMode === 'grid' ? 'bg-unicorn-500' : 'bg-slate-800 hover:bg-slate-700'}`}
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
                  className={`p-2 rounded transition-colors ${viewMode === 'list' ? 'bg-unicorn-500' : 'bg-slate-800 hover:bg-slate-700'}`}
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
        {(loading || filterLoading) && (
          viewMode === 'grid' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <CardSkeleton count={6} />
            </div>
          ) : (
            <ListSkeleton rows={6} />
          )
        )}

        {/* Agents Grouped by Domain */}
        {!loading && !filterLoading && Object.keys(groupedAgents).length === 0 && (
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

        {!loading && !filterLoading && Object.keys(groupedAgents).map(domain => {
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
                    <div key={agent.id} className="relative group">
                      <AgentCard
                        agent={agent}
                        onClick={() => navigate(`/agent/${agent.id}`)}
                      />
                      <div className="mt-4 flex gap-2 pt-4 border-t border-slate-700/50">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingAgent(agent);
                          }}
                          className="flex-1 px-4 py-2 bg-unicorn-600/20 text-unicorn-400 rounded-lg hover:bg-unicorn-600/30 transition-colors flex items-center justify-center space-x-2"
                        >
                          <Edit className="w-4 h-4" />
                          <span>Edit</span>
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeletingAgent(agent);
                          }}
                          className="flex-1 px-4 py-2 bg-red-600/20 text-red-400 rounded-lg hover:bg-red-600/30 transition-colors flex items-center justify-center space-x-2"
                        >
                          <Trash2 className="w-4 h-4" />
                          <span>Delete</span>
                        </button>
                      </div>
                      {/* Quick Chat overlay button */}
                      <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity z-10">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/chat?agent=${agent.id}`);
                          }}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-unicorn-600 hover:bg-unicorn-500 text-white text-sm font-medium shadow-lg transition-colors"
                        >
                          <MessageSquare className="w-4 h-4" />
                          Chat Now
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-2">
                  {domainAgents.map(agent => (
                    <AgentListItem
                      key={agent.id}
                      agent={agent}
                      navigate={navigate}
                      onEdit={() => setEditingAgent(agent)}
                      onDelete={() => setDeletingAgent(agent)}
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {editingAgent && (
        <AgentEditModal
          agent={editingAgent}
          onClose={() => setEditingAgent(null)}
          onSave={handleAgentUpdated}
        />
      )}

      {deletingAgent && (
        <AgentDeleteConfirmModal
          agent={deletingAgent}
          onClose={() => setDeletingAgent(null)}
          onDelete={handleAgentDeleted}
        />
      )}
    </div>
  );
};

// Agent List Item Component
const AgentListItem = ({ agent, navigate, onEdit, onDelete }) => {
  const statusConfig = getStatusConfig(agent.status);
  const tools = agentToolList(agent);
  const toolCount = tools.length;

  const handleChatClick = (e) => {
    e.stopPropagation();
    navigate(`/chat?agent=${agent.id}`);
  };

  return (
    <div
      className="card group hover:shadow-lg hover:shadow-unicorn-500/10 transition-all cursor-pointer"
      onClick={() => navigate(`/agent/${agent.id}`)}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center space-x-4 flex-1 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center text-xl flex-shrink-0">
            {agent.avatar || '🦄'}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold group-hover:text-unicorn-400 transition-colors truncate">
              {agent.displayName || agent.name}
            </h3>
            <p className="text-sm text-slate-400 truncate">
              {agent.rank && `${agent.rank} • `}
              {agent.title || agent.type}
            </p>
          </div>
        </div>

        {/* Tool badges */}
        <div className="hidden md:flex items-center gap-2 flex-shrink-0">
          {tools.slice(0, 3).map((tool, idx) => {
            const toolName = typeof tool === 'string' ? tool : (tool.tool?.name || tool.name);
            const ToolIcon = getToolIcon(toolName);
            return (
              <div
                key={idx}
                className="flex items-center gap-1 px-2 py-1 rounded bg-slate-800/50 border border-slate-700/50"
                title={toolName}
              >
                <ToolIcon className="w-3 h-3 text-cyan-400" />
                <span className="text-xs text-slate-400 hidden lg:inline">{toolName}</span>
              </div>
            );
          })}
          {toolCount > 3 && (
            <span className="px-2 py-1 rounded bg-slate-800/50 text-xs text-slate-500">
              +{toolCount - 3}
            </span>
          )}
          {toolCount === 0 && (
            <span className="text-xs text-slate-500">No tools</span>
          )}
        </div>

        {/* Capability summary */}
        <div className="hidden lg:flex items-center gap-2 text-xs text-slate-500 flex-shrink-0">
          <div className="flex items-center gap-1">
            <Wrench className="w-3 h-3" />
            <span>{toolCount}</span>
          </div>
          {agent.status === 'active' && (
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
          )}
        </div>

        {/* Status badge */}
        <span className={`px-3 py-1 rounded-full text-xs flex-shrink-0 ${
          agent.status === 'active' ? 'bg-emerald-500/20 text-emerald-400' :
          agent.status === 'draft' ? 'bg-yellow-500/20 text-yellow-400' :
          agent.status === 'inactive' ? 'bg-slate-500/20 text-slate-400' :
          'bg-slate-500/20 text-slate-400'
        }`}>
          {statusConfig.label}
        </span>

        {/* Quick Chat button */}
        <button
          onClick={handleChatClick}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-unicorn-500/20 text-unicorn-400 hover:bg-unicorn-500/30 transition-colors text-sm flex-shrink-0"
          title="Start chat"
        >
          <MessageSquare className="w-4 h-4" />
          <span className="hidden sm:inline">Chat</span>
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-unicorn-600/20 text-unicorn-400 hover:bg-unicorn-600/30 transition-colors text-sm flex-shrink-0"
          title="Edit agent"
        >
          <Edit className="w-4 h-4" />
          <span className="hidden sm:inline">Edit</span>
        </button>

        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600/20 text-red-400 hover:bg-red-600/30 transition-colors text-sm flex-shrink-0"
          title="Delete agent"
        >
          <Trash2 className="w-4 h-4" />
          <span className="hidden sm:inline">Delete</span>
        </button>
      </div>
    </div>
  );
};

// Helper function
function getStatusConfig(status) {
  return statusConfig[status] || { label: status, icon: '⚪', color: 'gray' };
}

export default AgentLibrary;
