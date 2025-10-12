/**
 * Agent-Tool Bridge Service
 * Manages the connection between AI agents and available tools/services
 * Handles permissions, rate limiting, logging, and memory updates
 */

const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();
// Optional services - will be loaded if available
let microservices = { startMicroservices: () => {}, microservices: [] };
let osintService = {};
let financialService = {};

try {
  microservices = require('./microservicesOrchestrator');
} catch (e) {}

try {
  osintService = require('./osintService');
} catch (e) {}

try {
  financialService = require('./financialService');
} catch (e) {}
const axios = require('axios');

class AgentToolsService {
  constructor() {
    // Tool permission mappings
    this.toolPermissions = {
      osint: ['search', 'investigate', 'deep-search', 'generate-report'],
      legal: ['research', 'analyze-document', 'case-law-search', 'generate-strategy', 'compliance-check'],
      financial: ['analyze', 'detect-fraud', 'budget-report', 'generate-report'],
      document: ['upload', 'process', 'extract', 'analyze'],
      workflow: ['execute', 'schedule', 'monitor'],
      voice: ['text-to-speech', 'transcribe']
    };

    // Agent rate limits (requests per minute)
    this.agentRateLimits = new Map();
    this.defaultRateLimit = 30;
    this.rateLimitWindow = 60000; // 1 minute

    // Tool usage statistics
    this.usageStats = new Map();
    
    // Agent tool access cache
    this.agentToolCache = new Map();
    this.cacheTimeout = 300000; // 5 minutes
  }

  /**
   * Get agent profile with permissions
   */
  async getAgentProfile(agentId) {
    // Check cache first
    const cached = this.agentToolCache.get(agentId);
    if (cached && (Date.now() - cached.timestamp < this.cacheTimeout)) {
      return cached.profile;
    }

    try {
      // Try to get custom agent first
      let agent = await prisma.customAgent.findUnique({
        where: { id: agentId },
        include: {
          presence: true
        }
      });

      if (!agent) {
        // Fall back to regular agent
        const regularAgent = await prisma.agent.findUnique({
          where: { id: agentId }
        });

        if (!regularAgent) {
          throw new Error(`Agent ${agentId} not found`);
        }

        // Convert regular agent to expected format
        agent = {
          ...regularAgent,
          tools: JSON.parse(regularAgent.capabilities || '[]'),
          domain: 'general'
        };
      } else {
        // Parse tools from JSON
        agent.tools = JSON.parse(agent.tools || '[]');
      }

      // Map tools to permissions
      const allowedTools = this.mapAgentTools(agent.tools, agent.domain);

      const profile = {
        id: agent.id,
        name: agent.name,
        domain: agent.domain,
        tools: agent.tools,
        allowedTools,
        isActive: agent.isActive !== false,
        rateLimit: this.getRateLimitForAgent(agent)
      };

      // Cache the profile
      this.agentToolCache.set(agentId, {
        profile,
        timestamp: Date.now()
      });

      return profile;
    } catch (error) {
      console.error(`Error getting agent profile for ${agentId}:`, error);
      throw error;
    }
  }

  /**
   * Map agent tools to allowed actions
   */
  mapAgentTools(tools, domain) {
    const allowed = new Set();

    // Domain-specific permissions
    switch (domain) {
      case 'legal':
        allowed.add('legal');
        break;
      case 'investigation':
      case 'intelligence':
        allowed.add('osint');
        allowed.add('document');
        break;
      case 'financial':
        allowed.add('financial');
        break;
      case 'administration':
        // Admin agents get all tools
        Object.keys(this.toolPermissions).forEach(tool => allowed.add(tool));
        break;
      default:
        // Map specific tools
        tools.forEach(tool => {
          if (tool.includes('osint') || tool.includes('search')) allowed.add('osint');
          if (tool.includes('legal') || tool.includes('contract')) allowed.add('legal');
          if (tool.includes('financial') || tool.includes('fraud')) allowed.add('financial');
          if (tool.includes('document') || tool.includes('process')) allowed.add('document');
          if (tool.includes('workflow')) allowed.add('workflow');
          if (tool.includes('voice') || tool.includes('speech')) allowed.add('voice');
        });
    }

    return Array.from(allowed);
  }

  /**
   * Get rate limit for agent based on their profile
   */
  getRateLimitForAgent(agent) {
    // Higher limits for certain domains
    if (agent.domain === 'administration') return 100;
    if (agent.domain === 'investigation') return 50;
    return this.defaultRateLimit;
  }

