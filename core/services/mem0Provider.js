/**
 * Mem0 Memory Provider Service
 * Advanced memory layer for AI agents with automatic extraction and graph support
 * Integrates with Unicorn Battalion's existing analytics for enhanced insights
 */

const { Memory } = require('mem0ai');
const memoryAnalyticsService = require('../memory/memoryAnalyticsService');

class Mem0Provider {
  constructor() {
    this.memory = null;
    this.initialized = false;
    this.initializeMemory();
  }

  /**
   * Initialize Mem0 with configuration
   */
  async initializeMemory() {
    try {
      const config = {
        llm: {
          provider: process.env.MEM0_LLM_PROVIDER || "openai",
          config: {
            model: process.env.MEM0_LLM_MODEL || "gpt-4o-mini",
            api_key: process.env.OPENAI_API_KEY || process.env.MEM0_LLM_API_KEY,
            // Use LiteLLM proxy if configured
            ...(process.env.LITELLM_PROXY_URL && {
              base_url: process.env.LITELLM_PROXY_URL + '/v1',
              api_key: process.env.LITELLM_API_KEY || 'sk-litellm-master-key'
            })
          }
        },
        embedder: {
          provider: process.env.MEM0_EMBEDDER_PROVIDER || "openai",
          config: {
            model: process.env.MEM0_EMBEDDER_MODEL || "text-embedding-3-small",
            api_key: process.env.OPENAI_API_KEY || process.env.MEM0_EMBEDDER_API_KEY,
            embedding_dims: parseInt(process.env.MEM0_EMBEDDING_DIMS || "1536")
          }
        },
        vector_store: {
          provider: process.env.MEM0_VECTOR_STORE || "qdrant",
          config: {
            host: process.env.QDRANT_HOST || "localhost",
            port: parseInt(process.env.QDRANT_PORT || "6333"),
            collection_name: process.env.MEM0_COLLECTION || "battalion_memories"
          }
        }
      };

      // Add graph store if Neo4j is configured (for Mem0g)
      if (process.env.NEO4J_URL) {
        config.graph_store = {
          provider: "neo4j",
          config: {
            url: process.env.NEO4J_URL,
            username: process.env.NEO4J_USERNAME || "neo4j",
            password: process.env.NEO4J_PASSWORD
          }
        };
      }

      this.memory = new Memory(config);
      this.initialized = true;
      console.log('🧠 Mem0 Provider initialized');
      console.log(`   Vector Store: ${config.vector_store.provider}`);
      if (config.graph_store) {
        console.log(`   Graph Store: ${config.graph_store.provider} (Mem0g enabled)`);
      }
    } catch (error) {
      console.error('❌ Failed to initialize Mem0:', error.message);
      this.initialized = false;
    }
  }

  /**
   * Check if Mem0 is initialized
   */
  ensureInitialized() {
    if (!this.initialized || !this.memory) {
      throw new Error('Mem0 not initialized. Check configuration.');
    }
  }

  /**
   * Add memory from conversation messages
   * Mem0 automatically extracts facts using LLM
   * @param {Array} messages - Array of {role, content} messages
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @param {Object} metadata - Additional metadata
   * @returns {Promise<Object>} Memory creation result
   */
  async addMemory(messages, userId, agentId = null, metadata = {}) {
    this.ensureInitialized();

    try {
      const options = {
        user_id: userId,
        ...(agentId && { agent_id: agentId }),
        metadata: {
          timestamp: new Date().toISOString(),
          source: 'battalion-platform',
          ...metadata
        }
      };

      const result = await this.memory.add(messages, options);

      console.log(`💾 Memory added for user ${userId}${agentId ? ` (agent: ${agentId})` : ''}`);
      return {
        success: true,
        memories: result.results || result,
        count: result.results?.length || 0
      };
    } catch (error) {
      console.error('❌ Mem0 add error:', error.message);
      return {
        success: false,
        error: error.message,
        memories: [],
        count: 0
      };
    }
  }

  /**
   * Search memories by semantic query
   * @param {string} query - Search query
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @param {number} limit - Maximum results
   * @param {Object} options - Additional search options
   * @returns {Promise<Array>} Array of relevant memories
   */
  async searchMemories(query, userId, agentId = null, limit = 10, options = {}) {
    this.ensureInitialized();

    try {
      const searchOptions = {
        user_id: userId,
        ...(agentId && { agent_id: agentId }),
        limit: limit,
        ...options
      };

      const results = await this.memory.search(query, searchOptions);

      return results.results || [];
    } catch (error) {
      console.error('❌ Mem0 search error:', error.message);
      return [];
    }
  }

  /**
   * Get all memories for a user/agent
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @param {number} limit - Maximum results
   * @returns {Promise<Array>} Array of all memories
   */
  async getAllMemories(userId, agentId = null, limit = 100) {
    this.ensureInitialized();

    try {
      const options = {
        user_id: userId,
        ...(agentId && { agent_id: agentId }),
        limit: limit
      };

      const results = await this.memory.get_all(options);

      return results.results || [];
    } catch (error) {
      console.error('❌ Mem0 get_all error:', error.message);
      return [];
    }
  }

  /**
   * Update a specific memory
   * @param {string} memoryId - Memory identifier
   * @param {string} newData - New memory content
   * @returns {Promise<Object>} Update result
   */
  async updateMemory(memoryId, newData) {
    this.ensureInitialized();

    try {
      const result = await this.memory.update(memoryId, { data: newData });
      console.log(`✏️  Memory ${memoryId} updated`);
      return { success: true, result };
    } catch (error) {
      console.error('❌ Mem0 update error:', error.message);
      return { success: false, error: error.message };
    }
  }

