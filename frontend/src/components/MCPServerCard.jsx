import { useState } from 'react';
import { Play, Square, Eye, Package, CheckCircle, XCircle, Loader2, AlertCircle, Settings } from 'lucide-react';
import { toast } from 'react-hot-toast';

// Server Icons (matching category)
const serverIcons = {
  // Infrastructure & Development
  github: '🐙',
  playwright: '🎭',
  slack: '💬',
  postgresql: '🐘',
  filesystem: '📁',
  memory: '🧠',
  fetch: '🌐',
  brave_search: '🔍',
  google_drive: '📂',
  puppeteer: '🎪',

  // Phase 1
  stripe: '💳',
  linear: '📊',
  git: '📦',
  notion: '📝',

  // Phase 2
  airtable: '🗂️',
  vercel: '▲',
  cloudflare: '☁️',
  supabase: '⚡',

  // Phase 3
  twilio: '📞',
  sendgrid: '📧',
  sentry: '🐛',
  monday: '📅',

  // Phase 4+
  shopify: '🛍️',
  salesforce: '☁️',
  zendesk: '🎫',
  jira: '📋',
  hubspot: '🎯',
  mailchimp: '📬',
  semrush: '📈',
  zapier: '⚡',
  amplitude: '📊',
  mixpanel: '📈',
  hotjar: '🔥',
  fullstory: '🎬',
};

const MCPServerCard = ({ server, onStart, onStop, onViewTools, onManage, isLoading, statusOverride }) => {
  const [actionLoading, setActionLoading] = useState(false);
  const isRunning = statusOverride ? statusOverride === 'running' : (server.status === 'running' || server.running);
  const icon = serverIcons[server.name] || '🔧';

  const handleStart = async () => {
    setActionLoading(true);
    try {
      await onStart(server.name);
      toast.success(`${server.display_name} started`);
    } catch (error) {
      toast.error(`Failed to start server: ${error.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      await onStop(server.name);
      toast.success(`${server.display_name} stopped`);
    } catch (error) {
      toast.error(`Failed to stop server: ${error.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="card hover:shadow-lg hover:shadow-purple-500/10 transition-all group">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className="text-3xl">{icon}</div>
          <div>
            <h3 className="font-semibold text-white group-hover:text-purple-400 transition-colors">
              {server.display_name}
            </h3>
            <p className="text-xs text-slate-500">{server.name}</p>
          </div>
        </div>

        {/* Status Badge */}
        <div className="flex items-center space-x-2">
          {isRunning ? (
            <span className="flex items-center space-x-1 px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400 text-xs">
              <CheckCircle className="w-3 h-3" />
              <span>Running</span>
            </span>
          ) : (
            <span className="flex items-center space-x-1 px-2 py-1 rounded-full bg-slate-500/20 text-slate-400 text-xs">
              <XCircle className="w-3 h-3" />
              <span>Stopped</span>
            </span>
          )}
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-slate-400 mb-4 line-clamp-2">
        {server.description}
      </p>

      {/* Category Tags */}
      <div className="flex flex-wrap gap-2 mb-4">
        <span className="px-2 py-1 rounded bg-purple-500/20 text-purple-400 text-xs">
          {server.category}
        </span>
        <span className="px-2 py-1 rounded bg-blue-500/20 text-blue-400 text-xs">
          Phase {server.phase}
        </span>
        {server.transport && (
          <span className="px-2 py-1 rounded bg-cyan-500/20 text-cyan-400 text-xs">
            {server.transport.toUpperCase()}
          </span>
        )}
      </div>

      {/* Tool Count */}
      <div className="flex items-center space-x-2 mb-4 text-slate-500 text-sm">
        <Package className="w-4 h-4" />
        <span>{server.tool_count || server.capabilities?.length || 0} tools available</span>
      </div>

      {/* Config Requirements */}
      {server.env_vars && server.env_vars.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center space-x-2 text-xs text-amber-400 mb-1">
            <AlertCircle className="w-3 h-3" />
            <span>Requires configuration</span>
          </div>
          <div className="flex flex-wrap gap-1">
            {server.env_vars.slice(0, 3).map((env, idx) => (
              <span key={idx} className="px-2 py-0.5 rounded bg-slate-800/50 text-slate-500 text-xs font-mono">
                {env}
              </span>
            ))}
            {server.env_vars.length > 3 && (
              <span className="px-2 py-0.5 rounded bg-slate-800/50 text-slate-500 text-xs">
                +{server.env_vars.length - 3}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex space-x-2">
        {isRunning ? (
          <button
            onClick={handleStop}
            disabled={actionLoading || isLoading}
            className="flex-1 px-3 py-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-lg transition-colors flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {actionLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Square className="w-4 h-4" />
            )}
            <span>Stop</span>
          </button>
        ) : (
          <button
            onClick={handleStart}
            disabled={actionLoading || isLoading}
            className="flex-1 px-3 py-2 bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 rounded-lg transition-colors flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            {actionLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            <span>Start</span>
          </button>
        )}

        <button
          onClick={() => onViewTools(server)}
          className="px-3 py-2 bg-purple-500/20 text-purple-400 hover:bg-purple-500/30 rounded-lg transition-colors flex items-center justify-center space-x-2"
        >
          <Eye className="w-4 h-4" />
          <span>Tools</span>
        </button>

        {onManage && (
          <button
            onClick={() => onManage(server)}
            className="px-3 py-2 bg-slate-700/60 text-slate-200 hover:bg-slate-600 rounded-lg transition-colors flex items-center justify-center space-x-2"
          >
            <Settings className="w-4 h-4" />
            <span>Manage</span>
          </button>
        )}
      </div>
    </div>
  );
};

export default MCPServerCard;