  /**
   * Check rate limit for agent
   */
  async checkRateLimit(agentId, toolName) {
    const now = Date.now();
    const key = `${agentId}_${toolName}`;

    if (!this.agentRateLimits.has(key)) {
      this.agentRateLimits.set(key, {
        count: 0,
        resetTime: now + this.rateLimitWindow
      });
    }

    const limit = this.agentRateLimits.get(key);

    if (now > limit.resetTime) {
      limit.count = 0;
      limit.resetTime = now + this.rateLimitWindow;
    }

    const agent = await this.getAgentProfile(agentId);
    const maxRequests = agent.rateLimit || this.defaultRateLimit;

    if (limit.count >= maxRequests) {
      throw new Error(`Rate limit exceeded for agent ${agentId} using ${toolName}. Max ${maxRequests} requests per minute.`);
    }

    limit.count++;
  }

  /**
   * Main method to execute tools for agents
   */
  async executeToolForAgent(agentId, toolName, action, parameters, caseId = null) {
    try {
      // 1. Validate agent permissions
      const agent = await this.getAgentProfile(agentId);
      if (!agent.isActive) {
        throw new Error(`Agent ${agentId} is not active`);
      }

      if (!agent.allowedTools.includes(toolName)) {
        throw new Error(`Agent ${agentId} does not have permission to use ${toolName}`);
      }

      // 2. Check if action is allowed for the tool
      if (this.toolPermissions[toolName] && !this.toolPermissions[toolName].includes(action)) {
        throw new Error(`Action ${action} is not available for tool ${toolName}`);
      }

      // 3. Check rate limits
      await this.checkRateLimit(agentId, toolName);

      // 4. Execute tool
      const startTime = Date.now();
      let result;
      
      try {
        switch (toolName) {
          case 'osint':
            result = await this.executeOSINTTool(action, parameters);
            break;
          case 'legal':
            result = await this.executeLegalTool(action, parameters);
            break;
          case 'financial':
            result = await this.executeFinancialTool(action, parameters, caseId);
            break;
          case 'document':
            result = await this.executeDocumentTool(action, parameters);
            break;
          case 'workflow':
            result = await this.executeWorkflowTool(action, parameters);
            break;
          case 'voice':
            result = await this.executeVoiceTool(action, parameters);
            break;
          default:
            throw new Error(`Unknown tool: ${toolName}`);
        }
      } catch (toolError) {
        console.error(`Tool execution error for ${toolName}:`, toolError);
        result = {
          success: false,
          error: toolError.message,
          toolName,
          action
        };
      }

      const executionTime = Date.now() - startTime;

      // 5. Log usage for audit and memory
      await this.logToolUsage(agentId, toolName, action, parameters, result, caseId, executionTime);

      // 6. Update agent memory with results
      await this.updateAgentMemory(agentId, toolName, action, result, caseId);

      // 7. Update usage statistics
      this.updateUsageStats(agentId, toolName, executionTime);

      return {
        success: true,
        result,
        executionTime,
        agentId,
        toolName,
        action,
        timestamp: new Date().toISOString()
      };

    } catch (error) {
      console.error(`Error executing tool ${toolName} for agent ${agentId}:`, error);
      
      // Log failed attempt
      await this.logToolUsage(agentId, toolName, action, parameters, 
        { error: error.message }, caseId, 0, false);
      
      throw error;
    }
  }

  /**
   * Execute OSINT tool actions
   */
  async executeOSINTTool(action, parameters) {
    switch (action) {
      case 'search':
        return await osintService.search(parameters.query, parameters.options || {});
      
      case 'investigate':
        return await osintService.investigateTarget(
          parameters.targetType,
          parameters.targetData,
          parameters.options || {}
        );
      
      case 'deep-search':
        return await microservices.deepSearch(
          parameters.query,
          parameters.depth || 3,
          parameters.options || {}
        );
      
      case 'generate-report':
        return await microservices.generateReport(
          parameters.investigationData,
          parameters.format || 'markdown'
        );
      
      default:
        throw new Error(`Unknown OSINT action: ${action}`);
    }
  }

