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
  Sun,
  Moon,
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
import Toggle from '../components/ui/Toggle';
import notify from '../utils/notify';
import { getPreferences, savePreferences } from '../utils/preferences';
import { applyTheme } from '../utils/theme';
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
  // Real, consumed preferences only (see src/utils/preferences.js). defaultModel
  // + streamResponses feed the chat request path (useAgentChat); notifications
  // gates toast output (src/utils/notify.js). Dropped the placebo theme/
  // compactMode toggles that nothing read.
  const [preferences, setPreferences] = useState(getPreferences);

  const updatePref = (key, value) => setPreferences((prev) => ({ ...prev, [key]: value }));

  useEffect(() => {
    loadSettings();
    loadApiKeys();
  }, []);

  useEffect(() => {
    savePreferences(preferences);
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
      notify.success('API key created');
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
      notify.success('API key revoked');
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
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gradient">
              Settings
            </h1>
            <p className="text-muted mt-1">Platform configuration and preferences</p>
          </div>
          <button
            onClick={loadSettings}
            disabled={loading}
            className="px-4 py-2 bg-elevated text-muted rounded-lg hover:bg-elevated transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* LLM Provider */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-4 flex items-center space-x-2">
            <Zap className="w-5 h-5 text-unicorn-400" />
            <span>LLM Provider</span>
          </h2>
          <div className="space-y-4">
            {providers.map((provider, idx) => (
              <div key={idx} className="p-4 bg-elevated/50 rounded-lg flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-10 h-10 rounded-lg bg-unicorn-500/20 flex items-center justify-center">
                    <Globe className="w-5 h-5 text-unicorn-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-fg">{provider.name}</h3>
                    <p className="text-sm text-muted">{provider.endpoint || provider.url}</p>
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
                    <span className="text-xs text-muted ml-2">
                      {provider.latency_ms} ms
                    </span>
                  )}
                </div>
              </div>
            ))}
            {providers.length === 0 && !loading && (
              <p className="text-muted text-center py-4">No providers configured</p>
            )}
          </div>
        </div>

        {/* API Keys */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-1 flex items-center space-x-2">
            <Key className="w-5 h-5 text-cyan-400" />
            <span>API Keys</span>
          </h2>
          <p className="text-sm text-muted mb-4">
            Personal keys for the Brigade API — send them as an <code className="text-muted">X-API-Key</code> header.
            The full key value is shown only once, at creation.
          </p>
          {keysError ? (
            <p className="text-muted text-center py-4">{keysError}</p>
          ) : (
            <>
              <div className="flex items-center space-x-2 mb-4">
                <input
                  type="text"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleCreateKey(); }}
                  placeholder="Key name (e.g. CLI, n8n, staging)"
                  className="flex-1 px-3 py-2 bg-elevated border border-border rounded-lg text-sm text-fg placeholder-slate-500 focus:ring-2 focus:ring-unicorn-500 focus:border-transparent outline-none"
                />
                <button
                  onClick={handleCreateKey}
                  disabled={creatingKey || !newKeyName.trim()}
                  className="px-4 py-2 bg-unicorn-600 hover:bg-unicorn-500 text-white rounded-lg transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creatingKey ? 'Creating…' : 'Create Key'}
                </button>
              </div>
              {keysLoading ? (
                <p className="text-muted text-center py-4">Loading keys…</p>
              ) : apiKeys.length > 0 ? (
                <div className="space-y-3">
                  {apiKeys.map((key) => (
                    <ApiKeyCard key={key.id} apiKey={key} onRevoke={handleRevokeKey} />
                  ))}
                </div>
              ) : (
                <p className="text-muted text-center py-4">No API keys yet — create one above.</p>
              )}
            </>
          )}
        </div>

        {/* Available Models */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-4 flex items-center space-x-2">
            <Cpu className="w-5 h-5 text-blue-400" />
            <span>Available Models ({models.length})</span>
          </h2>
          <div className="space-y-4">
            {Object.entries(modelCategories).map(([category, categoryModels]) => (
              <div key={category}>
                <h3 className="text-sm font-semibold text-muted uppercase tracking-wider mb-2">
                  {category} ({categoryModels.length})
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {categoryModels.slice(0, 6).map((model, idx) => (
                    <div key={idx} className="p-3 bg-elevated/50 rounded-lg flex items-center justify-between">
                      <div>
                        <p className="text-sm text-fg font-medium">{model.name || model.id}</p>
                        {model.provider && (
                          <p className="text-xs text-muted">{model.provider}</p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        {model.speed && (
                          <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                            Speed: {model.speed}/5
                          </span>
                        )}
                        {model.quality && (
                          <span className="text-xs px-2 py-0.5 rounded bg-unicorn-500/20 text-unicorn-400">
                            Quality: {model.quality}/5
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
                {categoryModels.length > 6 && (
                  <p className="text-xs text-muted mt-1">+ {categoryModels.length - 6} more</p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* User Preferences */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-4 flex items-center space-x-2">
            <Palette className="w-5 h-5 text-unicorn-400" />
            <span>Preferences</span>
          </h2>
          <div className="space-y-4">
            {/* Appearance — applied immediately + persisted; 'system' follows the OS.
                Wired to src/utils/theme.js which flips data-theme on <html>. */}
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-fg">Appearance</p>
                <p className="text-xs text-muted">Color theme for the interface</p>
              </div>
              <div
                role="radiogroup"
                aria-label="Color theme"
                className="flex items-center gap-1 rounded-lg border border-border/60 bg-elevated/60 p-1"
              >
                {[
                  { value: 'system', label: 'System', icon: Monitor },
                  { value: 'light', label: 'Light', icon: Sun },
                  { value: 'dark', label: 'Dark', icon: Moon },
                ].map(({ value, label, icon: Icon }) => {
                  const active = preferences.theme === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      onClick={() => {
                        updatePref('theme', value);
                        applyTheme(value);
                      }}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-unicorn-500/60 ${
                        active
                          ? 'bg-unicorn-600 text-white shadow'
                          : 'text-muted hover:text-fg'
                      }`}
                    >
                      <Icon className="w-4 h-4" aria-hidden="true" />
                      <span>{label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Default Model — used by new chats via useAgentChat when no per-window override is set */}
            <div className="flex items-center justify-between">
              <div>
                <label htmlFor="pref-default-model" className="text-sm font-medium text-fg">Default Model</label>
                <p className="text-xs text-muted">Model used for new conversations</p>
              </div>
              <select
                id="pref-default-model"
                value={preferences.defaultModel}
                onChange={(e) => {
                  updatePref('defaultModel', e.target.value);
                  notify.success('Default model updated');
                }}
                className="bg-elevated border border-border rounded-lg px-3 py-2 text-sm text-fg max-w-xs"
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

            {/* Stream Responses — read by useAgentChat to render tokens live vs. all-at-once */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-fg">Stream Responses</p>
                <p className="text-xs text-muted">Show text as it's generated</p>
              </div>
              <Toggle
                checked={preferences.streamResponses}
                onChange={(v) => updatePref('streamResponses', v)}
                label="Stream responses"
              />
            </div>

            {/* Notifications — read by notify.js to gate non-error toasts */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-fg">Notifications</p>
                <p className="text-xs text-muted">Show non-error toast notifications</p>
              </div>
              <Toggle
                checked={preferences.notifications}
                onChange={(v) => updatePref('notifications', v)}
                label="Notifications"
              />
            </div>
          </div>
        </div>

        {/* Platform Info */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-4 flex items-center space-x-2">
            <Info className="w-5 h-5 text-muted" />
            <span>Platform Info</span>
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-elevated/50 rounded-lg">
              <p className="text-xs text-muted">Platform</p>
              <p className="text-fg font-semibold">Unicorn Brigade</p>
            </div>
            <div className="p-3 bg-elevated/50 rounded-lg">
              <p className="text-xs text-muted">Version</p>
              <p className="text-fg font-semibold">{stats?.version ? `v${stats.version}` : '—'}</p>
            </div>
            <div className="p-3 bg-elevated/50 rounded-lg">
              <p className="text-xs text-muted">Backend</p>
              <p className="text-fg font-semibold">FastAPI + SQLAlchemy</p>
            </div>
            <div className="p-3 bg-elevated/50 rounded-lg">
              <p className="text-xs text-muted">Agents</p>
              <p className="text-fg font-semibold">{stats?.totalAgents ?? '—'}</p>
            </div>
          </div>
        </div>

        {/* Keyboard Shortcuts */}
        <div className="backdrop-blur-xl bg-card/50 border border-border/50 rounded-xl p-6">
          <h2 className="text-xl font-bold text-fg mb-4 flex items-center space-x-2">
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
              <div key={idx} className="flex items-center justify-between p-3 bg-elevated/50 rounded-lg">
                <span className="text-sm text-muted">{shortcut.action}</span>
                <kbd className="px-2 py-1 bg-elevated rounded text-xs text-muted font-mono">
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
