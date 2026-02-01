// MCP Registry API Service

class MCPService {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
    this.apiKey = localStorage.getItem('apiKey');
  }

  async request(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...(this.apiKey && { 'X-API-Key': this.apiKey }),
          ...options.headers,
        },
      });

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
      console.error('MCP API Request failed:', error);
      throw error;
    }
  }

  // ========== Server Management ==========

  async listServers() {
    return this.request('/mcp/registry/servers');
  }

  async getServer(name) {
    return this.request(`/mcp/registry/servers/${name}`);
  }

  async getRunningServers() {
    return this.request('/mcp/registry/servers/running');
  }

  async registerServer(serverConfig) {
    return this.request('/mcp/registry/servers', {
      method: 'POST',
      body: JSON.stringify(serverConfig),
    });
  }

  async unregisterServer(name) {
    return this.request(`/mcp/registry/servers/${name}`, {
      method: 'DELETE',
    });
  }

  async startServer(name) {
    return this.request(`/mcp/registry/servers/${name}/start`, {
      method: 'POST',
    });
  }

  async stopServer(name) {
    return this.request(`/mcp/registry/servers/${name}/stop`, {
      method: 'POST',
    });
  }

  async restartServer(name) {
    return this.request(`/mcp/registry/servers/${name}/restart`, {
      method: 'POST',
    });
  }

  // ========== Tool Invocation ==========

  async callTool(serverName, toolName, args) {
    return this.request('/mcp/registry/tools/call', {
      method: 'POST',
      body: JSON.stringify({
        server_name: serverName,
        tool_name: toolName,
        arguments: args,
      }),
    });
  }

  // ========== Code Sandbox ==========

  async getSandboxStatus() {
    return this.request('/mcp/registry/sandbox/status');
  }

  async executeSandbox(code, language = 'python') {
    return this.request('/mcp/registry/sandbox/execute', {
      method: 'POST',
      body: JSON.stringify({ code, language }),
    });
  }

  async executeSandboxWithFallback(code, language = 'python') {
    return this.request('/mcp/registry/sandbox/execute/fallback', {
      method: 'POST',
      body: JSON.stringify({ code, language }),
    });
  }

  // ========== Health ==========

  async getHealth() {
    return this.request('/mcp/registry/health');
  }
}

// Export singleton instance
const mcpService = new MCPService();
export default mcpService;
