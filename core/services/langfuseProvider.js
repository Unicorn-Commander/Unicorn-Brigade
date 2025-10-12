/**
 * Langfuse Observability Provider
 * Comprehensive agent monitoring, tracing, and evaluation
 */

const { Langfuse } = require('langfuse');

class LangfuseProvider {
  constructor() {
    this.langfuse = null;
    this.enabled = false;
    this.initializeLangfuse();
  }

  /**
   * Initialize Langfuse client
   */
  initializeLangfuse() {
    const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
    const secretKey = process.env.LANGFUSE_SECRET_KEY;

    if (!publicKey || !secretKey) {
      console.log('⚠️  Langfuse not configured (optional)');
      console.log('   Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable observability');
      this.enabled = false;
      return;
    }

    try {
      this.langfuse = new Langfuse({
        publicKey: publicKey,
        secretKey: secretKey,
        baseUrl: process.env.LANGFUSE_HOST || 'https://cloud.langfuse.com',
        flushAt: parseInt(process.env.LANGFUSE_FLUSH_AT || '15'),
        flushInterval: parseInt(process.env.LANGFUSE_FLUSH_INTERVAL || '1000')
      });

      this.enabled = true;
      console.log('📊 Langfuse observability enabled');
      console.log(`   Host: ${process.env.LANGFUSE_HOST || 'https://cloud.langfuse.com'}`);
    } catch (error) {
      console.error('❌ Failed to initialize Langfuse:', error.message);
      this.enabled = false;
    }
  }

  /**
   * Check if Langfuse is enabled
   */
  isEnabled() {
    return this.enabled && this.langfuse !== null;
  }

  /**
   * Create a new trace for agent execution
   * @param {string} name - Trace name
   * @param {string} userId - User identifier
   * @param {Object} metadata - Additional metadata
   * @param {Object} options - Trace options (sessionId, tags, etc.)
   * @returns {Object|null} Trace object or null if disabled
   */
  createTrace(name, userId = null, metadata = {}, options = {}) {
    if (!this.isEnabled()) {
      return this.createMockTrace(name);
    }

    try {
      const trace = this.langfuse.trace({
        name: name,
        userId: userId,
        metadata: {
          platform: 'Unicorn Battalion',
          timestamp: new Date().toISOString(),
          ...metadata
        },
        sessionId: options.sessionId,
        tags: options.tags || [],
        input: options.input,
        output: options.output
      });

      return trace;
    } catch (error) {
      console.error('Langfuse trace creation error:', error.message);
      return this.createMockTrace(name);
    }
  }

  /**
   * Log LLM generation (completion)
   * @param {Object} trace - Parent trace
   * @param {Object} config - Generation configuration
   * @returns {Object|null} Generation object
   */
  async logGeneration(trace, config) {
    if (!this.isEnabled() || !trace) {
      return null;
    }

    try {
      return trace.generation({
        name: config.name || 'llm-call',
        model: config.model,
        modelParameters: {
          temperature: config.temperature,
          maxTokens: config.maxTokens,
          topP: config.topP,
          ...config.modelParameters
        },
        input: config.input || config.messages,
        output: config.output || config.content,
        usage: {
          promptTokens: config.usage?.prompt_tokens,
          completionTokens: config.usage?.completion_tokens,
          totalTokens: config.usage?.total_tokens
        },
        metadata: {
          provider: config.provider,
          agentId: config.agentId,
          ...config.metadata
        },
        startTime: config.startTime,
        endTime: config.endTime || new Date(),
        completionStartTime: config.completionStartTime,
        level: config.level || 'DEFAULT'
      });
    } catch (error) {
      console.error('Langfuse generation logging error:', error.message);
      return null;
    }
  }

  /**
   * Log a span (generic operation)
   * @param {Object} trace - Parent trace
   * @param {Object} config - Span configuration
   * @returns {Object|null} Span object
   */
  logSpan(trace, config) {
    if (!this.isEnabled() || !trace) {
      return null;
    }

    try {
      return trace.span({
        name: config.name,
        input: config.input,
        output: config.output,
        metadata: {
          agentId: config.agentId,
          operation: config.operation,
          ...config.metadata
        },
        startTime: config.startTime,
        endTime: config.endTime || new Date(),
        level: config.level || 'DEFAULT'
      });
    } catch (error) {
      console.error('Langfuse span logging error:', error.message);
      return null;
    }
  }

  /**
   * Log an event (discrete action)
   * @param {Object} trace - Parent trace
   * @param {Object} config - Event configuration
   * @returns {Object|null} Event object
   */
  logEvent(trace, config) {
    if (!this.isEnabled() || !trace) {
      return null;
    }

    try {
      return trace.event({
        name: config.name,
        input: config.input,
        output: config.output,
        metadata: {
          agentId: config.agentId,
          eventType: config.eventType,
          ...config.metadata
        },
        level: config.level || 'DEFAULT',
        startTime: config.startTime || new Date()
      });
    } catch (error) {
      console.error('Langfuse event logging error:', error.message);
      return null;
    }
  }

