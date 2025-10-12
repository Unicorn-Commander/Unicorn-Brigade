/**
 * Agent Builder Service
 * Manages conversations with The General and agent creation
 */

const litellm = require('./litellmProvider');
const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
const fs = require('fs').promises;
const path = require('path');

class AgentBuilderService {
  constructor() {
    this.theGeneralConfig = null;
    this.conversationHistory = new Map(); // sessionId -> messages[]
    this.loadTheGeneral();
  }

  /**
   * Load The General's configuration
   */
  async loadTheGeneral() {
    try {
      const configPath = path.join(__dirname, '../../config/agents/the-general.json');
      const configData = await fs.readFile(configPath, 'utf-8');
      this.theGeneralConfig = JSON.parse(configData);
      console.log('✅ The General loaded and ready for duty');
    } catch (error) {
      console.error('❌ Failed to load The General configuration:', error);
      // Fallback configuration
      this.theGeneralConfig = {
        id: 'the-general-001',
        name: 'The General',
        model: 'gpt-4-turbo',
        temperature: 0.7,
        maxTokens: 4096,
        systemPrompt: 'You are The General, Chief Agent Engineering Officer of Unicorn Brigade. Help users build and deploy AI agents.'
      };
    }
  }

  /**
   * Chat with The General
   * @param {string} sessionId - Unique session ID for conversation tracking
   * @param {string} message - User message
   * @param {Object} context - Additional context (user info, etc.)
   * @returns {Promise<Object>} Response from The General
   */
  async chat(sessionId, message, context = {}) {
    try {
      // Initialize conversation history if needed
      if (!this.conversationHistory.has(sessionId)) {
        this.conversationHistory.set(sessionId, []);
      }

      const history = this.conversationHistory.get(sessionId);

      // Add context about available tools and capabilities
      const systemContext = await this.buildSystemContext();

      // Build messages array
      const messages = [
        {
          role: 'system',
          content: this.theGeneralConfig.systemPrompt + '\n\n' + systemContext
        },
        ...history,
        { role: 'user', content: message }
      ];

      // Send to LiteLLM
      const response = await litellm.sendMessage(
        this.theGeneralConfig.model,
        messages,
        {
          temperature: this.theGeneralConfig.temperature,
          maxTokens: this.theGeneralConfig.maxTokens
        }
      );

      // Update conversation history
      history.push(
        { role: 'user', content: message },
        { role: 'assistant', content: response.content }
      );

      // Keep only last 20 messages to prevent context overflow
      if (history.length > 20) {
        history.splice(0, history.length - 20);
      }

      // Check if The General wants to create an agent
      const agentCreationIntent = this.detectAgentCreationIntent(response.content);

      return {
        message: response.content,
        usage: response.usage,
        model: response.model,
        agentCreationIntent,
        sessionId
      };
    } catch (error) {
      console.error('Error chatting with The General:', error);
      throw error;
    }
  }

  /**
   * Build system context with available tools and agents
   */
  async buildSystemContext() {
    try {
      // Get available tools
      const tools = await prisma.tool.findMany({
        where: { isActive: true },
        select: {
          id: true,
          name: true,
          domain: true,
          type: true,
          description: true
        },
        take: 50
      });

      // Get existing agents for reference
      const existingAgents = await prisma.agent.findMany({
        select: {
          name: true,
          domain: true,
          subdomain: true,
          rank: true,
          title: true
        },
        take: 20,
        orderBy: { createdAt: 'desc' }
      });

      // Get domain statistics
      const domainStats = await prisma.agent.groupBy({
        by: ['domain'],
        _count: { domain: true },
        where: { domain: { not: null } }
      });

      return `
## Current System Context:

### Available Tools (${tools.length}):
${tools.slice(0, 10).map(t => `- ${t.name} (${t.type}${t.domain ? `, ${t.domain}` : ''}): ${t.description.substring(0, 80)}...`).join('\n')}
${tools.length > 10 ? `... and ${tools.length - 10} more` : ''}

### Recent Agents (${existingAgents.length}):
${existingAgents.slice(0, 5).map(a => `- ${a.name}${a.rank ? ` (${a.rank})` : ''}: ${a.domain || 'general'}${a.subdomain ? `/${a.subdomain}` : ''}`).join('\n')}

### Domain Coverage:
${domainStats.map(d => `- ${d.domain}: ${d._count.domain} agents`).join('\n')}

Use this information to make informed suggestions about agent design and available capabilities.
`;
    } catch (error) {
      console.error('Error building system context:', error);
      return '## System Context: Unable to load current system state';
    }
  }

  /**
   * Detect if The General intends to create an agent
   * This is a simple heuristic - could be improved with function calling
   */
  detectAgentCreationIntent(message) {
    const creationKeywords = [
      'create the agent',
      'deploy the agent',
      'shall i create',
      'ready to create',
      'proceed with creation',
      'let me create'
    ];

    const lowerMessage = message.toLowerCase();
    return creationKeywords.some(keyword => lowerMessage.includes(keyword));
  }