  /**
   * Delete a specific memory
   * @param {string} memoryId - Memory identifier
   * @returns {Promise<Object>} Delete result
   */
  async deleteMemory(memoryId) {
    this.ensureInitialized();

    try {
      const result = await this.memory.delete(memoryId);
      console.log(`🗑️  Memory ${memoryId} deleted`);
      return { success: true, result };
    } catch (error) {
      console.error('❌ Mem0 delete error:', error.message);
      return { success: false, error: error.message };
    }
  }

  /**
   * Delete all memories for a user/agent
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @returns {Promise<Object>} Delete result
   */
  async deleteAllMemories(userId, agentId = null) {
    this.ensureInitialized();

    try {
      const options = {
        user_id: userId,
        ...(agentId && { agent_id: agentId })
      };

      const result = await this.memory.delete_all(options);
      console.log(`🗑️  All memories deleted for user ${userId}${agentId ? ` (agent: ${agentId})` : ''}`);
      return { success: true, result };
    } catch (error) {
      console.error('❌ Mem0 delete_all error:', error.message);
      return { success: false, error: error.message };
    }
  }

  /**
   * Get memory history for a specific memory
   * @param {string} memoryId - Memory identifier
   * @returns {Promise<Array>} Memory history
   */
  async getMemoryHistory(memoryId) {
    this.ensureInitialized();

    try {
      const result = await this.memory.history(memoryId);
      return result.results || [];
    } catch (error) {
      console.error('❌ Mem0 history error:', error.message);
      return [];
    }
  }

  /**
   * Get memories with Unicorn Battalion analytics
   * Combines Mem0 memories with Unicorn Battalion's unique analytics capabilities
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @returns {Promise<Object>} Memories with analytics
   */
  async getMemoriesWithAnalytics(userId, agentId = null) {
    const memories = await this.getAllMemories(userId, agentId);

    // Convert Mem0 memories to format compatible with Unicorn Battalion analytics
    const formattedMemories = memories.map(m => ({
      id: m.id,
      content: m.memory,
      metadata: m.metadata || {},
      created_at: m.created_at,
      updated_at: m.updated_at
    }));

    try {
      // Use Unicorn Battalion's existing analytics service for advanced insights
      const analyticsReport = await memoryAnalyticsService.generateAnalyticsReport(
        agentId || userId,
        {
          timeframe: 'all',
          includeInsights: true,
          includePredictions: true
        }
      );

      return {
        memories: formattedMemories,
        count: memories.length,
        analytics: analyticsReport,
        hasAnalytics: true
      };
    } catch (error) {
      console.warn('Analytics generation failed, returning memories only:', error.message);
      return {
        memories: formattedMemories,
        count: memories.length,
        hasAnalytics: false
      };
    }
  }

  /**
   * Build context for agent from memories
   * Retrieves relevant memories and formats them for LLM context
   * @param {string} query - Current user message/query
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier
   * @param {number} limit - Max memories to include
   * @returns {Promise<string>} Formatted context string
   */
  async buildContext(query, userId, agentId, limit = 5) {
    const memories = await this.searchMemories(query, userId, agentId, limit);

    if (memories.length === 0) {
      return '';
    }

    const contextLines = memories.map((m, idx) =>
      `${idx + 1}. ${m.memory} (relevance: ${(m.score * 100).toFixed(1)}%)`
    );

    return `Relevant memories:\n${contextLines.join('\n')}`;
  }

  /**
   * Get memory statistics
   * @param {string} userId - User identifier
   * @param {string} agentId - Agent identifier (optional)
   * @returns {Promise<Object>} Memory statistics
   */
  async getMemoryStats(userId, agentId = null) {
    const memories = await this.getAllMemories(userId, agentId);

    return {
      totalMemories: memories.length,
      oldestMemory: memories[memories.length - 1]?.created_at,
      newestMemory: memories[0]?.created_at,
      averageLength: memories.length > 0
        ? memories.reduce((sum, m) => sum + m.memory.length, 0) / memories.length
        : 0
    };
  }

  /**
   * Health check for Mem0 service
   * @returns {Promise<Object>} Health status
   */
  async healthCheck() {
    try {
      if (!this.initialized || !this.memory) {
        return {
          status: 'unhealthy',
          error: 'Mem0 not initialized',
          initialized: false
        };
      }

      // Try a simple operation to verify connectivity
      await this.memory.get_all({ user_id: 'health-check', limit: 1 });

      return {
        status: 'healthy',
        initialized: true,
        provider: 'mem0ai'
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        initialized: this.initialized
      };
    }
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'Mem0 Memory Provider',
      version: '1.0.0',
      initialized: this.initialized,
      capabilities: [
        'Automatic memory extraction from conversations',
        'Semantic memory search',
        'Graph-based memory (if Neo4j configured)',
        'Multi-user and multi-agent support',
        'Memory history tracking',
        'Integration with Unicorn Battalion analytics',
        'Context building for agents'
      ],
      vectorStore: process.env.MEM0_VECTOR_STORE || 'qdrant',
      graphStore: process.env.NEO4J_URL ? 'neo4j' : 'none'
    };
  }
}

module.exports = new Mem0Provider();
