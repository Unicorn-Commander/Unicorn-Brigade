// API Service for Unicorn Command & Control
import { toast } from 'react-hot-toast';
import { buildAuthHeaders, handleUnauthorized } from './authHeaders';

class APIService {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
  }

  // Live accessor so callers that call getApiKey() still work if anything depends on it.
  get apiKey() {
    return localStorage.getItem('apiKey');
  }

  async request(endpoint, options = {}) {
    const { params, suppressToast, ...fetchOptions } = options;
    try {
      const url = new URL(`${this.baseURL}${endpoint}`);
      if (params) {
        Object.entries(params).forEach(([key, value]) => {
          if (value !== undefined && value !== null) {
            url.searchParams.append(key, String(value));
          }
        });
      }

      const response = await fetch(url.toString(), {
        ...fetchOptions,
        credentials: 'include',
        headers: buildAuthHeaders({
          'Content-Type': 'application/json',
          ...fetchOptions.headers,
        }),
      });

      // Handle non-JSON responses
      const contentType = response.headers.get('content-type');
      let data;

      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        const errorMessage = this.extractErrorMessage(response.status, data);
        const friendlyMessage = this.getUserFriendlyMessage(errorMessage);
        const apiError = new Error(errorMessage);
        apiError.status = response.status;
        apiError.data = data;

        if (response.status === 401 && !endpoint.includes('/auth/')) {
          handleUnauthorized();
        }

        if (!suppressToast && response.status !== 401) {
          toast.error(friendlyMessage, {
            duration: 5000,
            position: 'top-right',
          });
        }

        throw apiError;
      }

      return data;
    } catch (error) {
      console.error('API Request failed:', error);
      if (!suppressToast && !error?.status) {
        toast.error('Network error. Please check your connection.', {
          duration: 5000,
          position: 'top-right',
        });
      }
      throw error;
    }
  }

  extractErrorMessage(status, data) {
    const detail = data?.detail;
    const message =
      (typeof detail === 'string' ? detail : detail?.message) ||
      data?.message ||
      data?.error ||
      this.getDefaultErrorMessage(status);

    return message || 'An error occurred';
  }

  getDefaultErrorMessage(status) {
    switch (status) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'Authentication required. Please log in.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'Resource not found.';
      case 409:
        return 'Conflict. This resource may already exist.';
      case 422:
        return 'Validation error. Please check your input.';
      case 500:
        return 'Server error. Please try again later.';
      case 503:
        return 'Service temporarily unavailable. Please try again later.';
      default:
        return `Error ${status}. Something went wrong.`;
    }
  }

  getUserFriendlyMessage(message) {
    const errorMessages = {
      'Network error': 'Unable to connect to the server. Please check your internet connection.',
      ECONNREFUSED: 'Server is not responding. Please try again later.',
      ERR_NETWORK: 'Network connection failed. Please check your connection.',
      'Invalid credentials': 'Email or password is incorrect. Please try again.',
      'Token expired': 'Your session has expired. Please log in again.',
      'Validation error': 'Please check your input and try again.',
      'Missing required field': 'Please fill in all required fields.',
      'Agent not found': 'This agent does not exist or has been deleted.',
      'Workflow not found': 'This workflow does not exist.',
      'Server not found': 'This MCP server is not registered.',
      'Already exists': 'A resource with this name already exists.',
      'Duplicate key': 'This value is already in use.',
    };

    if (errorMessages[message]) {
      return errorMessages[message];
    }

    const lower = String(message || '').toLowerCase();
    for (const [key, value] of Object.entries(errorMessages)) {
      if (lower.includes(key.toLowerCase())) {
        return value;
      }
    }

    return message;
  }

  // ========== HTTP Method Helpers ==========

  async get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  async post(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put(endpoint, data, options = {}) {
    return this.request(endpoint, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  // ========== AI Providers ==========

  async getProviders() {
    return this.request('/providers');
  }

  async getProvider(id) {
    return this.request(`/providers/${id}`);
  }

  async createProvider(provider) {
    return this.request('/providers', {
      method: 'POST',
      body: JSON.stringify(provider),
    });
  }

  async updateProvider(id, updates) {
    return this.request(`/providers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteProvider(id) {
    return this.request(`/providers/${id}`, {
      method: 'DELETE',
    });
  }

  async testProvider(id) {
    return this.request(`/providers/${id}/test`, {
      method: 'POST',
    });
  }

  async setDefaultProvider(id) {
    return this.request(`/providers/${id}/set-default`, {
      method: 'POST',
    });
  }

  // Quick setup for OpenRouter
  async quickSetupOpenRouter(apiKey, name = 'OpenRouter Main') {
    return this.request('/providers/quick-setup/openrouter', {
      method: 'POST',
      body: JSON.stringify({ apiKey, name }),
    });
  }

  // Chat completion
  async chatCompletion(messages, agentId = null, model = null) {
    return this.request('/chat/completions', {
      method: 'POST',
      body: JSON.stringify({
        messages,
        agentId,
        model,
        temperature: 0.7,
        maxTokens: 1000
      }),
    });
  }

  // Get available models
  async getAvailableModels() {
    return this.request('/chat/models');
  }

  // ========== Agents ==========

  async getAgents() {
    return this.request('/agents');
  }

  async getAgent(id) {
    return this.request(`/agents/${id}`);
  }

  async createAgent(agent) {
    return this.request('/agents', {
      method: 'POST',
      body: JSON.stringify(agent),
    });
  }

  async updateAgent(id, updates) {
    return this.request(`/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteAgent(id) {
    return this.request(`/agents/${id}`, {
      method: 'DELETE',
    });
  }

  async chatWithAgent(agentId, message) {
    return this.request(`/agents/${agentId}/chat`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });
  }

  // ========== Authentication ==========

  async login(email, password) {
    const response = await this.request('/users/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (response.apiKey) {
      localStorage.setItem('apiKey', response.apiKey);
      localStorage.setItem('user', JSON.stringify(response.user));
    }

    return response;
  }

  async logout() {
    localStorage.removeItem('apiKey');
    localStorage.removeItem('user');
  }

  // Set API key manually (for direct API key entry)
  setApiKey(apiKey) {
    localStorage.setItem('apiKey', apiKey);
  }

  // Get current API key
  getApiKey() {
    return this.apiKey;
  }

  // Clear API key
  clearApiKey() {
    localStorage.removeItem('apiKey');
  }

  async register(name, email, password) {
    return this.request('/users/register', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    });
  }

  async verifyToken() {
    return this.request('/users/me');
  }

  // ========== MCP Registry ==========

  async getMCPServers() {
    return this.request('/mcp/registry/servers');
  }

  async getRunningMCPServers() {
    return this.request('/mcp/registry/servers/running');
  }

  async getMCPServerDetails(name) {
    return this.request(`/mcp/registry/servers/${name}`);
  }

  async startMCPServer(name) {
    return this.request(`/mcp/registry/servers/${name}/start`, {
      method: 'POST',
    });
  }

  async stopMCPServer(name) {
    return this.request(`/mcp/registry/servers/${name}/stop`, {
      method: 'POST',
    });
  }

  async restartMCPServer(name) {
    return this.request(`/mcp/registry/servers/${name}/restart`, {
      method: 'POST',
    });
  }

  async callMCPTool(serverName, toolName, args) {
    return this.request('/mcp/registry/tools/call', {
      method: 'POST',
      body: JSON.stringify({ server_name: serverName, tool_name: toolName, arguments: args }),
    });
  }

  async getMCPHealth() {
    return this.request('/mcp/registry/health');
  }

  // ========== Hierarchical Workflows ==========

  async getWorkflowTemplates() {
    return this.request('/hierarchical/templates');
  }

  async executeWorkflow(workflowId, inputs, modelConfig = null, asyncExecution = false) {
    return this.request('/hierarchical/execute', {
      method: 'POST',
      body: JSON.stringify({
        workflow_id: workflowId,
        inputs,
        async_execution: asyncExecution,
        model_config: modelConfig,
      }),
    });
  }

  async getWorkflowExecutions(filters = {}) {
    return this.request('/hierarchical/executions', { params: filters });
  }

  async getWorkflowExecutionDetails(executionId) {
    return this.request(`/hierarchical/executions/${executionId}`);
  }

  async cancelWorkflowExecution(executionId) {
    return this.request(`/hierarchical/executions/${executionId}/cancel`, {
      method: 'POST',
    });
  }

  // ========== Ralph Self-Correction ==========

  async executeRalphWorkflow(workflowId, inputs, options = {}) {
    return this.request('/ralph/execute', {
      method: 'POST',
      body: JSON.stringify({
        workflow_id: workflowId,
        inputs,
        ...options,
      }),
    });
  }

  async getRalphProgress(executionId) {
    return this.request(`/ralph/executions/${executionId}`);
  }

  async getRalphResult(executionId) {
    return this.request(`/ralph/executions/${executionId}/result`);
  }

  async provideRalphGuidance(executionId, guidance) {
    return this.request(`/ralph/executions/${executionId}/guidance`, {
      method: 'POST',
      body: JSON.stringify({ guidance }),
    });
  }

  async cancelRalphExecution(executionId) {
    return this.request(`/ralph/executions/${executionId}`, {
      method: 'DELETE',
    });
  }

  // ========== System ==========

  async getHealth() {
    return this.request('/health');
  }

  async getStats() {
    return this.request('/stats');
  }

  // ========== Tools ==========

  async getTools() {
    return this.request('/tools');
  }

  async executeTool(toolId, parameters) {
    return this.request(`/tools/${toolId}/execute`, {
      method: 'POST',
      body: JSON.stringify(parameters),
    });
  }

  // ========== Memory ==========

  async searchMemory(query, options = {}) {
    return this.request('/memory/search', {
      method: 'POST',
      body: JSON.stringify({ query, ...options }),
    });
  }

  async storeMemory(memory) {
    return this.request('/memory', {
      method: 'POST',
      body: JSON.stringify(memory),
    });
  }
}

// Export singleton instance
const api = new APIService();
export default api;
