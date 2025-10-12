import { useState, useEffect } from 'react';
import { Save, Plus, Code, Brain, Wrench, Sparkles, Trash2, Edit2, Copy, FileText, Users, Shield, Zap, Search, Filter, RefreshCw, AlertTriangle, Bot, Library, BookOpen, Award } from 'lucide-react';
import MonacoEditor from '@monaco-editor/react';
import { toast } from 'react-hot-toast';
import api from '../services/api';
import { agentPromptCatalog, getAllTemplates } from '../data/agentPromptCatalog';

const AgentBuilder = () => {
  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState(null);
  const [filterDomain, setFilterDomain] = useState('');
  const [filterType, setFilterType] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [showTemplateDetails, setShowTemplateDetails] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [agentConfig, setAgentConfig] = useState({
    name: '',
    type: 'individual',
    domain: '',
    avatar: '',
    persona: '',
    systemPrompt: '',
    tools: [],
    capabilities: [],
    status: 'active'
  });

  // Get all templates from catalog
  const agentTemplates = getAllTemplates();

  // Available tools
  const availableTools = [
    'Web Search',
    'Code Execution',
    'File Management',
    'API Calls',
    'Document Analysis',
    'Database Query',
    'Email Integration',
    'Calendar Access',
    'Social Media Scanner',
    'Financial Calculator',
    'Legal Database Search',
    'OSINT Tools',
    'Translation Services',
    'Image Recognition',
    'Voice Transcription'
  ];

  // Load agents on mount
  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await api.getAgents();
      setAgents(data);
    } catch (error) {
      toast.error('Failed to load agents');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const saveAgent = async () => {
    try {
      if (!agentConfig.name || !agentConfig.type) {
        toast.error('Agent name and type are required');
        return;
      }

      let result;
      if (isEditing && selectedAgent) {
        // Update existing agent
        result = await api.updateAgent(selectedAgent.id, agentConfig);
        toast.success('Agent updated successfully');
      } else {
        // Create new agent
        result = await api.createAgent(agentConfig);
        toast.success('Agent created successfully');
      }

      await loadAgents();
      resetForm();
    } catch (error) {
      toast.error(isEditing ? 'Failed to update agent' : 'Failed to create agent');
      console.error(error);
    }
  };

  const editAgent = (agent) => {
    setSelectedAgent(agent);
    setIsEditing(true);
    setAgentConfig({
      name: agent.name,
      type: agent.type,
      domain: agent.domain || '',
      avatar: agent.avatar || '',
      persona: agent.persona || '',
      systemPrompt: agent.systemPrompt || '',
      tools: JSON.parse(agent.tools || '[]'),
      capabilities: JSON.parse(agent.capabilities || '[]'),
      status: agent.status || 'active'
    });
  };

  const deleteAgent = async () => {
    try {
      await api.deleteAgent(agentToDelete.id);
      toast.success('Agent deleted successfully');
      await loadAgents();
      setShowDeleteConfirm(false);
      setAgentToDelete(null);
    } catch (error) {
      toast.error('Failed to delete agent');
      console.error(error);
    }
  };

  const duplicateAgent = (agent) => {
    setAgentConfig({
      name: `${agent.name} (Copy)`,
      type: agent.type,
      domain: agent.domain || '',
      avatar: agent.avatar || '',
      persona: agent.persona || '',
      systemPrompt: agent.systemPrompt || '',
      tools: JSON.parse(agent.tools || '[]'),
      capabilities: JSON.parse(agent.capabilities || '[]'),
      status: 'active'
    });
    setIsEditing(false);
    setSelectedAgent(null);
    toast.info('Agent duplicated - modify and save as new');
  };

  const loadTemplate = (template) => {
    setAgentConfig(template);
    setIsEditing(false);
    setSelectedAgent(null);
    toast.success(`Template loaded: ${template.name}`);
  };

  const resetForm = () => {
    setAgentConfig({
      name: '',
      type: 'individual',
      domain: '',
      avatar: '',
      persona: '',
      systemPrompt: '',
      tools: [],
      capabilities: [],
      status: 'active'
    });
    setIsEditing(false);
    setSelectedAgent(null);
  };

  const toggleTool = (tool) => {
    setAgentConfig(prev => ({
      ...prev,
      tools: prev.tools.includes(tool)
        ? prev.tools.filter(t => t !== tool)
        : [...prev.tools, tool]
    }));
  };

  const addCapability = (capability) => {
    if (capability && !agentConfig.capabilities.includes(capability)) {
      setAgentConfig(prev => ({
        ...prev,
        capabilities: [...prev.capabilities, capability]
      }));
    }
  };

  const removeCapability = (capability) => {
    setAgentConfig(prev => ({
      ...prev,
      capabilities: prev.capabilities.filter(c => c !== capability)
    }));
  };

  // Filter agents
  const filteredAgents = agents.filter(agent => {
    const matchesDomain = !filterDomain || agent.domain === filterDomain;
    const matchesType = !filterType || agent.type === filterType;
    const matchesSearch = !searchQuery ||
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (agent.domain && agent.domain.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesDomain && matchesType && matchesSearch;
  });

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gradient">Agent Builder</h1>
          <p className="text-slate-400 mt-1">Create, edit, and manage AI agents</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={loadAgents}
            className="btn-secondary flex items-center space-x-2"
          >
            <RefreshCw className="w-5 h-5" />
            <span>Refresh</span>
          </button>
          {(isEditing || agentConfig.name) && (
            <button
              onClick={resetForm}
              className="btn-secondary"
            >
              Cancel
            </button>
          )}
          <button
            onClick={saveAgent}
            className="btn-primary flex items-center space-x-2"
            disabled={!agentConfig.name}
          >
            <Save className="w-5 h-5" />
            <span>{isEditing ? 'Update' : 'Save'} Agent</span>
          </button>
        </div>
      </div>

      {/* Agent Templates - Professional Prompt Catalog */}
      <div className="card">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold flex items-center">
            <Library className="w-5 h-5 mr-2 text-unicorn-400" />
            Professional Agent Template Library
          </h2>
          <div className="flex items-center space-x-2">
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-800/50 text-sm"
            >
              <option value="all">All Categories</option>
              <option value="legal">Legal</option>
              <option value="financial">Financial</option>
              <option value="investigation">Investigation</option>
              <option value="orchestration">Orchestration</option>
              <option value="specialized">Specialized</option>
            </select>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
          {agentTemplates
            .filter(t => selectedCategory === 'all' || t.category === selectedCategory)
            .map((template, idx) => (
              <div
                key={template.id || idx}
                className="group relative p-4 rounded-lg glass-hover border border-slate-700/50 hover:border-unicorn-500/50 transition-all cursor-pointer"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-2xl">{template.icon}</span>
                  {template.type === 'orchestrator' && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-amber-500/20 text-amber-400">
                      Orchestrator
                    </span>
                  )}
                  {template.type === 'team_lead' && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-cyan-500/20 text-cyan-400">
                      Team Lead
                    </span>
                  )}
                </div>

                <h3 className="font-semibold text-sm mb-1">{template.name}</h3>
                <p className="text-xs text-slate-400 mb-2 line-clamp-2">
                  {template.description}
                </p>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-unicorn-400">{template.domain}</span>
                  <span className="text-slate-500">
                    {template.capabilities?.length || 0} capabilities
                  </span>
                </div>

                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-900 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                  <div className="flex space-x-2">
                    <button
                      onClick={() => {
                        setSelectedTemplate(template);
                        setShowTemplateDetails(true);
                      }}
                      className="flex-1 px-2 py-1 text-xs rounded bg-slate-700/80 hover:bg-slate-600/80 transition-colors"
                    >
                      <BookOpen className="w-3 h-3 inline mr-1" />
                      View
                    </button>
                    <button
                      onClick={() => loadTemplate(template)}
                      className="flex-1 px-2 py-1 text-xs rounded bg-unicorn-500/20 hover:bg-unicorn-500/30 text-unicorn-400 transition-colors"
                    >
                      <Award className="w-3 h-3 inline mr-1" />
                      Use
                    </button>
                  </div>
                </div>
              </div>
          ))}
        </div>

        <div className="mt-4 p-3 rounded-lg bg-unicorn-500/10 border border-unicorn-500/30">
          <p className="text-xs text-unicorn-400">
            <Sparkles className="w-3 h-3 inline mr-1" />
            Each template contains professionally crafted personas and system prompts optimized for maximum agent effectiveness.
          </p>
        </div>
      </div>

      {/* Template Detail Modal */}
      {showTemplateDetails && selectedTemplate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
          <div className="card max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <span className="text-3xl">{selectedTemplate.icon}</span>
                <div>
                  <h3 className="text-xl font-semibold">{selectedTemplate.name}</h3>
                  <p className="text-sm text-slate-400">{selectedTemplate.description}</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowTemplateDetails(false);
                  setSelectedTemplate(null);
                }}
                className="p-2 rounded-lg glass-hover"
              >
                <span className="text-xl">×</span>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-sm mb-2 text-unicorn-400">Capabilities</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedTemplate.capabilities?.map((cap, idx) => (
                    <span key={idx} className="px-2 py-1 rounded-full bg-unicorn-500/20 text-xs">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-sm mb-2 text-cyan-400">Tools</h4>
                <div className="flex flex-wrap gap-2">
                  {selectedTemplate.tools?.map((tool, idx) => (
                    <span key={idx} className="px-2 py-1 rounded-full bg-cyan-500/20 text-xs">
                      {tool}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-sm mb-2 text-emerald-400">Persona</h4>
                <div className="p-3 rounded-lg bg-slate-800/50 text-sm text-slate-300 whitespace-pre-wrap max-h-48 overflow-y-auto scrollbar-thin">
                  {selectedTemplate.persona}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-sm mb-2 text-amber-400">System Prompt</h4>
                <div className="p-3 rounded-lg bg-slate-800/50 text-sm text-slate-300 whitespace-pre-wrap max-h-48 overflow-y-auto scrollbar-thin">
                  {selectedTemplate.systemPrompt}
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4 border-t border-slate-700">
                <button
                  onClick={() => {
                    setShowTemplateDetails(false);
                    setSelectedTemplate(null);
                  }}
                  className="btn-secondary"
                >
                  Close
                </button>
                <button
                  onClick={() => {
                    loadTemplate(selectedTemplate);
                    setShowTemplateDetails(false);
                    setSelectedTemplate(null);
                  }}
                  className="btn-primary flex items-center space-x-2"
                >
                  <Award className="w-4 h-4" />
                  <span>Use This Template</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Agent List */}
      {agents.length > 0 && (
        <div className="card">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold flex items-center">
              <Users className="w-5 h-5 mr-2 text-cyan-400" />
              Existing Agents ({filteredAgents.length})
            </h2>
            <div className="flex items-center space-x-2">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search agents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-3 py-1.5 rounded-lg bg-slate-800/50 text-sm w-48"
                />
              </div>
              <select
                value={filterDomain}
                onChange={(e) => setFilterDomain(e.target.value)}
                className="px-3 py-1.5 rounded-lg bg-slate-800/50 text-sm"
              >
                <option value="">All Domains</option>
                <option value="legal">Legal</option>
                <option value="financial">Financial</option>
                <option value="investigation">Investigation</option>
                <option value="management">Management</option>
              </select>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="px-3 py-1.5 rounded-lg bg-slate-800/50 text-sm"
              >
                <option value="">All Types</option>
                <option value="individual">Individual</option>
                <option value="team_lead">Team Lead</option>
                <option value="orchestrator">Orchestrator</option>
              </select>
            </div>
          </div>

          <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin">
            {loading ? (
              <div className="text-center py-8 text-slate-400">Loading agents...</div>
            ) : filteredAgents.length === 0 ? (
              <div className="text-center py-8 text-slate-400">No agents found</div>
            ) : (
              filteredAgents.map((agent) => (
                <div
                  key={agent.id}
                  className="flex items-center justify-between p-3 rounded-lg glass-hover"
                >
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center text-white text-xl">
                      {agent.avatar || <Bot className="w-6 h-6" />}
                    </div>
                    <div>
                      <h3 className="font-semibold">{agent.name}</h3>
                      <p className="text-xs text-slate-400">
                        {agent.type} • {agent.domain || 'General'} • {agent.status}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => editAgent(agent)}
                      className="p-1.5 rounded glass-hover"
                      title="Edit"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => duplicateAgent(agent)}
                      className="p-1.5 rounded glass-hover"
                      title="Duplicate"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setAgentToDelete(agent);
                        setShowDeleteConfirm(true);
                      }}
                      className="p-1.5 rounded glass-hover text-red-400"
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Basic Configuration */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Brain className="w-5 h-5 mr-2 text-unicorn-400" />
            Basic Configuration
          </h2>

          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-slate-400 mb-2">Agent Name</label>
                <input
                  type="text"
                  value={agentConfig.name}
                  onChange={(e) => setAgentConfig({...agentConfig, name: e.target.value})}
                  className="w-full input"
                  placeholder="e.g., Financial Analyst"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Avatar</label>
                <input
                  type="text"
                  value={agentConfig.avatar}
                  onChange={(e) => setAgentConfig({...agentConfig, avatar: e.target.value})}
                  className="w-full input text-center text-2xl"
                  placeholder="🤖"
                  title="Enter an emoji or image URL"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Type</label>
              <select
                value={agentConfig.type}
                onChange={(e) => setAgentConfig({...agentConfig, type: e.target.value})}
                className="w-full input"
              >
                <option value="individual">Individual Contributor</option>
                <option value="team_lead">Team Lead</option>
                <option value="orchestrator">Orchestrator</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Domain</label>
              <input
                type="text"
                value={agentConfig.domain}
                onChange={(e) => setAgentConfig({...agentConfig, domain: e.target.value})}
                className="w-full input"
                placeholder="e.g., financial, legal, technology"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Status</label>
              <select
                value={agentConfig.status}
                onChange={(e) => setAgentConfig({...agentConfig, status: e.target.value})}
                className="w-full input"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="busy">Busy</option>
              </select>
            </div>
          </div>
        </div>

        {/* Tools & Capabilities */}
        <div className="card">
          <h2 className="text-xl font-semibold mb-4 flex items-center">
            <Wrench className="w-5 h-5 mr-2 text-cyan-400" />
            Tools & Capabilities
          </h2>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Available Tools</label>
              <div className="space-y-2 max-h-48 overflow-y-auto scrollbar-thin">
                {availableTools.map((tool) => (
                  <label key={tool} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={agentConfig.tools.includes(tool)}
                      onChange={() => toggleTool(tool)}
                      className="rounded"
                    />
                    <span className="text-sm">{tool}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">Capabilities</label>
              <div className="space-y-2">
                <div className="flex space-x-2">
                  <input
                    type="text"
                    placeholder="Add capability..."
                    className="flex-1 input text-sm"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        addCapability(e.target.value);
                        e.target.value = '';
                      }
                    }}
                  />
                  <button
                    onClick={(e) => {
                      const input = e.target.parentElement.querySelector('input');
                      addCapability(input.value);
                      input.value = '';
                    }}
                    className="btn-secondary px-3 py-1 text-sm"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {agentConfig.capabilities.map((capability, idx) => (
                    <span
                      key={idx}
                      className="px-3 py-1 rounded-full bg-unicorn-500/20 text-sm flex items-center space-x-1"
                    >
                      <span>{capability}</span>
                      <button
                        onClick={() => removeCapability(capability)}
                        className="ml-1 hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Persona & System Prompt */}
      <div className="card">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <Code className="w-5 h-5 mr-2 text-emerald-400" />
          Persona & System Prompt
        </h2>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">Persona (Markdown)</label>
            <div className="h-64 rounded-lg overflow-hidden border border-slate-700">
              <MonacoEditor
                height="100%"
                defaultLanguage="markdown"
                theme="vs-dark"
                value={agentConfig.persona}
                onChange={(value) => setAgentConfig({...agentConfig, persona: value})}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'off'
                }}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-2">System Prompt</label>
            <div className="h-64 rounded-lg overflow-hidden border border-slate-700">
              <MonacoEditor
                height="100%"
                defaultLanguage="markdown"
                theme="vs-dark"
                value={agentConfig.systemPrompt}
                onChange={(value) => setAgentConfig({...agentConfig, systemPrompt: value})}
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'off'
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="card bg-gradient-to-br from-unicorn-500/10 to-cyan-500/10 border-unicorn-500/30">
        <h2 className="text-xl font-semibold mb-4 flex items-center">
          <Sparkles className="w-5 h-5 mr-2 text-unicorn-400" />
          Agent Preview
        </h2>
        {agentConfig.name ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center text-white text-2xl">
                {agentConfig.avatar || <Bot className="w-7 h-7" />}
              </div>
              <div>
                <h3 className="text-lg font-semibold">{agentConfig.name}</h3>
                <p className="text-sm text-slate-400">
                  {agentConfig.type} • {agentConfig.domain || 'General'} • {agentConfig.status}
                </p>
              </div>
            </div>

            {agentConfig.persona && (
              <div>
                <h4 className="font-semibold text-sm mb-1">Persona</h4>
                <p className="text-sm text-slate-300">{agentConfig.persona}</p>
              </div>
            )}

            {agentConfig.capabilities.length > 0 && (
              <div>
                <h4 className="font-semibold text-sm mb-2">Capabilities</h4>
                <div className="flex flex-wrap gap-2">
                  {agentConfig.capabilities.map((cap, idx) => (
                    <span key={idx} className="px-2 py-1 rounded bg-unicorn-500/20 text-xs">
                      {cap}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {agentConfig.tools.length > 0 && (
              <div>
                <h4 className="font-semibold text-sm mb-2">Tools</h4>
                <div className="flex flex-wrap gap-2">
                  {agentConfig.tools.map((tool, idx) => (
                    <span key={idx} className="px-2 py-1 rounded bg-cyan-500/20 text-xs">
                      {tool}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-slate-400">
            Configure your agent to see a preview
          </div>
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card max-w-md">
            <div className="flex items-center space-x-3 mb-4">
              <AlertTriangle className="w-6 h-6 text-red-400" />
              <h3 className="text-xl font-semibold">Confirm Delete</h3>
            </div>
            <p className="text-slate-300 mb-6">
              Are you sure you want to delete <strong>{agentToDelete?.name}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setAgentToDelete(null);
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={deleteAgent}
                className="btn-primary bg-red-500 hover:bg-red-600"
              >
                Delete Agent
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentBuilder;