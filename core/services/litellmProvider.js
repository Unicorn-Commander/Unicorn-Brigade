/**
 * LiteLLM Provider Service
 * Multi-provider LLM abstraction layer supporting 100+ models
 * Supports OpenRouter, OpenAI, Anthropic, Google, and more
 */

const axios = require('axios');

class LiteLLMProvider {
  constructor() {
    // LiteLLM proxy configuration
    this.baseURL = process.env.LITELLM_PROXY_URL || 'http://localhost:4000';
    this.apiKey = process.env.LITELLM_API_KEY || 'sk-litellm-master-key';

    // Fallback to OpenRouter if LiteLLM not configured
    this.openRouterKey = process.env.OPENROUTER_API_KEY;
    this.useOpenRouterFallback = !process.env.LITELLM_PROXY_URL && this.openRouterKey;

    console.log(`🔌 LiteLLM Provider initialized`);
    if (this.useOpenRouterFallback) {
      console.log(`   Using OpenRouter fallback mode`);
    }
  }

  /**
   * Send message to LLM via LiteLLM proxy or OpenRouter
   * @param {string} model - Model name (e.g., "gpt-4", "claude-3-opus", "openrouter/anthropic/claude-3-opus")
   * @param {Array} messages - Array of message objects {role, content}
   * @param {Object} options - Additional options (temperature, max_tokens, stream, etc.)
   * @returns {Promise<Object>} Response with content, usage, model, provider
   */
  async sendMessage(model, messages, options = {}) {
    try {
      // Use OpenRouter fallback if configured
      if (this.useOpenRouterFallback) {
        return await this.sendOpenRouterMessage(model, messages, options);
      }

      // Standard LiteLLM proxy request
      const response = await axios.post(
        `${this.baseURL}/v1/chat/completions`,
        {
          model: model,
          messages: messages,
          temperature: options.temperature ?? 0.7,
          max_tokens: options.maxTokens || options.max_tokens || 2000,
          stream: options.stream || false,
          top_p: options.top_p,
          frequency_penalty: options.frequency_penalty,
          presence_penalty: options.presence_penalty,
          ...options
        },
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json'
          },
          timeout: options.timeout || 120000 // 2 minute default timeout
        }
      );

