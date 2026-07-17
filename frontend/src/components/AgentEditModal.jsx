import React, { useEffect, useMemo, useState } from 'react';
import { X, Save, Loader2, ChevronDown, Search } from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import api from '../services/api';
import Modal from './ui/Modal';

const FALLBACK_TOOL_IDS = [
  'web_search',
  'http_request',
  'calculator',
  'datetime',
  'json',
  'shell',
  'memory',
  'email',
  'file',
  'code',
  'text',
  'image',
  'database',
  'notify',
  'qrcode',
  'agentic_rag',
  'browser',
  'code_sandbox',
  'screenshot',
  'pdf_extract',
  'doc_generate',
  'data_analyze',
  'url_preview',
  'kg_query',
];

const formatToolLabel = (toolId) => toolId
  .replace(/_/g, ' ')
  .replace(/\b\w/g, (c) => c.toUpperCase());

const normalizeToolNames = (tools = []) => tools
  .map((tool) => (typeof tool === 'string' ? tool : tool?.tool?.name || tool?.name))
  .filter(Boolean);

export default function AgentEditModal({ agent, onClose, onSave }) {
  const [formData, setFormData] = useState({
    name: '',
    displayName: '',
    title: '',
    rank: '',
    bio: '',
    persona: '',
    systemPrompt: '',
    tools: [],
    model: '',
    temperature: 0.7,
    maxTokens: 2000,
    status: 'active'
  });

  const [availableTools, setAvailableTools] = useState([]);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [toolQuery, setToolQuery] = useState('');
  const [toolDropdownOpen, setToolDropdownOpen] = useState(false);

  useEffect(() => {
    if (agent) {
      const normalizedTools = normalizeToolNames(agent.tools || agent.agentTools || []);
      setFormData({
        name: agent.name || '',
        displayName: agent.displayName || '',
        title: agent.title || '',
        rank: agent.rank || '',
        bio: agent.bio || '',
        persona: agent.persona || '',
        systemPrompt: agent.systemPrompt || '',
        tools: normalizedTools,
        model: agent.model || 'openai/gpt-4o-mini',
        temperature: agent.temperature ?? 0.7,
        maxTokens: agent.maxTokens ?? 2000,
        status: agent.status || 'active'
      });
    }

    const fetchTools = async () => {
      try {
        const response = await api.getTools();
        const toolList = response?.tools || [];
        const formatted = toolList.map((tool) => ({
          id: tool.id || tool.name,
          name: tool.name || formatToolLabel(tool.id || tool.name)
        }));
        setAvailableTools(formatted);
      } catch (error) {
        console.error('Failed to fetch tools:', error);
        toast.error('Failed to load available tools, using fallback list');
        setAvailableTools(FALLBACK_TOOL_IDS.map((id) => ({ id, name: formatToolLabel(id) })));
      }
    };

    fetchTools();
  }, [agent]);

  const toolOptions = useMemo(() => {
    const options = availableTools.length
      ? availableTools
      : FALLBACK_TOOL_IDS.map((id) => ({ id, name: formatToolLabel(id) }));

    const selectedSet = new Set(formData.tools);
    const missingSelections = Array.from(selectedSet)
      .filter((toolId) => !options.some((tool) => tool.id === toolId))
      .map((toolId) => ({ id: toolId, name: formatToolLabel(toolId) }));

    return [...missingSelections, ...options];
  }, [availableTools, formData.tools]);

  const filteredTools = useMemo(() => {
    if (!toolQuery) return toolOptions;
    const query = toolQuery.toLowerCase();
    return toolOptions.filter((tool) =>
      tool.name.toLowerCase().includes(query) || tool.id.toLowerCase().includes(query)
    );
  }, [toolOptions, toolQuery]);

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name || formData.name.trim().length === 0) {
      newErrors.name = 'Name is required';
    }

    if (!formData.displayName || formData.displayName.trim().length === 0) {
      newErrors.displayName = 'Display name is required';
    }

    if (!formData.persona || formData.persona.trim().length < 10) {
      newErrors.persona = 'Persona must be at least 10 characters';
    }

    if (formData.temperature < 0 || formData.temperature > 2) {
      newErrors.temperature = 'Temperature must be between 0 and 2';
    }

    if (formData.maxTokens < 100 || formData.maxTokens > 32000) {
      newErrors.maxTokens = 'Max tokens must be between 100 and 32000';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!validateForm()) {
      toast.error('Please fix validation errors');
      return;
    }

    setLoading(true);
    const optimisticAgent = {
      ...agent,
      ...formData,
      tools: formData.tools,
    };
    const rollback = onSave?.(optimisticAgent, { optimistic: true });
    try {
      const updated = await api.updateAgent(agent.id, formData);
      notify.success(`${updated.displayName || formData.displayName} updated successfully`);
      onSave?.(updated, { optimistic: false });
      onClose();
    } catch (error) {
      console.error('Failed to update agent:', error);
      toast.error(error?.message || 'Failed to update agent');
      if (rollback) rollback();
    } finally {
      setLoading(false);
    }
  };

  const toggleTool = (toolId) => {
    setFormData((prev) => ({
      ...prev,
      tools: prev.tools.includes(toolId)
        ? prev.tools.filter((t) => t !== toolId)
        : [...prev.tools, toolId]
    }));
  };

  const selectedToolLabels = toolOptions
    .filter((tool) => formData.tools.includes(tool.id))
    .map((tool) => tool.name);

  return (
    <Modal
      isOpen
      onClose={onClose}
      ariaLabel="Edit Agent"
      showClose={false}
      closeOnBackdrop={false}
      size="3xl"
      panelClassName="bg-slate-800/90 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col focus:outline-none"
    >
        <div className="flex justify-between items-center p-6 border-b border-slate-700/50">
          <div>
            <h2 className="text-2xl font-bold text-white">Edit Agent</h2>
            <p className="text-sm text-slate-400 mt-1">Update {agent.displayName || agent.name}&apos;s configuration</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-3 min-h-[44px] min-w-[44px] hover:bg-slate-700/50 rounded-lg transition-colors"
            disabled={loading}
          >
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-unicorn-400">Basic Information</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  ID/Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className={`w-full bg-slate-700/50 border ${errors.name ? 'border-red-500' : 'border-slate-600'} rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500`}
                  placeholder="agent-id"
                  required
                  disabled={loading}
                />
                {errors.name && <p className="text-red-400 text-sm mt-1">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Display Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={formData.displayName}
                  onChange={(e) => setFormData({ ...formData, displayName: e.target.value })}
                  className={`w-full bg-slate-700/50 border ${errors.displayName ? 'border-red-500' : 'border-slate-600'} rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500`}
                  placeholder="Col. Sterling"
                  required
                  disabled={loading}
                />
                {errors.displayName && <p className="text-red-400 text-sm mt-1">{errors.displayName}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Title
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500"
                  placeholder="Financial Analyst & Strategist"
                  disabled={loading}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Rank
                </label>
                <select
                  aria-label="Rank"
                  value={formData.rank}
                  onChange={(e) => setFormData({ ...formData, rank: e.target.value })}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-unicorn-500"
                  disabled={loading}
                >
                  <option value="">Select Rank</option>
                  <option value="General">General</option>
                  <option value="Colonel">Colonel</option>
                  <option value="Lieutenant Colonel">Lieutenant Colonel</option>
                  <option value="Major">Major</option>
                  <option value="Captain">Captain</option>
                  <option value="Lieutenant">Lieutenant</option>
                  <option value="Sergeant">Sergeant</option>
                  <option value="Corporal">Corporal</option>
                  <option value="Private">Private</option>
                  <option value="Specialist">Specialist</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Bio
              </label>
              <textarea
                value={formData.bio}
                onChange={(e) => setFormData({ ...formData, bio: e.target.value })}
                className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500 min-h-[80px]"
                placeholder="Brief description of the agent's expertise..."
                disabled={loading}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Status
              </label>
              <select
                aria-label="Status"
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-unicorn-500"
                disabled={loading}
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="archived">Archived</option>
              </select>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-unicorn-400">Personality & Behavior</h3>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Persona <span className="text-red-400">*</span>
              </label>
              <textarea
                value={formData.persona}
                onChange={(e) => setFormData({ ...formData, persona: e.target.value })}
                className={`w-full bg-slate-700/50 border ${errors.persona ? 'border-red-500' : 'border-slate-600'} rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500 min-h-[100px]`}
                placeholder="You are a senior financial analyst. You think in terms of ROI..."
                required
                disabled={loading}
              />
              {errors.persona && <p className="text-red-400 text-sm mt-1">{errors.persona}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                System Prompt (Optional)
              </label>
              <textarea
                value={formData.systemPrompt}
                onChange={(e) => setFormData({ ...formData, systemPrompt: e.target.value })}
                className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500 min-h-[120px]"
                placeholder="Detailed instructions for the agent's behavior..."
                disabled={loading}
              />
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-unicorn-400">Model Configuration</h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Model
                </label>
                <select
                  aria-label="Model"
                  value={formData.model}
                  onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-unicorn-500"
                  disabled={loading}
                >
                  <option value="openai/gpt-4o">GPT-4o</option>
                  <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
                  <option value="anthropic/claude-sonnet-4.5">Claude Sonnet 4.5</option>
                  <option value="anthropic/claude-opus-4.5">Claude Opus 4.5</option>
                  <option value="openai/gpt-oss-120b">GPT OSS 120B</option>
                  <option value="openai/gpt-oss-20b">GPT OSS 20B</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Temperature: {formData.temperature}
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={formData.temperature}
                  onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                  className="w-full"
                  disabled={loading}
                />
                {errors.temperature && <p className="text-red-400 text-sm mt-1">{errors.temperature}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">
                  Max Tokens
                </label>
                <input
                  type="number"
                  value={formData.maxTokens}
                  onChange={(e) => setFormData({ ...formData, maxTokens: parseInt(e.target.value, 10) || 0 })}
                  className={`w-full bg-slate-700/50 border ${errors.maxTokens ? 'border-red-500' : 'border-slate-600'} rounded-lg px-4 py-2.5 text-white focus:outline-none focus:ring-2 focus:ring-unicorn-500`}
                  min="100"
                  max="32000"
                  disabled={loading}
                />
                {errors.maxTokens && <p className="text-red-400 text-sm mt-1">{errors.maxTokens}</p>}
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-unicorn-400">Available Tools</h3>

            <div className="relative">
              <button
                type="button"
                onClick={() => setToolDropdownOpen((prev) => !prev)}
                className="w-full flex items-center justify-between bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-left text-white"
                disabled={loading}
              >
                <span className="text-sm">
                  {selectedToolLabels.length
                    ? `${selectedToolLabels.length} tool${selectedToolLabels.length === 1 ? '' : 's'} selected`
                    : 'Select tools'}
                </span>
                <ChevronDown className={`w-4 h-4 transition-transform ${toolDropdownOpen ? 'rotate-180' : ''}`} />
              </button>

              {toolDropdownOpen && (
                <div className="absolute mt-2 w-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-10">
                  <div className="p-3 border-b border-slate-700">
                    <div className="relative">
                      <Search className="w-4 h-4 absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        value={toolQuery}
                        onChange={(e) => setToolQuery(e.target.value)}
                        placeholder="Search tools..."
                        className="w-full pl-8 pr-3 py-2 bg-slate-700/60 border border-slate-600 rounded-md text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500"
                      />
                    </div>
                  </div>
                  <div className="max-h-64 overflow-y-auto p-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                    {filteredTools.map((tool) => (
                      <label
                        key={tool.id}
                        className="flex items-center space-x-2 p-2 bg-slate-700/30 border border-slate-600 rounded-lg cursor-pointer hover:bg-slate-700/50 transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={formData.tools.includes(tool.id)}
                          onChange={() => toggleTool(tool.id)}
                          className="rounded text-unicorn-600 focus:ring-unicorn-500"
                        />
                        <span className="text-sm text-slate-300">{tool.name}</span>
                      </label>
                    ))}
                    {filteredTools.length === 0 && (
                      <p className="text-slate-400 text-sm">No tools match your search.</p>
                    )}
                  </div>
                </div>
              )}
            </div>

            {selectedToolLabels.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {selectedToolLabels.map((toolName) => (
                  <span
                    key={toolName}
                    className="px-2 py-1 rounded-full bg-unicorn-500/20 text-unicorn-300 text-xs"
                  >
                    {toolName}
                  </span>
                ))}
              </div>
            )}
          </div>
        </form>

        <div className="flex justify-end gap-3 p-6 border-t border-slate-700/50 bg-slate-800/50">
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-6 py-2.5 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading}
            className="px-6 py-2.5 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-600 hover:to-unicorn-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Save Changes</span>
              </>
            )}
          </button>
        </div>
    </Modal>
  );
}
