import { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Play,
  Clock,
  CheckCircle,
  AlertCircle,
  ChevronRight,
  ChevronDown,
  Users,
  Cpu,
  DollarSign,
  RefreshCw,
  X,
  Loader2,
  GitBranch,
  ArrowRight,
  Zap,
  Settings,
  FileText,
  Tag,
  Timer,
  Activity,
  PauseCircle,
  XCircle,
  Eye,
  BarChart3,
  List,
  Network,
  Grid3x3
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import WorkflowDiagram from '../components/WorkflowDiagram';
import WorkflowGallery from '../components/WorkflowGallery';
import WorkflowFilters from '../components/WorkflowFilters';
import WorkflowExecutionPanel from '../components/WorkflowExecutionPanel';
import Modal from '../components/ui/Modal';
import Breadcrumbs from '../components/Breadcrumbs';
import CardSkeleton from '../components/skeletons/CardSkeleton';
import TableSkeleton from '../components/skeletons/TableSkeleton';
import { apiJson, ApiError } from '../services/http';

// Tag colors
const tagColors = {
  finance: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  research: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  sales: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  devops: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  content: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  legal: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  medical: 'bg-red-500/20 text-red-400 border-red-500/30',
  investment: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  marketing: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  seo: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
  incident: 'bg-rose-500/20 text-rose-400 border-rose-500/30',
  monitoring: 'bg-violet-500/20 text-violet-400 border-violet-500/30',
  analysis: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
  documents: 'bg-lime-500/20 text-lime-400 border-lime-500/30',
  compliance: 'bg-unicorn-500/20 text-unicorn-400 border-unicorn-500/30',
  outreach: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  documentation: 'bg-slate-500/20 text-slate-400 border-slate-500/30',
};

// Status colors and icons
const statusConfig = {
  pending: { color: 'text-slate-400', bg: 'bg-slate-500/20', icon: Clock },
  running: { color: 'text-blue-400', bg: 'bg-blue-500/20', icon: Activity },
  waiting: { color: 'text-amber-400', bg: 'bg-amber-500/20', icon: PauseCircle },
  completed: { color: 'text-emerald-400', bg: 'bg-emerald-500/20', icon: CheckCircle },
  failed: { color: 'text-red-400', bg: 'bg-red-500/20', icon: XCircle },
  cancelled: { color: 'text-slate-400', bg: 'bg-slate-500/20', icon: XCircle },
};

const Workflows = () => {
  // State for workflow templates
  const [templates, setTemplates] = useState([]);
  const [filteredTemplates, setFilteredTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [templateDetail, setTemplateDetail] = useState(null);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [recentExecutions, setRecentExecutions] = useState([]);

  // State for executions
  const [executions, setExecutions] = useState([]);
  const [selectedExecution, setSelectedExecution] = useState(null);

  // State for model config
  // UI State
  const [loading, setLoading] = useState(true);
  const [executionsLoading, setExecutionsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTag, setSelectedTag] = useState('');
  const [selectedComplexity, setSelectedComplexity] = useState('');
  const [activeTab, setActiveTab] = useState('templates'); // templates, executions
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showExecutionModal, setShowExecutionModal] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null);
  const [pollingExecution, setPollingExecution] = useState(null);
  const [allTags, setAllTags] = useState([]);
  const [detailViewMode, setDetailViewMode] = useState('diagram'); // 'list' or 'diagram'
  const [viewMode, setViewMode] = useState('grid'); // 'grid' or 'list'
  const [sortBy, setSortBy] = useState('newest');

  // Load data on mount
  useEffect(() => {
    loadTemplates();
    loadExecutions();
    checkHealth();
  }, []);

  // Apply filters when templates or search/tag/complexity/sort changes
  useEffect(() => {
    applyFilters();
  }, [templates, searchQuery, selectedTag, selectedComplexity, sortBy]);

  // Extract unique tags
  useEffect(() => {
    const tags = new Set();
    templates.forEach(t => {
      (t.tags || []).forEach(tag => tags.add(tag));
    });
    setAllTags(Array.from(tags).sort());
  }, [templates]);

  // Poll for execution status
  useEffect(() => {
    let interval;
    if (pollingExecution) {
      interval = setInterval(async () => {
        try {
          const data = await apiJson(`/hierarchical/executions/${pollingExecution}`);
          const execution = data.execution;

          // Update execution in list
          setExecutions(prev => prev.map(e =>
            e.id === pollingExecution ? execution : e
          ));

          // Update selected execution if viewing it
          if (selectedExecution?.id === pollingExecution) {
            setSelectedExecution(execution);
          }

          // Stop polling if completed or failed
          if (['completed', 'failed', 'cancelled'].includes(execution.state)) {
            setPollingExecution(null);
            notify.success(`Workflow ${execution.state}`);
          }
        } catch (error) {
          // Keep polling on transient errors — next tick retries.
          console.error('Polling error:', error);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [pollingExecution, selectedExecution?.id]);

  const checkHealth = async () => {
    try {
      const data = await apiJson('/hierarchical/health');
      setHealthStatus(data.status === 'healthy' ? 'connected' : 'error');
    } catch (error) {
      console.error('Health check failed:', error);
      setHealthStatus('error');
    }
  };

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const [data] = await Promise.all([
        apiJson('/hierarchical/templates'),
        new Promise(resolve => setTimeout(resolve, 300)),
      ]);
      setTemplates(data.workflows || []);
    } catch (error) {
      console.error('Failed to load templates:', error);
      toast.error(error instanceof ApiError
        ? 'Failed to load workflow templates'
        : 'Failed to connect to workflow service');
    } finally {
      setLoading(false);
    }
  };

  const loadTemplateDetail = async (templateId) => {
    try {
      const data = await apiJson(`/hierarchical/templates/${templateId}`);
      setTemplateDetail(data.workflow);
      return data.workflow;
    } catch (error) {
      console.error('Failed to load template detail:', error);
      toast.error('Failed to load workflow details');
    }
    return null;
  };

  const loadExecutions = async () => {
    setExecutionsLoading(true);
    try {
      const data = await apiJson('/hierarchical/executions');
      setExecutions(data.executions || []);
    } catch (error) {
      console.error('Failed to load executions:', error);
    } finally {
      setExecutionsLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...templates];

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(t =>
        t.name?.toLowerCase().includes(query) ||
        t.description?.toLowerCase().includes(query) ||
        (t.tags || []).some(tag => tag.toLowerCase().includes(query))
      );
    }

    // Tag filter
    if (selectedTag) {
      filtered = filtered.filter(t => (t.tags || []).includes(selectedTag));
    }

    // Complexity filter
    if (selectedComplexity) {
      filtered = filtered.filter(t => {
        const stepCount = t.step_count || t.stepCount || (t.steps?.length || 0);
        const checkpointCount = t.checkpoint_count || t.checkpointCount || 0;

        switch (selectedComplexity) {
          case 'simple':
            return stepCount <= 3 && checkpointCount === 0;
          case 'moderate':
            return stepCount >= 4 && stepCount <= 5 && checkpointCount <= 1;
          case 'complex':
            return stepCount >= 6 || checkpointCount > 1;
          default:
            return true;
        }
      });
    }

    // Sorting
    switch (sortBy) {
      case 'name-asc':
        filtered.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
        break;
      case 'name-desc':
        filtered.sort((a, b) => (b.name || '').localeCompare(a.name || ''));
        break;
      case 'steps-asc':
        filtered.sort((a, b) => {
          const aSteps = a.step_count || a.stepCount || (a.steps?.length || 0);
          const bSteps = b.step_count || b.stepCount || (b.steps?.length || 0);
          return aSteps - bSteps;
        });
        break;
      case 'steps-desc':
        filtered.sort((a, b) => {
          const aSteps = a.step_count || a.stepCount || (a.steps?.length || 0);
          const bSteps = b.step_count || b.stepCount || (b.steps?.length || 0);
          return bSteps - aSteps;
        });
        break;
      case 'cost-asc':
      case 'cost-desc':
        // Cost is same for all templates with default preset, so no sorting needed
        break;
      case 'newest':
      default:
        // Keep original order (newest first from API)
        break;
    }

    setFilteredTemplates(filtered);
  };

  const handleViewTemplate = async (template) => {
    setSelectedTemplate(template);
    const detail = await loadTemplateDetail(template.id);
    if (detail) {
      setShowDetailModal(true);
    }
  };

  const handleExecuteClick = async (template) => {
    setSelectedTemplate(template);
    const detail = await loadTemplateDetail(template.id);
    if (detail) {
      setSelectedWorkflow(detail);
    }
  };

  const handleViewExecution = async (execution) => {
    try {
      const data = await apiJson(`/hierarchical/executions/${execution.id}`);
      setSelectedExecution(data.execution);
      setShowExecutionModal(true);

      // Start polling if running
      if (['running', 'waiting'].includes(data.execution.state)) {
        setPollingExecution(execution.id);
      }
    } catch (error) {
      console.error('Failed to load execution:', error);
      toast.error('Failed to load execution details');
    }
  };

  const handleCancelExecution = async (executionId) => {
    try {
      await apiJson(`/hierarchical/executions/${executionId}/cancel`, {
        method: 'POST',
      });
      notify.success('Execution cancelled');
      setPollingExecution(null);
      await loadExecutions();
    } catch (error) {
      console.error('Failed to cancel:', error);
      toast.error('Failed to cancel execution');
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Unknown';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatDuration = (seconds) => {
    if (!seconds) return '-';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs.toFixed(0)}s`;
  };

  const formatCost = (cost) => {
    if (!cost || cost === 0) return 'Free';
    return `$${cost.toFixed(4)}`;
  };

  return (
    <div className="min-h-screen p-4 md:p-6 lg:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <Breadcrumbs />
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-unicorn-500 to-unicorn-400 bg-clip-text text-transparent">
              Hierarchical Workflows
            </h1>
            <p className="text-slate-400 mt-1">
              3-Tier Agent Orchestration: Orchestrator → Team Leads → Workers
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
              onClick={() => { loadTemplates(); loadExecutions(); checkHealth(); }}
              className="p-2 bg-slate-800 hover:bg-slate-700 rounded-lg transition-colors"
              title="Refresh"
              aria-label="Refresh workflows"
            >
              <RefreshCw className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex space-x-4 border-b border-slate-700">
          <button
            onClick={() => setActiveTab('templates')}
            className={`px-4 py-2 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === 'templates'
                ? 'text-unicorn-400 border-unicorn-400'
                : 'text-slate-400 border-transparent hover:text-slate-200'
            }`}
          >
            <div className="flex items-center space-x-2">
              <GitBranch className="w-4 h-4" />
              <span>Workflow Templates</span>
              <span className="px-2 py-0.5 rounded-full bg-slate-800 text-xs">
                {templates.length}
              </span>
            </div>
          </button>
          <button
            onClick={() => setActiveTab('executions')}
            className={`px-4 py-2 font-medium transition-colors border-b-2 -mb-px ${
              activeTab === 'executions'
                ? 'text-unicorn-400 border-unicorn-400'
                : 'text-slate-400 border-transparent hover:text-slate-200'
            }`}
          >
            <div className="flex items-center space-x-2">
              <Activity className="w-4 h-4" />
              <span>Execution History</span>
              <span className="px-2 py-0.5 rounded-full bg-slate-800 text-xs">
                {executions.length}
              </span>
            </div>
          </button>
        </div>

        {/* Templates Tab */}
        {activeTab === 'templates' && (
          <>
            {/* Enhanced Filters */}
            <WorkflowFilters
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              selectedTag={selectedTag}
              setSelectedTag={setSelectedTag}
              selectedComplexity={selectedComplexity}
              setSelectedComplexity={setSelectedComplexity}
              viewMode={viewMode}
              setViewMode={setViewMode}
              sortBy={sortBy}
              setSortBy={setSortBy}
              allTags={allTags}
              resultCount={filteredTemplates.length}
              totalCount={templates.length}
            />

            {/* Gallery View */}
            <WorkflowGallery
              workflows={filteredTemplates}
              viewMode={viewMode}
              loading={loading}
              onViewDetails={handleViewTemplate}
              onExecute={handleExecuteClick}
            />

            {recentExecutions.length > 0 && (
              <div className="mt-8">
                <h3 className="text-xl font-bold text-white mb-4">Recent Executions</h3>
                {executionsLoading ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    <CardSkeleton count={3} />
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {recentExecutions.map(execution => (
                      <div
                        key={execution.id}
                        className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4"
                      >
                        <div className="flex justify-between items-start mb-2">
                          <span className="font-medium text-white">
                            {execution.workflowName || execution.workflow_name || execution.workflowId || execution.workflow_id}
                          </span>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            execution.state === 'completed' ? 'bg-green-500/20 text-green-400' :
                            execution.state === 'failed' ? 'bg-red-500/20 text-red-400' :
                            'bg-blue-500/20 text-blue-400'
                          }`}>
                            {execution.state}
                          </span>
                        </div>
                        <div className="text-sm text-slate-400">
                          {execution.startedAt || execution.started_at
                            ? new Date(execution.startedAt || execution.started_at).toLocaleString()
                            : 'Just now'}
                        </div>
                        {((execution.totalCost ?? execution.total_cost) !== undefined) && (
                          <div className="text-xs text-green-400 mt-2">
                            Cost: ${((execution.totalCost ?? execution.total_cost) || 0).toFixed(4)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* Executions Tab */}
        {activeTab === 'executions' && (
          <>
            {/* Execution Stats Summary */}
            {executionsLoading && (
              <div className="space-y-4">
                <TableSkeleton rows={6} columns={6} />
                <div className="lg:hidden">
                  <CardSkeleton count={4} />
                </div>
              </div>
            )}

            {!executionsLoading && executions.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-400">Total Executions</span>
                    <Activity className="w-4 h-4 text-unicorn-400" />
                  </div>
                  <p className="text-2xl font-bold text-white mt-1">{executions.length}</p>
                </div>
                <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-400">Completed</span>
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  </div>
                  <p className="text-2xl font-bold text-emerald-400 mt-1">
                    {executions.filter(e => e.state === 'completed').length}
                  </p>
                </div>
                <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-400">Running</span>
                    <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                  </div>
                  <p className="text-2xl font-bold text-blue-400 mt-1">
                    {executions.filter(e => ['running', 'waiting'].includes(e.state)).length}
                  </p>
                </div>
                <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-400">Total Cost</span>
                    <DollarSign className="w-4 h-4 text-amber-400" />
                  </div>
                  <p className="text-2xl font-bold text-amber-400 mt-1">
                    ${executions.reduce((sum, e) => sum + (e.total_cost || 0), 0).toFixed(4)}
                  </p>
                </div>
              </div>
            )}

            {/* Executions List */}
            {!executionsLoading && executions.length > 0 ? (
              <div className="backdrop-blur-xl bg-slate-900/50 border border-slate-700/50 rounded-xl overflow-hidden">
                <div className="hidden lg:block overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Workflow</th>
                        <th className="text-left px-6 py-4 text-sm font-medium text-slate-400">Status</th>
                        <th className="text-left px-6 py-4 text-sm font-medium text-slate-400 hidden md:table-cell">Started</th>
                        <th className="text-left px-6 py-4 text-sm font-medium text-slate-400 hidden lg:table-cell">Duration</th>
                        <th className="text-left px-6 py-4 text-sm font-medium text-slate-400 hidden lg:table-cell">Cost</th>
                        <th className="text-right px-6 py-4 text-sm font-medium text-slate-400">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {executions.map(execution => {
                        const status = statusConfig[execution.state] || statusConfig.pending;
                        const StatusIcon = status.icon;
                        const isActive = ['running', 'waiting'].includes(execution.state);

                        return (
                          <tr
                            key={execution.id}
                            className={`border-b border-slate-800 hover:bg-slate-800/50 transition-colors cursor-pointer ${
                              isActive ? 'bg-blue-500/5' : ''
                            }`}
                            onClick={() => handleViewExecution(execution)}
                          >
                            <td className="px-6 py-4">
                              <div>
                                <p className="font-medium text-white">{execution.workflow_name || execution.workflow_id}</p>
                                <p className="text-xs text-slate-400 font-mono">{execution.id.slice(0, 8)}...</p>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg ${status.bg}`}>
                                {isActive ? (
                                  <Loader2 className={`w-4 h-4 ${status.color} animate-spin`} />
                                ) : (
                                  <StatusIcon className={`w-4 h-4 ${status.color}`} />
                                )}
                                <span className={`text-sm capitalize ${status.color}`}>{execution.state}</span>
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm text-slate-400 hidden md:table-cell">
                              <div>
                                <p>{formatDate(execution.started_at)}</p>
                                {execution.completed_at && (
                                  <p className="text-xs text-slate-400">
                                    Completed: {formatDate(execution.completed_at)}
                                  </p>
                                )}
                              </div>
                            </td>
                            <td className="px-6 py-4 text-sm hidden lg:table-cell">
                              <span className={`${
                                execution.duration_seconds > 60 ? 'text-amber-400' :
                                execution.duration_seconds > 0 ? 'text-emerald-400' :
                                'text-slate-400'
                              }`}>
                                {formatDuration(execution.duration_seconds)}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm hidden lg:table-cell">
                              <span className={`font-medium ${
                                (execution.total_cost || 0) === 0 ? 'text-emerald-400' :
                                (execution.total_cost || 0) < 0.1 ? 'text-slate-300' :
                                'text-amber-400'
                              }`}>
                                {formatCost(execution.total_cost)}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-right">
                              <div className="flex items-center justify-end space-x-2">
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleViewExecution(execution); }}
                                  className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
                                  title="View Details"
                                  aria-label="View execution details"
                                >
                                  <Eye className="w-4 h-4 text-slate-400 hover:text-white" />
                                </button>
                                {isActive && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleCancelExecution(execution.id); }}
                                    className="p-2 hover:bg-red-500/20 rounded-lg transition-colors"
                                    title="Cancel"
                                    aria-label="Cancel execution"
                                  >
                                    <XCircle className="w-4 h-4 text-red-400" />
                                  </button>
                                )}
                                {execution.state === 'completed' && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      // Find template and re-run
                                      const template = templates.find(t => t.id === execution.workflow_id);
                                      if (template) handleExecuteClick(template);
                                    }}
                                    className="p-2 hover:bg-unicorn-500/20 rounded-lg transition-colors"
                                    title="Run Again"
                                    aria-label="Run workflow again"
                                  >
                                    <RefreshCw className="w-4 h-4 text-unicorn-400" />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="lg:hidden space-y-4 p-4">
                  {executions.map((execution) => {
                    const status = statusConfig[execution.state] || statusConfig.pending;
                    const StatusIcon = status.icon;
                    const isActive = ['running', 'waiting'].includes(execution.state);

                    return (
                      <div
                        key={execution.id}
                        className="bg-slate-800/60 border border-slate-700/50 rounded-lg p-4 space-y-3"
                        onClick={() => handleViewExecution(execution)}
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div>
                            <p className="font-medium text-white">
                              {execution.workflow_name || execution.workflow_id}
                            </p>
                            <p className="text-xs text-slate-400 font-mono">{execution.id.slice(0, 8)}...</p>
                          </div>
                          <span className={`inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg ${status.bg}`}>
                            {isActive ? (
                              <Loader2 className={`w-4 h-4 ${status.color} animate-spin`} />
                            ) : (
                              <StatusIcon className={`w-4 h-4 ${status.color}`} />
                            )}
                            <span className={`text-xs capitalize ${status.color}`}>{execution.state}</span>
                          </span>
                        </div>

                        <div className="text-sm text-slate-400">
                          <span className="font-medium text-slate-300">Started:</span> {formatDate(execution.started_at)}
                        </div>

                        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
                          <span>
                            Duration: {formatDuration(execution.duration_seconds)}
                          </span>
                          <span>
                            Cost: {formatCost(execution.total_cost)}
                          </span>
                        </div>

                        <div className="flex items-center gap-2 pt-2 border-t border-slate-700/50">
                          <button
                            onClick={(e) => { e.stopPropagation(); handleViewExecution(execution); }}
                            className="px-3 py-2 min-h-[44px] bg-slate-700/60 text-slate-200 rounded-lg hover:bg-slate-600 transition-colors"
                          >
                            View
                          </button>
                          {isActive && (
                            <button
                              onClick={(e) => { e.stopPropagation(); handleCancelExecution(execution.id); }}
                              className="px-3 py-2 min-h-[44px] bg-red-500/20 text-red-300 rounded-lg hover:bg-red-500/30 transition-colors"
                            >
                              Cancel
                            </button>
                          )}
                          {execution.state === 'completed' && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                const template = templates.find(t => t.id === execution.workflow_id);
                                if (template) handleExecuteClick(template);
                              }}
                              className="px-3 py-2 min-h-[44px] bg-unicorn-500/20 text-unicorn-300 rounded-lg hover:bg-unicorn-500/30 transition-colors"
                            >
                              Run Again
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : !executionsLoading ? (
              <div className="text-center py-12">
                <Activity className="w-16 h-16 text-slate-600 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-slate-300 mb-2">No executions yet</h3>
                <p className="text-slate-400 mb-6">Run a workflow to see its execution history here</p>
                <button
                  onClick={() => setActiveTab('templates')}
                  className="px-4 py-2 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors"
                >
                  Browse Workflows
                </button>
              </div>
            ) : (
              <TableSkeleton rows={5} columns={6} />
            )}
          </>
        )}
      </div>

      {/* Template Detail Modal */}
      {showDetailModal && templateDetail && (
        <Modal
          onClose={() => setShowDetailModal(false)}
          ariaLabel={`${templateDetail.name} details`}
          showClose={false}
          panelClassName="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-4xl w-full max-h-[85vh] overflow-y-auto focus:outline-none"
        >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-4">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-unicorn-600 to-unicorn-500 flex items-center justify-center">
                  <GitBranch className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">{templateDetail.name}</h2>
                  <p className="text-slate-400">{templateDetail.description}</p>
                </div>
              </div>
              <button
                onClick={() => setShowDetailModal(false)}
                aria-label="Close dialog"
                className="text-slate-400 hover:text-white p-3 min-h-[44px] min-w-[44px] hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2 mb-6">
              {(templateDetail.tags || []).map(tag => (
                <span
                  key={tag}
                  className={`px-3 py-1 rounded text-sm border ${tagColors[tag] || 'bg-slate-500/20 text-slate-400 border-slate-500/30'}`}
                >
                  {tag}
                </span>
              ))}
            </div>

            {/* Required Inputs */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-white mb-3">Required Inputs</h3>
              <div className="flex flex-wrap gap-2">
              {(templateDetail.required_inputs || templateDetail.requiredInputs || []).map(input => (
                  <span
                    key={input}
                    className="px-3 py-1 bg-slate-800 rounded text-sm text-slate-300 font-mono"
                  >
                    {input}
                  </span>
                ))}
              </div>
            </div>

            {/* Team Leads */}
            {templateDetail.team_leads && templateDetail.team_leads.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Team Leads Involved</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {templateDetail.team_leads.map(lead => (
                    <div
                      key={lead.id}
                      className="p-4 bg-slate-800/50 rounded-lg border border-slate-700"
                    >
                      <div className="flex items-center space-x-3">
                        <Users className="w-5 h-5 text-unicorn-400" />
                        <div>
                          <p className="font-medium text-white">{lead.name}</p>
                          <p className="text-xs text-slate-400">{lead.domain} domain</p>
                        </div>
                      </div>
                      {lead.workers && lead.workers.length > 0 && (
                        <p className="text-xs text-slate-400 mt-2">
                          {lead.workers.length} workers available
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Workflow Steps */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold text-white">Workflow Steps</h3>
                <div className="flex items-center space-x-2 bg-slate-800/50 rounded-lg p-1">
                  <button
                    onClick={() => setDetailViewMode('diagram')}
                    className={`px-3 py-1.5 rounded-md flex items-center space-x-2 transition-colors ${
                      detailViewMode === 'diagram'
                        ? 'bg-unicorn-500 text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <Network className="w-4 h-4" />
                    <span className="text-sm">Diagram</span>
                  </button>
                  <button
                    onClick={() => setDetailViewMode('list')}
                    className={`px-3 py-1.5 rounded-md flex items-center space-x-2 transition-colors ${
                      detailViewMode === 'list'
                        ? 'bg-unicorn-500 text-white'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <List className="w-4 h-4" />
                    <span className="text-sm">List</span>
                  </button>
                </div>
              </div>

              {detailViewMode === 'diagram' ? (
                <WorkflowDiagram workflow={templateDetail} />
              ) : (
                <div className="space-y-3">
                  {(templateDetail.steps || []).map((step, idx) => (
                    <div
                      key={step.id}
                      className="flex items-start space-x-4 p-4 bg-slate-800/50 rounded-lg border border-slate-700"
                    >
                      <div className="w-8 h-8 rounded-full bg-unicorn-500/20 flex items-center justify-center text-unicorn-400 font-semibold text-sm flex-shrink-0">
                        {idx + 1}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <h4 className="font-medium text-white">{step.name}</h4>
                          <span className="text-xs text-slate-400 font-mono">{step.executor}</span>
                        </div>
                        <p className="text-sm text-slate-400 mt-1">{step.description}</p>
                        {step.outputs && step.outputs.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {step.outputs.map(output => (
                              <span
                                key={output}
                                className="px-2 py-0.5 bg-slate-700 rounded text-xs text-slate-300"
                              >
                                {output}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      {idx < (templateDetail.steps || []).length - 1 && (
                        <ArrowRight className="w-4 h-4 text-slate-600 flex-shrink-0 mt-2" />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Checkpoints */}
            {templateDetail.checkpoints && templateDetail.checkpoints.length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Human Checkpoints</h3>
                <div className="space-y-3">
                  {templateDetail.checkpoints.map(checkpoint => (
                    <div
                      key={checkpoint.id}
                      className="p-4 bg-amber-500/10 rounded-lg border border-amber-500/30"
                    >
                      <div className="flex items-center space-x-2 mb-2">
                        <PauseCircle className="w-5 h-5 text-amber-400" />
                        <span className="font-medium text-amber-400">{checkpoint.name}</span>
                        <span className="px-2 py-0.5 rounded bg-amber-500/20 text-xs text-amber-400">
                          {checkpoint.type}
                        </span>
                      </div>
                      <p className="text-sm text-slate-400">{checkpoint.prompt}</p>
                      {checkpoint.options && checkpoint.options.length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {checkpoint.options.map(option => (
                            <span
                              key={option}
                              className="px-2 py-1 bg-slate-800 rounded text-xs text-slate-300"
                            >
                              {option}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex space-x-3 pt-4 border-t border-slate-700">
              <button
                onClick={() => { setShowDetailModal(false); handleExecuteClick(selectedTemplate); }}
                className="flex-1 px-4 py-3 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-500 hover:to-unicorn-400 transition-colors flex items-center justify-center space-x-2"
              >
                <Play className="w-5 h-5" />
                <span>Execute Workflow</span>
              </button>
            </div>
        </Modal>
      )}

      {/* Execution Detail Modal */}
      {showExecutionModal && selectedExecution && (
        <Modal
          onClose={() => { setShowExecutionModal(false); setPollingExecution(null); }}
          ariaLabel={`${selectedExecution.workflow_name || selectedExecution.workflow_id} execution`}
          showClose={false}
          panelClassName="backdrop-blur-xl bg-slate-900/95 border border-slate-700/50 rounded-xl p-8 max-w-4xl w-full max-h-[85vh] overflow-y-auto focus:outline-none"
        >
            <div className="flex items-start justify-between mb-6">
              <div className="flex items-center space-x-4">
                <div className={`w-12 h-12 rounded-lg flex items-center justify-center ${statusConfig[selectedExecution.state]?.bg || 'bg-slate-700'}`}>
                  {(() => {
                    const StatusIcon = statusConfig[selectedExecution.state]?.icon || Clock;
                    return <StatusIcon className={`w-6 h-6 ${statusConfig[selectedExecution.state]?.color || 'text-slate-400'}`} />;
                  })()}
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-white">
                    {selectedExecution.workflow_name || selectedExecution.workflow_id}
                  </h2>
                  <p className="text-slate-400 font-mono text-sm">{selectedExecution.id}</p>
                </div>
              </div>
              <button
                onClick={() => { setShowExecutionModal(false); setPollingExecution(null); }}
                aria-label="Close dialog"
                className="text-slate-400 hover:text-white p-3 min-h-[44px] min-w-[44px] hover:bg-slate-800 rounded-lg transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Status Banner */}
            <div className={`p-4 rounded-lg mb-6 ${statusConfig[selectedExecution.state]?.bg || 'bg-slate-800'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  {(() => {
                    const StatusIcon = statusConfig[selectedExecution.state]?.icon || Clock;
                    return <StatusIcon className={`w-5 h-5 ${statusConfig[selectedExecution.state]?.color || 'text-slate-400'}`} />;
                  })()}
                  <span className={`font-medium capitalize ${statusConfig[selectedExecution.state]?.color || 'text-slate-400'}`}>
                    {selectedExecution.state}
                  </span>
                  {['running', 'waiting'].includes(selectedExecution.state) && (
                    <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                  )}
                </div>
                <div className="flex items-center space-x-4 text-sm">
                  {selectedExecution.duration_seconds && (
                    <span className="text-slate-400">
                      <Timer className="w-4 h-4 inline mr-1" />
                      {formatDuration(selectedExecution.duration_seconds)}
                    </span>
                  )}
                  <span className="text-slate-400">
                    <DollarSign className="w-4 h-4 inline" />
                    {formatCost(selectedExecution.total_cost)}
                  </span>
                  {selectedExecution.total_tokens && (
                    <span className="text-slate-400">
                      <BarChart3 className="w-4 h-4 inline mr-1" />
                      {selectedExecution.total_tokens.toLocaleString()} tokens
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Step Results */}
            {selectedExecution.step_results && Object.keys(selectedExecution.step_results).length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Step Results</h3>
                <div className="space-y-3">
                  {Object.entries(selectedExecution.step_results).map(([stepId, result], idx) => (
                    <div
                      key={stepId}
                      className="p-4 bg-slate-800/50 rounded-lg border border-slate-700"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-3">
                          <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center">
                            <CheckCircle className="w-4 h-4 text-emerald-400" />
                          </div>
                          <span className="font-medium text-white">{stepId}</span>
                        </div>
                        {result.model_used && (
                          <span className="text-xs text-slate-400 font-mono">{result.model_used}</span>
                        )}
                      </div>
                      <div className="bg-slate-900 rounded p-3 overflow-x-auto">
                        <pre className="text-sm text-slate-300 whitespace-pre-wrap">
                          {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
                        </pre>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Final Outputs */}
            {selectedExecution.outputs && Object.keys(selectedExecution.outputs).length > 0 && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Final Outputs</h3>
                <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(selectedExecution.outputs, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Error Message */}
            {selectedExecution.error && (
              <div className="mb-6 p-4 bg-red-500/10 rounded-lg border border-red-500/30">
                <div className="flex items-center space-x-2 mb-2">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <span className="font-medium text-red-400">Error</span>
                </div>
                <p className="text-sm text-red-300">{selectedExecution.error}</p>
              </div>
            )}

            {/* Model Config Used */}
            {selectedExecution.model_config_used && (
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-white mb-3">Model Configuration</h3>
                <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
                  <pre className="text-sm text-slate-300 whitespace-pre-wrap overflow-x-auto">
                    {JSON.stringify(selectedExecution.model_config_used, null, 2)}
                  </pre>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex space-x-3 pt-4 border-t border-slate-700">
              {['running', 'waiting'].includes(selectedExecution.state) && (
                <button
                  onClick={() => handleCancelExecution(selectedExecution.id)}
                  className="px-4 py-2 bg-red-500/20 text-red-400 rounded-lg hover:bg-red-500/30 transition-colors flex items-center space-x-2"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Cancel Execution</span>
                </button>
              )}
              <button
                onClick={() => { setShowExecutionModal(false); setPollingExecution(null); }}
                className="flex-1 px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors"
              >
                Close
              </button>
            </div>
        </Modal>
      )}

      {selectedWorkflow && (
        <WorkflowExecutionPanel
          workflow={selectedWorkflow}
          onClose={() => setSelectedWorkflow(null)}
          onExecutionComplete={(execution) => {
            setRecentExecutions(prev => [execution, ...prev].slice(0, 10));
            setSelectedWorkflow(null);
            loadExecutions();
          }}
        />
      )}
    </div>
  );
};

export default Workflows;
