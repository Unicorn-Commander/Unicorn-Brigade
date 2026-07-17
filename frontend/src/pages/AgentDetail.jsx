import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Edit, Save, X, MessageSquare, Play, Code, Key, BarChart, Settings, Network, Clock, Wrench, Plus } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { apiJson } from '../services/http';
import ReactMarkdown from 'react-markdown';
import AgentArchitectureDiagram from '../components/AgentArchitectureDiagram';
import AgentTimeline from '../components/AgentTimeline';
import ToolSelector from '../components/ToolSelector';
import ApiKeyCard from '../components/ApiKeyCard';
import GenerateApiKeyModal from '../components/GenerateApiKeyModal';
import KeyRevealModal from '../components/KeyRevealModal';
import AgentConfigurationTab from '../components/AgentConfigurationTab';

const AgentDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [editedAgent, setEditedAgent] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [buildSession, setBuildSession] = useState(null);
  const [loadingSession, setLoadingSession] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [generatedKey, setGeneratedKey] = useState(null);

  useEffect(() => {
    loadAgent();
  }, [id]);

  const loadAgent = async () => {
    setLoading(true);
    try {
      const data = await apiJson(`/agents/${id}`);
      setAgent(data);
      setEditedAgent(data);

      // Try to load build session if sessionId exists
      if (data.sessionId) {
        loadBuildSession(data.sessionId);
      }
    } catch (error) {
      console.error('Failed to load agent:', error);
      toast.error('Failed to load agent');
      navigate('/library');
    } finally {
      setLoading(false);
    }
  };

  const loadBuildSession = async (sessionId) => {
    setLoadingSession(true);
    try {
      const data = await apiJson(`/agent-builder/session/${sessionId}`);
      setBuildSession(data);
    } catch (error) {
      console.error('Failed to load build session:', error);
      // Don't show error toast - it's okay if session doesn't exist
      setBuildSession(null);
    } finally {
      setLoadingSession(false);
    }
  };

  const saveChanges = async () => {
    try {
      await apiJson(`/agents/${id}`, {
        method: 'PUT',
        body: JSON.stringify(editedAgent)
      });
      toast.success('Agent updated successfully');
      setAgent(editedAgent);
      setEditMode(false);
    } catch (error) {
      console.error('Failed to update agent:', error);
      toast.error('Failed to update agent');
    }
  };

  const cancelEdit = () => {
    setEditedAgent(agent);
    setEditMode(false);
  };

  const handleKeyGenerated = (newKey) => {
    setGeneratedKey(newKey);
    setShowKeyModal(false);
    loadAgent(); // Reload agent to update API keys list
  };

  const handleRevokeKey = async (apiKey) => {
    try {
      await apiJson(`/agents/${id}/api-keys/${apiKey.id}`, { method: 'DELETE' });
      toast.success('API key revoked');
      loadAgent(); // Reload agent to update API keys list
    } catch (error) {
      console.error('Failed to revoke API key:', error);
      toast.error('Failed to revoke API key');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-unicorn-500"></div>
          <p className="text-slate-400 mt-4">Loading agent...</p>
        </div>
      </div>
    );
  }

  if (!agent) return null;

  const currentAgent = editMode ? editedAgent : agent;

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <button
            onClick={() => navigate('/library')}
            className="btn-secondary flex items-center space-x-2"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Library</span>
          </button>

          <div className="flex items-center space-x-3">
            {editMode ? (
              <>
                <button onClick={cancelEdit} className="btn-secondary flex items-center space-x-2">
                  <X className="w-4 h-4" />
                  <span>Cancel</span>
                </button>
                <button onClick={saveChanges} className="btn-primary flex items-center space-x-2">
                  <Save className="w-4 h-4" />
                  <span>Save Changes</span>
                </button>
              </>
            ) : (
              <button onClick={() => setEditMode(true)} className="btn-primary flex items-center space-x-2">
                <Edit className="w-4 h-4" />
                <span>Edit Agent</span>
              </button>
            )}
          </div>
        </div>

        {/* Agent Header Card */}
        <div className="card">
          <div className="flex items-start space-x-6">
            <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-unicorn-500 to-cyan-500 flex items-center justify-center text-4xl">
              {currentAgent.avatar || '🦄'}
            </div>
            <div className="flex-1">
              {editMode ? (
                <input
                  type="text"
                  value={editedAgent.displayName || editedAgent.name}
                  onChange={(e) => setEditedAgent({ ...editedAgent, displayName: e.target.value })}
                  className="text-3xl font-bold bg-transparent border-b border-slate-600 focus:border-unicorn-500 outline-none mb-2 w-full"
                />
              ) : (
                <h1 className="text-3xl font-bold text-gradient mb-2">
                  {currentAgent.displayName || currentAgent.name}
                </h1>
              )}

              {editMode ? (
                <input
                  type="text"
                  value={editedAgent.title || ''}
                  onChange={(e) => setEditedAgent({ ...editedAgent, title: e.target.value })}
                  className="text-lg bg-transparent border-b border-slate-600 focus:border-unicorn-500 outline-none mb-3 w-full"
                  placeholder="Agent title..."
                />
              ) : (
                currentAgent.title && <p className="text-lg text-slate-300 mb-3">{currentAgent.title}</p>
              )}

              <div className="flex items-center space-x-4 text-sm">
                <span className="px-3 py-1 rounded-full bg-unicorn-500/20 text-unicorn-300">
                  {currentAgent.rank || 'Agent'}
                </span>
                <span className="px-3 py-1 rounded-full bg-cyan-500/20 text-cyan-300">
                  {currentAgent.domain || 'General'}
                </span>
                <span className="px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300">
                  {currentAgent.status || 'active'}
                </span>
              </div>
            </div>
          </div>

          {editMode ? (
            <textarea
              value={editedAgent.bio || ''}
              onChange={(e) => setEditedAgent({ ...editedAgent, bio: e.target.value })}
              className="w-full mt-4 p-3 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent resize-none"
              rows={3}
              placeholder="Agent bio..."
            />
          ) : (
            currentAgent.bio && (
              <p className="mt-4 text-slate-300 leading-relaxed">{currentAgent.bio}</p>
            )
          )}
        </div>

        {/* Tabs */}
        <div className="card">
          <div className="flex border-b border-slate-700 mb-6 overflow-x-auto">
            {[
              { id: 'overview', label: 'Overview', icon: BarChart },
              { id: 'architecture', label: 'Architecture', icon: Network },
              { id: 'build-history', label: 'Build History', icon: Clock },
              { id: 'tools', label: 'Tools', icon: Wrench },
              { id: 'configuration', label: 'Configuration', icon: Settings },
              { id: 'system-prompt', label: 'System Prompt', icon: Code },
              { id: 'api-keys', label: 'API Keys', icon: Key }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-3 border-b-2 transition-colors whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'border-unicorn-500 text-unicorn-400'
                    : 'border-transparent text-slate-400 hover:text-slate-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Tab Content */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Capabilities */}
              <div>
                <h3 className="text-lg font-semibold mb-3">Capabilities</h3>
                <div className="flex flex-wrap gap-2">
                  {(currentAgent.capabilities || []).map((cap, idx) => (
                    <span key={idx} className="px-3 py-1 rounded-full bg-unicorn-500/20 text-unicorn-300 text-sm">
                      {cap}
                    </span>
                  ))}
                  {(!currentAgent.capabilities || currentAgent.capabilities.length === 0) && (
                    <p className="text-slate-400">No capabilities defined</p>
                  )}
                </div>
              </div>

              {/* Tools */}
              <div>
                <h3 className="text-lg font-semibold mb-3">Tools</h3>
                <div className="space-y-2">
                  {(currentAgent.agentTools || []).map(at => (
                    <div key={at.id} className="p-3 rounded-lg bg-slate-800/50 border border-slate-700">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium">{at.tool.name}</h4>
                          <p className="text-sm text-slate-400">{at.tool.description}</p>
                        </div>
                        <span className="px-2 py-1 rounded text-xs bg-cyan-500/20 text-cyan-300">
                          {at.tool.type}
                        </span>
                      </div>
                    </div>
                  ))}
                  {(!currentAgent.agentTools || currentAgent.agentTools.length === 0) && (
                    <p className="text-slate-400">No tools assigned</p>
                  )}
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 rounded-lg bg-slate-800/50">
                  <p className="text-sm text-slate-400">Messages</p>
                  <p className="text-2xl font-bold">{currentAgent._count?.messages || 0}</p>
                </div>
                <div className="p-4 rounded-lg bg-slate-800/50">
                  <p className="text-sm text-slate-400">Tasks</p>
                  <p className="text-2xl font-bold">{currentAgent._count?.tasks || 0}</p>
                </div>
                <div className="p-4 rounded-lg bg-slate-800/50">
                  <p className="text-sm text-slate-400">API Keys</p>
                  <p className="text-2xl font-bold">{currentAgent._count?.apiKeys || 0}</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'architecture' && (
            <AgentArchitectureDiagram agent={currentAgent} />
          )}

          {activeTab === 'build-history' && (
            <div>
              {loadingSession ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-unicorn-500"></div>
                  <p className="text-slate-400 mt-4">Loading build history...</p>
                </div>
              ) : (
                <AgentTimeline
                  session={buildSession}
                  agentName={currentAgent.displayName || currentAgent.name}
                />
              )}
            </div>
          )}

          {activeTab === 'tools' && (
            <div>
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Tool Management</h3>
                <p className="text-sm text-slate-400">
                  Configure the tools available to this agent. Tools extend the agent's capabilities with specialized functions.
                </p>
              </div>
              <ToolSelector
                agentId={id}
                assignedTools={currentAgent.agentTools?.map(at => at.tool) || []}
                onUpdate={loadAgent}
              />
            </div>
          )}

          {activeTab === 'configuration' && (
            <AgentConfigurationTab
              agent={currentAgent}
              editMode={editMode}
              onUpdate={(updatedAgent) => setEditedAgent(updatedAgent)}
            />
          )}

          {activeTab === 'system-prompt' && (
            <div>
              {editMode ? (
                <textarea
                  value={editedAgent.systemPrompt || ''}
                  onChange={(e) => setEditedAgent({ ...editedAgent, systemPrompt: e.target.value })}
                  className="w-full h-96 p-4 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent font-mono text-sm resize-none"
                />
              ) : (
                <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700">
                  <div className="prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{currentAgent.systemPrompt || '*No system prompt defined*'}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'api-keys' && (
            <div className="space-y-4">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="text-lg font-semibold mb-2">API Keys</h3>
                  <p className="text-sm text-slate-400">
                    API keys allow external applications to invoke this agent. Keep them secure!
                  </p>
                </div>
                <button
                  onClick={() => setShowKeyModal(true)}
                  className="btn-primary flex items-center space-x-2"
                >
                  <Plus className="w-4 h-4" />
                  <span>Generate New Key</span>
                </button>
              </div>

              {(currentAgent.apiKeys || []).map(key => (
                <ApiKeyCard
                  key={key.id}
                  apiKey={key}
                  onRevoke={handleRevokeKey}
                />
              ))}

              {(!currentAgent.apiKeys || currentAgent.apiKeys.length === 0) && (
                <div className="text-center py-12">
                  <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-800/50 mb-4">
                    <Key className="w-8 h-8 text-slate-600" />
                  </div>
                  <p className="text-slate-400 mb-2">No API keys generated yet</p>
                  <p className="text-sm text-slate-400">Create your first API key to get started</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modals */}
        {showKeyModal && (
          <GenerateApiKeyModal
            agentId={id}
            onSuccess={handleKeyGenerated}
            onClose={() => setShowKeyModal(false)}
          />
        )}

        {generatedKey && (
          <KeyRevealModal
            apiKey={generatedKey}
            onClose={() => setGeneratedKey(null)}
          />
        )}
      </div>
    </div>
  );
};

export default AgentDetail;
