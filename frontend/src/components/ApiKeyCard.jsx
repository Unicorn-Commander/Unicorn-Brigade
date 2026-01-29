import { useState } from 'react';
import { Key, Trash2, Eye, EyeOff, Clock, CheckCircle, XCircle } from 'lucide-react';

const ApiKeyCard = ({ apiKey, onRevoke, onViewDetails }) => {
  const [showKey, setShowKey] = useState(false);

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const formatLastUsed = (dateString) => {
    if (!dateString) return 'Never';

    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return formatDate(dateString);
  };

  const handleRevoke = () => {
    if (window.confirm(`Are you sure you want to revoke "${apiKey.name}"? This action cannot be undone.`)) {
      onRevoke(apiKey);
    }
  };

  const isExpired = apiKey.expiresAt && new Date(apiKey.expiresAt) < new Date();
  const isActive = (apiKey.isActive !== undefined ? apiKey.isActive : true) && !isExpired;

  return (
    <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700 hover:border-slate-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-1">
            <Key className="w-4 h-4 text-cyan-400" />
            <h4 className="font-medium text-white">{apiKey.name}</h4>
          </div>

          {/* API Key */}
          <div className="flex items-center space-x-2 mb-2">
            <code className="text-sm font-mono text-slate-400">
              {showKey ? apiKey.key || `${apiKey.keyPrefix}...` : `${apiKey.keyPrefix}...`}
            </code>
            {apiKey.key && (
              <button
                onClick={() => setShowKey(!showKey)}
                className="p-1 rounded hover:bg-slate-700 transition-colors"
                title={showKey ? 'Hide key' : 'Show key'}
              >
                {showKey ? (
                  <EyeOff className="w-3 h-3 text-slate-400" />
                ) : (
                  <Eye className="w-3 h-3 text-slate-400" />
                )}
              </button>
            )}
          </div>

          {/* Metadata */}
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            <div className="flex items-center space-x-1">
              <Clock className="w-3 h-3" />
              <span>Created {formatDate(apiKey.createdAt)}</span>
            </div>
            <div className="flex items-center space-x-1">
              <span>Last used: {formatLastUsed(apiKey.lastUsedAt)}</span>
            </div>
            {apiKey.expiresAt && (
              <div className="flex items-center space-x-1">
                <span>
                  {isExpired ? 'Expired' : 'Expires'} {formatDate(apiKey.expiresAt)}
                </span>
              </div>
            )}
          </div>

          {/* Permissions */}
          {apiKey.permissions && apiKey.permissions.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {apiKey.permissions.map((perm, idx) => (
                <span
                  key={idx}
                  className="px-2 py-0.5 rounded text-xs bg-cyan-500/20 text-cyan-300 border border-cyan-500/30"
                >
                  {perm}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Status and Actions */}
        <div className="flex items-start space-x-2 ml-4">
          <div
            className={`px-2 py-1 rounded text-xs font-medium flex items-center space-x-1 ${
              isActive
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                : 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
            }`}
          >
            {isActive ? (
              <>
                <CheckCircle className="w-3 h-3" />
                <span>Active</span>
              </>
            ) : (
              <>
                <XCircle className="w-3 h-3" />
                <span>{isExpired ? 'Expired' : 'Inactive'}</span>
              </>
            )}
          </div>

          <button
            onClick={handleRevoke}
            className="p-2 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors"
            title="Revoke key"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Rate Limit Info */}
      {apiKey.rateLimit && (
        <div className="pt-3 border-t border-slate-700">
          <div className="text-xs text-slate-400">
            Rate limit: <span className="text-slate-300 font-medium">{apiKey.rateLimit}</span> requests/minute
          </div>
        </div>
      )}
    </div>
  );
};

export default ApiKeyCard;
