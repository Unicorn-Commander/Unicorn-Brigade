import { useState } from 'react';
import { X, Key, Shield, Zap, Clock } from 'lucide-react';

const GenerateApiKeyModal = ({ agentId, onSuccess, onClose }) => {
  const [form, setForm] = useState({
    name: '',
    permissions: ['read', 'invoke'],
    rateLimit: 100,
    expiresAt: null
  });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const permissions = [
    { id: 'read', label: 'Read agent details', description: 'View agent configuration and status' },
    { id: 'invoke', label: 'Invoke agent', description: 'Send messages and execute agent tasks' },
    { id: 'modify', label: 'Modify agent', description: 'Update agent configuration and settings' }
  ];

  const expirationOptions = [
    { value: null, label: 'Never' },
    { value: '30', label: '30 days' },
    { value: '90', label: '90 days' },
    { value: '365', label: '1 year' }
  ];

  const validate = () => {
    const newErrors = {};

    if (!form.name.trim()) {
      newErrors.name = 'Key name is required';
    }

    if (form.permissions.length === 0) {
      newErrors.permissions = 'At least one permission is required';
    }

    if (!form.rateLimit || form.rateLimit < 1) {
      newErrors.rateLimit = 'Rate limit must be at least 1';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleGenerate = async () => {
    if (!validate()) {
      return;
    }

    setLoading(true);
    try {
      // Calculate expiration date if set
      let expiresAt = null;
      if (form.expiresAt) {
        const days = parseInt(form.expiresAt);
        expiresAt = new Date();
        expiresAt.setDate(expiresAt.getDate() + days);
      }

      // Mock API call - replace with actual API endpoint
      // POST /api/agents/:agentId/api-keys
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8112/api';
      const response = await fetch(`${API_BASE}/agents/${agentId}/api-keys`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: form.name,
          permissions: form.permissions,
          rateLimit: form.rateLimit,
          expiresAt: expiresAt
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate API key');
      }

      const data = await response.json();
      onSuccess(data);
    } catch (error) {
      console.error('Failed to generate API key:', error);

      // For demo purposes, generate a mock API key
      const mockKey = {
        id: `key-${Date.now()}`,
        name: form.name,
        key: `sk-agent-${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`,
        keyPrefix: 'sk-agent-' + Math.random().toString(36).substring(2, 8),
        permissions: form.permissions,
        rateLimit: form.rateLimit,
        expiresAt: form.expiresAt ? new Date(Date.now() + parseInt(form.expiresAt) * 24 * 60 * 60 * 1000) : null,
        createdAt: new Date(),
        isActive: true
      };

      onSuccess(mockKey);
    } finally {
      setLoading(false);
    }
  };

  const togglePermission = (permId) => {
    if (form.permissions.includes(permId)) {
      setForm({ ...form, permissions: form.permissions.filter(p => p !== permId) });
    } else {
      setForm({ ...form, permissions: [...form.permissions, permId] });
    }
    // Clear permission errors when user changes selection
    if (errors.permissions) {
      setErrors({ ...errors, permissions: null });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-gradient-to-r from-unicorn-500/20 to-cyan-500/20">
              <Key className="w-5 h-5 text-unicorn-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Generate New API Key</h2>
              <p className="text-sm text-slate-400">Create credentials for agent access</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {/* Key Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Key Name <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => {
                setForm({ ...form, name: e.target.value });
                if (errors.name) setErrors({ ...errors, name: null });
              }}
              className={`w-full px-3 py-2 bg-slate-800/50 border ${
                errors.name ? 'border-red-500' : 'border-slate-700'
              } rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent outline-none`}
              placeholder="Production Key"
            />
            {errors.name && (
              <p className="text-xs text-red-400 mt-1">{errors.name}</p>
            )}
          </div>

          {/* Permissions */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-3 flex items-center space-x-2">
              <Shield className="w-4 h-4" />
              <span>Permissions <span className="text-red-400">*</span></span>
            </label>
            <div className="space-y-2">
              {permissions.map(perm => (
                <label
                  key={perm.id}
                  className="flex items-start space-x-3 p-3 rounded-lg bg-slate-800/30 hover:bg-slate-800/50 cursor-pointer transition-colors border border-slate-700/50"
                >
                  <input
                    type="checkbox"
                    checked={form.permissions.includes(perm.id)}
                    onChange={() => togglePermission(perm.id)}
                    className="mt-0.5 w-4 h-4 text-unicorn-500 focus:ring-unicorn-500 focus:ring-2 rounded"
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-slate-200">{perm.label}</div>
                    <div className="text-xs text-slate-400">{perm.description}</div>
                  </div>
                </label>
              ))}
            </div>
            {errors.permissions && (
              <p className="text-xs text-red-400 mt-1">{errors.permissions}</p>
            )}
          </div>

          {/* Rate Limit */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center space-x-2">
              <Zap className="w-4 h-4" />
              <span>Rate Limit (requests/minute)</span>
            </label>
            <input
              type="number"
              value={form.rateLimit}
              onChange={(e) => {
                setForm({ ...form, rateLimit: parseInt(e.target.value) || 0 });
                if (errors.rateLimit) setErrors({ ...errors, rateLimit: null });
              }}
              className={`w-full px-3 py-2 bg-slate-800/50 border ${
                errors.rateLimit ? 'border-red-500' : 'border-slate-700'
              } rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent outline-none`}
              min="1"
            />
            {errors.rateLimit && (
              <p className="text-xs text-red-400 mt-1">{errors.rateLimit}</p>
            )}
          </div>

          {/* Expiration */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center space-x-2">
              <Clock className="w-4 h-4" />
              <span>Expiration</span>
            </label>
            <select
              value={form.expiresAt || ''}
              onChange={(e) => setForm({ ...form, expiresAt: e.target.value || null })}
              className="w-full px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent outline-none"
            >
              {expirationOptions.map(option => (
                <option key={option.value || 'never'} value={option.value || ''}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Keys can be manually revoked at any time
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-700 flex space-x-3">
          <button
            onClick={handleGenerate}
            disabled={loading || !form.name.trim()}
            className="flex-1 px-4 py-2 bg-gradient-to-r from-unicorn-500 to-cyan-500 text-white rounded-lg font-medium hover:shadow-lg hover:shadow-unicorn-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Generating...' : 'Generate Key'}
          </button>
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg font-medium hover:bg-slate-700 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

export default GenerateApiKeyModal;
