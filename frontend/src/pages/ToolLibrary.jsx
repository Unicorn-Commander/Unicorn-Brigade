import { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Wrench,
  Code,
  Database,
  Globe,
  Server,
  Boxes,
  CheckCircle,
  Plus,
  ExternalLink,
  Copy,
  ArrowRight
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';
import CardSkeleton from '../components/skeletons/CardSkeleton';
import api from '../services/api';

const ToolLibrary = () => {
  const [tools, setTools] = useState([]);
  const [filteredTools, setFilteredTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('');
  const [selectedDomain, setSelectedDomain] = useState('');
  const [selectedTool, setSelectedTool] = useState(null);

  useEffect(() => {
    loadTools();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [tools, searchQuery, selectedType, selectedDomain]);

  const loadTools = async () => {
    try {
      const data = await api.getTools();
      setTools(data.tools || data || []);
    } catch (error) {
      console.error('Failed to load tools:', error);
      toast.error('Failed to load tools');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...tools];

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(tool =>
        tool.name.toLowerCase().includes(query) ||
        tool.description.toLowerCase().includes(query) ||
        tool.capabilities.some(cap => cap.toLowerCase().includes(query))
      );
    }

    if (selectedType) {
      filtered = filtered.filter(tool => tool.type === selectedType);
    }

    if (selectedDomain) {
      filtered = filtered.filter(tool => tool.domain === selectedDomain);
    }

    setFilteredTools(filtered);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const toolTypes = [...new Set(tools.map(t => t.type).filter(Boolean))].sort();
  const domains = [...new Set(tools.map(t => t.domain).filter(Boolean))].sort();

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-unicorn-500 to-unicorn-400 bg-clip-text text-transparent">
              Tool Library
            </h1>
            <p className="text-slate-400 mt-1">
              {filteredTools.length} of {tools.length} tools available
            </p>
          </div>
          <button className="px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center space-x-2">
            <Plus className="w-5 h-5" />
            <span>Add Custom Tool</span>
          </button>
        </div>

        {/* Filters */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Search */}
            <div className="relative md:col-span-1">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search tools..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
              />
            </div>

            {/* Type Filter */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
            >
              <option value="">All Types</option>
              {toolTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>

            {/* Domain Filter */}
            <select
              value={selectedDomain}
              onChange={(e) => setSelectedDomain(e.target.value)}
              className="px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
            >
              <option value="">All Domains</option>
              {domains.map(domain => (
                <option key={domain} value={domain} className="capitalize">{domain}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Tools Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? (
            <CardSkeleton count={6} />
          ) : (
            filteredTools.map(tool => (
              <div
                key={tool.id}
                className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 hover:border-unicorn-500/50 transition-all cursor-pointer group"
                onClick={() => setSelectedTool(tool)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="text-3xl">{tool.icon}</div>
                    <div>
                      <h3 className="font-semibold text-white group-hover:text-unicorn-400 transition-colors">
                        {tool.name}
                      </h3>
                      <p className="text-xs text-slate-400">{tool.provider}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs ${
                    tool.type === 'MCP' ? 'bg-unicorn-500/20 text-unicorn-400' :
                    tool.type === 'Python' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {tool.type}
                  </span>
                </div>

                <p className="text-sm text-slate-400 mb-4 line-clamp-2">{tool.description}</p>

                <div className="flex flex-wrap gap-2 mb-4">
                  {tool.capabilities.slice(0, 2).map((cap, idx) => (
                    <span key={idx} className="px-2 py-1 rounded bg-slate-800 text-xs text-slate-300">
                      {cap}
                    </span>
                  ))}
                  {tool.capabilities.length > 2 && (
                    <span className="px-2 py-1 rounded bg-slate-800 text-xs text-slate-400">
                      +{tool.capabilities.length - 2} more
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <span className={`text-xs flex items-center space-x-1 ${
                    tool.status === 'active' ? 'text-emerald-400' : 'text-orange-400'
                  }`}>
                    <CheckCircle className="w-3 h-3" />
                    <span>{tool.status === 'active' ? 'Ready' : 'Beta'}</span>
                  </span>
                  <ArrowRight className="w-4 h-4 text-unicorn-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Empty State */}
        {!loading && filteredTools.length === 0 && (
          <div className="text-center py-12">
            <Wrench className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">No tools found</h3>
            <p className="text-slate-400">Try adjusting your filters</p>
          </div>
        )}
      </div>

      {/* Tool Detail Modal */}
      {selectedTool && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-6 z-50"
          onClick={() => setSelectedTool(null)}
        >
          <div
            className="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-4">
                <div className="text-4xl">{selectedTool.icon}</div>
                <div>
                  <h2 className="text-2xl font-bold text-white">{selectedTool.name}</h2>
                  <p className="text-slate-400">{selectedTool.provider}</p>
                </div>
              </div>
              <button
                onClick={() => setSelectedTool(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-slate-300 mb-6">{selectedTool.description}</p>

            <div className="space-y-6">
              {/* Type & Domain */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-slate-400 mb-2">Type</p>
                  <span className={`inline-block px-3 py-1 rounded ${
                    selectedTool.type === 'MCP' ? 'bg-unicorn-500/20 text-unicorn-400' :
                    selectedTool.type === 'Python' ? 'bg-blue-500/20 text-blue-400' :
                    'bg-emerald-500/20 text-emerald-400'
                  }`}>
                    {selectedTool.type}
                  </span>
                </div>
                <div>
                  <p className="text-sm text-slate-400 mb-2">Domain</p>
                  <span className="inline-block px-3 py-1 rounded bg-slate-800 text-slate-300 capitalize">
                    {selectedTool.domain}
                  </span>
                </div>
              </div>

              {/* Capabilities */}
              <div>
                <p className="text-sm text-slate-400 mb-2">Capabilities</p>
                <div className="flex flex-wrap gap-2">
                  {selectedTool.capabilities.map((cap, idx) => (
                    <span key={idx} className="px-3 py-1 rounded bg-slate-800 text-slate-300 text-sm">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              {/* Parameters */}
              <div>
                <p className="text-sm text-slate-400 mb-2">Parameters</p>
                <div className="bg-slate-800/50 rounded-lg p-4 font-mono text-sm">
                  {selectedTool.parameters.map((param, idx) => (
                    <div key={idx} className="text-slate-300">
                      <span className="text-unicorn-400">{param}</span>
                      {idx < selectedTool.parameters.length - 1 && <span className="text-slate-400">,</span>}
                    </div>
                  ))}
                </div>
              </div>

              {/* Usage Example */}
              <div>
                <p className="text-sm text-slate-400 mb-2">Usage Example</p>
                <div className="bg-slate-800/50 rounded-lg p-4 font-mono text-sm relative">
                  <button
                    onClick={() => copyToClipboard(`agent.use_tool("${selectedTool.id}", {params})`)}
                    className="absolute top-2 right-2 p-2 hover:bg-slate-700 rounded"
                  >
                    <Copy className="w-4 h-4 text-slate-400" />
                  </button>
                  <code className="text-slate-300">
                    agent.use_tool(<span className="text-emerald-400">"{selectedTool.id}"</span>, &#123;params&#125;)
                  </code>
                </div>
              </div>

              {/* Actions */}
              <div className="flex space-x-3">
                <button className="flex-1 px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors">
                  Add to Agent
                </button>
                <button className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors flex items-center space-x-2">
                  <ExternalLink className="w-4 h-4" />
                  <span>Docs</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolLibrary;
