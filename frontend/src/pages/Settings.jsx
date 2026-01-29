import { useState, useEffect } from 'react';
import {
  Settings as SettingsIcon,
  Zap,
  Globe,
  Cpu,
  Database,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Monitor,
  Palette,
  Bell,
  Shield,
  Info
} from 'lucide-react';
import { toast } from 'react-hot-toast';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';

const Settings = () => {
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [preferences, setPreferences] = useState(() => {
    const saved = localStorage.getItem('brigade-preferences');
    return saved ? JSON.parse(saved) : {
      theme: 'dark',
      defaultModel: 'openai/gpt-4o-mini',
      notifications: true,
      compactMode: false,
      streamResponses: true,
    };
  });

  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    localStorage.setItem('brigade-preferences', JSON.stringify(preferences));
  }, [preferences]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const [providersRes, modelsRes] = await Promise.all([
        fetch(`${API_BASE}/providers`),
        fetch(`${API_BASE}/chat/models`),
      ]);
      const providersData = await providersRes.json();
      const modelsData = await modelsRes.json();
      setProviders(providersData.providers || []);
      setModels(modelsData.models || []);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const modelCategories = models.reduce((acc, m) => {
    const cat = m.category || 'unknown';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(m);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
              Settings
            </h1>
            <p className="text-slate-400 mt-1">Platform configuration and preferences</p>
          </div>
          <button
            onClick={loadSettings}
            disabled={loading}
            className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* LLM Provider */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Zap className="w-5 h-5 text-purple-400" />
            <span>LLM Provider</span>
          </h2>
          <div className="space-y-4">
            {providers.map((provider, idx) => (
              <div key={idx} className="p-4 bg-slate-800/50 rounded-lg flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                    <Globe className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-white">{provider.name}</h3>
                    <p className="text-sm text-slate-400">{provider.endpoint || provider.url}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {provider.status === 'connected' || provider.modelsAvailable > 0 ? (
                    <span className="flex items-center space-x-1 text-emerald-400 text-sm">
                      <CheckCircle className="w-4 h-4" />
                      <span>Connected</span>
                    </span>
                  ) : (
                    <span className="flex items-center space-x-1 text-orange-400 text-sm">
                      <AlertCircle className="w-4 h-4" />
                      <span>Disconnected</span>
                    </span>
                  )}
                  {provider.modelsAvailable > 0 && (
                    <span className="text-xs text-slate-500 ml-2">
                      {provider.modelsAvailable} models
                    </span>
                  )}
                </div>
              </div>
            ))}
            {providers.length === 0 && !loading && (
              <p className="text-slate-500 text-center py-4">No providers configured</p>
            )}
          </div>
        </div>

        {/* Available Models */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-blue-400" />
            <span>Available Models ({models.length})</span>
          </h2>
          <div className="space-y-4">
            {Object.entries(modelCategories).map(([category, categoryModels]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-2">
                  {category} ({categoryModels.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {categoryModels.slice(0, 6).map((model, idx) => (
                    <div key={idx} className="p-3 bg-slate-800/50 rounded-lg flex items-center justify-between">
                      <div>
                        <p className="text-sm text-white font-medium">{model.name || model.id}</p>
                        {model.provider && (
                          <p className="text-xs text-slate-500">{model.provider}</p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        {model.speed && (
                          <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            Speed: {model.speed}/5
                          </span>
                        )}
                        {model.quality && (
                          <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-400">
                            Quality: {model.quality}/5
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {categoryModels.length > 6 && (
                  <p className="text-xs text-slate-500 mt-1">+ {categoryModels.length - 6} more</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* User Preferences */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Palette className="w-5 h-5 text-pink-400" />
            <span>Preferences</span>
          </h2>
          <div className="space-y-4">
            {/* Default Model */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">Default Model</p>
                <p className="text-xs text-slate-400">Model used for new conversations</p>
              </div>
              <select
                value={preferences.defaultModel}
                onChange={(e) => {
                  setPreferences({ ...preferences, defaultModel: e.target.value });
                  toast.success('Default model updated');
                }}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white"
              >
                <option value="openai/gpt-4o-mini">GPT-4o Mini (Fast)</option>
                <option value="openai/gpt-4o">GPT-4o (Quality)</option>
                <option value="anthropic/claude-3.5-sonnet">Claude 3.5 Sonnet</option>
                <option value="google/gemini-pro">Gemini Pro</option>
              </select>
            </div>

            {/* Stream Responses */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">Stream Responses</p>
                <p className="text-xs text-slate-400">Show text as it's generated</p>
              </div>
              <button
                onClick={() => setPreferences({ ...preferences, streamResponses: !preferences.streamResponses })}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  preferences.streamResponses ? 'bg-purple-500' : 'bg-slate-700'
                }`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.streamResponses ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {/* Notifications */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">Notifications</p>
                <p className="text-xs text-slate-400">Show toast notifications</p>
              </div>
              <button
                onClick={() => setPreferences({ ...preferences, notifications: !preferences.notifications })}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  preferences.notifications ? 'bg-purple-500' : 'bg-slate-700'
                }`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.notifications ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {/* Compact Mode */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-white">Compact Mode</p>
                <p className="text-xs text-slate-400">Reduce spacing in UI</p>
              </div>
              <button
                onClick={() => setPreferences({ ...preferences, compactMode: !preferences.compactMode })}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  preferences.compactMode ? 'bg-purple-500' : 'bg-slate-700'
                }`}
              >
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                  preferences.compactMode ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>
          </div>
        </div>

        {/* Platform Info */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Info className="w-5 h-5 text-slate-400" />
            <span>Platform Info</span>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">Platform</p>
              <p className="text-white font-semibold">Unicorn Brigade</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">Version</p>
              <p className="text-white font-semibold">v1.0.0</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">Backend</p>
              <p className="text-white font-semibold">FastAPI + LangGraph</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">LLM Gateway</p>
              <p className="text-white font-semibold">Ops-Center</p>
            </div>
          </div>
        </div>

        {/* Keyboard Shortcuts */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-4 flex items-center space-x-2">
            <Monitor className="w-5 h-5 text-cyan-400" />
            <span>Keyboard Shortcuts</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { keys: '⌘ K', action: 'Command palette' },
              { keys: 'Enter', action: 'Send message (in chat)' },
              { keys: 'Shift + Enter', action: 'New line (in chat)' },
              { keys: 'Esc', action: 'Close dialogs' },
            ].map((shortcut, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg">
                <span className="text-sm text-slate-300">{shortcut.action}</span>
                <kbd className="px-2 py-1 bg-slate-700 rounded text-xs text-slate-400 font-mono">
                  {shortcut.keys}
                </kbd>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