  /**
   * Score a trace/generation/span
   * @param {string} traceId - Trace identifier
   * @param {Object} score - Score configuration
   */
  async score(traceId, score) {
    if (!this.isEnabled()) {
      return null;
    }

    try {
      return this.langfuse.score({
        traceId: traceId,
        name: score.name,
        value: score.value,
        comment: score.comment,
        dataType: score.dataType || 'NUMERIC',
        configId: score.configId
      });
    } catch (error) {
      console.error('Langfuse scoring error:', error.message);
      return null;
    }
  }

  /**
   * Update a trace
   * @param {string} traceId - Trace identifier
   * @param {Object} updates - Updates to apply
   */
  async updateTrace(traceId, updates) {
    if (!this.isEnabled()) {
      return null;
    }

    try {
      return this.langfuse.trace({
        id: traceId,
        ...updates
      });
    } catch (error) {
      console.error('Langfuse trace update error:', error.message);
      return null;
    }
  }

  /**
   * Flush pending events
   * Call this before shutdown to ensure all events are sent
   */
  async flush() {
    if (!this.isEnabled()) {
      return;
    }

    try {
      await this.langfuse.flushAsync();
      console.log('📊 Langfuse events flushed');
    } catch (error) {
      console.error('Langfuse flush error:', error.message);
    }
  }

  /**
   * Shutdown Langfuse (flush and cleanup)
   */
  async shutdown() {
    if (!this.isEnabled()) {
      return;
    }

    try {
      await this.langfuse.shutdownAsync();
      console.log('📊 Langfuse shutdown complete');
    } catch (error) {
      console.error('Langfuse shutdown error:', error.message);
    }
  }

  /**
   * Create mock trace when Langfuse is disabled
   * Provides same interface for development without observability
   */
  createMockTrace(name) {
    return {
      id: `mock-${Date.now()}`,
      name: name,
      generation: () => null,
      span: () => null,
      event: () => null,
      update: () => null
    };
  }

  /**
   * Helper: Log complete agent interaction
   * @param {Object} config - Interaction configuration
   * @returns {Object} Trace object
   */
  logAgentInteraction(config) {
    const trace = this.createTrace(
      config.agentName || 'agent-interaction',
      config.userId,
      {
        agentId: config.agentId,
        agentName: config.agentName,
        interactionType: config.interactionType || 'chat'
      },
      {
        sessionId: config.sessionId,
        tags: config.tags,
        input: config.input,
        output: config.output
      }
    );

    // Log the LLM generation if provided
    if (config.llmCall) {
      this.logGeneration(trace, {
        name: 'agent-llm-call',
        model: config.llmCall.model,
        temperature: config.llmCall.temperature,
        input: config.llmCall.messages,
        output: config.llmCall.response,
        usage: config.llmCall.usage,
        provider: config.llmCall.provider,
        agentId: config.agentId
      });
    }

    // Log memory operations if provided
    if (config.memoryOperations) {
      config.memoryOperations.forEach(op => {
        this.logSpan(trace, {
          name: `memory-${op.operation}`,
          input: op.input,
          output: op.output,
          operation: op.operation,
          agentId: config.agentId
        });
      });
    }

    // Log tool calls if provided
    if (config.toolCalls) {
      config.toolCalls.forEach(tool => {
        this.logSpan(trace, {
          name: `tool-${tool.name}`,
          input: tool.input,
          output: tool.output,
          operation: 'tool_execution',
          agentId: config.agentId,
          metadata: { toolName: tool.name }
        });
      });
    }

    return trace;
  }

  /**
   * Health check
   */
  async healthCheck() {
    if (!this.isEnabled()) {
      return {
        status: 'disabled',
        message: 'Langfuse not configured'
      };
    }

    try {
      // Simple check - Langfuse client is initialized
      return {
        status: 'healthy',
        enabled: true,
        baseUrl: process.env.LANGFUSE_HOST || 'https://cloud.langfuse.com'
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message
      };
    }
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'Langfuse Observability Provider',
      version: '1.0.0',
      enabled: this.enabled,
      capabilities: this.enabled
        ? [
            'Trace creation and management',
            'LLM generation logging',
            'Span and event tracking',
            'Scoring and evaluation',
            'Agent interaction logging',
            'Memory and tool tracking'
          ]
        : ['Mock tracing (observability disabled)'],
      baseUrl: process.env.LANGFUSE_HOST || 'https://cloud.langfuse.com'
    };
  }
}

module.exports = new LangfuseProvider();
