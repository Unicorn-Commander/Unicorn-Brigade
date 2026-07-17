import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  MessageSquare,
  Trash2,
  Clock,
  Hash,
  Cpu,
  Loader2,
  MessagesSquare,
  AlertCircle,
  ArrowUpDown
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import { apiJson } from '../services/http';

const Conversations = () => {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [filteredConversations, setFilteredConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    loadConversations();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [conversations, searchQuery, sortBy]);

  const loadConversations = async () => {
    setLoading(true);
    setError(null);
    try {
      // No hardcoded user_id: the backend scopes the list to the authenticated
      // user (and defaults to "anonymous" otherwise).
      const data = await apiJson('/conversations');
      setConversations(data.conversations || []);
    } catch (err) {
      console.error('Failed to load conversations:', err);
      setError('Failed to load conversations. The backend may not be available yet.');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...conversations];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(conv =>
        conv.title?.toLowerCase().includes(query) ||
        conv.agent?.displayName?.toLowerCase().includes(query) ||
        conv.agent?.name?.toLowerCase().includes(query) ||
        conv.model?.toLowerCase().includes(query)
      );
    }

    // Sort
    filtered.sort((a, b) => {
      if (sortBy === 'newest') {
        return new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0);
      } else if (sortBy === 'oldest') {
        return new Date(a.updated_at || a.created_at || 0) - new Date(b.updated_at || b.created_at || 0);
      } else if (sortBy === 'most-messages') {
        return (b.message_count || 0) - (a.message_count || 0);
      } else if (sortBy === 'a-z') {
        return (a.title || '').localeCompare(b.title || '');
      }
      return 0;
    });

    setFilteredConversations(filtered);
  };

  const deleteConversation = async (e, conversationId) => {
    e.stopPropagation();

    if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
      return;
    }

    setDeletingId(conversationId);
    try {
      await apiJson(`/conversations/${conversationId}`, { method: 'DELETE' });
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      notify.success('Conversation deleted');
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      toast.error('Failed to delete conversation');
    } finally {
      setDeletingId(null);
    }
  };

  const resumeConversation = (conversationId) => {
    navigate(`/chat?conversation=${conversationId}`);
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'completed': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'archived': return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-unicorn-500 to-unicorn-400 bg-clip-text text-transparent">
              Conversations
            </h1>
            <p className="text-slate-400 mt-1">
              {filteredConversations.length} of {conversations.length} conversations
            </p>
          </div>

          <button
            onClick={() => navigate('/chat')}
            className="flex items-center space-x-2 px-4 py-2 rounded-lg bg-unicorn-600 hover:bg-unicorn-500 text-white font-medium transition-all"
          >
            <MessageSquare className="w-5 h-5" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Filters */}
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 backdrop-blur-xl p-4">
          <div className="flex flex-col md:flex-row md:items-center gap-4">
            {/* Search */}
            <div className="relative flex-1">
              <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search conversations by title, agent, or model..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-unicorn-500/50 focus:border-unicorn-500/50 transition-all"
              />
            </div>

            {/* Sort */}
            <div className="flex items-center space-x-2">
              <ArrowUpDown className="w-4 h-4 text-slate-400" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="px-3 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-unicorn-500/50 focus:border-unicorn-500/50"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="most-messages">Most Messages</option>
                <option value="a-z">A-Z</option>
              </select>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-16">
            <Loader2 className="w-12 h-12 text-unicorn-400 animate-spin mx-auto mb-4" />
            <p className="text-slate-400">Loading conversations...</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="text-center py-16">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto mb-4">
              <AlertCircle className="w-8 h-8 text-red-400" />
            </div>
            <h3 className="text-xl font-semibold text-white mb-2">Unable to Load Conversations</h3>
            <p className="text-slate-400 max-w-md mx-auto mb-6">{error}</p>
            <button
              onClick={loadConversations}
              className="px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 hover:text-white hover:border-unicorn-500/40 transition-all"
            >
              Try Again
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && conversations.length === 0 && (
          <div className="text-center py-16">
            <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-unicorn-500/20 to-unicorn-500/20 flex items-center justify-center mx-auto mb-6">
              <MessagesSquare className="w-10 h-10 text-unicorn-400" />
            </div>
            <h3 className="text-2xl font-bold text-white mb-2">No Conversations Yet</h3>
            <p className="text-slate-400 max-w-md mx-auto mb-6">
              Start chatting with an agent to create your first conversation. All your chats will be saved here for easy access.
            </p>
            <button
              onClick={() => navigate('/chat')}
              className="flex items-center space-x-2 px-6 py-3 rounded-lg bg-unicorn-600 hover:bg-unicorn-500 text-white font-medium transition-all mx-auto"
            >
              <MessageSquare className="w-5 h-5" />
              <span>Start a Conversation</span>
            </button>
          </div>
        )}

        {/* No Search Results */}
        {!loading && !error && conversations.length > 0 && filteredConversations.length === 0 && (
          <div className="text-center py-16">
            <Search className="w-12 h-12 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No Matching Conversations</h3>
            <p className="text-slate-400 mb-4">
              No conversations match your search for "{searchQuery}"
            </p>
            <button
              onClick={() => setSearchQuery('')}
              className="text-unicorn-400 hover:text-unicorn-300 text-sm transition-colors"
            >
              Clear search
            </button>
          </div>
        )}

        {/* Conversations List */}
        {!loading && !error && filteredConversations.length > 0 && (
          <div className="space-y-3">
            {filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => resumeConversation(conv.id)}
                className="group relative overflow-hidden rounded-xl border border-slate-700/50 bg-slate-900/50 backdrop-blur-xl cursor-pointer transition-all duration-300 hover:border-unicorn-500/40 hover:shadow-lg hover:shadow-unicorn-500/10"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    {/* Left: Avatar + Content */}
                    <div className="flex items-start space-x-4 flex-1 min-w-0">
                      {/* Agent Avatar */}
                      <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-gradient-to-br from-slate-700 to-slate-600 border border-slate-600/50 flex items-center justify-center text-2xl shadow-lg">
                        {conv.agent?.avatar || '🦄'}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        {/* Title */}
                        <h3 className="text-base font-semibold text-white group-hover:text-unicorn-400 transition-colors truncate">
                          {conv.title || 'Untitled Conversation'}
                        </h3>

                        {/* Agent Name */}
                        <p className="text-sm text-slate-400 mt-0.5">
                          with {conv.agent?.displayName || conv.agent?.name || 'Unknown Agent'}
                        </p>

                        {/* Meta Info */}
                        <div className="flex flex-wrap items-center gap-3 mt-2.5">
                          {/* Message Count */}
                          <div className="flex items-center space-x-1.5 text-xs text-slate-400">
                            <Hash className="w-3 h-3" />
                            <span>{conv.message_count || 0} messages</span>
                          </div>

                          {/* Model */}
                          {conv.model && (
                            <div className="flex items-center space-x-1.5 px-2 py-0.5 rounded-md bg-slate-800/60 border border-slate-700/50 text-xs text-slate-400">
                              <Cpu className="w-3 h-3" />
                              <span>{conv.model.split('/').pop()}</span>
                            </div>
                          )}

                          {/* Status */}
                          {conv.status && (
                            <span className={`px-2 py-0.5 rounded-md text-xs border ${getStatusColor(conv.status)}`}>
                              {conv.status}
                            </span>
                          )}

                          {/* Tokens */}
                          {conv.total_tokens > 0 && (
                            <div className="flex items-center space-x-1 text-xs text-slate-400">
                              <span>{conv.total_tokens.toLocaleString()} tokens</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Right: Timestamp + Actions */}
                    <div className="flex flex-col items-end space-y-2 flex-shrink-0">
                      {/* Timestamp */}
                      <div className="flex items-center space-x-1.5 text-xs text-slate-400">
                        <Clock className="w-3 h-3" />
                        <span>{formatTimestamp(conv.updated_at || conv.created_at)}</span>
                      </div>

                      {/* Delete Button */}
                      <button
                        onClick={(e) => deleteConversation(e, conv.id)}
                        disabled={deletingId === conv.id}
                        className="p-1.5 rounded-lg text-slate-600 opacity-0 group-hover:opacity-100 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-all"
                        title="Delete conversation"
                        aria-label="Delete conversation"
                      >
                        {deletingId === conv.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Hover glow effect */}
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r from-unicorn-500/5 to-unicorn-500/5 pointer-events-none"></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default Conversations;
