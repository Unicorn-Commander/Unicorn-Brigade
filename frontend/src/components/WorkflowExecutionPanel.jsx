import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  X,
  Play,
  StopCircle,
  CheckCircle,
  AlertCircle,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
  Terminal,
  AlertTriangle,
  Zap,
  RefreshCw
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import api from '../services/api';

const terminalExecutionStates = new Set(['completed', 'failed', 'cancelled']);

const getRequiredInputs = (workflow) => workflow.required_inputs || workflow.requiredInputs || [];

const normalizeExecution = (raw) => {
  const exec = raw?.execution || raw?.data?.execution || raw || {};
  return {
    id: exec.id || exec.execution_id || exec.executionId,
    workflowId: exec.workflowId || exec.workflow_id,
    workflowName: exec.workflowName || exec.workflow_name,
    state: exec.state || exec.status,
    startedAt: exec.startedAt || exec.started_at,
    completedAt: exec.completedAt || exec.completed_at,
    outputs: exec.outputs || exec.result,
    totalCost: exec.totalCost || exec.total_cost,
    totalTokens: exec.totalTokens || exec.total_tokens,
    stepExecutions: exec.stepExecutions || exec.step_executions || exec.step_results || {},
    error: exec.error,
    modelConfigUsed: exec.modelConfigUsed || exec.model_config_used,
    pendingCheckpoint: exec.pendingCheckpoint || exec.pending_checkpoint,
    checkpointResponses: exec.checkpointResponses || exec.checkpoint_responses,
    raw: exec,
  };
};

const normalizeStepExecutions = (stepExecutions) => {
  if (Array.isArray(stepExecutions)) {
    return stepExecutions.map((step) => ({
      stepId: step.stepId || step.step_id,
      state: step.state || step.status,
      startedAt: step.startedAt || step.started_at,
      completedAt: step.completedAt || step.completed_at,
      executorId: step.executorId || step.executor_id,
      modelUsed: step.modelUsed || step.model_used,
      inputsReceived: step.inputsReceived || step.inputs_received,
      outputs: step.outputs,
      workerCalls: step.workerCalls || step.worker_calls,
      error: step.error,
      retries: step.retries,
      tokensUsed: step.tokensUsed || step.tokens_used,
      estimatedCost: step.estimatedCost || step.estimated_cost,
      raw: step,
    }));
  }

  return Object.entries(stepExecutions || {}).map(([key, value]) => ({
    stepId: value?.stepId || value?.step_id || key,
    state: value?.state || value?.status,
    startedAt: value?.startedAt || value?.started_at,
    completedAt: value?.completedAt || value?.completed_at,
    executorId: value?.executorId || value?.executor_id,
    modelUsed: value?.modelUsed || value?.model_used,
    inputsReceived: value?.inputsReceived || value?.inputs_received,
    outputs: value?.outputs,
    workerCalls: value?.workerCalls || value?.worker_calls,
    error: value?.error,
    retries: value?.retries,
    tokensUsed: value?.tokensUsed || value?.tokens_used,
    estimatedCost: value?.estimatedCost || value?.estimated_cost,
    raw: value,
  }));
};

const toSeconds = (start, end) => {
  if (!start || !end) return null;
  const startDate = new Date(start);
  const endDate = new Date(end);
  if (Number.isNaN(startDate.valueOf()) || Number.isNaN(endDate.valueOf())) return null;
  return (endDate - startDate) / 1000;
};

const getStepIcon = (status) => {
  switch (status) {
    case 'completed':
      return <CheckCircle className="w-5 h-5 text-green-400" />;
    case 'failed':
      return <AlertCircle className="w-5 h-5 text-red-400" />;
    case 'running':
    case 'delegating':
    case 'waiting_workers':
    case 'aggregating':
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    case 'skipped':
      return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
    default:
      return <Clock className="w-5 h-5 text-slate-400" />;
  }
};

const getStateColor = (state) => {
  switch (state) {
    case 'completed':
      return 'text-green-400';
    case 'failed':
      return 'text-red-400';
    case 'running':
    case 'waiting_checkpoint':
    case 'paused':
      return 'text-blue-400';
    case 'cancelled':
      return 'text-orange-400';
    default:
      return 'text-slate-400';
  }
};

