// Agent Trace API Service
// Handles all API calls for code attribution tracking
import { buildAuthHeaders, handleUnauthorized } from './authHeaders';

class TraceService {
  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8100/api/v1';
  }

  async request(endpoint, options = {}) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        credentials: 'include',
        headers: buildAuthHeaders({
          'Content-Type': 'application/json',
          ...options.headers,
        }),
      });

      const contentType = response.headers.get('content-type');
      let data;

      if (contentType && contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      if (!response.ok) {
        if (response.status === 401 && !endpoint.includes('/auth/')) {
          handleUnauthorized();
        }
        throw new Error(data.error || data.message || `API Error: ${response.statusText}`);
      }

      return data;
    } catch (error) {
      console.error('Trace API Request failed:', error);
      throw error;
    }
  }

  // ========== Code Attributions ==========

  /**
   * Get recent code attributions
   * @param {Object} filters - Optional filters (days, limit, offset)
   * @returns {Promise<Array>} List of attributions
   */
  async getAttributions(filters = {}) {
    const params = new URLSearchParams();

    if (filters.days) params.append('days', filters.days);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);

    const queryString = params.toString();
    return this.request(`/trace/recent${queryString ? `?${queryString}` : '?days=7'}`);
  }

  /**
   * Get attributions for a specific file
   * @param {string} filePath - Path to the file
   * @returns {Promise<Object>} File attribution details with line-by-line data
   */
  async getFileAttributions(filePath) {
    return this.request(`/trace/files/${encodeURIComponent(filePath)}`);
  }

  /**
   * Get attributions by agent
   * @param {string} agentId - Agent ID
   * @returns {Promise<Object>} Agent attribution summary and details
   */
  async getAgentAttributions(agentId) {
    return this.request(`/trace/agents/${agentId}`);
  }

  /**
   * Get recent attribution activity
   * @param {number} days - Number of days to look back (default: 1)
   * @returns {Promise<Array>} Recent attributions
   */
  async getRecentActivity(days = 1) {
    return this.request(`/trace/recent?days=${days}`);
  }

  /**
   * Get attribution statistics
   * @returns {Promise<Object>} Statistics summary
   */
  async getStatistics() {
    return this.request('/trace/stats');
  }

  /**
   * Get attributions by session/conversation
   * @param {string} sessionId - Session ID
   * @returns {Promise<Array>} Attributions for this session
   */
  async getSessionAttributions(sessionId) {
    return this.request(`/trace/sessions/${sessionId}`);
  }

  /**
   * Get file tree with attribution metadata
   * Returns unique files from recent attributions
   * @returns {Promise<Array>} List of files with attribution counts
   */
  async getFileTree() {
    // Build file tree from recent attributions
    const attributions = await this.getRecentActivity(30);
    const fileMap = new Map();

    attributions.forEach(attr => {
      const path = attr.filePath;
      if (!fileMap.has(path)) {
        fileMap.set(path, {
          path,
          attributionCount: 0,
          totalLines: 0,
          agents: new Set()
        });
      }

      const file = fileMap.get(path);
      file.attributionCount++;
      file.totalLines += (attr.endLine - attr.startLine + 1);
      file.agents.add(attr.agentName);
    });

    return Array.from(fileMap.values()).map(f => ({
      ...f,
      agents: Array.from(f.agents)
    }));
  }

  /**
   * Export attribution report
   * @param {Object} filters - Export filters
   * @param {string} format - Export format (json, csv)
   * @returns {Promise<Blob>} Report file
   */
  async exportReport(filters = {}, format = 'csv') {
    const body = {
      agentId: filters.agentId || null,
      filePath: filters.filePath || null,
      changeType: filters.changeType || null,
      startDate: filters.startDate || null,
      endDate: filters.endDate || null,
      format: format
    };

    const response = await fetch(`${this.baseURL}/trace/report`, {
      method: 'POST',
      credentials: 'include',
      headers: buildAuthHeaders({
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(body)
    });

    if (response.status === 401) {
      handleUnauthorized();
    }

    if (!response.ok) {
      throw new Error(`Export failed: ${response.statusText}`);
    }

    return response.blob();
  }

  /**
   * Health check for Agent Trace subsystem
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    return this.request('/trace/health');
  }
}

// Export singleton instance
const traceService = new TraceService();
export default traceService;