  /**
   * Execute Legal tool actions
   */
  async executeLegalTool(action, parameters) {
    const baseUrl = process.env.BACKEND_URL || 'http://localhost:3001';
    
    switch (action) {
      case 'research':
        const researchResponse = await axios.post(`${baseUrl}/api/legal/research`, parameters);
        return researchResponse.data;
      
      case 'analyze-document':
        const analyzeResponse = await axios.post(`${baseUrl}/api/legal/analyze-document`, parameters);
        return analyzeResponse.data;
      
      case 'case-law-search':
        const caseLawResponse = await axios.post(`${baseUrl}/api/legal/case-law`, parameters);
        return caseLawResponse.data;
      
      case 'generate-strategy':
        const strategyResponse = await axios.post(`${baseUrl}/api/legal/strategy`, parameters);
        return strategyResponse.data;
      
      case 'compliance-check':
        const complianceResponse = await axios.post(`${baseUrl}/api/legal/compliance-check`, parameters);
        return complianceResponse.data;
      
      default:
        throw new Error(`Unknown legal action: ${action}`);
    }
  }

  /**
   * Execute Financial tool actions
   */
  async executeFinancialTool(action, parameters, caseId) {
    switch (action) {
      case 'analyze':
        return await financialService.analyzeFinancials({
          ...parameters,
          caseId
        });
      
      case 'detect-fraud':
        return await financialService.detectFraud({
          transactions: parameters.transactions,
          caseId
        });
      
      case 'budget-report':
        if (!caseId) {
          throw new Error('Case ID required for budget report');
        }
        return await financialService.generateFinancialReport(caseId);
      
      case 'generate-report':
        return await financialService.generateFinancialReport(
          parameters.caseId || caseId
        );
      
      default:
        throw new Error(`Unknown financial action: ${action}`);
    }
  }

  /**
   * Execute Document tool actions
   */
  async executeDocumentTool(action, parameters) {
    switch (action) {
      case 'process':
        return await microservices.processDocument(
          parameters.fileBuffer,
          parameters.fileName,
          parameters.options || {}
        );
      
      case 'extract':
        return await microservices.processDocument(
          parameters.fileBuffer,
          parameters.fileName,
          {
            extractText: true,
            extractEntities: true,
            extractMetadata: true
          }
        );
      
      case 'analyze':
        return await microservices.processDocument(
          parameters.fileBuffer,
          parameters.fileName,
          {
            generateSummary: true,
            extractEntities: true,
            analyzeSentiment: true
          }
        );
      
      default:
        throw new Error(`Unknown document action: ${action}`);
    }
  }

  /**
   * Execute Workflow tool actions
   */
  async executeWorkflowTool(action, parameters) {
    switch (action) {
      case 'execute':
        return await microservices.executeWorkflow(
          parameters.workflow,
          parameters.parameters || {}
        );
      
      case 'schedule':
        // Add scheduling logic here
        throw new Error('Workflow scheduling not yet implemented');
      
      case 'monitor':
        // Add monitoring logic here
        throw new Error('Workflow monitoring not yet implemented');
      
      default:
        throw new Error(`Unknown workflow action: ${action}`);
    }
  }

  /**
   * Execute Voice tool actions
   */
  async executeVoiceTool(action, parameters) {
    switch (action) {
      case 'text-to-speech':
        const audioBuffer = await microservices.generateSpeech(
          parameters.text,
          parameters.voice || 'alloy',
          parameters.options || {}
        );
        
        // Convert ArrayBuffer to base64 for easier transmission
        const base64Audio = Buffer.from(audioBuffer).toString('base64');
        
        return {
          format: parameters.options?.format || 'mp3',
          audio: base64Audio,
          duration: null // Would need audio processing to determine
        };
      
      case 'transcribe':
        // Add transcription logic here
        throw new Error('Transcription not yet implemented');
      
      default:
        throw new Error(`Unknown voice action: ${action}`);
    }
  }

  /**
   * Log tool usage for audit trail
   */
  async logToolUsage(agentId, toolName, action, parameters, result, caseId, executionTime, success = true) {
    try {
      await prisma.activityLog.create({
        data: {
          userId: agentId, // Using userId field for agentId
          caseId,
          action: `tool:${toolName}:${action}`,
          details: {
            tool: toolName,
            action,
            parameters,
            result: success ? 'Tool executed successfully' : result.error,
            executionTime,
            success,
            timestamp: new Date().toISOString()
          }
        }
      });
    } catch (error) {
      console.error('Failed to log tool usage:', error);
      // Don't throw - logging failure shouldn't break tool execution
    }
  }

