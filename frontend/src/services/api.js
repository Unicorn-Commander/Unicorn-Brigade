// API Service for Unicorn Command & Control

class APIService {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
    this.token = localStorage.getItem('token');
  }

  async request(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(this.token && { 'Authorization': `Bearer ${this.token}` }),
          ...options.headers,
        },
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
        throw new Error(data.error || data.message || `API Error: ${response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('API Request failed:', error);
      throw error;
    }
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

  async login(username, password) {
    const response = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    if (response.token) {
      this.token = response.token;
      localStorage.setItem('token', response.token);
      localStorage.setItem('user', JSON.stringify(response.user));
    }

    return response;
  }

  async logout() {
    await this.request('/auth/logout', {
      method: 'POST',
    });

    this.token = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
  }

  async register(username, email, password) {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, email, password }),
    });
  }

  async verifyToken() {
    return this.request('/auth/verify');
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