  /**
   * Parse agent configuration from The General's response
   * This extracts structured data from conversational text
   */
  parseAgentConfiguration(message) {
    // This is a simplified parser
    // In production, you'd want The General to output JSON or use function calling
    const config = {
      name: this.extractField(message, 'name'),
      displayName: this.extractField(message, 'display name'),
      title: this.extractField(message, 'title'),
      domain: this.extractField(message, 'domain'),
      subdomain: this.extractField(message, 'subdomain'),
      rank: this.extractField(message, 'rank'),
      bio: this.extractField(message, 'bio'),
      systemPrompt: this.extractField(message, 'system prompt'),
      model: this.extractField(message, 'model') || 'gpt-4-turbo',
      temperature: parseFloat(this.extractField(message, 'temperature')) || 0.7,
      maxTokens: parseInt(this.extractField(message, 'max tokens')) || 4096,
      capabilities: this.extractList(message, 'capabilities'),
      tools: this.extractList(message, 'tools')
    };

    return config;
  }

  /**
   * Helper to extract a field from text
   */
  extractField(text, fieldName) {
    const patterns = [
      new RegExp(`${fieldName}:\\s*["']?([^"'\\n]+)["']?`, 'i'),
      new RegExp(`${fieldName}\\s+is\\s+["']?([^"'\\n]+)["']?`, 'i'),
      new RegExp(`["']${fieldName}["']\\s*:\\s*["']([^"']+)["']`, 'i')
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match) {
        return match[1].trim();
      }
    }

    return null;
  }

  /**
   * Helper to extract a list from text
   */
  extractList(text, fieldName) {
    const pattern = new RegExp(`${fieldName}:\\s*\\[([^\\]]+)\\]`, 'i');
    const match = text.match(pattern);

    if (match) {
      return match[1]
        .split(',')
        .map(item => item.trim().replace(/["']/g, ''))
        .filter(item => item.length > 0);
    }

    return [];
  }

  /**
   * Create agent from configuration
   * @param {Object} config - Agent configuration
   * @param {string} createdBy - User ID
   * @returns {Promise<Object>} Created agent
   */
  async createAgent(config, createdBy = null) {
    try {
      // Validate required fields
      if (!config.name || !config.systemPrompt) {
        throw new Error('Agent name and system prompt are required');
      }

      // Find tools by name if provided
      let toolIds = [];
      if (config.tools && config.tools.length > 0) {
        const tools = await prisma.tool.findMany({
          where: {
            name: { in: config.tools }
          },
          select: { id: true }
        });
        toolIds = tools.map(t => t.id);
      }

      // Create agent
      const agent = await prisma.agent.create({
        data: {
          name: config.name,
          displayName: config.displayName || config.name,
          title: config.title,
          type: config.type || 'individual',
          domain: config.domain,
          subdomain: config.subdomain,
          department: config.department,
          rank: config.rank,
          avatar: config.avatar || '🦄',
          avatarUrl: config.avatarUrl,
          avatarStyle: config.avatarStyle,
          bio: config.bio,
          persona: config.persona || '',
          systemPrompt: config.systemPrompt,
          status: config.status || 'draft',
          capabilities: JSON.stringify(config.capabilities || []),
          memory: JSON.stringify({}),
          performance: JSON.stringify({}),
          model: config.model || 'gpt-4-turbo',
          temperature: config.temperature ?? 0.7,
          maxTokens: config.maxTokens || 4096,
          requiresAuth: config.requiresAuth || false,
          pricingModel: config.pricingModel || 'free',
          basePrice: config.basePrice,
          version: config.version || '1.0.0',
          createdBy: createdBy,
          createdByAgent: 'the-general-001'
        }
      });

      // Attach tools
      if (toolIds.length > 0) {
        await Promise.all(
          toolIds.map(toolId =>
            prisma.agentTool.create({
              data: {
                agentId: agent.id,
                toolId: toolId,
                config: JSON.stringify({})
              }
            })
          )
        );
      }

      // Fetch complete agent
      const completeAgent = await prisma.agent.findUnique({
        where: { id: agent.id },
        include: {
          agentTools: {
            include: {
              tool: true
            }
          }
        }
      });

      console.log(`✅ Agent created: ${agent.name} (${agent.id})`);

      return completeAgent;
    } catch (error) {
      console.error('Error creating agent:', error);
      throw error;
    }
  }

  /**
   * Clear conversation history for a session
   */
  clearSession(sessionId) {
    this.conversationHistory.delete(sessionId);
  }

  /**
   * Get conversation history for a session
   */
  getHistory(sessionId) {
    return this.conversationHistory.get(sessionId) || [];
  }

  /**
   * Get service info
   */
  getInfo() {
    return {
      service: 'Agent Builder Service',
      version: '1.0.0',
      theGeneral: {
        id: this.theGeneralConfig?.id,
        name: this.theGeneralConfig?.name,
        title: this.theGeneralConfig?.title,
        status: this.theGeneralConfig ? 'ready' : 'not loaded'
      },
      activeSessions: this.conversationHistory.size
    };
  }
}

module.exports = new AgentBuilderService();
