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
  Key,
  Info
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';
import ApiKeyCard from '../components/ApiKeyCard';
import KeyRevealModal from '../components/KeyRevealModal';
import { apiJson } from '../services/http';

const Settings = () => {
  const [providers, setProviders] = useState([]);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [apiKeys, setApiKeys] = useState([]);
  const [keysLoading, setKeysLoading] = useState(true);
  const [keysError, setKeysError] = useState(null);
  const [newKeyName, setNewKeyName] = useState('');
  const [creatingKey, setCreatingKey] = useState(false);
  const [revealedKey, setRevealedKey] = useState(null);
  const [preferences, setPreferences] = useState(() => {
    const saved = localStorage.getItem('brigade-preferences');
    return saved ? JSON.parse(saved) : {
      theme: 'dark',
      defaultModel: '',
      notifications: true,
      compactMode: false,
      streamResponses: true,
    };
  });

  useEffect(() => {
    loadSettings();
    loadApiKeys();
  }, []);

  useEffect(() => {
    localStorage.setItem('brigade-preferences', JSON.stringify(preferences));
  }, [preferences]);

  const loadSettings = async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        apiJson('/providers'),
        apiJson('/chat/models'),
        apiJson('/stats'),
      ]);
      const providersData = results[0].status === 'fulfilled' ? results[0].value : {};
      const modelsData = results[1].status === 'fulfilled' ? results[1].value : {};
      const statsData = results[2].status === 'fulfilled' ? results[2].value : null;
      setProviders(providersData.providers || []);
      setModels(modelsData.models || []);
      setStats(statsData);
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadApiKeys = async () => {
    setKeysLoading(true);
    try {
      const data = await apiJson('/users/me/api-keys', { redirectOn401: false });
      setApiKeys(data.keys || []);
      setKeysError(null);
    } catch (error) {
      setApiKeys([]);
      setKeysError(
        error.status === 401
          ? 'Sign in to manage your API keys'
          : error.message || 'Failed to load API keys'
      );
    } finally {
      setKeysLoading(false);
    }
  };

  const handleCreateKey = async () => {
    const name = newKeyName.trim();
    if (!name || creatingKey) return;
    setCreatingKey(true);
    try {
      const created = await apiJson('/users/me/api-keys', {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
      setRevealedKey(created); // full key value is only returned once
      setNewKeyName('');
      toast.success('API key created');
      await loadApiKeys();
    } catch (error) {
      toast.error(error.message || 'Failed to create API key');
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (key) => {
    try {
      await apiJson(`/users/me/api-keys/${key.id}`, { method: 'DELETE' });
      toast.success('API key revoked');
      setApiKeys(prev => prev.filter(k => k.id !== key.id));
    } catch (error) {
      toast.error(error.message || 'Failed to revoke API key');
    }
  };

  const modelCategories = models.reduce((acc, m) => {
    const cat = m.category || 'unknown';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(m);
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <Breadcrumbs />
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
                  {provider.status === 'connected' ? (
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
                  {typeof provider.latency_ms === 'number' && (
                    <span className="text-xs text-slate-500 ml-2">
                      {provider.latency_ms} ms
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

        {/* API Keys */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-white mb-1 flex items-center space-x-2">
            <Key className="w-5 h-5 text-cyan-400" />
            <span>API Keys</span>
          </h2>
          <p className="text-sm text-slate-400 mb-4">
            Personal keys for the Brigade API — send them as an <code className="text-slate-300">X-API-Key</code> header.
            The full key value is shown only once, at creation.
          </p>
          {keysError ? (
            <p className="text-slate-500 text-center py-4">{keysError}</p>
          ) : (
            <>
              <div className="flex items-center space-x-2 mb-4">
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleCreateKey(); }}
                  placeholder="Key name (e.g. CLI, n8n, staging)"
                  className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:ring-2 focus:ring-purple-500 focus:border-transparent outline-none"
                />
                <button
                  onClick={handleCreateKey}
                  disabled={creatingKey || !newKeyName.trim()}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creatingKey ? 'Creating…' : 'Create Key'}
                </button>
              </div>
              {keysLoading ? (
                <p className="text-slate-500 text-center py-4">Loading keys…</p>
              ) : apiKeys.length > 0 ? (
                <div className="space-y-3">
                  {apiKeys.map((key) => (
                    <ApiKeyCard key={key.id} apiKey={key} onRevoke={handleRevokeKey} />
                  ))}
                </div>
              ) : (
                <p className="text-slate-500 text-center py-4">No API keys yet — create one above.</p>
              )}
            </>
          )}
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
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white max-w-xs"
              >
                <option value="">Auto (server default)</option>
                {models.map((model, idx) => (
                  <option key={idx} value={model.id || model.name}>
                    {model.name || model.id}
                    {model.provider ? ` (${model.provider})` : ''}
                  </option>
                ))}
                {models.length === 0 && (
                  <option disabled>Loading models...</option>
                )}
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
              <p className="text-white font-semibold">{stats?.version ? `v${stats.version}` : '—'}</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">Backend</p>
              <p className="text-white font-semibold">FastAPI + SQLAlchemy</p>
            </div>
            <div className="p-3 bg-slate-800/50 rounded-lg">
              <p className="text-xs text-slate-400">Agents</p>
              <p className="text-white font-semibold">{stats?.totalAgents ?? '—'}</p>
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

      {/* One-time reveal of a freshly created key */}
      {revealedKey && (
        <KeyRevealModal apiKey={revealedKey} onClose={() => setRevealedKey(null)} />
      )}
    </div>
  );
};

export default Settings;
