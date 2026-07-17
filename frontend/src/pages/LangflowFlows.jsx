import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search,
  Plus,
  Play,
  Download,
  Upload,
  Trash2,
  ExternalLink,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  X,
  Workflow,
  Clock,
  FileJson,
  Copy,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import Breadcrumbs from '../components/Breadcrumbs';
import { apiJson, ApiError } from '../services/http';

const LangflowFlows = () => {
  const [flows, setFlows] = useState([]);
  const [filteredFlows, setFilteredFlows] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [healthStatus, setHealthStatus] = useState(null);
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [showRunModal, setShowRunModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [flowToDelete, setFlowToDelete] = useState(null);
  const [runInputs, setRunInputs] = useState({});
  const [runOutput, setRunOutput] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    checkHealth();
    loadFlows();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [flows, searchQuery]);

  const checkHealth = async () => {
    try {
      const data = await apiJson('/langflow/health');
      // Check for 'healthy' status, anything else is an error (unreachable, disabled, etc.)
      setHealthStatus(data.status === 'healthy' ? 'connected' : 'error');
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus('error');
    }
  };

  const loadFlows = async () => {
    setLoading(true);
    try {
      const data = await apiJson('/langflow/flows');
      setFlows(data.flows || []);
    } catch (error) {
      console.error('Failed to load flows:', error);
      // ApiError = backend answered with an error payload; anything else = unreachable.
      toast.error(error instanceof ApiError
        ? (error.message || 'Failed to load flows')
        : 'Failed to connect to Langflow service');
      setFlows([]);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    // Ensure flows is always an array
    const flowsArray = Array.isArray(flows) ? flows : [];
    let filtered = [...flowsArray];

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(flow =>
        flow?.name?.toLowerCase().includes(query) ||
        flow?.description?.toLowerCase().includes(query)
      );
    }

    setFilteredFlows(filtered);
  };

  const handleFlowClick = async (flow) => {
    try {
      const data = await apiJson(`/langflow/flows/${flow.id}`);
      setSelectedFlow(data);
      setRunInputs({});
      setRunOutput(null);
      setShowRunModal(true);
    } catch (error) {
      console.error('Failed to load flow details:', error);
      toast.error('Failed to load flow details');
    }
  };

  const handleRunFlow = async () => {
    if (!selectedFlow) return;

    setIsRunning(true);
    setRunOutput(null);

    try {
      const data = await apiJson(`/langflow/flows/${selectedFlow.id}/run`, {
        method: 'POST',
        body: JSON.stringify({ inputs: runInputs }),
      });

      setRunOutput(data);
      toast.success('Flow executed successfully');
    } catch (error) {
      console.error('Failed to run flow:', error);
      if (error instanceof ApiError) {
        toast.error(error.message || 'Failed to run flow');
        setRunOutput({ error: error.message || 'Execution failed' });
      } else {
        toast.error('Failed to run flow');
        setRunOutput({ error: error.message });
      }
    } finally {
      setIsRunning(false);
    }
  };

  const handleExportFlow = async (flow, e) => {
    e?.stopPropagation();
    setIsExporting(true);

    try {
      const data = await apiJson(`/langflow/flows/${flow.id}/export`);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${flow.name || 'flow'}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success('Flow exported successfully');
    } catch (error) {
      console.error('Failed to export flow:', error);
      toast.error('Failed to export flow');
    } finally {
      setIsExporting(false);
    }
  };

  const handleImportFlow = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const text = await file.text();
      const flowData = JSON.parse(text);

      await apiJson('/langflow/flows/import', {
        method: 'POST',
        body: JSON.stringify(flowData),
      });

      toast.success('Flow imported successfully');
      loadFlows();
    } catch (error) {
      console.error('Failed to import flow:', error);
      // ApiError = backend rejected the flow; anything else = bad local file.
      toast.error(error instanceof ApiError
        ? (error.message || 'Failed to import flow')
        : 'Invalid JSON file');
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleDeleteFlow = async () => {
    if (!flowToDelete) return;

    try {
      await apiJson(`/langflow/flows/${flowToDelete.id}`, {
        method: 'DELETE',
      });

      toast.success('Flow deleted successfully');
      setFlows(flows.filter(f => f.id !== flowToDelete.id));
      setShowDeleteModal(false);
      setFlowToDelete(null);
    } catch (error) {
      console.error('Failed to delete flow:', error);
      toast.error('Failed to delete flow');
    }
  };

  const confirmDelete = (flow, e) => {
    e?.stopPropagation();
    setFlowToDelete(flow);
    setShowDeleteModal(true);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-unicorn-500 to-unicorn-400 bg-clip-text text-transparent">
              Langflow Flows
            </h1>
            <p className="text-slate-400 mt-1">
              {filteredFlows.length} of {flows.length} flows
            </p>
          </div>

          <div className="flex items-center space-x-4">
            {/* Health Status */}
            <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg ${
              healthStatus === 'connected'
                ? 'bg-emerald-500/20 text-emerald-400'
                : healthStatus === 'error'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-slate-500/20 text-slate-400'
            }`}>
              {healthStatus === 'connected' ? (
                <CheckCircle className="w-4 h-4" />
              ) : healthStatus === 'error' ? (
                <AlertCircle className="w-4 h-4" />
              ) : (
                <Loader2 className="w-4 h-4 animate-spin" />
              )}
              <span className="text-sm font-medium">
                {healthStatus === 'connected' ? 'Connected' : healthStatus === 'error' ? 'Disconnected' : 'Checking...'}
              </span>
            </div>

            {/* Refresh Button */}
            <button
              onClick={() => { checkHealth(); loadFlows(); }}
              className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-5 h-5 text-slate-400" />
            </button>

            {/* Import Button */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleImportFlow}
              accept=".json"
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors flex items-center space-x-2"
            >
              <Upload className="w-5 h-5" />
              <span>Import</span>
            </button>

            {/* Open Langflow Button */}
            <a
              href="http://localhost:7860"
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center space-x-2"
            >
              <ExternalLink className="w-5 h-5" />
              <span>Open Langflow</span>
            </a>
          </div>
        </div>

        {/* Search */}
        <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
          <div className="relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search flows..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-unicorn-500"></div>
            <p className="text-slate-400 mt-4">Loading flows...</p>
          </div>
        )}

        {/* Flows Grid */}
        {!loading && filteredFlows.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredFlows.map(flow => (
              <div
                key={flow.id}
                className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6 hover:border-unicorn-500/50 transition-all cursor-pointer group"
                onClick={() => handleFlowClick(flow)}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-unicorn-600 to-unicorn-500 flex items-center justify-center">
                      <Workflow className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-white group-hover:text-unicorn-400 transition-colors">
                        {flow.name || 'Untitled Flow'}
                      </h3>
                      <p className="text-xs text-slate-400 flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(flow.updated_at || flow.created_at)}</span>
                      </p>
                    </div>
                  </div>
                </div>

                <p className="text-sm text-slate-400 mb-4 line-clamp-2">
                  {flow.description || 'No description provided'}
                </p>

                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleFlowClick(flow); }}
                      className="p-2 bg-unicorn-500/20 hover:bg-unicorn-500/30 text-unicorn-400 rounded-lg transition-colors"
                      title="Run Flow"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => handleExportFlow(flow, e)}
                      className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg transition-colors"
                      title="Export Flow"
                      disabled={isExporting}
                    >
                      <Download className="w-4 h-4" />
                    </button>
                    <button
                      onClick={(e) => confirmDelete(flow, e)}
                      className="p-2 bg-slate-800 hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded-lg transition-colors"
                      title="Delete Flow"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                  <ChevronRight className="w-4 h-4 text-unicorn-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && filteredFlows.length === 0 && (
          <div className="text-center py-12">
            <Workflow className="w-16 h-16 text-slate-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-slate-300 mb-2">
              {searchQuery ? 'No flows found' : 'No flows yet'}
            </h3>
            <p className="text-slate-400 mb-6">
              {searchQuery
                ? 'Try adjusting your search'
                : 'Create your first flow in Langflow or import one'}
            </p>
            <div className="flex items-center justify-center space-x-4">
              <button
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition-colors flex items-center space-x-2"
              >
                <Upload className="w-5 h-5" />
                <span>Import Flow</span>
              </button>
              <a
                href="http://localhost:7860"
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center space-x-2"
              >
                <Plus className="w-5 h-5" />
                <span>Create in Langflow</span>
              </a>
            </div>
          </div>
        )}
      </div>

      {/* Run Flow Modal */}
      {showRunModal && selectedFlow && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-6 z-50"
          onClick={() => setShowRunModal(false)}
        >
          <div
            className="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-unicorn-600 to-unicorn-500 flex items-center justify-center">
                  <Workflow className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">{selectedFlow.name || 'Untitled Flow'}</h2>
                  <p className="text-slate-400">Run this flow with custom inputs</p>
                </div>
              </div>
              <button
                onClick={() => setShowRunModal(false)}
                className="text-slate-400 hover:text-white p-2 hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {selectedFlow.description && (
              <p className="text-slate-300 mb-6">{selectedFlow.description}</p>
            )}

            <div className="space-y-6">
              {/* Flow Info */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm text-slate-400 mb-2">Flow ID</p>
                  <div className="flex items-center space-x-2">
                    <code className="px-3 py-1 bg-slate-800 rounded text-sm text-slate-300 font-mono truncate flex-1">
                      {selectedFlow.id}
                    </code>
                    <button
                      onClick={() => copyToClipboard(selectedFlow.id)}
                      className="p-2 hover:bg-slate-800 rounded transition-colors"
                    >
                      <Copy className="w-4 h-4 text-slate-400" />
                    </button>
                  </div>
                </div>
                <div>
                  <p className="text-sm text-slate-400 mb-2">Last Updated</p>
                  <span className="px-3 py-1 bg-slate-800 rounded text-sm text-slate-300">
                    {formatDate(selectedFlow.updated_at || selectedFlow.created_at)}
                  </span>
                </div>
              </div>

              {/* Input Fields */}
              <div>
                <p className="text-sm text-slate-400 mb-2">Input Value</p>
                <textarea
                  value={runInputs.input_value || ''}
                  onChange={(e) => setRunInputs({ ...runInputs, input_value: e.target.value })}
                  placeholder="Enter your input message..."
                  className="w-full px-4 py-3 bg-slate-800/50 border border-slate-700 rounded-lg focus:ring-2 focus:ring-unicorn-500 focus:border-transparent resize-none h-24"
                />
              </div>

              {/* Run Button */}
              <button
                onClick={handleRunFlow}
                disabled={isRunning}
                className="w-full px-4 py-3 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Running...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Run Flow</span>
                  </>
                )}
              </button>

              {/* Output Display */}
              {runOutput && (
                <div>
                  <p className="text-sm text-slate-400 mb-2">Output</p>
                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 max-h-64 overflow-y-auto">
                    {runOutput.error ? (
                      <div className="text-red-400 flex items-start space-x-2">
                        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                        <span>{runOutput.error}</span>
                      </div>
                    ) : (
                      <pre className="text-slate-300 text-sm whitespace-pre-wrap font-mono">
                        {typeof runOutput === 'string'
                          ? runOutput
                          : JSON.stringify(runOutput, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex space-x-3 pt-4 border-t border-slate-700">
                <button
                  onClick={(e) => handleExportFlow(selectedFlow, e)}
                  disabled={isExporting}
                  className="flex-1 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors flex items-center justify-center space-x-2"
                >
                  <Download className="w-4 h-4" />
                  <span>Export</span>
                </button>
                <a
                  href={`http://localhost:7860/flow/${selectedFlow.id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex-1 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors flex items-center justify-center space-x-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  <span>Edit in Langflow</span>
                </a>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && flowToDelete && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-6 z-50"
          onClick={() => setShowDeleteModal(false)}
        >
          <div
            className="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-md w-full"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center mb-6">
              <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-4">
                <Trash2 className="w-8 h-8 text-red-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Delete Flow</h2>
              <p className="text-slate-400">
                Are you sure you want to delete <span className="text-white font-medium">{flowToDelete.name || 'this flow'}</span>? This action cannot be undone.
              </p>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={() => setShowDeleteModal(false)}
                className="flex-1 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteFlow}
                className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LangflowFlows;