  /**
   * Update agent memory with tool results
   */
  async updateAgentMemory(agentId, toolName, action, result, caseId) {
    try {
      // Create memory entry
      const memoryContent = {
        tool: toolName,
        action,
        resultSummary: this.summarizeResult(result),
        timestamp: new Date().toISOString()
      };

      await prisma.agentMemory.create({
        data: {
          agentId,
          type: 'tool_usage',
          category: 'domain',
          content: JSON.stringify(memoryContent),
          metadata: JSON.stringify({
            toolName,
            action,
            caseId,
            success: !result.error
          }),
          importance: result.error ? 0.3 : 0.7,
          accessCount: 1,
          lastAccessed: new Date()
        }
      });

      // If this is important information, also store as long-term memory
      if (!result.error && this.isImportantResult(result)) {
        await prisma.agentMemory.create({
          data: {
            agentId,
            type: 'long_term',
            category: caseId ? 'case' : 'general',
            content: JSON.stringify({
              tool: toolName,
              action,
              result: result,
              context: `Important finding from ${toolName} ${action}`
            }),
            metadata: JSON.stringify({
              toolName,
              action,
              caseId
            }),
            importance: 0.9
          }
        });
      }
    } catch (error) {
      console.error('Failed to update agent memory:', error);
      // Don't throw - memory update failure shouldn't break tool execution
    }
  }

  /**
   * Summarize result for memory storage
   */
  summarizeResult(result) {
    if (result.error) {
      return `Error: ${result.error}`;
    }

    if (typeof result === 'string') {
      return result.substring(0, 200);
    }

    if (result.summary) {
      return result.summary;
    }

    if (result.results && Array.isArray(result.results)) {
      return `Found ${result.results.length} results`;
    }

    return JSON.stringify(result).substring(0, 200);
  }

  /**
   * Determine if a result is important enough for long-term memory
   */
  isImportantResult(result) {
    // Check for keywords indicating importance
    const importantKeywords = ['critical', 'fraud', 'violation', 'urgent', 'suspicious', 'anomaly'];
    const resultStr = JSON.stringify(result).toLowerCase();
    
    return importantKeywords.some(keyword => resultStr.includes(keyword));
  }

  /**
   * Update usage statistics
   */
  updateUsageStats(agentId, toolName, executionTime) {
    const key = `${agentId}_${toolName}`;
    
    if (!this.usageStats.has(key)) {
      this.usageStats.set(key, {
        count: 0,
        totalTime: 0,
        avgTime: 0,
        lastUsed: null
      });
    }

    const stats = this.usageStats.get(key);
    stats.count++;
    stats.totalTime += executionTime;
    stats.avgTime = stats.totalTime / stats.count;
    stats.lastUsed = new Date().toISOString();
  }

  /**
   * Get available tools for an agent
   */
  async getAvailableTools(agentId) {
    const agent = await this.getAgentProfile(agentId);
    
    const tools = {};
    for (const toolName of agent.allowedTools) {
      tools[toolName] = {
        name: toolName,
        actions: this.toolPermissions[toolName] || [],
        description: this.getToolDescription(toolName)
      };
    }

    return {
      agentId,
      agentName: agent.name,
      domain: agent.domain,
      tools,
      rateLimit: agent.rateLimit
    };
  }

  /**
   * Get tool description
   */
  getToolDescription(toolName) {
    const descriptions = {
      osint: 'Open Source Intelligence gathering and investigation tools',
      legal: 'Legal research, document analysis, and strategy generation',
      financial: 'Financial analysis, fraud detection, and budget management',
      document: 'Document processing, extraction, and analysis',
      workflow: 'Workflow execution and orchestration',
      voice: 'Text-to-speech and audio processing'
    };

    return descriptions[toolName] || 'Tool for specialized operations';
  }

  /**
   * Get usage statistics for an agent
   */
  getUsageStats(agentId) {
    const agentStats = {};
    
    for (const [key, stats] of this.usageStats.entries()) {
      if (key.startsWith(`${agentId}_`)) {
        const toolName = key.replace(`${agentId}_`, '');
        agentStats[toolName] = stats;
      }
    }

    return agentStats;
  }

  /**
   * Clear rate limits (for testing)
   */
  clearRateLimits() {
    this.agentRateLimits.clear();
  }

  /**
   * Clear cache
   */
  clearCache() {
    this.agentToolCache.clear();
  }
}

// Export singleton instance
module.exports = new AgentToolsService();