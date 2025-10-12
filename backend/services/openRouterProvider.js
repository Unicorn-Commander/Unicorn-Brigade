const axios = require('axios');

/**
 * OpenRouter Inference Provider
 * Production-ready LLM provider for medical and other domains
 */
class OpenRouterProvider {
  constructor(apiKey = null) {
    this.apiKey = apiKey || process.env.OPENROUTER_API_KEY;
    this.baseURL = 'https://openrouter.ai/api/v1';
    this.siteName = process.env.SITE_NAME || 'Unicorn Command Control';
    this.siteURL = process.env.SITE_URL || 'http://localhost:8113';

    // Model mappings for different use cases
    this.models = {
      // Medical models - use more capable models for medical
      'medical_primary': 'anthropic/claude-3-opus',
      'medical_specialist': 'openai/gpt-4-turbo-preview',
      'medical_emergency': 'anthropic/claude-3-opus',

      // General purpose models
      'default': 'anthropic/claude-3-sonnet',
      'fast': 'anthropic/claude-3-haiku',
      'powerful': 'anthropic/claude-3-opus',

      // Fallback chain for reliability
      'fallback_chain': [
        'anthropic/claude-3-sonnet',
        'openai/gpt-4-turbo-preview',
        'google/gemini-pro',
        'meta-llama/llama-3-70b-instruct'
      ]
    };

    // Track usage for analytics
    this.usage = {
      totalTokens: 0,
      totalCost: 0,
      requestCount: 0
    };
  }

  /**
   * Main completion method - compatible with medical orchestrator
   */
  async complete(options) {
    const {
      messages,
      model = 'default',
      temperature = 0.7,
      max_tokens = 1000,
      stream = false
    } = options;

    // Get the actual model name
    const modelName = this.models[model] || model;

    try {
      const response = await axios.post(
        `${this.baseURL}/chat/completions`,
        {
          model: modelName,
          messages: messages,
          temperature: temperature,
          max_tokens: max_tokens,
          stream: stream,
          // OpenRouter specific headers
          transforms: ['middle-out'],
          route: 'fallback'
        },
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json',
            'HTTP-Referer': this.siteURL,
            'X-Title': this.siteName
          }
        }
      );

      // Track usage
      if (response.data.usage) {
        this.usage.totalTokens += response.data.usage.total_tokens || 0;
        this.usage.totalCost += response.data.usage.total_cost || 0;
        this.usage.requestCount++;
      }

      // Return in format expected by orchestrator
      return {
        content: response.data.choices[0].message.content,
        model: modelName,
        usage: response.data.usage,
        id: response.data.id
      };

    } catch (error) {
      console.error('OpenRouter API Error:', error.response?.data || error.message);

      // Try fallback models if main fails
      if (error.response?.status === 429 || error.response?.status === 503) {
        return await this.fallbackComplete(options);
      }

      throw new Error(`OpenRouter Error: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  /**
   * Fallback completion with model chain
   */
  async fallbackComplete(options) {
    const fallbackModels = this.models.fallback_chain;

    for (const fallbackModel of fallbackModels) {
      try {
        console.log(`Trying fallback model: ${fallbackModel}`);

        const response = await axios.post(
          `${this.baseURL}/chat/completions`,
          {
            model: fallbackModel,
            messages: options.messages,
            temperature: options.temperature || 0.7,
            max_tokens: options.max_tokens || 1000
          },
          {
            headers: {
              'Authorization': `Bearer ${this.apiKey}`,
              'Content-Type': 'application/json',
              'HTTP-Referer': this.siteURL,
              'X-Title': this.siteName
            }
          }
        );

        return {
          content: response.data.choices[0].message.content,
          model: fallbackModel,
          usage: response.data.usage,
          fallback: true
        };

      } catch (error) {
        console.error(`Fallback model ${fallbackModel} failed:`, error.message);
        continue;
      }
    }

    throw new Error('All fallback models failed');
  }

  /**
   * Stream completion for real-time responses
   */
  async *streamComplete(options) {
    const {
      messages,
      model = 'default',
      temperature = 0.7,
      max_tokens = 1000
    } = options;

    const modelName = this.models[model] || model;

    try {
      const response = await axios.post(
        `${this.baseURL}/chat/completions`,
        {
          model: modelName,
          messages: messages,
          temperature: temperature,
          max_tokens: max_tokens,
          stream: true
        },
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json',
            'HTTP-Referer': this.siteURL,
            'X-Title': this.siteName
          },
          responseType: 'stream'
        }
      );

      let buffer = '';

      for await (const chunk of response.data) {
        buffer += chunk.toString();
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.trim() === '' || line.trim() === 'data: [DONE]') continue;

          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.choices?.[0]?.delta?.content) {
                yield data.choices[0].delta.content;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('OpenRouter Stream Error:', error);
      throw error;
    }
  }

  /**
   * Get available models from OpenRouter
   */
  async getAvailableModels() {
    try {
      const response = await axios.get(
        `${this.baseURL}/models`,
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`
          }
        }
      );

      return response.data.data.map(model => ({
        id: model.id,
        name: model.name,
        contextLength: model.context_length,
        pricing: model.pricing
      }));
    } catch (error) {
      console.error('Error fetching models:', error);
      return [];
    }
  }

  /**
   * Check API key validity and balance
   */
  async checkStatus() {
    try {
      const response = await axios.get(
        'https://openrouter.ai/api/v1/auth/key',
        {
          headers: {
            'Authorization': `Bearer ${this.apiKey}`
          }
        }
      );

      return {
        valid: true,
        balance: response.data.data?.usage?.balance || 0,
        limit: response.data.data?.usage?.limit || 0,
        usage: this.usage
      };
    } catch (error) {
      return {
        valid: false,
        error: error.message
      };
    }
  }

  /**
   * Get usage statistics
   */
  getUsageStats() {
    return {
      ...this.usage,
      averageTokensPerRequest: this.usage.requestCount > 0
        ? Math.round(this.usage.totalTokens / this.usage.requestCount)
        : 0,
      averageCostPerRequest: this.usage.requestCount > 0
        ? (this.usage.totalCost / this.usage.requestCount).toFixed(4)
        : 0
    };
  }
}

module.exports = OpenRouterProvider;