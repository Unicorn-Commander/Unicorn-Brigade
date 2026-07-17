import React, { useState } from 'react';
import {
  Play,
  StopCircle,
  RefreshCw,
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  Server,
  Terminal,
  Code
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import notify from '../utils/notify';
import api from '../services/api';
import Modal from './ui/Modal';

export default function MCPServerControlPanel({ server, onClose, onServerUpdated }) {
  const [actionLoading, setActionLoading] = useState(null); // 'start', 'stop', 'restart'
  const [serverDetails, setServerDetails] = useState(server);
  const [testingTool, setTestingTool] = useState(null);
  const [testArgsText, setTestArgsText] = useState('{}');
  const [testResult, setTestResult] = useState(null);
  const [testLoading, setTestLoading] = useState(false);

  const refreshDetails = async () => {
    const updated = await api.getMCPServerDetails(server.name);
    setServerDetails(updated);
    onServerUpdated?.(updated);
  };

  const handleServerAction = async (action) => {
    setActionLoading(action);
    try {
      if (action === 'start') {
        await api.startMCPServer(server.name);
        notify.success(`${server.display_name || server.name} started successfully`);
      } else if (action === 'stop') {
        await api.stopMCPServer(server.name);
        notify.success(`${server.display_name || server.name} stopped successfully`);
      } else if (action === 'restart') {
        await api.restartMCPServer(server.name);
        notify.success(`${server.display_name || server.name} restarted successfully`);
      }

      await refreshDetails();
    } catch (error) {
      console.error(`Failed to ${action} server:`, error);
      toast.error(error?.message || `Failed to ${action} server`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleTestTool = async (toolName) => {
    setTestLoading(true);
    setTestResult(null);
    try {
      const parsedArgs = testArgsText.trim() ? JSON.parse(testArgsText) : {};
      const result = await api.callMCPTool(server.name, toolName, parsedArgs);
      setTestResult({
        success: true,
        data: result,
      });
      notify.success('Tool executed successfully');
    } catch (error) {
      const message = error?.message || 'Tool execution failed';
      setTestResult({
        success: false,
        error: message,
      });
      toast.error(message);
    } finally {
      setTestLoading(false);
    }
  };

  const getStatusBadge = (running) => {
    if (running) {
      return (
        <span className="inline-flex items-center space-x-1 px-2 py-1 bg-green-500/20 text-green-400 rounded-full text-xs">
          <CheckCircle className="w-3 h-3" />
          <span>Running</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center space-x-1 px-2 py-1 bg-slate-500/20 text-slate-400 rounded-full text-xs">
        <AlertCircle className="w-3 h-3" />
        <span>Stopped</span>
      </span>
    );
  };

  return (
    <Modal
      onClose={onClose}
      ariaLabel={`${serverDetails.display_name || serverDetails.name} controls`}
      showClose={false}
      closeOnBackdrop={false}
      panelClassName="bg-slate-800/90 backdrop-blur-xl border border-slate-700/50 rounded-xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col focus:outline-none"
    >
        <div className="flex justify-between items-start p-6 border-b border-slate-700/50">
          <div className="flex items-start space-x-4">
            <div className="p-3 bg-unicorn-500/20 rounded-lg">
              <Server className="w-8 h-8 text-unicorn-400" />
            </div>
            <div>
              <div className="flex items-center space-x-3">
                <h2 className="text-2xl font-bold text-white">
                  {serverDetails.display_name || serverDetails.name}
                </h2>
                {getStatusBadge(serverDetails.running)}
              </div>
              <p className="text-sm text-slate-400 mt-1">
                {serverDetails.description}
              </p>
              <div className="flex gap-2 mt-2">
                <span className="px-2 py-1 bg-blue-500/20 text-blue-400 text-xs rounded-full">
                  {(serverDetails.transport || 'STDIO').toUpperCase()}
                </span>
                <span className="px-2 py-1 bg-unicorn-500/20 text-unicorn-400 text-xs rounded-full">
                  {serverDetails.capabilities?.length || 0} tools
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            className="p-3 min-h-[44px] min-w-[44px] hover:bg-slate-700/50 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-slate-400" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
          <div className="w-full lg:w-1/3 border-b lg:border-b-0 lg:border-r border-slate-700/50 p-6 overflow-y-auto">
            <h3 className="text-lg font-semibold text-white mb-4">Server Controls</h3>

            <fieldset disabled={Boolean(actionLoading)} className="space-y-2 mb-6">
              <button
                onClick={() => handleServerAction('start')}
                disabled={serverDetails.running || actionLoading}
                className="w-full px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {actionLoading === 'start' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Starting...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5" />
                    <span>Start Server</span>
                  </>
                )}
              </button>

              <button
                onClick={() => handleServerAction('stop')}
                disabled={!serverDetails.running || actionLoading}
                className="w-full px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {actionLoading === 'stop' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Stopping...</span>
                  </>
                ) : (
                  <>
                    <StopCircle className="w-5 h-5" />
                    <span>Stop Server</span>
                  </>
                )}
              </button>

              <button
                onClick={() => handleServerAction('restart')}
                disabled={actionLoading}
                className="w-full px-4 py-3 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              >
                {actionLoading === 'restart' ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Restarting...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-5 h-5" />
                    <span>Restart Server</span>
                  </>
                )}
              </button>
            </fieldset>

            <div className="pt-6 border-t border-slate-700/50">
              <h4 className="text-sm font-semibold text-slate-300 mb-3">Server Information</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">Name:</span>
                  <span className="text-white font-mono">{serverDetails.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Transport:</span>
                  <span className="text-white">{serverDetails.transport || 'STDIO'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Enabled:</span>
                  <span className={serverDetails.enabled ? 'text-green-400' : 'text-red-400'}>
                    {serverDetails.enabled ? 'Yes' : 'No'}
                  </span>
                </div>
                {serverDetails.config_file && (
                  <div className="flex justify-between">
                    <span className="text-slate-400">Config:</span>
                    <span className="text-white text-xs truncate">{serverDetails.config_file}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col">
            <div className="p-4 border-b border-slate-700/50 bg-slate-800/50">
              <h3 className="text-lg font-semibold text-white">Available Tools</h3>
              <p className="text-sm text-slate-400 mt-1">
                {serverDetails.capabilities?.length || 0} capabilities
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {serverDetails.capabilities && serverDetails.capabilities.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {serverDetails.capabilities.map((tool) => (
                    <div
                      key={tool}
                      className="bg-slate-700/30 border border-slate-600/50 rounded-lg p-4 hover:bg-slate-700/50 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <Code className="w-4 h-4 text-unicorn-400" />
                            <span className="font-medium text-white text-sm">{tool}</span>
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            setTestingTool(tool);
                            setTestArgsText('{}');
                            setTestResult(null);
                          }}
                          disabled={!serverDetails.running}
                          className="px-3 py-1 bg-unicorn-600/20 text-unicorn-400 text-xs rounded-lg hover:bg-unicorn-600/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Test
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-slate-400">
                  <Code className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No capabilities defined for this server</p>
                </div>
              )}
            </div>

            {testingTool && (
              <div className="border-t border-slate-700/50 p-6 bg-slate-800/30">
                <div className="flex justify-between items-center mb-4">
                  <h4 className="text-lg font-semibold text-white">
                    Testing: {testingTool}
                  </h4>
                  <button
                    onClick={() => setTestingTool(null)}
                    aria-label="Close tool test"
                    className="p-3 min-h-[44px] min-w-[44px] text-slate-400 hover:text-white"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Arguments (JSON)
                  </label>
                  <textarea
                    value={testArgsText}
                    onChange={(e) => setTestArgsText(e.target.value)}
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-white font-mono text-sm focus:outline-none focus:ring-2 focus:ring-unicorn-500 min-h-[100px]"
                    placeholder='{"param": "value"}'
                  />
                </div>

                <button
                  onClick={() => handleTestTool(testingTool)}
                  disabled={testLoading}
                  className="w-full px-4 py-2.5 bg-gradient-to-r from-unicorn-600 to-unicorn-500 text-white rounded-lg hover:from-unicorn-600 hover:to-unicorn-500 transition-colors disabled:opacity-50 flex items-center justify-center space-x-2"
                >
                  {testLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Executing...</span>
                    </>
                  ) : (
                    <>
                      <Terminal className="w-5 h-5" />
                      <span>Execute Tool</span>
                    </>
                  )}
                </button>

                {testResult && (
                  <div className="mt-4">
                    <div className={`border rounded-lg p-4 ${
                      testResult.success
                        ? 'bg-green-500/10 border-green-500/30'
                        : 'bg-red-500/10 border-red-500/30'
                    }`}>
                      <div className="flex items-center space-x-2 mb-2">
                        {testResult.success ? (
                          <CheckCircle className="w-5 h-5 text-green-400" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-red-400" />
                        )}
                        <span className={`font-medium ${
                          testResult.success ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {testResult.success ? 'Success' : 'Error'}
                        </span>
                      </div>
                      <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap">
                        {testResult.success
                          ? JSON.stringify(testResult.data, null, 2)
                          : testResult.error}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
    </Modal>
  );
}
