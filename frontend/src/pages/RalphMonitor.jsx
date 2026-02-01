/**
 * RalphMonitor - Self-Correcting Workflow Monitor
 *
 * Visualizes Ralph workflow executions with:
 * - Real-time progress tracking
 * - Task breakdown and status
 * - Iteration history
 * - Mid-execution guidance injection
 * - Error recovery visualization
 */

import { useState, useEffect } from 'react';
import {
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  RefreshCw,
  MessageSquare,
  TrendingUp,
  Clock,
  Zap,
  AlertCircle,
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import api from '../services/api';

const RalphMonitor = () => {
  const [executions, setExecutions] = useState([]);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [loading, setLoading] = useState(true);
  const [guidanceInput, setGuidanceInput] = useState('');
  const [submittingGuidance, setSubmittingGuidance] = useState(false);

  // Load executions
  useEffect(() => {
    loadExecutions();
    const interval = setInterval(loadExecutions, 3000); // Poll every 3s
    return () => clearInterval(interval);
  }, []);

  const loadExecutions = async () => {
    try {
      const response = await api.get('/ralph/executions');
      setExecutions(response.data);
      setLoading(false);

      // Auto-refresh selected execution if still running
      if (selectedExecution && !selectedExecution.is_complete) {
        await loadExecutionDetails(selectedExecution.execution_id);
      }
    } catch (error) {
      console.error('Error loading executions:', error);
      toast.error('Failed to load executions');
      setLoading(false);
    }
  };

  const loadExecutionDetails = async (executionId) => {
    try {
      const response = await api.get(`/ralph/executions/${executionId}`);
      setSelectedExecution(response.data);
    } catch (error) {
      console.error('Error loading execution details:', error);
    }
  };

  const handleInjectGuidance = async () => {
    if (!guidanceInput.trim() || !selectedExecution) return;

    setSubmittingGuidance(true);
    try {
      await api.post(`/ralph/executions/${selectedExecution.execution_id}/guidance`, {
        guidance: guidanceInput,
      });
      toast.success('Guidance injected successfully');
      setGuidanceInput('');
      await loadExecutionDetails(selectedExecution.execution_id);
    } catch (error) {
      toast.error('Failed to inject guidance');
    } finally {
      setSubmittingGuidance(false);
    }
  };

  const handleCancelExecution = async (executionId) => {
    try {
      await api.delete(`/ralph/executions/${executionId}`);
      toast.success('Execution cancelled');
      setExecutions(executions.filter((e) => e.execution_id !== executionId));
      if (selectedExecution?.execution_id === executionId) {
        setSelectedExecution(null);
      }
    } catch (error) {
      toast.error('Failed to cancel execution');
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'success':
        return 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30';
      case 'failed':
        return 'text-red-400 bg-red-500/20 border-red-500/30';
      case 'running':
        return 'text-blue-400 bg-blue-500/20 border-blue-500/30';
      case 'paused':
        return 'text-amber-400 bg-amber-500/20 border-amber-500/30';
      default:
        return 'text-slate-400 bg-slate-500/20 border-slate-500/30';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4" />;
      case 'failed':
        return <XCircle className="w-4 h-4" />;
      case 'running':
        return <RefreshCw className="w-4 h-4 animate-spin" />;
      case 'paused':
        return <Pause className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="w-8 h-8 text-purple-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 p-6">
      {/* Header */}
      <div className="max-w-7xl mx-auto mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-white">Ralph Monitor</h1>
            <p className="text-slate-400">Self-correcting workflow executions</p>
          </div>
        </div>

        <div className="flex items-center gap-4 mt-4">
          <div className="px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700">
            <span className="text-slate-400 text-sm">Active Executions:</span>
            <span className="ml-2 text-white font-semibold">{executions.filter((e) => !e.is_complete).length}</span>
          </div>
          <div className="px-4 py-2 rounded-lg bg-slate-800/50 border border-slate-700">
            <span className="text-slate-400 text-sm">Completed:</span>
            <span className="ml-2 text-white font-semibold">{executions.filter((e) => e.is_complete).length}</span>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Execution List */}
        <div className="lg:col-span-1 space-y-4">
          <h2 className="text-xl font-semibold text-white mb-4">Executions</h2>

          {executions.length === 0 ? (
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-8 text-center">
              <AlertCircle className="w-12 h-12 text-slate-500 mx-auto mb-3" />
              <p className="text-slate-400">No executions running</p>
            </div>
          ) : (
            executions.map((execution) => (
              <div
                key={execution.execution_id}
                onClick={() => loadExecutionDetails(execution.execution_id)}
                className={`backdrop-blur-xl bg-slate-900/50 border rounded-xl p-4 cursor-pointer transition-all hover:border-purple-500/50 ${
                  selectedExecution?.execution_id === execution.execution_id
                    ? 'border-purple-500'
                    : 'border-slate-700/50'
                }`}
              >
                {/* Status Badge */}
                <div className="flex items-center justify-between mb-3">
                  <span className={`px-2 py-1 rounded-lg text-xs border flex items-center gap-1.5 ${getStatusColor(execution.status)}`}>
                    {getStatusIcon(execution.status)}
                    {execution.status}
                  </span>
                  <span className="text-xs text-slate-500">Iteration {execution.iteration}/{execution.max_iterations}</span>
                </div>

                {/* Workflow ID */}
                <h3 className="text-sm font-semibold text-white mb-2 truncate">{execution.workflow_id}</h3>

                {/* Progress Bar */}
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden mb-2">
                  <div
                    className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all"
                    style={{ width: `${execution.progress_percent}%` }}
                  />
                </div>

                <div className="flex items-center justify-between text-xs text-slate-400">
                  <span>{execution.progress_percent}% complete</span>
                  {execution.is_paused && (
                    <span className="text-amber-400 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      Needs guidance
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Execution Details */}
        <div className="lg:col-span-2">
          {selectedExecution ? (
            <div className="space-y-6">
              {/* Header */}
              <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-2xl font-bold text-white mb-1">{selectedExecution.workflow_id}</h2>
                    <p className="text-sm text-slate-400">Execution ID: {selectedExecution.execution_id}</p>
                  </div>
                  <button
                    onClick={() => handleCancelExecution(selectedExecution.execution_id)}
                    className="px-3 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors text-sm"
                  >
                    Cancel
                  </button>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-slate-800/40 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Iteration</div>
                    <div className="text-lg font-semibold text-white">{selectedExecution.iteration}/{selectedExecution.max_iterations}</div>
                  </div>
                  <div className="bg-slate-800/40 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Progress</div>
                    <div className="text-lg font-semibold text-white">{selectedExecution.progress_percent}%</div>
                  </div>
                  <div className="bg-slate-800/40 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Completed</div>
                    <div className="text-lg font-semibold text-emerald-400">{selectedExecution.tasks.completed}</div>
                  </div>
                  <div className="bg-slate-800/40 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Failed</div>
                    <div className="text-lg font-semibold text-red-400">{selectedExecution.tasks.failed}</div>
                  </div>
                </div>
              </div>

              {/* Task Breakdown */}
              <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Task Breakdown</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="text-center p-3 bg-slate-800/40 rounded-lg">
                    <div className="text-2xl font-bold text-white mb-1">{selectedExecution.tasks.total}</div>
                    <div className="text-xs text-slate-400">Total Tasks</div>
                  </div>
                  <div className="text-center p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                    <div className="text-2xl font-bold text-emerald-400 mb-1">{selectedExecution.tasks.completed}</div>
                    <div className="text-xs text-emerald-400/80">Completed</div>
                  </div>
                  <div className="text-center p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                    <div className="text-2xl font-bold text-blue-400 mb-1">{selectedExecution.tasks.in_progress}</div>
                    <div className="text-xs text-blue-400/80">In Progress</div>
                  </div>
                  <div className="text-center p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                    <div className="text-2xl font-bold text-red-400 mb-1">{selectedExecution.tasks.failed}</div>
                    <div className="text-xs text-red-400/80">Failed</div>
                  </div>
                </div>
              </div>

              {/* Guidance Injection */}
              {selectedExecution.is_paused && (
                <div className="backdrop-blur-xl bg-amber-900/20 border border-amber-500/30 rounded-xl p-6">
                  <div className="flex items-start gap-3 mb-4">
                    <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-lg font-semibold text-amber-400 mb-1">Workflow Needs Guidance</h3>
                      <p className="text-sm text-amber-200/80">
                        This workflow is paused and waiting for additional context or instructions to continue.
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <textarea
                      value={guidanceInput}
                      onChange={(e) => setGuidanceInput(e.target.value)}
                      placeholder="Enter guidance or additional context..."
                      rows={3}
                      className="w-full px-4 py-3 bg-slate-900/50 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors resize-none"
                    />
                    <button
                      onClick={handleInjectGuidance}
                      disabled={!guidanceInput.trim() || submittingGuidance}
                      className="w-full px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                      {submittingGuidance ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          Injecting...
                        </>
                      ) : (
                        <>
                          <MessageSquare className="w-4 h-4" />
                          Inject Guidance & Resume
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-12 text-center">
              <TrendingUp className="w-16 h-16 text-slate-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-slate-400 mb-2">No Execution Selected</h3>
              <p className="text-slate-500">Select an execution from the list to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default RalphMonitor;
