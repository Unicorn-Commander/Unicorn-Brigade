import { useState } from 'react';
import { X, Search, Wrench, Copy, ExternalLink } from 'lucide-react';
import { toast } from 'react-hot-toast';

const MCPToolList = ({ server, tools, onClose }) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredTools = tools.filter(tool => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      tool.name?.toLowerCase().includes(query) ||
      tool.description?.toLowerCase().includes(query)
    );
  });

  const copyToolName = (toolName) => {
    navigator.clipboard.writeText(toolName);
    toast.success('Tool name copied');
  };

  const serverIcons = {
    github: '🐙', playwright: '🎭', slack: '💬', postgresql: '🐘',
    filesystem: '📁', memory: '🧠', fetch: '🌐', brave_search: '🔍',
    google_drive: '📂', puppeteer: '🎪', stripe: '💳', linear: '📊',
    git: '📦', notion: '📝', airtable: '🗂️', vercel: '▲',
    cloudflare: '☁️', supabase: '⚡', twilio: '📞', sendgrid: '📧',
    sentry: '🐛', monday: '📅', shopify: '🛍️', salesforce: '☁️',
    zendesk: '🎫', jira: '📋', hubspot: '🎯', mailchimp: '📬',
    semrush: '📈', zapier: '⚡', amplitude: '📊', mixpanel: '📈',
    hotjar: '🔥', fullstory: '🎬',
  };

  const icon = serverIcons[server.name] || '🔧';

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-6 z-50"
      onClick={onClose}
    >
      <div
        className="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-4xl w-full max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex items-center space-x-4">
            <div className="text-4xl">{icon}</div>
            <div>
              <h2 className="text-2xl font-bold text-white">{server.display_name}</h2>
              <p className="text-slate-400">
                {tools.length} tool{tools.length !== 1 ? 's' : ''} available
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-3 min-h-[44px] min-w-[44px] text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Search */}
        <div className="relative mb-6">
          <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search tools..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent text-white placeholder-slate-500"
          />
        </div>

        {/* Tools List */}
        <div className="flex-1 overflow-y-auto space-y-3 pr-2">
          {filteredTools.length === 0 ? (
            <div className="text-center py-12">
              <Wrench className="w-12 h-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">
                {searchQuery ? 'No tools match your search' : 'No tools available'}
              </p>
            </div>
          ) : (
            filteredTools.map((tool, idx) => (
              <div
                key={idx}
                className="card hover:border-purple-500/50 transition-all group"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-2">
                      <Wrench className="w-4 h-4 text-purple-400 flex-shrink-0" />
                      <h3 className="font-semibold text-white group-hover:text-purple-400 transition-colors truncate">
                        {tool.name}
                      </h3>
                    </div>

                    {tool.description && (
                      <p className="text-sm text-slate-400 mb-3 line-clamp-2">
                        {tool.description}
                      </p>
                    )}

                    {/* Parameters */}
                    {tool.inputSchema?.properties && (
                      <div className="mt-2">
                        <p className="text-xs text-slate-500 mb-1">Parameters:</p>
                        <div className="flex flex-wrap gap-1">
                          {Object.keys(tool.inputSchema.properties).slice(0, 5).map((param, pidx) => (
                            <span
                              key={pidx}
                              className="px-2 py-0.5 rounded bg-slate-800/50 text-slate-400 text-xs font-mono"
                            >
                              {param}
                              {tool.inputSchema.required?.includes(param) && (
                                <span className="text-red-400">*</span>
                              )}
                            </span>
                          ))}
                          {Object.keys(tool.inputSchema.properties).length > 5 && (
                            <span className="px-2 py-0.5 rounded bg-slate-800/50 text-slate-500 text-xs">
                              +{Object.keys(tool.inputSchema.properties).length - 5}
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2 ml-4">
                    <button
                      onClick={() => copyToolName(tool.name)}
                      className="p-2 hover:bg-slate-800 rounded transition-colors"
                      title="Copy tool name"
                    >
                      <Copy className="w-4 h-4 text-slate-400 hover:text-white" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="mt-6 pt-6 border-t border-slate-700/50 flex justify-between items-center">
          <div className="text-sm text-slate-500">
            {server.category} • Phase {server.phase}
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default MCPToolList;