      return this.formatResponse(response.data, model);
    } catch (error) {
      console.error('❌ LiteLLM error:', error.response?.data || error.message);

      // Try OpenRouter as fallback if available
      if (this.openRouterKey && !this.useOpenRouterFallback) {
        console.log('🔄 Falling back to OpenRouter...');
        return await this.sendOpenRouterMessage(model, messages, options);
      }

      throw error;
    }
  }

  /**
   * Send message directly to OpenRouter
   */
  async sendOpenRouterMessage(model, messages, options = {}) {
    try {
      // Convert model name if it doesn't have openrouter/ prefix
      let openRouterModel = model;
      if (!model.includes('/')) {
        // Map common model names to OpenRouter format
        const modelMap = {
          'gpt-4': 'openai/gpt-4',
          'gpt-4-turbo': 'openai/gpt-4-turbo',
          'gpt-3.5-turbo': 'openai/gpt-3.5-turbo',
          'claude-3-opus': 'anthropic/claude-3-opus',
          'claude-3-sonnet': 'anthropic/claude-3-sonnet',
          'claude-3-haiku': 'anthropic/claude-3-haiku',
          'claude-3.5-sonnet': 'anthropic/claude-3.5-sonnet',
          'gemini-pro': 'google/gemini-pro'
        };
        openRouterModel = modelMap[model] || model;
      }

      const response = await axios.post(
        'https://openrouter.ai/api/v1/chat/completions',
        {
          model: openRouterModel,
          messages: messages,
          temperature: options.temperature ?? 0.7,
          max_tokens: options.maxTokens || options.max_tokens || 2000,
          top_p: options.top_p,
          frequency_penalty: options.frequency_penalty,
          presence_penalty: options.presence_penalty
        },
        {
          headers: {
            'Authorization': `Bearer ${this.openRouterKey}`,
            'HTTP-Referer': process.env.OPENROUTER_REFERER || 'http://localhost:8112',
            'X-Title': process.env.OPENROUTER_TITLE || 'Unicorn Battalion',
            'Content-Type': 'application/json'
          },
          timeout: options.timeout || 120000
        }
      );

      return this.formatResponse(response.data, openRouterModel, 'openrouter');
    } catch (error) {
      console.error('❌ OpenRouter error:', error.response?.data || error.message);
      throw error;
    }
  }

  /**
   * Stream response from LLM
   * @param {string} model - Model name
   * @param {Array} messages - Array of message objects
   * @param {Object} options - Additional options
   * @returns {AsyncGenerator} Yields content chunks
   */
  async *streamMessage(model, messages, options = {}) {
    const url = this.useOpenRouterFallback
      ? 'https://openrouter.ai/api/v1/chat/completions'
      : `${this.baseURL}/v1/chat/completions`;

    const headers = this.useOpenRouterFallback
      ? {
          'Authorization': `Bearer ${this.openRouterKey}`,
          'HTTP-Referer': process.env.OPENROUTER_REFERER || 'http://localhost:8112',
          'X-Title': process.env.OPENROUTER_TITLE || 'Unicorn Battalion',
          'Content-Type': 'application/json'
        }
      : {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json'
        };

    const response = await fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        model: model,
        messages: messages,
        stream: true,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens || options.max_tokens || 2000,
        ...options
      })
    });

    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.statusText}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data:')) continue;

          const data = trimmed.slice(5).trim();
          if (data === '[DONE]') continue;

          try {
            const parsed = JSON.parse(data);
            const content = parsed.choices?.[0]?.delta?.content;
            if (content) {
              yield content;
            }
          } catch (e) {
            // Skip parsing errors for malformed chunks
            console.warn('Failed to parse SSE chunk:', data);
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Format response to standard format
   */
  formatResponse(data, model, forcedProvider = null) {
    return {
      content: data.choices[0].message.content,
      usage: data.usage || {
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0
      },
      model: data.model || model,
      provider: forcedProvider || this.extractProvider(model),
      raw: data // Keep raw response for advanced use cases
    };
  }

  /**
   * Extract provider from model name
   */
  extractProvider(model) {
    if (model.includes('openrouter/')) return 'openrouter';
    if (model.startsWith('gpt-')) return 'openai';
    if (model.startsWith('claude-')) return 'anthropic';
    if (model.startsWith('gemini-')) return 'google';
    if (model.includes('mistral')) return 'mistral';
    if (model.includes('llama')) return 'meta';
    return 'unknown';
  }

  /**
   * Get available models from LiteLLM proxy
   */
  async getModels() {
    try {
      if (this.useOpenRouterFallback) {
        return await this.getOpenRouterModels();
      }

      const response = await axios.get(`${this.baseURL}/models`, {
        headers: { 'Authorization': `Bearer ${this.apiKey}` },
        timeout: 10000
      });

      return response.data.data || [];
    } catch (error) {
      console.error('Failed to fetch models:', error.message);
      return [];
    }
  }

  /**
   * Get available models from OpenRouter
   */
  async getOpenRouterModels() {
    try {
      const response = await axios.get('https://openrouter.ai/api/v1/models', {
        headers: { 'Authorization': `Bearer ${this.openRouterKey}` },
        timeout: 10000
      });

      return response.data.data || [];
    } catch (error) {
      console.error('Failed to fetch OpenRouter models:', error.message);
      return [];
    }
  }

  /**
   * Check if LiteLLM proxy is available
   */
  async healthCheck() {
    try {
      if (this.useOpenRouterFallback) {
        // Check OpenRouter
        await axios.get('https://openrouter.ai/api/v1/models', {
          headers: { 'Authorization': `Bearer ${this.openRouterKey}` },
          timeout: 5000
        });
        return { status: 'healthy', provider: 'openrouter' };
      }

      // Check LiteLLM proxy
      await axios.get(`${this.baseURL}/health`, { timeout: 5000 });
      return { status: 'healthy', provider: 'litellm' };
    } catch (error) {
      return {
        status: 'unhealthy',
        error: error.message,
        provider: this.useOpenRouterFallback ? 'openrouter' : 'litellm'
      };
    }
  }

  /**
   * Calculate cost estimate for a request
   * @param {string} model - Model name
   * @param {number} promptTokens - Number of prompt tokens
   * @param {number} completionTokens - Number of completion tokens
   * @returns {number} Estimated cost in USD
   */
  estimateCost(model, promptTokens, completionTokens) {
    // Pricing per 1M tokens (as of 2025)
    const pricing = {
      'gpt-4': { prompt: 30, completion: 60 },
      'gpt-4-turbo': { prompt: 10, completion: 30 },
      'gpt-3.5-turbo': { prompt: 0.5, completion: 1.5 },
      'claude-3-opus': { prompt: 15, completion: 75 },
      'claude-3-sonnet': { prompt: 3, completion: 15 },
      'claude-3-haiku': { prompt: 0.25, completion: 1.25 },
      'claude-3.5-sonnet': { prompt: 3, completion: 15 },
      'gemini-pro': { prompt: 0.5, completion: 1.5 }
    };

    const modelPricing = pricing[model] || { prompt: 5, completion: 15 }; // Default pricing

    const promptCost = (promptTokens / 1000000) * modelPricing.prompt;
    const completionCost = (completionTokens / 1000000) * modelPricing.completion;

    return promptCost + completionCost;
  }

  /**
   * Get service information
   */
  getServiceInfo() {
    return {
      name: 'LiteLLM Provider',
      version: '1.0.0',
      mode: this.useOpenRouterFallback ? 'openrouter-fallback' : 'litellm-proxy',
      baseURL: this.useOpenRouterFallback ? 'https://openrouter.ai' : this.baseURL,
      capabilities: [
        'Multi-provider support (100+ models)',
        'Streaming responses',
        'Automatic fallback',
        'Cost estimation',
        'Health monitoring'
      ]
    };
  }
}

module.exports = new LiteLLMProvider();