export default function WorkflowExecutionPanel({ workflow, onClose, onExecutionComplete }) {
  const [inputs, setInputs] = useState({});
  const [execution, setExecution] = useState(null);
  const [executionSource, setExecutionSource] = useState('hierarchical');
  const [loading, setLoading] = useState(false);
  const [expandedSteps, setExpandedSteps] = useState(new Set());
  const [autoScroll, setAutoScroll] = useState(true);
  const [ralphProgress, setRalphProgress] = useState(null);
  const [ralphResult, setRalphResult] = useState(null);
  const [discoveryStartedAt, setDiscoveryStartedAt] = useState(null);
  const progressRef = useRef(null);

  useEffect(() => {
    const initialInputs = {};
    getRequiredInputs(workflow).forEach((input) => {
      initialInputs[input] = '';
    });
    setInputs(initialInputs);
    setExecution(null);
    setExecutionSource('hierarchical');
    setRalphProgress(null);
    setRalphResult(null);
    setExpandedSteps(new Set());
    setDiscoveryStartedAt(null);
  }, [workflow]);

  useEffect(() => {
    if (autoScroll && progressRef.current) {
      progressRef.current.scrollTop = progressRef.current.scrollHeight;
    }
  }, [execution, ralphProgress, autoScroll]);

  useEffect(() => {
    if (!execution?.id || executionSource !== 'hierarchical') return;
    if (terminalExecutionStates.has(execution.state)) return;

    const interval = setInterval(async () => {
      try {
        const updatedRaw = await api.getWorkflowExecutionDetails(execution.id);
        const updated = normalizeExecution(updatedRaw);
        setExecution(updated);

        if (terminalExecutionStates.has(updated.state)) {
          clearInterval(interval);
          if (updated.state === 'completed') {
            notify.success('Workflow completed successfully');
            onExecutionComplete?.(updated);
          } else if (updated.state === 'failed') {
            toast.error('Workflow failed');
          }
        }
      } catch (error) {
        console.error('Failed to fetch execution status:', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [execution?.id, execution?.state, executionSource, onExecutionComplete]);

  useEffect(() => {
    if (!discoveryStartedAt || execution?.id || executionSource !== 'hierarchical') return;

    const interval = setInterval(async () => {
      try {
        const list = await api.getWorkflowExecutions();
        const executions = list.executions || list.execution || list || [];
        const candidates = executions
          .map(normalizeExecution)
          .filter((exec) => exec.workflowId === workflow.id || exec.workflowName === workflow.name)
          .filter((exec) => {
            if (!exec.startedAt) return true;
            return new Date(exec.startedAt).valueOf() >= discoveryStartedAt;
          });

        if (candidates.length > 0) {
          const newest = candidates.sort((a, b) => {
            const aTime = a.startedAt ? new Date(a.startedAt).valueOf() : 0;
            const bTime = b.startedAt ? new Date(b.startedAt).valueOf() : 0;
            return bTime - aTime;
          })[0];
          setExecution(newest);
          setDiscoveryStartedAt(null);
        }
      } catch (error) {
        console.error('Failed to discover execution:', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [discoveryStartedAt, execution?.id, executionSource, workflow.id, workflow.name]);

  useEffect(() => {
    if (!execution?.id || executionSource !== 'ralph') return;

    const interval = setInterval(async () => {
      try {
        const progress = await api.getRalphProgress(execution.id);
        setRalphProgress(progress);

        if (progress.is_complete) {
          clearInterval(interval);
          const result = await api.getRalphResult(execution.id);
          setRalphResult(result);
          setExecution((prev) => ({
            ...prev,
            state: result.outcome === 'success' ? 'completed' : 'failed',
          }));
          if (result.outcome === 'success') {
            notify.success('Self-correction completed successfully');
          } else {
            toast.error('Self-correction failed');
          }
        }
      } catch (error) {
        console.error('Failed to fetch Ralph progress:', error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [execution?.id, executionSource]);

  const handleExecute = async (e) => {
    e.preventDefault();

    const requiredInputs = getRequiredInputs(workflow);
    const missingInputs = requiredInputs.filter(
      (input) => !inputs[input] || inputs[input].trim() === ''
    );

    if (missingInputs.length > 0) {
      toast.error(`Missing required inputs: ${missingInputs.join(', ')}`);
      return;
    }

    setLoading(true);
    setExecution({
      id: null,
      workflowId: workflow.id,
      workflowName: workflow.name,
      state: 'running',
      stepExecutions: {},
    });
    setDiscoveryStartedAt(Date.now());
    try {
      const resultRaw = await api.executeWorkflow(workflow.id, inputs, null, true);
      const result = normalizeExecution(resultRaw);

      if (result.id && result.id !== 'pending') {
        setExecution(result);
      } else {
        setExecution((prev) => ({
          ...prev,
          state: prev?.state || 'queued',
        }));
      }

      notify.success('Workflow execution started');
    } catch (error) {
      console.error('Failed to start workflow:', error);
      toast.error(error?.message || 'Failed to start workflow');
      setExecution(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!execution?.id) return;

    try {
      if (executionSource === 'ralph') {
        await api.cancelRalphExecution(execution.id);
      } else {
        await api.cancelWorkflowExecution(execution.id);
      }
      notify.success('Workflow cancelled');
      setExecution((prev) => ({ ...prev, state: 'cancelled' }));
    } catch (error) {
      toast.error('Failed to cancel workflow');
    }
  };

  const handleRetryWithRalph = async () => {
    setLoading(true);
    try {
      const result = await api.executeRalphWorkflow(workflow.id, inputs, {
        async_execution: true,
        max_iterations: 5,
        retry_failed_execution: execution?.id,
      });

      setExecution({
        id: result.execution_id,
        workflowId: result.workflow_id,
        workflowName: workflow.name,
        state: result.status || 'running',
      });
      setExecutionSource('ralph');
      setRalphProgress(null);
      setRalphResult(null);
      notify.success('Retrying with self-correction enabled');
    } catch (error) {
      toast.error(error?.message || 'Failed to retry workflow');
    } finally {
      setLoading(false);
    }
  };

  const toggleStep = (stepId) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(stepId)) {
        next.delete(stepId);
      } else {
        next.add(stepId);
      }
      return next;
    });
  };

  const stepDefinitions = workflow.steps || workflow.workflowSteps || [];
  const stepExecutionList = normalizeStepExecutions(execution?.stepExecutions || {});

  const steps = useMemo(() => {
    const resolved = [];
    const usedStepIds = new Set();

    stepDefinitions.forEach((stepDef, index) => {
      const stepId = stepDef.id || stepDef.step_id || stepDef.name || `step-${index + 1}`;
      const matching = stepExecutionList.find((item) => item.stepId === stepId) || stepExecutionList[index];

      usedStepIds.add(stepId);

      const duration = toSeconds(matching?.startedAt, matching?.completedAt);

      resolved.push({
        id: stepId,
        name: stepDef.name || stepDef.title || stepDef.executor || `Step ${index + 1}`,
        assignedTo: stepDef.executor || stepDef.assigned_to || stepDef.assignedTo,
        status: matching?.state || 'pending',
        duration,
        error: matching?.error,
        result: matching?.outputs,
        metadata: {
          model_used: matching?.modelUsed,
          executor_id: matching?.executorId,
          tokens_used: matching?.tokensUsed,
          estimated_cost: matching?.estimatedCost,
          retries: matching?.retries,
        },
      });
    });

    stepExecutionList.forEach((stepExec, index) => {
      if (usedStepIds.has(stepExec.stepId)) return;
      const duration = toSeconds(stepExec.startedAt, stepExec.completedAt);
      resolved.push({
        id: stepExec.stepId || `step-exec-${index + 1}`,
        name: stepExec.stepId || `Step ${index + 1}`,
        assignedTo: stepExec.executorId,
        status: stepExec.state || 'pending',
        duration,
        error: stepExec.error,
        result: stepExec.outputs,
        metadata: {
          model_used: stepExec.modelUsed,
          executor_id: stepExec.executorId,
          tokens_used: stepExec.tokensUsed,
          estimated_cost: stepExec.estimatedCost,
          retries: stepExec.retries,
        },
      });
    });

    return resolved;
  }, [stepDefinitions, stepExecutionList]);

  const completedStepCount = steps.filter((step) => step.status === 'completed').length;
  const totalStepCount = steps.length;
  const progressPercent = execution?.raw?.progress_percent
    ?? (totalStepCount > 0 ? Math.round((completedStepCount / totalStepCount) * 100) : 0);
  const currentStepIndex = execution?.raw?.current_step ?? completedStepCount;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800/90 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl w-full max-w-6xl max-h-[90vh] flex flex-col">
        <div className="flex justify-between items-start p-6 border-b border-slate-700/50">
          <div>
            <h2 className="text-2xl font-bold text-white">{workflow.name}</h2>
            <p className="text-sm text-slate-400 mt-1">{workflow.description}</p>
            <div className="flex gap-2 mt-2">
              {workflow.tags?.map((tag) => (
                <span
                  key={tag}
                  className="px-2 py-1 bg-unicorn-500/20 text-unicorn-400 text-xs rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-3 min-h-[44px] min-w-[44px] hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
          <div className="w-full lg:w-1/3 border-b lg:border-b-0 lg:border-r border-slate-700/50 p-6 overflow-y-auto">
            <h3 className="text-lg font-semibold text-white mb-4">
              {execution ? 'Inputs (Submitted)' : 'Configure Workflow'}
            </h3>

            <form onSubmit={handleExecute} className="space-y-4">
              {getRequiredInputs(workflow).map((input) => (
                <div key={input}>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    {input.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    value={inputs[input] || ''}
                    onChange={(e) => setInputs({ ...inputs, [input]: e.target.value })}
                    disabled={!!execution}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-unicorn-500 disabled:opacity-50 min-h-[80px]"
                    placeholder={`Enter ${input.replace(/_/g, ' ')}...`}
                  />
                </div>
              ))}

              {!execution && (
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full px-4 py-3 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-600 hover:to-unicorn-500 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Starting...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5" />
                      <span>Execute Workflow</span>
                    </>
                  )}
                </button>
              )}

              {execution && ['running', 'waiting_checkpoint', 'paused'].includes(execution.state) && (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center space-x-2"
                >
                  <StopCircle className="w-5 h-5" />
                  <span>Cancel Workflow</span>
                </button>
              )}

              {execution && execution.state === 'failed' && (
                <button
                  type="button"
                  onClick={handleRetryWithRalph}
                  disabled={loading}
                  className="w-full px-4 py-3 bg-gradient-to-r from-orange-600 to-yellow-600 text-white rounded-lg hover:from-orange-700 hover:to-yellow-700 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  <Zap className="w-5 h-5" />
                  <span>Retry with Self-Correction</span>
                </button>
              )}
            </form>

            {execution && (
              <div className="mt-6 pt-6 border-t border-slate-700/50 space-y-3">
                <h4 className="text-sm font-semibold text-slate-300">Execution Info</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Status:</span>
                    <span className={`font-medium ${getStateColor(execution.state)}`}>
                      {(execution.state || 'pending').toUpperCase()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Steps:</span>
                    <span className="text-white">
                      {completedStepCount} / {totalStepCount}
                    </span>
                  </div>
                  {execution.totalCost !== undefined && execution.totalCost !== null && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Cost:</span>
                      <span className="text-green-400">${execution.totalCost.toFixed(4)}</span>
                    </div>
                  )}
                  {execution.startedAt && (
                    <div className="flex justify-between">
                      <span className="text-slate-400">Started:</span>
                      <span className="text-white text-xs">
                        {new Date(execution.startedAt).toLocaleTimeString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="flex-1 flex flex-col">
            {execution ? (
              <>
                <div className="p-4 border-b border-slate-700/50 flex justify-between items-center bg-slate-800/50">
                  <h3 className="text-lg font-semibold text-white">Execution Progress</h3>
                  <label className="flex items-center space-x-2 text-sm text-slate-400">
                    <input
                      type="checkbox"
                      checked={autoScroll}
                      onChange={(e) => setAutoScroll(e.target.checked)}
                      className="rounded text-unicorn-600 focus:ring-unicorn-500"
                    />
                    <span>Auto-scroll</span>
                  </label>
                </div>

                <div ref={progressRef} className="flex-1 overflow-y-auto p-6 space-y-3">
                  {execution.state === 'running' && (
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-slate-400">
                          Step {currentStepIndex} of {totalStepCount || '?'}
                        </span>
                        <span className="text-sm text-unicorn-400">
                          {progressPercent}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-700/50 rounded-full h-2">
                        <div
                          className="bg-gradient-to-r from-unicorn-600 to-unicorn-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {executionSource === 'ralph' && (
                    <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-4 mb-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <RefreshCw className="w-5 h-5 text-orange-400" />
                          <span className="text-sm font-medium text-orange-300">Self-Correction in Progress</span>
                        </div>
                        {ralphProgress?.progress_percent !== undefined && (
                          <span className="text-sm text-orange-200">
                            {ralphProgress.progress_percent}%
                          </span>
                        )}
                      </div>
                      {ralphProgress && (
                        <div className="mt-3 text-xs text-slate-300 grid grid-cols-2 gap-2">
                          <div>Iteration: {ralphProgress.iteration} / {ralphProgress.max_iterations}</div>
                          <div>Tasks: {ralphProgress.tasks?.completed || 0} / {ralphProgress.tasks?.total || 0}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {steps.map((step, index) => (
                    <div
                      key={step.id}
                      className="bg-slate-700/30 border border-slate-600/50 rounded-lg overflow-hidden"
                    >
                      <button
                        onClick={() => toggleStep(step.id)}
                        className="w-full flex items-center justify-between p-4 hover:bg-slate-700/50 transition-colors"
                      >
                        <div className="flex items-center space-x-3">
                          {getStepIcon(step.status)}
                          <div className="text-left">
                            <div className="font-medium text-white">
                              Step {index + 1}: {step.name}
                            </div>
                            {step.assignedTo && (
                              <div className="text-xs text-slate-400 mt-1">
                                Assigned to: {step.assignedTo}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center space-x-3">
                          {step.duration !== null && step.duration !== undefined && (
                            <span className="text-xs text-slate-400">
                              {step.duration.toFixed(2)}s
                            </span>
                          )}
                          {expandedSteps.has(step.id) ? (
                            <ChevronDown className="w-5 h-5 text-slate-400" />
                          ) : (
                            <ChevronRight className="w-5 h-5 text-slate-400" />
                          )}
                        </div>
                      </button>

                      {expandedSteps.has(step.id) && (
                        <div className="px-4 pb-4 space-y-3 border-t border-slate-600/50 pt-4">
                          {step.error && (
                            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                              <div className="flex items-start space-x-2">
                                <AlertCircle className="w-5 h-5 text-red-400 mt-0.5" />
                                <div className="flex-1">
                                  <div className="text-sm font-medium text-red-300">Error</div>
                                  <div className="text-sm text-red-200 mt-1">{step.error}</div>
                                </div>
                              </div>
                            </div>
                          )}

                          {step.result && (
                            <div className="bg-slate-800/50 rounded-lg p-3">
                              <div className="flex items-center space-x-2 mb-2">
                                <Terminal className="w-4 h-4 text-slate-400" />
                                <span className="text-sm font-medium text-slate-300">Result</span>
                              </div>
                              <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                                {typeof step.result === 'string'
                                  ? step.result
                                  : JSON.stringify(step.result, null, 2)}
                              </pre>
                            </div>
                          )}

                          {step.metadata && (
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              {Object.entries(step.metadata)
                                .filter(([, value]) => value !== undefined && value !== null && value !== '')
                                .map(([key, value]) => (
                                  <div key={key} className="flex justify-between">
                                    <span className="text-slate-400">{key}:</span>
                                    <span className="text-white">{String(value)}</span>
                                  </div>
                                ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}

                  {steps.length === 0 && (
                    <div className="text-center py-12 text-slate-400">
                      <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3" />
                      <p>Initializing workflow execution...</p>
                    </div>
                  )}
                </div>

                {execution.state === 'completed' && execution.outputs && (
                  <div className="p-6 border-t border-slate-700/50 bg-green-500/5">
                    <h4 className="text-lg font-semibold text-green-400 mb-3 flex items-center space-x-2">
                      <CheckCircle className="w-5 h-5" />
                      <span>Workflow Completed</span>
                    </h4>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <pre className="text-sm text-slate-300 overflow-x-auto whitespace-pre-wrap">
                        {typeof execution.outputs === 'string'
                          ? execution.outputs
                          : JSON.stringify(execution.outputs, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}

                {executionSource === 'ralph' && ralphResult && (
                  <div className="p-6 border-t border-slate-700/50 bg-orange-500/5">
                    <h4 className="text-lg font-semibold text-orange-300 mb-3 flex items-center space-x-2">
                      <RefreshCw className="w-5 h-5" />
                      <span>Self-Correction Result</span>
                    </h4>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <pre className="text-sm text-slate-300 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(ralphResult, null, 2)}
                      </pre>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-400">
                <div className="text-center">
                  <Play className="w-16 h-16 mx-auto mb-4 opacity-50" />
                  <p className="text-lg">Ready to execute</p>
                  <p className="text-sm mt-2">Fill in the inputs and click Execute Workflow</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
