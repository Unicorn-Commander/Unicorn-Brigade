// Agent Trace API Service
// Handles all API calls for code attribution tracking.
// All HTTP goes through the unified apiFetch/apiJson client so auth headers
// and 401 recovery behave exactly like the rest of the app.
import { apiFetch, apiJson, ApiError } from './http';

/**
 * Normalize an attribution record to the snake_case shape the attribution UI
 * consumes (CodeAttribution page, CodeAttributionCard, AttributionTimeline).
 *
 * The trace API returns camelCase (filePath, agentName, startLine, …) while
 * the UI renders file_path / agent_name / lines_count / timestamp. Mapping
 * once at the service boundary keeps every consumer on one shape.
 */
function normalizeAttribution(attr) {
  if (!attr || typeof attr !== 'object') return attr;

  const startLine = attr.startLine ?? attr.start_line ?? null;
  const endLine = attr.endLine ?? attr.end_line ?? null;
  const createdAt = attr.createdAt ?? attr.created_at ?? null;

  return {
    ...attr,
    file_path: attr.filePath ?? attr.file_path ?? '',
    agent_id: attr.agentId ?? attr.agent_id ?? null,
    agent_name: attr.agentName ?? attr.agent_name ?? '',
    session_id: attr.sessionId ?? attr.session_id ?? null,
    change_type: attr.changeType ?? attr.change_type ?? null,
    code_hash: attr.codeHash ?? attr.code_hash ?? null,
    generated_code: attr.generatedCode ?? attr.generated_code ?? '',
    start_line: startLine,
    end_line: endLine,
    lines_count:
      startLine != null && endLine != null
        ? endLine - startLine + 1
        : attr.lines_count ?? 0,
    created_at: createdAt,
    timestamp: createdAt ?? attr.timestamp ?? null,
  };
}

function normalizeList(data) {
  return Array.isArray(data) ? data.map(normalizeAttribution) : [];
}

/**
 * Normalize /trace/stats (totalLines, uniqueAgents, topAgents[], …) to the
 * shape AttributionStats renders (total_lines, agents{}, files{}, …).
 */
function normalizeStats(stats) {
  if (!stats || typeof stats !== 'object') return stats;

  const agents = {};
  (stats.topAgents || []).forEach((a) => {
    if (a?.agentName) agents[a.agentName] = a.totalLines ?? a.attributionCount ?? 0;
  });

  const files = {};
  (stats.topFiles || []).forEach((f) => {
    if (f?.filePath) files[f.filePath] = f.attributionCount ?? 0;
  });

  return {
    ...stats,
    total_lines: stats.totalLines ?? 0,
    total_attributions: stats.totalAttributions ?? 0,
    total_agents: stats.uniqueAgents ?? 0,
    total_files: stats.uniqueFiles ?? 0,
    agents,
    files,
  };
}

/** The trace endpoints 404 an empty window — treat that as "no data". */
function emptyOn404(error) {
  if (error instanceof ApiError && error.status === 404) return [];
  throw error;
}

class TraceService {
  // ========== Code Attributions ==========

  /**
   * Get recent code attributions
   * @param {Object} filters - Optional filters (days, limit, offset)
   * @returns {Promise<Array>} List of attributions
   */
  async getAttributions(filters = {}) {
    return apiJson('/trace/recent', {
      params: {
        days: filters.days ?? 7,
        limit: filters.limit,
        offset: filters.offset,
      },
    })
      .then(normalizeList)
      .catch(emptyOn404);
  }

  /**
   * Search attributions by substring match on file path, agent, model, or
   * prompt. The trace API has no server-side search endpoint, so this filters
   * the recent-attributions window client-side.
   * @param {string} query - Search text
   * @param {Object} filters - Optional filters forwarded to getAttributions (days, limit, offset)
   * @returns {Promise<Array>} Matching attributions
   */
  async searchAttributions(query, filters = {}) {
    const attributions = await this.getAttributions(filters);
    const q = (query || '').trim().toLowerCase();
    if (!q) return attributions;

    return attributions.filter((attr) =>
      [attr.file_path, attr.agent_name, attr.agent_id, attr.model, attr.prompt].some(
        (field) => (field || '').toLowerCase().includes(q)
      )
    );
  }

  /**
   * Get attributions for a specific file
   * @param {string} filePath - Path to the file
   * @returns {Promise<Object>} File attribution details with line-by-line data
   */
  async getFileAttributions(filePath) {
    const data = await apiJson(`/trace/files/${encodeURIComponent(filePath)}`);
    if (data && Array.isArray(data.attributions)) {
      return { ...data, attributions: normalizeList(data.attributions) };
    }
    return data;
  }

  /**
   * Get attributions by agent
   * @param {string} agentId - Agent ID
   * @returns {Promise<Array>} Agent attributions
   */
  async getAgentAttributions(agentId) {
    return apiJson(`/trace/agents/${encodeURIComponent(agentId)}`)
      .then(normalizeList)
      .catch(emptyOn404);
  }

  /**
   * Get recent attribution activity
   * @param {number} days - Number of days to look back (default: 1)
   * @returns {Promise<Array>} Recent attributions
   */
  async getRecentActivity(days = 1) {
    return this.getAttributions({ days });
  }

  /**
   * Get attribution statistics.
   * NOTE: /trace/stats accepts no filters — always global.
   * @returns {Promise<Object>} Statistics summary
   */
  async getStatistics() {
    const stats = await apiJson('/trace/stats');
    return normalizeStats(stats);
  }

  /**
   * Get attributions by session/conversation
   * @param {string} sessionId - Session ID
   * @returns {Promise<Array>} Attributions for this session
   */
  async getSessionAttributions(sessionId) {
    return apiJson(`/trace/sessions/${encodeURIComponent(sessionId)}`)
      .then(normalizeList)
      .catch(emptyOn404);
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
      const path = attr.file_path;
      if (!path) return;
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
      file.totalLines += attr.lines_count || 0;
      file.agents.add(attr.agent_name);
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

    const response = await apiFetch('/trace/report', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new ApiError(response.status, null, `Export failed: ${response.statusText}`);
    }

    return response.blob();
  }

  /**
   * Health check for Agent Trace subsystem
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    return apiJson('/trace/health');
  }
}

// Export singleton instance
const traceService = new TraceService();
export default traceService;
