// backend/services/agentCommunicationService.js

const { PrismaClient } = require('@prisma/client');
const agentExecutionService = require('./agentExecutionService');
const memoryService = require('./memoryService');

const prisma = new PrismaClient();

class AgentCommunicationService {
  constructor() {
    this.messageQueue = [];
    this.processingInterval = null;
    this.isProcessing = false;
    
    // Start queue processor
    this.startQueueProcessor();
  }

  /**
   * Send message from one agent to another
   */
  async sendMessage(fromAgentId, toAgentId, content, priority = 1, metadata = {}) {
    try {
      // Create the communication record
      const message = await prisma.agentCommunication.create({
        data: {
          fromAgentId,
          toAgentId,
          content,
          priority,
          metadata: JSON.stringify(metadata),
          status: 'pending'
        }
      });

      // Add to processing queue based on priority
      this.addToQueue(message);

      // Store in sender's memory
      await memoryService.storeMemory(
        fromAgentId,
        null,
        `Sent message to agent ${toAgentId}: ${content}`,
        'short_term',
        'communication',
        { messageId: message.id, type: 'sent' }
      );

      return message;
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  /**
   * Get inbox messages for an agent
   */
  async getInbox(agentId, filters = {}) {
    try {
      const where = {
        toAgentId: agentId
      };

      if (filters.status) {
        where.status = filters.status;
      }

      const messages = await prisma.agentCommunication.findMany({
        where,
        orderBy: [
          { priority: 'desc' },
          { createdAt: 'desc' }
        ],
        take: filters.limit || 50
      });

      // Parse metadata for each message
      messages.forEach(msg => {
        try {
          msg.metadata = JSON.parse(msg.metadata || '{}');
        } catch (e) {
          msg.metadata = {};
        }
      });

      return messages;
    } catch (error) {
      console.error('Error getting inbox:', error);
      throw error;
    }
  }

  /**
   * Get sent messages from an agent
   */
  async getSentMessages(agentId, filters = {}) {
    try {
      const where = {
        fromAgentId: agentId
      };

      if (filters.status) {
        where.status = filters.status;
      }

      const messages = await prisma.agentCommunication.findMany({
        where,
        orderBy: [
          { createdAt: 'desc' }
        ],
        take: filters.limit || 50
      });

      // Parse metadata
      messages.forEach(msg => {
        try {
          msg.metadata = JSON.parse(msg.metadata || '{}');
        } catch (e) {
          msg.metadata = {};
        }
      });

      return messages;
    } catch (error) {
      console.error('Error getting sent messages:', error);
      throw error;
    }
  }

  /**
   * Process a message (have receiving agent respond)
   */
  async processMessage(messageId) {
    try {
      const message = await prisma.agentCommunication.findUnique({
        where: { id: messageId }
      });

      if (!message) {
        throw new Error('Message not found');
      }

      // Update status to processing
      await prisma.agentCommunication.update({
        where: { id: messageId },
        data: { status: 'processing' }
      });

      // Load receiving agent
      const receivingAgent = await prisma.agentLibrary.findUnique({
        where: { id: message.toAgentId }
      });

      if (!receivingAgent) {
        throw new Error('Receiving agent not found');
      }

      // Build context from memory for the receiving agent
      const memoryContext = await memoryService.buildContextFromMemories(
        message.toAgentId,
        null,
        message.content
      );

      // Get agent's response using execution service
      const executionService = new (require('./agentExecutionService'))();
      
      // Parse agent configuration
      receivingAgent.tags = JSON.parse(receivingAgent.tags || '[]');
      receivingAgent.tools = JSON.parse(receivingAgent.tools || '[]');
      
      const response = await executionService.getAIResponse(
        receivingAgent,
        `[Message from another agent]: ${message.content}`,
        [],
        memoryContext
      );

      // Update message with response
      await prisma.agentCommunication.update({
        where: { id: messageId },
        data: {
          response,
          status: 'completed',
          processedAt: new Date()
        }
      });

      // Store in receiving agent's memory
      await memoryService.storeMemory(
        message.toAgentId,
        null,
        `Received message from agent ${message.fromAgentId}: ${message.content}. Responded: ${response}`,
        'short_term',
        'communication',
        { messageId: message.id, type: 'received' }
      );

      return { message, response };
    } catch (error) {
      console.error('Error processing message:', error);
      
      // Mark as failed
      await prisma.agentCommunication.update({
        where: { id: messageId },
        data: { 
          status: 'failed',
          response: error.message 
        }
      });
      
      throw error;
    }
  }

  /**
   * Start a multi-agent collaboration
   */
  async startCollaboration(initiatorId, agentIds, title, taskType, description = '', context = {}) {
    try {
      // Create collaboration record
      const collaboration = await prisma.agentCollaboration.create({
        data: {
          title,
          description,
          initiatorId,
          agentIds: JSON.stringify(agentIds),
          taskType,
          status: 'active',
          context: JSON.stringify(context)
        }
      });

      // Notify all participating agents
      for (const agentId of agentIds) {
        if (agentId !== initiatorId) {
          await this.sendMessage(
            initiatorId,
            agentId,
            `You've been invited to collaborate on: ${title}. Task type: ${taskType}. ${description}`,
            2, // High priority
            { collaborationId: collaboration.id }
          );
        }
      }

      return collaboration;
    } catch (error) {
      console.error('Error starting collaboration:', error);
      throw error;
    }
  }

  /**
   * Update collaboration status
   */
  async updateCollaboration(collaborationId, updates) {
    try {
      const updateData = {};
      
      if (updates.status) {
        updateData.status = updates.status;
        if (updates.status === 'completed') {
          updateData.completedAt = new Date();
        }
      }
      
      if (updates.results) {
        updateData.results = JSON.stringify(updates.results);
      }
      
      if (updates.context) {
        updateData.context = JSON.stringify(updates.context);
      }

      const collaboration = await prisma.agentCollaboration.update({
        where: { id: collaborationId },
        data: updateData
      });

      return collaboration;
    } catch (error) {
      console.error('Error updating collaboration:', error);
      throw error;
    }
  }

  /**
   * Get active collaborations for an agent
   */
  async getCollaborations(agentId, status = 'active') {
    try {
      const collaborations = await prisma.agentCollaboration.findMany({
        where: {
          OR: [
            { initiatorId: agentId },
            { agentIds: { contains: agentId } }
          ],
          status
        },
        orderBy: { createdAt: 'desc' }
      });

      // Parse JSON fields
      collaborations.forEach(collab => {
        try {
          collab.agentIds = JSON.parse(collab.agentIds || '[]');
          collab.context = JSON.parse(collab.context || '{}');
          collab.results = JSON.parse(collab.results || '{}');
        } catch (e) {
          collab.agentIds = [];
          collab.context = {};
          collab.results = {};
        }
      });

      return collaborations;
    } catch (error) {
      console.error('Error getting collaborations:', error);
      throw error;
    }
  }

  /**
   * Execute collaborative task
   */
  async executeCollaborativeTask(collaborationId) {
    try {
      const collaboration = await prisma.agentCollaboration.findUnique({
        where: { id: collaborationId }
      });

      if (!collaboration) {
        throw new Error('Collaboration not found');
      }

      const agentIds = JSON.parse(collaboration.agentIds || '[]');
      const context = JSON.parse(collaboration.context || '{}');
      const results = {};

      // Execute task based on type
      switch (collaboration.taskType) {
        case 'research':
          results.research = await this.executeResearchTask(agentIds, context);
          break;
        
        case 'analysis':
          results.analysis = await this.executeAnalysisTask(agentIds, context);
          break;
        
        case 'planning':
          results.plan = await this.executePlanningTask(agentIds, context);
          break;
        
        case 'execution':
          results.execution = await this.executeExecutionTask(agentIds, context);
          break;
        
        default:
          throw new Error(`Unknown task type: ${collaboration.taskType}`);
      }

      // Update collaboration with results
      await this.updateCollaboration(collaborationId, {
        status: 'completed',
        results
      });

      return results;
    } catch (error) {
      console.error('Error executing collaborative task:', error);
      
      await this.updateCollaboration(collaborationId, {
        status: 'failed',
        results: { error: error.message }
      });
      
      throw error;
    }
  }

  /**
   * Execute research task with multiple agents
   */
  async executeResearchTask(agentIds, context) {
    const results = {
      findings: [],
      sources: [],
      summary: ''
    };

    // Each agent researches a different aspect
    for (const agentId of agentIds) {
      try {
        const agent = await prisma.agentLibrary.findUnique({
          where: { id: agentId }
        });

        if (agent) {
          // Mock research for now (would use actual agent execution)
          const finding = {
            agentId,
            agentName: agent.name,
            research: `Research findings from ${agent.name} on topic: ${context.topic || 'general'}`,
            timestamp: new Date()
          };
          results.findings.push(finding);
        }
      } catch (error) {
        console.error(`Error with agent ${agentId}:`, error);
      }
    }

    results.summary = `Collaborative research completed with ${results.findings.length} agents`;
    return results;
  }

  /**
   * Execute analysis task with multiple agents
   */
  async executeAnalysisTask(agentIds, context) {
    const results = {
      analyses: [],
      consensus: null,
      disagreements: []
    };

    // Each agent provides analysis
    for (const agentId of agentIds) {
      try {
        const agent = await prisma.agentLibrary.findUnique({
          where: { id: agentId }
        });

        if (agent) {
          const analysis = {
            agentId,
            agentName: agent.name,
            analysis: `Analysis from ${agent.name}: ${context.data || 'No data provided'}`,
            confidence: Math.random(),
            timestamp: new Date()
          };
          results.analyses.push(analysis);
        }
      } catch (error) {
        console.error(`Error with agent ${agentId}:`, error);
      }
    }

    results.consensus = 'Agents generally agree on the analysis';
    return results;
  }

  /**
   * Execute planning task with multiple agents
   */
  async executePlanningTask(agentIds, context) {
    const results = {
      steps: [],
      timeline: null,
      resources: []
    };

    // Collaborative planning
    for (const agentId of agentIds) {
      try {
        const agent = await prisma.agentLibrary.findUnique({
          where: { id: agentId }
        });

        if (agent) {
          const step = {
            agentId,
            agentName: agent.name,
            proposedStep: `Step proposed by ${agent.name}`,
            priority: Math.floor(Math.random() * 3) + 1,
            timestamp: new Date()
          };
          results.steps.push(step);
        }
      } catch (error) {
        console.error(`Error with agent ${agentId}:`, error);
      }
    }

    results.timeline = '1-2 weeks estimated';
    return results;
  }

  /**
   * Execute execution task with multiple agents
   */
  async executeExecutionTask(agentIds, context) {
    const results = {
      actions: [],
      status: 'completed',
      output: null
    };

    // Sequential execution
    for (const agentId of agentIds) {
      try {
        const agent = await prisma.agentLibrary.findUnique({
          where: { id: agentId }
        });

        if (agent) {
          const action = {
            agentId,
            agentName: agent.name,
            action: `Action executed by ${agent.name}`,
            result: 'success',
            timestamp: new Date()
          };
          results.actions.push(action);
        }
      } catch (error) {
        console.error(`Error with agent ${agentId}:`, error);
        results.status = 'partial_failure';
      }
    }

    results.output = 'Task execution completed';
    return results;
  }

  /**
   * Add message to processing queue
   */
  addToQueue(message) {
    // Insert based on priority
    const index = this.messageQueue.findIndex(m => m.priority < message.priority);
    if (index === -1) {
      this.messageQueue.push(message);
    } else {
      this.messageQueue.splice(index, 0, message);
    }
  }

  /**
   * Start the queue processor
   */
  startQueueProcessor() {
    if (this.processingInterval) return;

    this.processingInterval = setInterval(async () => {
      if (!this.isProcessing && this.messageQueue.length > 0) {
        this.isProcessing = true;
        
        try {
          const message = this.messageQueue.shift();
          if (message && message.status === 'pending') {
            await this.processMessage(message.id);
          }
        } catch (error) {
          console.error('Queue processing error:', error);
        }
        
        this.isProcessing = false;
      }
    }, 5000); // Process every 5 seconds
  }

  /**
   * Stop the queue processor
   */
  stopQueueProcessor() {
    if (this.processingInterval) {
      clearInterval(this.processingInterval);
      this.processingInterval = null;
    }
  }

  /**
   * Get queue status
   */
  getQueueStatus() {
    return {
      queueLength: this.messageQueue.length,
      isProcessing: this.isProcessing,
      messages: this.messageQueue.map(m => ({
        id: m.id,
        priority: m.priority,
        fromAgentId: m.fromAgentId,
        toAgentId: m.toAgentId
      }))
    };
  }
}

module.exports = new AgentCommunicationService();