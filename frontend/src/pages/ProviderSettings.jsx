import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Key,
  Plus,
  Save,
  Trash2,
  CheckCircle,
  AlertCircle,
  Loader2,
  Eye,
  EyeOff,
  TestTube,
  Shield,
  DollarSign,
  Zap,
  Info
} from 'lucide-react';
import api from '../services/api';
import toast from 'react-hot-toast';

const ProviderSettings = () => {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);
  const [testingProvider, setTestingProvider] = useState(null);
  const [showApiKeys, setShowApiKeys] = useState({});
  const [visibleKeys, setVisibleKeys] = useState({});

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    type: 'openrouter',
    apiKey: '',
    endpoint: '',
    isDefault: false,
    config: {
      model: '',
      maxTokens: 4096,
      temperature: 0.7
    }
  });

  // Provider presets
  const providerPresets = {
    openrouter: {
      name: 'OpenRouter',
      endpoint: 'https://openrouter.ai/api/v1',
      models: ['claude-3-opus-20240229', 'gpt-4-turbo-preview', 'mistral-large'],
      icon: '🌐',
      description: 'Access multiple AI models through one API',
      pricing: 'Pay per token across models'
    },
    openai: {
      name: 'OpenAI',
      endpoint: 'https://api.openai.com/v1',
      models: ['gpt-4-turbo-preview', 'gpt-3.5-turbo'],
      icon: '🤖',
      description: 'ChatGPT and GPT-4 models',
      pricing: '$0.01-0.03 per 1K tokens'
    },
    anthropic: {
      name: 'Anthropic',
      endpoint: 'https://api.anthropic.com/v1',
      models: ['claude-3-opus-20240229', 'claude-3-sonnet-20240229'],
      icon: '🔮',
      description: 'Claude models with 200K context',
      pricing: '$0.015-0.075 per 1K tokens'
    },
    google: {
      name: 'Google AI',
      endpoint: 'https://generativelanguage.googleapis.com/v1',
      models: ['gemini-pro', 'gemini-pro-vision'],
      icon: '🌈',
      description: 'Gemini models with multimodal support',
      pricing: 'Free tier available'
    },
    ollama: {
      name: 'Ollama',
      endpoint: 'http://localhost:11434',
      models: ['llama2', 'mistral', 'codellama'],
      icon: '🦙',
      description: 'Local models, no API costs',
      pricing: 'Free (self-hosted)'
    }
  };

  useEffect(() => {
    fetchProviders();
  }, []);

  const fetchProviders = async () => {
    try {
      setLoading(true);
      const data = await api.getProviders();
      setProviders(data);
    } catch (error) {
      toast.error('Failed to fetch providers');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSetup = async () => {
    const apiKey = prompt('Enter your OpenRouter API key:');
    if (!apiKey) return;

    try {
      const response = await api.quickSetupOpenRouter(apiKey);

      // Show success with model count
      if (response.models && response.models.length > 0) {
        toast.success(`OpenRouter configured! Found ${response.models.length} models available.`);

        // Show some example models
        const examples = response.models.slice(0, 5).join(', ');
        setTimeout(() => {
          toast.success(`Models include: ${examples}...`, { duration: 5000 });
        }, 500);
      } else {
        toast.success('OpenRouter configured successfully!');
      }

      // Refresh providers list
      fetchProviders();
    } catch (error) {
      toast.error('Failed to setup OpenRouter');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      let provider;
      if (editingProvider) {
        provider = await api.updateProvider(editingProvider.id, formData);
        setProviders(providers.map(p => p.id === provider.id ? provider : p));
        toast.success('Provider updated successfully');
      } else {
        // Set endpoint based on type
        const preset = providerPresets[formData.type];
        const dataToSend = {
          ...formData,
          endpoint: formData.endpoint || preset.endpoint,
          config: JSON.stringify(formData.config)
        };

        provider = await api.createProvider(dataToSend);
        setProviders([...providers, provider]);
        toast.success('Provider added successfully');
      }

      // Reset form
      setFormData({
        name: '',
        type: 'openrouter',
        apiKey: '',
        endpoint: '',
        isDefault: false,
        config: { model: '', maxTokens: 4096, temperature: 0.7 }
      });
      setShowAddForm(false);
      setEditingProvider(null);
    } catch (error) {
      toast.error(error.message || 'Failed to save provider');
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;

    try {
      await api.deleteProvider(id);
      setProviders(providers.filter(p => p.id !== id));
      toast.success('Provider deleted');
    } catch (error) {
      toast.error('Failed to delete provider');
    }
  };

  const handleTest = async (provider) => {
    setTestingProvider(provider.id);
    try {
      const result = await api.testProvider(provider.id);

      // Show success with model info if available
      if (result.models && result.models.length > 0) {
        toast.success(`${provider.name} is working! Found ${result.models.length} models.`);

        // Show some example models
        const examples = result.models.slice(0, 5).join(', ');
        setTimeout(() => {
          toast.success(`Available models: ${examples}...`, { duration: 5000 });
        }, 500);

        // Update provider's config with new models
        if (result.models.length > 0) {
          await api.updateProvider(provider.id, {
            ...provider,
            config: {
              ...provider.config,
              models: result.models
            }
          });
          // Refresh providers list
          fetchProviders();
        }
      } else {
        toast.success(`${provider.name} is working correctly!`);
      }
    } catch (error) {
      toast.error(`Test failed: ${error.message}`);
    } finally {
      setTestingProvider(null);
    }
  };

  const handleSetDefault = async (provider) => {
    try {
      await api.setDefaultProvider(provider.id);
      setProviders(providers.map(p => ({
        ...p,
        isDefault: p.id === provider.id
      })));
      toast.success(`${provider.name} set as default`);
    } catch (error) {
      toast.error('Failed to set default provider');
    }
  };

  const toggleApiKeyVisibility = async (id) => {
    const isVisible = showApiKeys[id];

    if (!isVisible) {
      // Fetch the actual key when showing
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8112'}/api/providers?showKeys=true`);
        const data = await response.json();
        const provider = data.find(p => p.id === id);

        if (provider) {
          setVisibleKeys(prev => ({ ...prev, [id]: provider.apiKey }));
        }
      } catch (error) {
        console.error('Error fetching API key:', error);
      }
    }

    setShowApiKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 animate-spin text-unicorn-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gradient">AI Provider Settings</h1>
          <p className="text-slate-400 mt-1">Configure your AI model providers and API keys</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={handleQuickSetup}
            className="btn-secondary flex items-center space-x-2"
          >
            <Zap className="w-5 h-5" />
            <span>Quick Setup OpenRouter</span>
          </button>
          <button
            onClick={() => setShowAddForm(true)}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Add Provider</span>
          </button>
        </div>
      </div>

      {/* Provider List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {providers.map((provider) => {
          const preset = providerPresets[provider.type];
          const config = typeof provider.config === 'string'
            ? JSON.parse(provider.config)
            : provider.config;

          return (
            <motion.div
              key={provider.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="card relative"
            >
              {provider.isDefault && (
                <div className="absolute -top-2 -right-2">
                  <span className="bg-emerald-500 text-white text-xs px-2 py-1 rounded-full">
                    Default
                  </span>
                </div>
              )}

              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center space-x-3">
                  <div className="text-3xl">{preset?.icon || '🤖'}</div>
                  <div>
                    <h3 className="text-xl font-semibold">{provider.name}</h3>
                    <p className="text-sm text-slate-400">{preset?.description}</p>
                  </div>
                </div>
                {provider.isActive ? (
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-amber-500" />
                )}
              </div>

              <div className="space-y-3">
                {/* API Key */}
                <div>
                  <label className="text-xs text-slate-500">API Key</label>
                  <div className="flex items-center space-x-2">
                    <input
                      type={showApiKeys[provider.id] ? 'text' : 'password'}
                      value={showApiKeys[provider.id] ? (visibleKeys[provider.id] || provider.apiKey) : '••••••••••••••••'}
                      readOnly
                      className="flex-1 input text-sm font-mono"
                    />
                    <button
                      onClick={() => toggleApiKeyVisibility(provider.id)}
                      className="p-2 glass-hover rounded-lg"
                    >
                      {showApiKeys[provider.id] ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Endpoint */}
                <div>
                  <label className="text-xs text-slate-500">Endpoint</label>
                  <input
                    type="text"
                    value={provider.endpoint}
                    readOnly
                    className="w-full input text-sm"
                  />
                </div>

                {/* Models */}
                {config?.models && config.models.length > 0 && (
                  <div>
                    <label className="text-xs text-slate-500">Available Models ({config.models.length})</label>
                    <div className="mt-1 text-xs text-slate-400">
                      {config.models.slice(0, 3).join(', ')}
                      {config.models.length > 3 && `, +${config.models.length - 3} more`}
                    </div>
                  </div>
                )}

                {/* Default Model */}
                {config?.settings?.defaultModel && (
                  <div>
                    <label className="text-xs text-slate-500">Default Model</label>
                    <input
                      type="text"
                      value={config.settings.defaultModel}
                      readOnly
                      className="w-full input text-sm"
                    />
                  </div>
                )}

                {/* Pricing */}
                {preset?.pricing && (
                  <div className="flex items-center space-x-2 text-sm text-slate-400">
                    <DollarSign className="w-4 h-4" />
                    <span>{preset.pricing}</span>
                  </div>
                )}

                {/* Actions */}
                <div className="flex space-x-2 pt-2">
                  <button
                    onClick={() => handleTest(provider)}
                    disabled={testingProvider === provider.id}
                    className="flex-1 btn-secondary text-sm flex items-center justify-center space-x-1"
                  >
                    {testingProvider === provider.id ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <TestTube className="w-4 h-4" />
                    )}
                    <span>Test</span>
                  </button>

                  {!provider.isDefault && (
                    <button
                      onClick={() => handleSetDefault(provider)}
                      className="flex-1 btn-secondary text-sm flex items-center justify-center space-x-1"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>Set Default</span>
                    </button>
                  )}

                  <button
                    onClick={() => {
                      setEditingProvider(provider);
                      setFormData({
                        name: provider.name,
                        type: provider.type,
                        apiKey: provider.apiKey,
                        endpoint: provider.endpoint,
                        isDefault: provider.isDefault,
                        config: typeof provider.config === 'string'
                          ? JSON.parse(provider.config)
                          : provider.config
                      });
                      setShowAddForm(true);
                    }}
                    className="p-2 glass-hover rounded-lg"
                  >
                    <Save className="w-4 h-4" />
                  </button>

                  <button
                    onClick={() => handleDelete(provider.id)}
                    className="p-2 glass-hover rounded-lg text-red-400 hover:text-red-300"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </motion.div>
          );
        })}

        {/* Empty State */}
        {providers.length === 0 && (
          <div className="col-span-2 card text-center py-12">
            <Key className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold mb-2">No Providers Configured</h3>
            <p className="text-slate-400 mb-6">
              Add an AI provider to start using agents
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="btn-primary mx-auto"
            >
              Add Your First Provider
            </button>
          </div>
        )}
      </div>

      {/* Add/Edit Form Modal */}
      <AnimatePresence>
        {showAddForm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowAddForm(false)}
          >
            <motion.div
              initial={{ scale: 0.9 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.9 }}
              className="card max-w-2xl w-full max-h-[90vh] overflow-y-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-2xl font-bold mb-6">
                {editingProvider ? 'Edit Provider' : 'Add AI Provider'}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Provider Type */}
                <div>
                  <label className="block text-sm font-medium mb-2">Provider Type</label>
                  <select
                    value={formData.type}
                    onChange={(e) => {
                      const type = e.target.value;
                      const preset = providerPresets[type];
                      setFormData({
                        ...formData,
                        type,
                        endpoint: preset.endpoint,
                        name: formData.name || preset.name
                      });
                    }}
                    className="w-full input"
                    disabled={editingProvider}
                  >
                    {Object.entries(providerPresets).map(([key, preset]) => (
                      <option key={key} value={key}>
                        {preset.icon} {preset.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Name */}
                <div>
                  <label className="block text-sm font-medium mb-2">Display Name</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full input"
                    placeholder="e.g., My OpenRouter Account"
                    required
                  />
                </div>

                {/* API Key */}
                <div>
                  <label className="block text-sm font-medium mb-2">
                    API Key
                    <span className="text-xs text-slate-500 ml-2">
                      <Shield className="w-3 h-3 inline mr-1" />
                      Encrypted before storage
                    </span>
                  </label>
                  <input
                    type="password"
                    value={formData.apiKey}
                    onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                    className="w-full input"
                    placeholder="sk-..."
                    required={!editingProvider}
                  />
                </div>

                {/* Endpoint */}
                <div>
                  <label className="block text-sm font-medium mb-2">
                    API Endpoint
                    <span className="text-xs text-slate-500 ml-2">(optional)</span>
                  </label>
                  <input
                    type="url"
                    value={formData.endpoint}
                    onChange={(e) => setFormData({ ...formData, endpoint: e.target.value })}
                    className="w-full input"
                    placeholder={providerPresets[formData.type].endpoint}
                  />
                </div>

                {/* Default Model */}
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Default Model
                    <span className="text-xs text-slate-500 ml-2">(optional)</span>
                  </label>
                  <select
                    value={formData.config.model}
                    onChange={(e) => setFormData({
                      ...formData,
                      config: { ...formData.config, model: e.target.value }
                    })}
                    className="w-full input"
                  >
                    <option value="">Select a model...</option>
                    {providerPresets[formData.type].models.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                </div>

                {/* Temperature */}
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Temperature: {formData.config.temperature}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={formData.config.temperature}
                    onChange={(e) => setFormData({
                      ...formData,
                      config: { ...formData.config, temperature: parseFloat(e.target.value) }
                    })}
                    className="w-full"
                  />
                </div>

                {/* Max Tokens */}
                <div>
                  <label className="block text-sm font-medium mb-2">Max Tokens</label>
                  <input
                    type="number"
                    value={formData.config.maxTokens}
                    onChange={(e) => setFormData({
                      ...formData,
                      config: { ...formData.config, maxTokens: parseInt(e.target.value) }
                    })}
                    className="w-full input"
                    min="1"
                    max="128000"
                  />
                </div>

                {/* Set as Default */}
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="isDefault"
                    checked={formData.isDefault}
                    onChange={(e) => setFormData({ ...formData, isDefault: e.target.checked })}
                    className="rounded"
                  />
                  <label htmlFor="isDefault" className="text-sm">
                    Set as default provider
                  </label>
                </div>

                {/* Actions */}
                <div className="flex space-x-3 pt-4">
                  <button type="submit" className="btn-primary flex-1">
                    {editingProvider ? 'Update Provider' : 'Add Provider'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddForm(false);
                      setEditingProvider(null);
                      setFormData({
                        name: '',
                        type: 'openrouter',
                        apiKey: '',
                        endpoint: '',
                        isDefault: false,
                        config: { model: '', maxTokens: 4096, temperature: 0.7 }
                      });
                    }}
                    className="btn-secondary flex-1"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Info Box */}
      <div className="card bg-blue-500/10 border-blue-500/30">
        <div className="flex items-start space-x-3">
          <Info className="w-5 h-5 text-blue-400 mt-1" />
          <div className="flex-1">
            <h3 className="font-semibold text-blue-400 mb-1">Getting Started</h3>
            <p className="text-sm text-slate-300">
              1. Click "Quick Setup OpenRouter" for the fastest setup with access to multiple models<br />
              2. Or click "Add Provider" to configure OpenAI, Anthropic, Google, or local Ollama<br />
              3. Test your connection to ensure everything works<br />
              4. Start chatting with agents using real AI models!
            </p>
            <p className="text-sm text-slate-400 mt-2">
              <strong>Free models on OpenRouter:</strong> meta-llama/llama-3-8b-instruct:free,
              mistralai/mistral-7b-instruct:free, google/gemma-7b-it:free
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProviderSettings;