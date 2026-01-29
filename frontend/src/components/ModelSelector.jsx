import { useState, useEffect } from 'react';
import { Cpu, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

// Fallback hardcoded models if API fails
const FALLBACK_MODELS = [
  {
    provider: 'OpenAI',
    models: [
      { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', pricing: '$10', contextWindow: '128K' },
      { id: 'gpt-4', name: 'GPT-4', pricing: '$30', contextWindow: '8K' },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', pricing: '$0.50', contextWindow: '16K' }
    ]
  },
  {
    provider: 'Anthropic',
    models: [
      { id: 'claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', pricing: '$3', contextWindow: '200K' },
      { id: 'claude-3-opus', name: 'Claude 3 Opus', pricing: '$15', contextWindow: '200K' },
      { id: 'claude-3-haiku', name: 'Claude 3 Haiku', pricing: '$0.25', contextWindow: '200K' }
    ]
  },
  {
    provider: 'Google',
    models: [
      { id: 'gemini-pro', name: 'Gemini Pro', pricing: '$0.50', contextWindow: '32K' },
      { id: 'gemini-pro-vision', name: 'Gemini Pro Vision', pricing: '$0.50', contextWindow: '16K' }
    ]
  },
  {
    provider: 'Meta',
    models: [
      { id: 'llama-3-70b', name: 'Llama 3 70B', pricing: '$0.70', contextWindow: '8K' },
      { id: 'llama-3-8b', name: 'Llama 3 8B', pricing: '$0.10', contextWindow: '8K' }
    ]
  }
];

const ModelSelector = ({
  value,
  onChange,
  disabled = false,
  allowAIChoice = false,
  className = ''
}) => {
  const [modelGroups, setModelGroups] = useState(FALLBACK_MODELS);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_BASE}/agent-builder/info`);
      const availableModels = response.data?.capabilities?.availableModels;
      if (availableModels && Array.isArray(availableModels) && availableModels.length > 0) {
        const grouped = groupModelsByProvider(availableModels);
        if (grouped.length > 0) {
          setModelGroups(grouped);
        }
      }
      // If availableModels is empty or not present, keep fallback models silently
    } catch (error) {
      console.error('Failed to load models, using fallback:', error);
      setError('Using cached model list');
      // Keep fallback models
    } finally {
      setLoading(false);
    }
  };

  const groupModelsByProvider = (models) => {
    const groups = {};
    models.forEach(model => {
      const provider = model.provider || 'Other';
      if (!groups[provider]) {
        groups[provider] = [];
      }
      groups[provider].push(model);
    });

    return Object.entries(groups).map(([provider, models]) => ({
      provider,
      models
    }));
  };

  const getSelectedModelInfo = () => {
    if (!value || value === 'ai-choice') return null;

    for (const group of modelGroups) {
      const model = group.models.find(m => m.id === value);
      if (model) return model;
    }
    return null;
  };

  const selectedModel = getSelectedModelInfo();

  return (
    <div className="space-y-2">
      <div className="relative">
        <select
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || loading}
          className={`w-full px-4 py-2.5 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent appearance-none pr-10 disabled:opacity-50 disabled:cursor-not-allowed ${className}`}
        >
          {allowAIChoice && (
            <option value="ai-choice">Let The General decide</option>
          )}

          {modelGroups.map(group => (
            <optgroup key={group.provider} label={group.provider}>
              {group.models.map(model => (
                <option key={model.id} value={model.id}>
                  {model.name} {model.pricing && `- ${model.pricing}/1M`}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        <div className="absolute right-3 top-1/2 transform -translate-y-1/2 pointer-events-none">
          <Cpu className="w-4 h-4 text-slate-400" />
        </div>
      </div>

      {selectedModel && (
        <div className="flex items-center space-x-4 text-xs text-slate-400 bg-slate-800/30 rounded-lg p-2 border border-slate-700/50">
          <div className="flex items-center space-x-1">
            <span className="text-slate-500">Provider:</span>
            <span className="text-unicorn-400 font-medium">{selectedModel.provider || 'Unknown'}</span>
          </div>
          {selectedModel.contextWindow && (
            <div className="flex items-center space-x-1">
              <span className="text-slate-500">Context:</span>
              <span className="text-cyan-400 font-medium">{selectedModel.contextWindow}</span>
            </div>
          )}
          {selectedModel.pricing && (
            <div className="flex items-center space-x-1">
              <span className="text-slate-500">Cost:</span>
              <span className="text-emerald-400 font-medium">{selectedModel.pricing}/1M tokens</span>
            </div>
          )}
        </div>
      )}

      {error && (
        <div className="flex items-center space-x-2 text-xs text-amber-400">
          <AlertCircle className="w-3 h-3" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <p className="text-xs text-slate-400 italic">Loading available models...</p>
      )}
    </div>
  );
};

export default ModelSelector;
